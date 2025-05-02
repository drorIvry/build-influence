import typer
from loguru import logger
import os
import json
from pathlib import Path
import time

from build_influence.utils import setup_logging
from build_influence.config import config
from build_influence.analysis import RepositoryAnalyzer
from build_influence.interview import Interviewer

app = typer.Typer(
    name="build-influence",
    help="Analyzes code repositories and generates content.",
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
    setup_logging()
    logger.info("Build Influence CLI started.")
    logger.info(f"Using configuration from: {config_file}")
    ctx.ensure_object(dict)
    analysis_output = config.get("analysis", {}).get(
        "output_file",
        ANALYSIS_FILENAME,
    )
    interview_output = config.get("interview", {}).get(
        "log_file",
        INTERVIEW_LOG_FILENAME,
    )
    ctx.obj["ANALYSIS_FILE"] = Path(analysis_output)
    ctx.obj["INTERVIEW_LOG_FILE"] = Path(interview_output)


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
        False, "--force", "-f", help="Force re-analysis even if results file exists."
    ),
):
    """Analyzes a code repository and saves the results."""
    analysis_file_path: Path = ctx.obj["ANALYSIS_FILE"]
    logger.info(f"Starting analysis for repository: {repo_path}")

    if analysis_file_path.exists() and not force:
        typer.secho(
            f"Analysis file '{analysis_file_path}' exists.", fg=typer.colors.YELLOW
        )
        typer.echo("Use --force to overwrite.")
        logger.warning("Analysis skipped: File exists and --force not used.")
        return

    # Pass repo_path as string to analyzer if it expects str
    analyzer = RepositoryAnalyzer(str(repo_path))
    try:
        analysis_results = analyzer.analyze()
        analysis_file_path.parent.mkdir(parents=True, exist_ok=True)
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
def interview(ctx: typer.Context):
    """Starts an interactive interview based on analysis results."""
    analysis_file_path: Path = ctx.obj["ANALYSIS_FILE"]
    interview_log_file: Path = ctx.obj["INTERVIEW_LOG_FILE"]

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
def generate():
    """Generates content based on analysis. (Not Implemented)"""
    typer.echo("Content generation logic (Not Implemented).")
    logger.info("Generate command executed (placeholder).")


@app.command()
def publish():
    """Publishes content to platforms. (Not Implemented)"""
    typer.echo("Publication logic (Not Implemented).")
    logger.info("Publish command executed (placeholder).")


@app.command()
def configure():
    """Configures application settings. (Not Implemented)"""
    typer.echo("Configuration logic (Not Implemented).")
    logger.info("Configure command executed (placeholder).")


@app.command()
def logs(
    lines: int = typer.Option(10, "--lines", "-n", help="Number of log lines to show."),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output."),
):
    """Displays the application log file."""
    try:
        log_file_str = config.logging.file_path
        log_file = Path(log_file_str)
    except AttributeError:
        typer.secho("Log file path not configured correctly.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if not log_file.exists():
        typer.secho(f"Log file not found: {log_file}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    try:
        if follow:
            typer.echo(f"Following log: {log_file} (Ctrl+C to exit)")
            with open(log_file, "r") as f:
                f.seek(0, os.SEEK_END)
                while True:
                    line = f.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    typer.echo(line.strip())
        else:
            with open(log_file, "r") as f:
                log_lines = f.readlines()
                for line in log_lines[-lines:]:
                    typer.echo(line.strip())
    except FileNotFoundError:
        typer.secho(f"Log file not found: {log_file}", fg=typer.colors.RED)
    except KeyboardInterrupt:
        typer.echo("\nStopped following log.")
    except Exception as e:
        typer.secho(f"Error reading log file: {e}", fg=typer.colors.RED)


if __name__ == "__main__":
    app()
