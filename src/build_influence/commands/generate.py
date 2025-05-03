import typer
from loguru import logger
import os
import json
from pathlib import Path
from typing import Dict, Type, List
from rich.console import Console
from rich.markdown import Markdown

# Import constants and types from cli or a dedicated constants module if created
from ..constants import AVAILABLE_GENERATORS, DEFAULT_CONTENT_TYPES
from build_influence.generation import BaseContentGenerator


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

    # Use imported generator strategies
    generator_strategies: Dict[str, Type[BaseContentGenerator]] = AVAILABLE_GENERATORS

    # Use imported default content types
    default_content_types: Dict[str, str] = DEFAULT_CONTENT_TYPES

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
