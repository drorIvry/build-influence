import typer
from loguru import logger
import os
import time
from pathlib import Path


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
                # Go to the end of the file
                f.seek(0, os.SEEK_END)
                # Start tailing
                while True:
                    line = f.readline()
                    if not line:
                        time.sleep(0.1)  # Sleep briefly
                        continue
                    typer.echo(line.strip())  # Print the line
        else:
            typer.echo(f"Showing last {lines} lines from {log_file_path}:")
            with open(log_file_path, "r") as f:
                log_lines = f.readlines()
                for line in log_lines[-lines:]:
                    typer.echo(line.strip())
    except FileNotFoundError:
        # This case might be redundant due to the initial check, but good practice
        typer.secho(f"Log file not found: {log_file_path}", fg=typer.colors.RED)
    except KeyboardInterrupt:
        typer.echo("\nStopped following log.")
    except Exception as e:
        typer.secho(f"Error reading log file: {e}", fg=typer.colors.RED)
        logger.error(f"Error reading log file {log_file_path}: {e}", exc_info=True)
        # Consider exiting with error code
