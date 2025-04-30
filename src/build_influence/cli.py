import typer
from loguru import logger
import os
from typing_extensions import Annotated

from build_influence.utils import setup_logging

# Import config to ensure it's loaded early
from build_influence.config import config

app = typer.Typer()


@app.callback()
def callback():
    """Build Influence: Analyze code & generate content automatically."""
    # Setup logging as early as possible.
    # The setup_logging function reads config/env vars itself.
    setup_logging()
    logger.debug("CLI callback executed. Logging setup.")
    logger.debug(f"Config loaded. LLM model: {config.llm.model}")


# Type definitions for arguments/options for clarity and line length
RepoPath = Annotated[
    str, typer.Argument(help="Path to the local repository to analyze.")
]
AnalysisFile = Annotated[
    str | None, typer.Option(help="Path to pre-computed analysis data.")
]
ContentID = Annotated[str, typer.Argument(help="ID or path of the content to publish.")]
LogLines = Annotated[
    int, typer.Option("-n", "--lines", help="Number of log lines to show.")
]
LogFollow = Annotated[bool, typer.Option("-f", "--follow", help="Follow log output.")]


@app.command()
def analyze(repo_path: RepoPath):
    """Analyze a code repository."""
    logger.info(f"Analyzing repository at: {repo_path}")
    print(f"Analyzing repository: {repo_path}...")
    # TODO: Implement repository analysis logic
    print("Analysis complete (placeholder).")


@app.command()
def generate(analysis_file: AnalysisFile = None):
    """Generate content based on repository analysis."""
    if analysis_file:
        logger.info(f"Generating content from analysis file: {analysis_file}")
        print(f"Generating content from analysis file: {analysis_file}...")
    else:
        logger.info("Generating content (default analysis/settings)")
        print("Generating content...")
    # TODO: Implement content generation logic
    print("Content generation complete (placeholder).")


@app.command()
def publish(content_id: ContentID):
    """Publish generated content to specified platforms."""
    logger.info(f"Publishing content: {content_id}")
    print(f"Publishing content: {content_id}...")
    # TODO: Implement publication logic
    print("Publishing complete (placeholder).")


@app.command()
def configure():
    """Configure settings for Build Influence (interactive or file-based)."""
    logger.info("Entering configuration mode...")
    print("Config command (placeholder). This might open an editor or guide.")
    # TODO: Implement configuration logic
    config_file_path = config.get("_config_file", "Not loaded from file")
    print(f"Current config file: {config_file_path}")
    print(f"Log level: {config.logging.level}")


@app.command()
def logs(lines: LogLines = 20, follow: LogFollow = False):
    """Show the latest log entries."""
    log_file = config.logging.file
    logger.info(f"Showing logs from {log_file}. Lines: {lines}, Follow: {follow}")
    print(f"Showing last {lines} lines of {log_file}:")
    # Basic implementation: tail the log file
    try:
        if follow:
            # Note: Simple follow, may not be robust.
            print(f"Following {log_file}... Press Ctrl+C to stop.")
            with open(log_file, "r") as f:
                # Move to the end of the file
                f.seek(0, os.SEEK_END)
                while True:
                    line = f.readline()
                    if not line:
                        # No new line, wait briefly
                        typer.sleep(0.1)
                        continue
                    # Print the new line
                    print(line.strip())
        else:
            # Read last N lines (inefficient for huge files)
            with open(log_file, "r") as f:
                all_lines = f.readlines()
                for line in all_lines[-lines:]:
                    print(line.strip())
    except FileNotFoundError:
        print(f"Log file not found: {log_file}")
        logger.error(f"Log file not found: {log_file}")
    except Exception as e:
        print(f"Error reading log file: {e}")
        logger.exception("Error reading log file")


if __name__ == "__main__":
    app()
