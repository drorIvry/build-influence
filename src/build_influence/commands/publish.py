import typer
from loguru import logger
from pathlib import Path
from rich.console import Console

from build_influence.config import config
from build_influence.publication import (
    get_publisher,
    PublicationContent,
    PublishResult,
)


def publish(
    ctx: typer.Context,  # Context might not be needed if config is imported directly
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
        # TODO: Add logic to extract title/tags from frontmatter if present
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

    # --- 3. Perform Publication (Config is passed directly now) ---
    publish_message = f"Publishing to [bold cyan]{platform}[/bold cyan]..."
    result: PublishResult | None = None
    with console.status(publish_message, spinner="dots"):
        try:
            # Pass the global config object
            logger.debug(f"Passing config to publisher: {config.get('platforms', {})}")
            result = publisher.publish(publication_content, config)
        except Exception as e:
            # Catch unexpected errors during the publish call itself
            msg = f"Unexpected error during publishing: {e}"
            console.print(f"\n:x: [bold red]Error:[/bold red] {msg}")
            logger.error(msg, exc_info=True)
            raise typer.Exit(code=1)

    # --- 4. Display Result ---
    if result:
        if result.success:
            success_msg = f"✅ Successfully published to {platform}!"
            if result.url:
                success_msg += f" URL: [link={result.url}]{result.url}[/link]"
            # Show message if no URL, but publication succeeded (e.g., Twitter)
            elif result.message:
                success_msg += f" ({result.message})"

            console.print(success_msg)
            pub_log_msg = f"Publication successful for {platform}."
            if result.url:
                pub_log_msg += f" URL: {result.url}"
            elif result.message:
                pub_log_msg += f" Message: {result.message}"
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


# Note: Removed the platform config loading section as the global `config` is now imported directly.
# The publisher's `publish` method is expected to handle accessing its specific config section.
