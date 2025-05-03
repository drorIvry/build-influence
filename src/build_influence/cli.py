import typer
from loguru import logger
from pathlib import Path

from build_influence.utils import setup_logging
from build_influence.config import config

# Import command functions
from .commands.analyze import analyze
from .commands.interview import interview
from .commands.generate import generate
from .commands.publish import publish
from .commands.logs import logs
from .commands.interactive_workflow import interactive_workflow

app = typer.Typer(
    name="build-influence",
    help="Analyzes code repositories and generates content.",
    no_args_is_help=False,
    invoke_without_command=True,
)

# --- Constants and Mappings --- #

ANALYSIS_FILENAME = "analysis_results.json"
INTERVIEW_LOG_FILENAME = "interview_log.json"

# --- Callback (Global Setup) --- #


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
        config.get("output_dirs", {}).get(
            "analysis",
            "output/analysis",
        ),
    )
    interview_dir = Path(
        config.get("output_dirs", {}).get("interviews", "output/interviews")
    )
    content_dir = Path(
        config.get("output_dirs", {}).get(
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

    # If no command is specified, run the interactive workflow
    if ctx.invoked_subcommand is None:
        logger.info("No subcommand invoked, starting interactive workflow.")
        # Manually invoke the interactive workflow command
        # Pass the context explicitly
        ctx.invoke(interactive_workflow, ctx=ctx)


# --- Register Commands --- #

app.command()(analyze)
app.command()(interview)
app.command()(generate)
app.command()(publish)
app.command()(logs)
app.command("run")(interactive_workflow)  # Register with alias


# Keep configure command placeholder here
@app.command()
def configure():
    """Configures application settings. (Not Implemented)"""
    typer.echo("Configuration logic (Not Implemented).")
    logger.info("Configure command executed (placeholder).")


# --- Main Execution --- #

if __name__ == "__main__":
    app()
