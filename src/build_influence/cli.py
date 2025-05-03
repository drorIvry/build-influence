import typer
from loguru import logger
import os
import json
from pathlib import Path
import time
from typing import Dict, Type, List
from rich.console import Console
from rich.markdown import Markdown

from build_influence.utils import setup_logging
from build_influence.config import config
from build_influence.analysis import RepositoryAnalyzer
from build_influence.interview import Interviewer
from build_influence.generation import (
    BaseContentGenerator,
    MarkdownGenerator,
    DevtoGenerator,
    TwitterGenerator,
    LinkedinGenerator,
)

app = typer.Typer(
    name="build-influence",
    help="Analyzes code repositories and generates content.",
    no_args_is_help=True,
)

ANALYSIS_FILENAME = "analysis_results.json"
INTERVIEW_LOG_FILENAME = "interview_log.json"


@app.callback()
def callback(
    ctx: typer.Context,
    config_file: Path = typer.Option(
        "config.yaml",
        help="Path to the configuration file.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
):
    """Build Influence CLI."""
    # Eagerly setup logging before doing anything else
    setup_logging()

    logger.debug(f"Using configuration file: {config_file}")
    # Config is loaded globally in config/loader.py
    # Store base output directories in context
    analysis_dir = Path(
        config.get("output_dirs").get(
            "analysis",
            "output/analysis",
        ),
    )
    interview_dir = Path(
        config.get("output_dirs").get("interviews", "output/interviews")
    )
    content_dir = Path(
        config.get("output_dirs").get(
            "content",
            "output/content",
        ),
    )

    # Ensure directories exist
    analysis_dir.mkdir(parents=True, exist_ok=True)
    interview_dir.mkdir(parents=True, exist_ok=True)
    content_dir.mkdir(parents=True, exist_ok=True)

    ctx.obj = {
        "CONFIG_FILE": config_file,
        "ANALYSIS_DIR": analysis_dir,
        "INTERVIEW_DIR": interview_dir,
        "CONTENT_OUTPUT_DIR": content_dir,
    }
    logger.debug(f"Context initialized with output directories: {ctx.obj}")


@app.command()
def analyze(
    ctx: typer.Context,
    repo_path: Path = typer.Argument(
        ".",
        help="Path to the local code repository to analyze.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force re-analysis even if results file exists.",
    ),
):
    """Analyzes a code repository and saves the results."""
    # Construct analysis file path using repo name
    safe_repo_name = "".join(c if c.isalnum() else "_" for c in repo_path.name)
    analysis_file_path = ctx.obj["ANALYSIS_DIR"] / f"{safe_repo_name}_analysis.json"
    logger.info(f"Starting analysis for repository: {repo_path}")
    logger.info(f"Analysis results will be saved to: {analysis_file_path}")

    if analysis_file_path.exists() and not force:
        typer.secho(
            f"Analysis file '{analysis_file_path}' exists.",
            fg=typer.colors.YELLOW,
        )
        typer.echo("Use --force to overwrite.")
        logger.warning("Analysis skipped: File exists and --force not used.")
        return

    analyzer = RepositoryAnalyzer(str(repo_path))
    try:
        analysis_results = analyzer.analyze()

        # Add the original repo path to the results
        analysis_results["original_repo_path"] = str(repo_path.resolve())

        with open(analysis_file_path, "w") as f:
            json.dump(analysis_results, f, indent=2)
        msg = f"Analysis complete. Saved to '{analysis_file_path}'"
        typer.secho(msg, fg=typer.colors.GREEN)
        logger.info(f"Analysis results saved to {analysis_file_path}")
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        typer.secho(f"Error during analysis: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command()
def interview(
    ctx: typer.Context,
    repo_name: str = typer.Argument(
        ...,
        help=("The name of the repository (used for finding " "analysis/log files)."),
    ),
):
    """Starts an interactive interview based on analysis results."""
    analysis_dir: Path = ctx.obj["ANALYSIS_DIR"]
    interview_dir: Path = ctx.obj["INTERVIEW_DIR"]

    # Construct file paths using the provided repo_name
    safe_repo_name = "".join(c if c.isalnum() else "_" for c in repo_name)
    analysis_file_path = analysis_dir / f"{safe_repo_name}_analysis.json"
    interview_log_file = interview_dir / f"{safe_repo_name}_interview.json"

    if not analysis_file_path.exists():
        msg = f"Analysis file '{analysis_file_path}' not found."
        typer.secho(msg, fg=typer.colors.RED)
        typer.echo("Please run the 'analyze' command first.")
        logger.error("Interview command failed: Analysis results not found.")
        raise typer.Exit(code=1)

    try:
        with open(analysis_file_path, "r") as f:
            analysis_data = json.load(f)
        logger.info(f"Loaded analysis data from {analysis_file_path}")
    except json.JSONDecodeError as e:
        msg = f"Error reading '{analysis_file_path}': Invalid JSON."
        logger.error(f"Failed to decode JSON from {analysis_file_path}: {e}")
        typer.secho(msg, fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except Exception as e:
        msg = f"Error reading analysis file: {e}"
        logger.error(f"Failed to read analysis file {analysis_file_path}: {e}")
        typer.secho(msg, fg=typer.colors.RED)
        raise typer.Exit(code=1)

    interviewer = Interviewer(analysis_data)
    try:
        interview_results = interviewer.conduct_interview()

        if not interview_results:
            msg = "Interview completed, but no answers were recorded."
            typer.secho(msg, fg=typer.colors.YELLOW)
            logger.warning("Interview finished with no recorded answers.")
            return

        try:
            interview_log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(interview_log_file, "w") as f:
                log_data = [{"question": q, "answer": a} for q, a in interview_results]
                json.dump(log_data, f, indent=2)
            msg = f"Interview log saved to '{interview_log_file}'"
            typer.secho(msg, fg=typer.colors.GREEN)
            logger.info(f"Interview log saved to {interview_log_file}")
        except Exception as e:
            log_err = f"Failed to save log to {interview_log_file}: {e}"
            logger.error(log_err)
            typer.secho(f"Error saving interview log: {e}", fg=typer.colors.RED)

    except Exception as e:
        err_intro = "An error occurred during the interview:"
        logger.error(f"{err_intro} {e}", exc_info=True)
        typer.secho(f"{err_intro} {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command()
def generate(
    ctx: typer.Context,
    repo_name: str = typer.Argument(
        ...,
        help=("The name of the repository (used for finding " "analysis/log files)."),
    ),
    platform: str | None = typer.Option(
        None,
        "--platform",
        "-p",
        help="Target platform (e.g., devto, twitter, linkedin, markdown). "
        "If omitted, generates for all platforms.",
    ),
    content_type: str | None = typer.Argument(
        None,
        help="Type of content (e.g., announcement, deepdive). "
        "If omitted, uses platform default.",
    ),
):
    """
    Generates content based on analysis results using a platform-specific
    strategy. If no platform is specified, generates for all.
    """
    console = Console()
    analysis_dir: Path = ctx.obj["ANALYSIS_DIR"]
    interview_dir: Path = ctx.obj["INTERVIEW_DIR"]
    content_output_dir: Path = ctx.obj["CONTENT_OUTPUT_DIR"]

    # Construct analysis file path
    safe_repo_name = "".join(c if c.isalnum() else "_" for c in repo_name)
    analysis_file_path = analysis_dir / f"{safe_repo_name}_analysis.json"

    # --- Load data ONCE --- Moved outside the loop
    if not analysis_file_path.exists():
        msg = f"Analysis file '{analysis_file_path}' not found."
        console.print(f":x: [bold red]Error:[/bold red] {msg}")
        console.print("Please run the 'analyze' command first.")
        logger.error("Generate command failed: Analysis results not found.")
        raise typer.Exit(code=1)

    try:
        with open(analysis_file_path, "r") as f:
            analysis_data = json.load(f)
        logger.info(f"Loaded analysis data from {analysis_file_path}")
    except json.JSONDecodeError as e:
        msg = f"Error reading '{analysis_file_path}': Invalid JSON."
        logger.error(f"Failed to decode JSON from {analysis_file_path}: {e}")
        console.print(f":x: [bold red]Error:[/bold red] {msg}")
        raise typer.Exit(code=1)
    except Exception as e:
        msg = f"Error reading analysis file: {e}"
        logger.error(f"Failed to read analysis file {analysis_file_path}: {e}")
        console.print(f":x: [bold red]Error:[/bold red] {msg}")
        raise typer.Exit(code=1)

    interview_data = None
    readme_content = None
    original_repo_path_str = analysis_data.get("original_repo_path")

    # Load interview data
    interview_log_file = interview_dir / f"{safe_repo_name}_interview.json"
    if interview_log_file.exists():
        try:
            with open(interview_log_file, "r") as f:
                interview_data = json.load(f)
            logger.info(f"Loaded interview data from {interview_log_file}")
        except json.JSONDecodeError as e:
            logger.warning(
                f"Could not decode interview log JSON from "
                f"{interview_log_file}': {e}"
            )
        except Exception as e:
            logger.warning(
                f"Could not read interview log file " f"{interview_log_file}': {e}"
            )

    # Load README content
    if original_repo_path_str:
        original_repo_path = Path(original_repo_path_str)
        readme_found = False
        for readme_name in ["README.md", "README.rst", "README.txt", "README"]:
            readme_path = original_repo_path / readme_name
            if readme_path.exists() and readme_path.is_file():
                try:
                    with open(readme_path, "r") as f:
                        readme_content = f.read()
                    logger.info(f"Loaded README content from {readme_path}")
                    readme_found = True
                    break
                except Exception as e:
                    logger.warning(f"Could not read README {readme_path}: {e}")
        if not readme_found:
            logger.info("No README file found in repository root.")
    else:
        logger.warning("Original repository path not found in analysis results.")
    # --- End loading data ---

    # Map platform strings to generator classes (Strategy pattern)
    generator_strategies: Dict[str, Type[BaseContentGenerator]] = {
        "markdown": MarkdownGenerator,
        "devto": DevtoGenerator,
        "twitter": TwitterGenerator,
        "linkedin": LinkedinGenerator,
    }

    # Default content types per platform
    default_content_types = {
        "markdown": "announcement",
        "devto": "deepdive",
        "twitter": "thread_intro",  # Example default
        "linkedin": "post_summary",  # Example default
    }

    # --- Determine target platforms --- #
    target_platforms: List[str] = []
    if platform is None:
        # Default to all platforms
        target_platforms = list(generator_strategies.keys())
        logger.info(
            f"No platform specified, generating for all: " f"{target_platforms}"
        )
    else:
        selected_platform = platform.lower()
        if selected_platform not in generator_strategies:
            msg = (
                f"Invalid platform '{selected_platform}'. Choose from: "
                f"{list(generator_strategies.keys())}"
            )
            console.print(f":x: [bold red]Error:[/bold red] {msg}")
            logger.error(f"Invalid generation platform specified: {selected_platform}")
            raise typer.Exit(code=1)
        target_platforms = [selected_platform]
        logger.info(f"Generating for specified platform: {selected_platform}")

    # --- Loop through platforms and generate --- #
    generation_successful = False  # Track if at least one generation worked
    for current_platform in target_platforms:
        console.rule(f"[bold blue]Platform: {current_platform}[/bold blue]")

        # Determine the content type for this platform
        current_content_type = content_type.lower() if content_type else None
        if not current_content_type:
            current_content_type = default_content_types.get(current_platform)
            if not current_content_type:
                msg = (
                    f"No default content type defined for platform "
                    f"'{current_platform}'. Skipping."
                )
                console.print(f":yellow_circle: [yellow]Warning:[/yellow] {msg}")
                logger.warning(msg)
                continue  # Skip to next platform
            else:
                logger.info(
                    f"Using default content type '{current_content_type}' "
                    f"for {current_platform}"
                )
        else:
            logger.info(
                f"Using specified content type '{current_content_type}' "
                f"for {current_platform}"
            )

        # Select the appropriate generator strategy
        GeneratorClass = generator_strategies[current_platform]
        generator = GeneratorClass(
            analysis_data,
            interview_data=interview_data,
            readme_content=readme_content,
        )
        logger.info(
            f"Using {GeneratorClass.__name__} for platform " f"'{current_platform}'."
        )

        try:
            # Initial Generation
            generation_message = (
                f"Generating [bold magenta]{current_content_type}[/bold magenta] "
                f"content for [bold cyan]{current_platform}[/bold cyan]..."
            )
            generated_content = None
            with console.status(generation_message, spinner="dots"):
                generated_content = generator.generate(
                    content_type=current_content_type,
                )

            if generated_content:
                console.print("✨ Initial content generated successfully! ✨")

                current_content = generated_content
                user_action = None  # Track if user saves or discards

                # --- Feedback Loop --- #
                while True:
                    console.rule(
                        f"[bold blue]Preview & Refine ({current_platform})[/bold blue]"
                    )
                    is_markdown_output = current_platform in [
                        "markdown",
                        "devto",
                    ]
                    if is_markdown_output:
                        console.print(Markdown(current_content))
                    else:
                        console.print(current_content)
                    console.rule()

                    feedback_prompt = "\nType your feedback to refine, 'save' to keep, or 'discard' to abandon: "
                    feedback_input = typer.prompt(
                        feedback_prompt, default="", show_default=False
                    ).strip()

                    if feedback_input.lower() == "save":
                        user_action = "save"
                        break
                    elif feedback_input.lower() == "discard":
                        user_action = "discard"
                        console.print(
                            f"[yellow]Discarding content for {current_platform}.[/yellow]"
                        )
                        logger.info(
                            f"User discarded content for {current_platform} "
                            f"after feedback loop."
                        )
                        break
                    elif feedback_input:  # User provided feedback
                        console.print("🔄 Refining content based on feedback...")
                        refinement_message = "Applying feedback..."
                        new_content = None
                        with console.status(refinement_message, spinner="dots"):
                            try:
                                new_content = generator.regenerate_with_feedback(
                                    original_content=current_content,
                                    feedback=feedback_input,
                                    content_type=current_content_type,
                                )
                            except Exception as regen_e:
                                logger.error(
                                    f"Error during regeneration call: {regen_e}",
                                    exc_info=True,
                                )
                                console.print(
                                    f"[bold red]Error applying feedback:[/bold red] {regen_e}"
                                )
                                # Continue loop with old content

                        if new_content:
                            console.print("✅ Refinement applied!")
                            current_content = new_content
                        else:
                            console.print(
                                "[yellow]Could not apply feedback. "
                                "Please try again or refine your feedback.[/yellow]"
                            )
                        # Continue the loop to show refined content/ask again
                    else:  # Empty input
                        console.print(
                            "Please provide feedback, or type 'save' or 'discard'."
                        )
                        # Continue loop
                # --- End Feedback Loop --- #

                # Determine output filename (moved here, used only if saving)
                output_extension = (
                    ".md"
                    if is_markdown_output
                    else (".txt" if current_platform == "twitter" else ".txt")
                )
                output_filename = (
                    f"{safe_repo_name}_{current_platform}_"
                    f"{current_content_type}{output_extension}"
                )
                output_filepath = content_output_dir / output_filename

                # Save if the user chose to save
                if user_action == "save":
                    try:
                        with open(output_filepath, "w") as f:
                            f.write(current_content)  # Save the final version
                        success_msg = (
                            f"✅ Successfully saved content to: "
                            f"[link=file://{output_filepath.resolve()}]"
                            f"{output_filepath}[/link]"
                        )
                        console.print(success_msg)
                        logger.info(f"Content saved to {output_filepath}")
                        generation_successful = True  # Mark success
                    except IOError as e:
                        save_err_msg = f"Error saving content to {output_filepath}: {e}"
                        console.print(f":x: [bold red]Error:[/bold red] {save_err_msg}")
                        logger.error(save_err_msg)
                        # Decide whether to continue or exit? For now, continue.
                # else: user chose discard, already logged

            else:
                error_msg = (
                    f"Failed to generate initial content for {current_platform} "
                    f"{current_content_type}. Check logs."
                )
                console.print(f":x: [bold red]Error:[/bold red] {error_msg}")
                logger.error(
                    f"Content generation failed for "
                    f"{current_platform}/{current_content_type}."
                )
                # Continue to next platform

        except Exception as e:
            err_intro = (
                f"An error occurred during content generation/refinement "
                f"for {current_platform}:"
            )
            logger.error(f"{err_intro} {e}", exc_info=True)
            console.print(f":x: [bold red]{err_intro}[/bold red] {e}")
            # Continue to next platform

    # --- End loop --- #

    if not generation_successful:
        console.print(
            ":warning: [yellow]No content was successfully generated and saved.[/yellow]"
        )
        logger.warning("Generate command finished, but no content was saved.")
        # Optionally raise Exit here if failure is critical


@app.command()
def publish():
    """Publishes content to platforms. (Not Implemented)"""
    typer.echo("Publication logic (Not Implemented).")
    logger.info("Publish command executed (placeholder).")
    raise typer.Exit(code=1)


@app.command()
def configure():
    """Configures application settings. (Not Implemented)"""
    typer.echo("Configuration logic (Not Implemented).")
    logger.info("Configure command executed (placeholder).")


@app.command()
def logs(
    lines: int = typer.Option(
        10,
        "--lines",
        "-n",
        help="Number of log lines to show.",
    ),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output."),
):
    """Displays the application log file."""
    log_file_path = Path(os.getenv("LOG_FILE", "logs/build_influence.log"))
    if not log_file_path.exists():
        typer.secho(
            f"Log file not found: {log_file_path}",
            fg=typer.colors.RED,
        )
        logger.error(
            f"Log file access failed: {log_file_path} does not exist.",
        )
        raise typer.Exit(code=1)

    try:
        if follow:
            typer.echo(f"Following log: {log_file_path} (Ctrl+C to exit)")
            with open(log_file_path, "r") as f:
                f.seek(0, os.SEEK_END)
                while True:
                    line = f.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    typer.echo(line.strip())
        else:
            typer.echo(f"Showing last {lines} lines from {log_file_path}:")
            with open(log_file_path, "r") as f:
                log_lines = f.readlines()
                for line in log_lines[-lines:]:
                    typer.echo(line.strip())
    except FileNotFoundError:
        typer.secho(f"Log file not found: {log_file_path}", fg=typer.colors.RED)
    except KeyboardInterrupt:
        typer.echo("\nStopped following log.")
    except Exception as e:
        typer.secho(f"Error reading log file: {e}", fg=typer.colors.RED)


if __name__ == "__main__":
    app()
