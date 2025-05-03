import typer
from loguru import logger
import json
from pathlib import Path

from build_influence.analysis import RepositoryAnalyzer


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
    analysis_dir: Path = ctx.obj["ANALYSIS_DIR"]
    # Construct analysis file path using repo name
    safe_repo_name = "".join(c if c.isalnum() else "_" for c in repo_path.name)

    analysis_file_path = analysis_dir / f"{safe_repo_name}_analysis.json"
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
