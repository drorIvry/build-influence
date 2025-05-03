import typer
from loguru import logger
import os
import json
from pathlib import Path
import time
from typing import Dict, Type, List, Tuple
from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm

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
from build_influence.publication import (
    get_publisher,
    PublicationContent,
    PublishResult,
)

app = typer.Typer(
    name="build-influence",
    help="Analyzes code repositories and generates content.",
    no_args_is_help=True,
)

ANALYSIS_FILENAME = "analysis_results.json"
INTERVIEW_LOG_FILENAME = "interview_log.json"

# Mapping from platform name to Generator class
AVAILABLE_GENERATORS: Dict[str, Type[BaseContentGenerator]] = {
    "markdown": MarkdownGenerator,
    "devto": DevtoGenerator,
    "twitter": TwitterGenerator,
    "linkedin": LinkedinGenerator,
    # Add other generators here as they are created
}

# Default content types per platform (copied from generate command for now)
DEFAULT_CONTENT_TYPES = {
    "markdown": "announcement",
    "devto": "deepdive",
    "twitter": "thread_intro",
    "linkedin": "post_summary",
}


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
        help=("The name of the repository (used for finding analysis/log files)."),
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
        help=("The name of the repository (used for finding analysis/log files)."),
    ),
    platform: str | None = typer.Option(
        None,
        "--platform",
        "-p",
        help=(
            "Target platform (e.g., devto, twitter, linkedin, markdown). "
            "If omitted, generates for all platforms."
        ),
    ),
    content_type: str | None = typer.Argument(
        None,
        help=(
            "Type of content (e.g., announcement, deepdive). "
            "If omitted, uses platform default."
        ),
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
                f"'{interview_log_file}': {e}"
            )
        except Exception as e:
            logger.warning(
                f"Could not read interview log file " f"'{interview_log_file}': {e}"
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
        logger.warning(
            "Original repository path not found in analysis results.",
        )
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
        logger.info(f"No platform specified, generating for all: {target_platforms}")
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
            f"Using {GeneratorClass.__name__} for platform '{current_platform}'."
        )

        try:
            # Initial Generation
            generation_message = (
                f"Generating [bold magenta]{current_content_type}"
                "[/bold magenta] content "
                f"for [bold cyan]{current_platform}[/bold cyan]..."
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
                previous_content = None  # To store content for revert
                can_revert = False  # Flag to enable/disable revert option

                # --- Feedback Loop --- #
                while True:
                    # Clear screen for cleaner UX
                    os.system("cls" if os.name == "nt" else "clear")

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

                    prompt_options = (
                        "Type your feedback to refine, 'save' to keep, or "
                        "'discard' to abandon."
                    )
                    if can_revert:
                        prompt_options += " Type 'revert' to undo the last change."

                    feedback_input = typer.prompt(
                        f"\n{prompt_options}\n> ", default="", show_default=False
                    ).strip()

                    if feedback_input.lower() == "save":
                        user_action = "save"
                        break
                    elif feedback_input.lower() == "discard":
                        user_action = "discard"
                        console.print(
                            f"[yellow]Discarding content for "
                            f"{current_platform}.[/yellow]"
                        )
                        logger.info(
                            f"User discarded content for {current_platform} "
                            f"after feedback loop."
                        )
                        break
                    elif feedback_input.lower() == "revert" and can_revert:
                        if previous_content is not None:
                            console.print("⏪ Reverting to previous version...")
                            current_content = previous_content
                            # Clear previous after revert
                            previous_content = None
                            # Disable revert until next change
                            can_revert = False
                            # Continue loop to show reverted content
                        else:
                            # Should not happen if managed correctly
                            console.print(
                                "[yellow]Cannot revert: No previous version "
                                "stored.[/yellow]"
                            )
                    elif feedback_input.lower() == "revert" and not can_revert:
                        console.print(
                            "[yellow]Cannot revert: No changes to undo yet.[/yellow]"
                        )
                    elif feedback_input:  # User provided feedback
                        console.print("🔄 Refining content based on feedback...")
                        refinement_message = "Applying feedback..."
                        new_content = None
                        # Store current state before attempting refinement
                        previous_content = current_content
                        can_revert = True  # Enable revert after this attempt

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
                                    f"[bold red]Error applying feedback:[/bold red] "
                                    f"{regen_e}"
                                )
                                # Revert state because refinement failed
                                previous_content = None
                                can_revert = False
                                # Continue loop with old content

                        if new_content:
                            console.print("✅ Refinement applied!")
                            current_content = new_content
                            # Keep previous_content and can_revert as they are
                        else:
                            console.print(
                                "[yellow]Could not apply feedback. "
                                "Previous version kept.[/yellow]"
                            )
                            # Revert state because refinement returned None
                            previous_content = None
                            can_revert = False
                        # Continue the loop to show refined content/ask again
                    else:  # Empty input
                        console.print(
                            "Please provide feedback, or type 'save', 'discard'"
                            + (" or 'revert'." if can_revert else ".")
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
        console.print(":warning: [yellow]No content was generated and saved.[/yellow]")
        logger.warning("Generate command finished, but no content was saved.")
        # Optionally raise Exit here if failure is critical


@app.command()
def publish(
    ctx: typer.Context,
    content_file: Path = typer.Argument(
        ...,
        help="Path to the generated content file to publish.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
    platform: str = typer.Argument(
        ...,
        help="Platform to publish to (e.g., devto, twitter, linkedin). "
        "Must match a configured platform.",
    ),
):
    """Publishes a single generated content file to a specific platform."""
    console = Console()
    logger.info(f"Attempting to publish '{content_file}' to platform '{platform}'")

    # --- 1. Load Content ---
    try:
        with open(content_file, "r") as f:
            # For now, treat the entire file content as the body.
            # Future improvements could parse frontmatter for title/tags.
            body_content = f.read()
        if not body_content:
            console.print(
                f":x: [bold red]Error:[/bold red] Content file "
                f"'{content_file}' is empty."
            )
            logger.error(f"Publish failed: Content file '{content_file}' is empty.")
            raise typer.Exit(code=1)
        # Basic content structure - assumes title/tags might be handled differently
        # or not needed for all platforms (like Twitter). Dev.to requires title.
        # Let's derive a basic title from filename if needed.
        content_title = content_file.stem.replace("_", " ").title()
        publication_content = PublicationContent(body=body_content, title=content_title)
        logger.debug(f"Loaded content from {content_file}")

    except Exception as e:
        msg = f"Error reading content file '{content_file}': {e}"
        console.print(f":x: [bold red]Error:[/bold red] {msg}")
        logger.error(msg, exc_info=True)
        raise typer.Exit(code=1)

    # --- 2. Get Publisher ---
    publisher = get_publisher(platform.lower())
    if not publisher:
        msg = (
            f"No publisher found for platform '{platform}'. Available "
            f"publishers are configured in publication/__init__.py."
        )
        console.print(f":x: [bold red]Error:[/bold red] {msg}")
        logger.error(msg)
        raise typer.Exit(code=1)
    logger.info(f"Using publisher: {publisher}")

    # --- 3. Get Platform Configuration ---
    platform_key = platform.lower()
    platform_config = config
    if not platform_config:
        # Special check for devto/dev.to alias
        if platform_key == "dev.to":
            platform_key = "devto"

    if not platform_config or not isinstance(platform_config, dict):
        msg = (
            f"Config for platform '{platform}' not found/invalid "
            f"in config under 'platforms' key."
        )
        console.print(f":x: [bold red]Error:[/bold red] {msg}")
        logger.error(msg)
        console.print("Example config structure:")
        console.print(
            """
platforms:
  devto:
    api_key: YOUR_KEY
  twitter:
    api_key: YOUR_TOKEN
"""
        )
        raise typer.Exit(code=1)
    logger.debug(f"Loaded configuration for platform '{platform}'.")

    # --- 4. Perform Publication ---
    publish_message = f"Publishing to [bold cyan]{platform}[/bold cyan]..."
    result: PublishResult | None = None
    with console.status(publish_message, spinner="dots"):
        try:
            logger.info(f">>>> config: {config.get('platforms', {})}")
            result = publisher.publish(publication_content, config)
        except Exception as e:
            # Catch unexpected errors during the publish call itself
            msg = f"Unexpected error during publishing: {e}"
            console.print(f"\n:x: [bold red]Error:[/bold red] {msg}")
            logger.error(msg, exc_info=True)
            raise typer.Exit(code=1)

    # --- 5. Display Result ---
    if result:
        if result.success:
            success_msg = f"✅ Successfully published to {platform}!"
            if result.url:
                success_msg += f" URL: [link={result.url}]{result.url}[/link]"
            else:
                # Show message if no URL, but publication succeeded
                success_msg += f" {result.message}"
            console.print(success_msg)
            pub_log_msg = f"Publication successful for {platform}."
            if result.url:
                pub_log_msg += f" URL: {result.url}"
            logger.success(pub_log_msg)
        else:
            error_msg = (
                f":x: [bold red]Failed to publish to {platform}:[/bold red] "
                f"{result.message}"
            )
            console.print(error_msg)
            logger.error(f"Publication failed for {platform}. Reason: {result.message}")
            raise typer.Exit(code=1)  # Exit with error on failure
    else:
        # Should not happen if publisher returns correctly, but handle defensively
        console.print(
            ":x: [bold red]Error:[/bold red] Publisher did not return a result."
        )
        logger.error(f"Publisher for {platform} failed to return a result.")
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
        typer.secho(f"Log file not found: {log_file_path}", fg=typer.colors.RED)
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


# --- Interactive Workflow Command ---


@app.command(name="run")
def interactive_workflow(ctx: typer.Context):
    """Runs the full workflow interactively: Analyze -> Interview -> Generate -> Publish."""
    console = Console()
    console.print(Markdown("# Build Influence Interactive Workflow"))

    # --- Context Setup ---
    analysis_dir: Path = ctx.obj["ANALYSIS_DIR"]
    interview_dir: Path = ctx.obj["INTERVIEW_DIR"]
    content_output_dir: Path = ctx.obj["CONTENT_OUTPUT_DIR"]

    # --- 1. Get Repository Path ---
    repo_path_str = Prompt.ask(
        "[bold cyan]Enter the path to the local code repository to analyze[/]",
        default=".",
    )
    repo_path = Path(repo_path_str).resolve()

    if not repo_path.is_dir() or not repo_path.exists():
        console.print(
            f"[bold red]Error:[/bold red] Path '{repo_path}' is not a valid directory."
        )
        raise typer.Exit(code=1)

    safe_repo_name = "".join(c if c.isalnum() else "_" for c in repo_path.name)
    analysis_file_path = analysis_dir / f"{safe_repo_name}_analysis.json"
    interview_log_file = interview_dir / f"{safe_repo_name}_interview.json"

    console.print(f"\nAnalyzing repository: [blue]{repo_path}[/blue]")
    logger.info(f"Starting interactive analysis for repository: {repo_path}")

    # --- 2. Run Analysis ---
    analysis_results = None
    if analysis_file_path.exists():
        if Confirm.ask(
            f"Analysis file [magenta]'{analysis_file_path}'[/magenta] already exists. Use existing file?",
            default=True,
        ):
            try:
                with open(analysis_file_path, "r") as f:
                    analysis_results = json.load(f)
                console.print(
                    f"Loaded existing analysis from [green]{analysis_file_path}[/green]"
                )
                logger.info(f"Loaded existing analysis file: {analysis_file_path}")
            except Exception as e:
                console.print(
                    f"[bold red]Error:[/bold red] Failed to load existing analysis file: {e}"
                )
                logger.error(
                    f"Failed to load existing analysis {analysis_file_path}: {e}",
                    exc_info=True,
                )
                if not Confirm.ask("Proceed with re-analysis?", default=True):
                    raise typer.Exit()
                analysis_results = None  # Force re-analysis
        else:
            logger.info("User chose to re-analyze.")

    if analysis_results is None:
        console.print("Running repository analysis... this might take a moment.")
        try:
            analyzer = RepositoryAnalyzer(str(repo_path))
            analysis_results = analyzer.analyze()
            analysis_results["original_repo_path"] = str(
                repo_path
            )  # Ensure path is stored

            analysis_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(analysis_file_path, "w") as f:
                json.dump(analysis_results, f, indent=2)
            console.print(
                f"Analysis complete. Results saved to [green]{analysis_file_path}[/green]"
            )
            logger.info(f"Analysis successful. Saved to {analysis_file_path}")
        except Exception as e:
            console.print(f"[bold red]Error during analysis:[/bold red] {e}")
            logger.error(f"Analysis failed: {e}", exc_info=True)
            raise typer.Exit(code=1)

    # --- 3. Conduct Interview ---
    console.print(Markdown("\n---\n## Step 2: Conduct Interview"))

    interview_data = None
    if interview_log_file.exists():
        if Confirm.ask(
            f"Interview log [magenta]'{interview_log_file}'[/magenta] already exists. Use existing log?",
            default=True,
        ):
            try:
                with open(interview_log_file, "r") as f:
                    interview_data = json.load(
                        f
                    )  # Assuming log format is list of dicts
                console.print(
                    f"Loaded existing interview log from [green]{interview_log_file}[/green]"
                )
                logger.info(f"Loaded existing interview log: {interview_log_file}")
            except Exception as e:
                console.print(
                    f"[bold red]Error:[/bold red] Failed to load existing interview log: {e}"
                )
                logger.error(
                    f"Failed to load existing interview log {interview_log_file}: {e}",
                    exc_info=True,
                )
                if not Confirm.ask("Proceed with new interview?", default=True):
                    console.print("[yellow]Skipping interview step.[/yellow]")
                else:
                    interview_data = None  # Force new interview
        else:
            logger.info("User chose to conduct a new interview.")
            interview_data = None

    if interview_data is None:
        if Confirm.ask(
            "\nProceed with AI-powered interview based on analysis?", default=True
        ):
            console.print("Starting interview... Answer the questions below.")
            try:
                interviewer = Interviewer(analysis_results)
                interview_results_list = interviewer.conduct_interview()

                if interview_results_list:
                    interview_data = [
                        {"question": q, "answer": a} for q, a in interview_results_list
                    ]
                    try:
                        interview_log_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(interview_log_file, "w") as f:
                            json.dump(interview_data, f, indent=2)
                        console.print(
                            f"Interview log saved to [green]{interview_log_file}[/green]"
                        )
                        logger.info(f"Interview log saved: {interview_log_file}")
                    except Exception as e:
                        console.print(
                            f"[bold red]Error:[/bold red] Failed to save interview log: {e}"
                        )
                        logger.error(
                            f"Failed to save interview log: {e}", exc_info=True
                        )
                else:
                    console.print(
                        "[yellow]Interview completed, but no answers recorded.[/yellow]"
                    )
                    logger.warning("Interview finished with no recorded answers.")
                    # Proceed without interview data

            except Exception as e:
                console.print(f"[bold red]Error during interview:[/bold red] {e}")
                logger.error(f"Interview failed: {e}", exc_info=True)
                # Decide if we should exit or allow proceeding without interview
                if not Confirm.ask(
                    "Interview failed. Continue to content generation without interview data?",
                    default=False,
                ):
                    raise typer.Exit(code=1)
        else:
            console.print("[yellow]Skipping interview step.[/yellow]")
            logger.info("User skipped interview step.")

    # --- 4. Generate Content ---
    console.print(Markdown("\n---\n## Step 3: Generate Content"))
    generated_content_files: List[Tuple[str, Path]] = []  # Store (platform, path)

    # Prepare generation context
    generation_context = analysis_results or {}
    if interview_data:
        generation_context["interview_summary"] = "\n".join(
            [f"Q: {item['question']}\nA: {item['answer']}" for item in interview_data]
        )
        generation_context["interview_raw"] = interview_data

    # Ask user which platforms to generate for
    available_platform_names = list(AVAILABLE_GENERATORS.keys())
    selected_platforms_str = Prompt.ask(
        f"[bold cyan]Enter platforms to generate content for (comma-separated)[/bold cyan]\
        Available: {', '.join(available_platform_names)}\
        (Leave blank to skip generation)",
        default=",".join(available_platform_names),  # Default to all
    )

    if not selected_platforms_str.strip():
        console.print("[yellow]Skipping content generation step.[/yellow]")
        logger.info("User skipped content generation.")
        selected_platforms = []
    else:
        selected_platforms = [
            p.strip().lower() for p in selected_platforms_str.split(",")
        ]

    generation_output_base = content_output_dir / safe_repo_name
    generation_output_base.mkdir(parents=True, exist_ok=True)

    for platform in selected_platforms:
        if platform not in AVAILABLE_GENERATORS:
            console.print(
                f"[yellow]Warning:[/yellow] Unknown platform '{platform}'. Skipping."
            )
            logger.warning(f"Skipping unknown generation platform: {platform}")
            continue

        console.print(
            f"\nGenerating content for platform: [bold blue]{platform}[/bold blue]"
        )
        logger.info(f"Generating content for platform: {platform}")

        try:
            generator_class = AVAILABLE_GENERATORS[platform]
            generator = generator_class(generation_context)

            # Determine content type
            current_content_type = DEFAULT_CONTENT_TYPES.get(platform, "default")
            logger.info(f"Using content type '{current_content_type}' for {platform}")

            # --- Initial Generation ---
            initial_content = None
            with console.status(
                f"Generating initial content for {platform}...", spinner="dots"
            ):
                initial_content = generator.generate(content_type=current_content_type)

            if not initial_content:
                console.print(
                    f"[yellow]Initial generation failed for {platform}. Skipping.[/yellow]"
                )
                logger.warning(
                    f"Initial generation for {platform} returned no content."
                )
                continue

            console.print("✨ Initial content generated successfully! ✨")

            # --- Feedback and Refinement Loop ---
            current_content = initial_content
            previous_content = None
            can_revert = False
            user_action = None  # To track save/discard

            while True:
                # Clear screen for cleaner UX (optional, can be removed)
                # os.system("cls" if os.name == "nt" else "clear")

                console.rule(
                    f"[bold blue]Preview & Refine ({platform} - {current_content_type})[/bold blue]"
                )
                is_markdown_output = platform in ["markdown", "devto"]
                if is_markdown_output:
                    console.print(Markdown(current_content))
                else:
                    console.print(current_content)
                console.rule()

                prompt_options = "Type feedback to refine, 'save', or 'discard'."
                if can_revert:
                    prompt_options += " Type 'revert' to undo last change."

                feedback_input = Prompt.ask(
                    f"\n{prompt_options}\n> ", default="", show_default=False
                ).strip()

                if feedback_input.lower() == "save":
                    user_action = "save"
                    break
                elif feedback_input.lower() == "discard":
                    user_action = "discard"
                    break
                elif feedback_input.lower() == "revert" and can_revert:
                    if previous_content is not None:
                        console.print("⏪ Reverting to previous version...")
                        current_content = previous_content
                        previous_content = None  # Clear after revert
                        can_revert = False  # Disable until next change
                    else:
                        console.print(
                            "[yellow]Cannot revert: No previous version stored.[/yellow]"
                        )
                elif feedback_input.lower() == "revert" and not can_revert:
                    console.print(
                        "[yellow]Cannot revert: No changes to undo yet.[/yellow]"
                    )
                elif feedback_input:  # User provided feedback
                    console.print("🔄 Refining content based on feedback...")
                    previous_content = current_content  # Store before refining
                    can_revert = True
                    new_content = None
                    with console.status("Applying feedback...", spinner="dots"):
                        try:
                            new_content = generator.regenerate_with_feedback(
                                original_content=current_content,
                                feedback=feedback_input,
                                content_type=current_content_type,
                            )
                        except Exception as regen_e:
                            logger.error(
                                f"Error during regeneration: {regen_e}", exc_info=True
                            )
                            console.print(
                                f"[bold red]Error applying feedback:[/bold red] {regen_e}"
                            )
                            previous_content = None  # Failed, clear previous
                            can_revert = False

                    if new_content:
                        console.print("✅ Refinement applied!")
                        current_content = new_content
                    else:
                        console.print(
                            "[yellow]Could not apply feedback. Keeping previous version.[/yellow]"
                        )
                        previous_content = None  # Failed, clear previous
                        can_revert = False
                else:  # Empty input
                    console.print(
                        "Please provide feedback, or type 'save'/'discard'"
                        + ("/'revert'" if can_revert else ".")
                    )
            # --- End Feedback Loop ---

            # --- Save or Discard --- #
            if user_action == "save":
                filename_suggestion = f"{safe_repo_name}_{platform}_{current_content_type}.{generator.FILE_EXTENSION}"
                output_file = generation_output_base / filename_suggestion
                try:
                    with open(output_file, "w") as f:
                        f.write(
                            current_content
                        )  # Write the final, possibly refined, content
                    console.print(
                        f"Content for {platform} saved to [green]{output_file}[/green]"
                    )
                    logger.info(f"Content for {platform} saved to {output_file}")
                    generated_content_files.append((platform, output_file))
                except Exception as e:
                    console.print(
                        f"[bold red]Error saving content for {platform} to {output_file}:[/bold red] {e}"
                    )
                    logger.error(
                        f"Failed to save content for {platform} to {output_file}: {e}",
                        exc_info=True,
                    )
            elif user_action == "discard":
                console.print(
                    f"[yellow]Discarded content generation for {platform}.[/yellow]"
                )
                logger.info(
                    f"User discarded content for {platform} after refinement loop."
                )
            # else: Should not happen if loop exited correctly

        except Exception as e:
            console.print(
                f"[bold red]Error during generation/refinement for {platform}:[/bold red] {e}"
            )
            logger.error(f"Generation failed for {platform}: {e}", exc_info=True)

    # --- 5. Publish Content ---
    console.print(Markdown("\n---\n## Step 4: Publish Content"))

    if not generated_content_files:
        console.print(
            "[yellow]No content files were generated. Skipping publication.[/yellow]"
        )
        logger.info("Skipping publication step as no content was generated.")
    else:
        console.print("The following content files were generated:")
        publish_choices = {}
        for i, (platform, file_path) in enumerate(generated_content_files):
            display_path = (
                file_path.relative_to(Path.cwd())
                if file_path.is_relative_to(Path.cwd())
                else file_path
            )
            console.print(
                f"  [bold white]{i + 1}.[/bold white] [cyan]{platform:<10}[/cyan] -> [magenta]{display_path}[/magenta]"
            )
            publish_choices[str(i + 1)] = (platform, file_path)

        publish_selection_str = Prompt.ask(
            "\n[bold cyan]Enter the number(s) of the files to publish (comma-separated), or leave blank to skip[/bold cyan]",
            default="",
        )

        if not publish_selection_str.strip():
            console.print("[yellow]Skipping publication step.[/yellow]")
            logger.info("User skipped publication step.")
        else:
            selected_indices = [
                s.strip() for s in publish_selection_str.split(",") if s.strip()
            ]
            published_count = 0
            failed_count = 0

            for index in selected_indices:
                if index in publish_choices:
                    platform_to_publish, file_to_publish = publish_choices[index]
                    console.print(
                        f"\nAttempting to publish [magenta]{file_to_publish.name}[/magenta] to [blue]{platform_to_publish}[/blue]..."
                    )

                    # Double-check with user before potentially irreversible action
                    if not Confirm.ask(
                        f"Confirm publishing to {platform_to_publish}?", default=True
                    ):
                        console.print(
                            f"[yellow]Skipped publishing {file_to_publish.name}.[/yellow]"
                        )
                        logger.info(f"User skipped publishing {file_to_publish}")
                        continue

                    try:
                        # Read content from file
                        with open(file_to_publish, "r") as f:
                            content_to_publish = f.read()

                        publisher = get_publisher(platform_to_publish)
                        if not publisher:
                            console.print(
                                f"[bold red]Error:[/bold red] No publisher configured or found for platform '{platform_to_publish}'."
                            )
                            logger.error(
                                f"No publisher found for {platform_to_publish}"
                            )
                            failed_count += 1
                            continue

                        try:
                            # Assuming publisher needs PublicationContent object
                            pub_content = PublicationContent(
                                body=content_to_publish,
                                # Add other metadata if needed/available
                                title=f"Content from {safe_repo_name}",  # Basic title
                                tags=[],
                            )
                        except Exception:
                            logger.exception("error parsing the content")

                        # Perform the publication
                        result: PublishResult = publisher.publish(pub_content, config)

                        if result.success:
                            console.print(
                                f"[green]Successfully published to {platform_to_publish}[/green] {result.url or ''}"
                            )
                            logger.info(
                                f"Successfully published {file_to_publish} to {platform_to_publish}. URL: {result.url}"
                            )
                            published_count += 1
                        else:
                            console.print(
                                f"[bold red]Failed to publish to {platform_to_publish}:[/bold red] {result.message}"
                            )
                            logger.error(
                                f"Failed to publish {file_to_publish} to {platform_to_publish}: {result.message}"
                            )
                            failed_count += 1

                    except FileNotFoundError:
                        console.print(
                            f"[bold red]Error:[/bold red] Content file not found: {file_to_publish}"
                        )
                        logger.error(
                            f"Publish failed: File not found {file_to_publish}"
                        )
                        failed_count += 1
                    except Exception as e:
                        console.print(
                            f"[bold red]Error during publication to {platform_to_publish}:[/bold red] {e}"
                        )
                        logger.error(
                            f"Publication to {platform_to_publish} failed: {e}",
                            exc_info=True,
                        )
                        failed_count += 1
                else:
                    console.print(
                        f"[yellow]Warning:[/yellow] Invalid selection '{index}'. Skipping."
                    )

            console.print(
                f"\nPublication summary: {published_count} succeeded, {failed_count} failed."
            )

    console.print(Markdown("\n---\n## Workflow Complete"))
    logger.info("Interactive workflow finished.")


if __name__ == "__main__":
    app()
