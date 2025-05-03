import typer
from loguru import logger

# import os # Removed
import json
from pathlib import Path
from typing import List, Tuple  # Removed Dict, Type
from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm

# Import constants and types from cli or a dedicated constants module
# from build_influence.cli import AVAILABLE_GENERATORS, DEFAULT_CONTENT_TYPES # OLD IMPORT
from ..constants import AVAILABLE_GENERATORS, DEFAULT_CONTENT_TYPES  # NEW IMPORT
from build_influence.config import config
from build_influence.analysis import RepositoryAnalyzer
from build_influence.interview import Interviewer

# from build_influence.generation import BaseContentGenerator # Removed
from build_influence.publication import (
    get_publisher,
    PublicationContent,
    PublishResult,
)


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
    # TODO: Improve context preparation (e.g., load README here)
    generation_context = analysis_results or {}
    if interview_data:
        # Simple summary for now, might need better structuring for LLM
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

    generation_output_base = (
        content_output_dir  # Save directly in content dir for simplicity
    )
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
            # TODO: Pass README content to generator if loaded earlier
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

            # --- Feedback and Refinement Loop --- #
            current_content = initial_content
            previous_content = None
            can_revert = False
            user_action = None  # To track save/discard

            while True:
                # Optional clear screen removed for better history view during interaction
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
            # --- End Feedback Loop --- #

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

    # --- 5. Publish Content --- #
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

                        # Create PublicationContent object
                        # TODO: Enhance title/tag extraction from content/filename
                        pub_content = PublicationContent(
                            body=content_to_publish,
                            title=f"Content about {safe_repo_name}",  # Basic title
                            tags=[],
                        )

                        # Perform the publication using the global config
                        result: PublishResult | None = None
                        with console.status(
                            f"Publishing to {platform_to_publish}...", spinner="dots"
                        ):
                            result = publisher.publish(pub_content, config)

                        if result and result.success:
                            success_message = f"[green]Successfully published to {platform_to_publish}[/green]"
                            if result.url:
                                success_message += (
                                    f" URL: [link={result.url}]{result.url}[/link]"
                                )
                            elif result.message:
                                success_message += f" ({result.message})"
                            console.print(success_message)
                            logger.info(
                                f"Successfully published {file_to_publish} to {platform_to_publish}. URL: {result.url}"
                            )
                            published_count += 1
                        elif result:
                            console.print(
                                f"[bold red]Failed to publish to {platform_to_publish}:[/bold red] {result.message}"
                            )
                            logger.error(
                                f"Failed to publish {file_to_publish} to {platform_to_publish}: {result.message}"
                            )
                            failed_count += 1
                        else:
                            console.print(
                                f"[bold red]Error:[/bold red] Publisher for {platform_to_publish} did not return a result."
                            )
                            logger.error(
                                f"Publisher for {platform_to_publish} failed to return result."
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
