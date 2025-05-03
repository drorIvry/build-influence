import typer
from loguru import logger
import json
from pathlib import Path

from build_influence.interview import Interviewer


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
