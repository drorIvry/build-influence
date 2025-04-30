import typer
from loguru import logger
import os
from typing_extensions import Annotated
import json

from build_influence.utils import setup_logging

# Import config to ensure it's loaded early
from build_influence.config import config
from build_influence.analysis import RepositoryAnalyzer

app = typer.Typer()


@app.callback()
def callback():
    """Build Influence: Analyze code & docs using AI, generate content."""
    # Setup logging as early as possible.
    # The setup_logging function reads config/env vars itself.
    setup_logging()
    logger.debug("CLI callback executed. Logging setup.")
    logger.debug(f"Config loaded. LLM model: {config.llm.model}")


# Type definitions for arguments/options for clarity and line length
RepoPath = Annotated[str, typer.Argument(help="Path to the local repository.")]
AnalysisFile = Annotated[
    str | None, typer.Option(help="Path to pre-computed analysis data.")
]
ContentID = Annotated[str, typer.Argument(help="ID or path of content to publish.")]
LogLines = Annotated[int, typer.Option("-n", "--lines", help="Num log lines.")]
LogFollow = Annotated[bool, typer.Option("-f", "--follow", help="Follow log output.")]
OutputJson = Annotated[
    str | None, typer.Option("--output", "-o", help="Save analysis JSON to path.")
]


@app.command()
def analyze(repo_path: RepoPath, output_file: OutputJson = None):
    """Analyze a code repository using AI for code & doc insights."""
    logger.info(f"Analyzing repository at: {repo_path}")
    print(f"Analyzing repository: {repo_path}... (AI analysis may take time)")

    try:
        analyzer = RepositoryAnalyzer(repo_path)
        result = analyzer.analyze()

        print("\n--- Analysis Summary ---")
        print(f"Repo Name: {result['repo_name']}")
        print(f"Metadata Type: {result['metadata'].get('type', 'unknown')}")
        ai_analyzed_count = result.get("files_analyzed_count", 0)
        tree_count = len(result.get("file_tree", []))
        print(f"Files in Tree: {tree_count} (Potential)")
        print(f"AI Files Analyzed: {ai_analyzed_count} (Code/Docs, up to limit)")

        if output_file:
            logger.info(f"Saving analysis result to: {output_file}")
            try:
                with open(output_file, "w") as f:
                    # Use default=str for potential non-serializable types like Path
                    json.dump(result, f, indent=2, default=str)
                print(f"Analysis result saved to {output_file}")
            except Exception as e:
                err_msg = f"Failed to save results to {output_file}"
                logger.error(f"{err_msg}: {e}")
                print(f"Error: {err_msg}")
        else:
            # Optionally print AI insights for first few files if not saving
            print("\n--- AI Insight Snippets (First 5 Files) ---")
            files_shown = 0
            for file_info in result.get("file_tree", []):
                if files_shown >= 5:
                    break

                insights = None
                insight_type = None
                if file_info.get("ai_code_insights"):
                    insights = file_info["ai_code_insights"]
                    insight_type = "Code"
                elif file_info.get("ai_doc_insights"):
                    insights = file_info["ai_doc_insights"]
                    insight_type = "Doc"

                if insights:
                    rel_path = file_info["path"]
                    print(f"\n  File: {rel_path} ([{insight_type} Insights])")
                    if insights.get("error"):
                        print(f"    Error: {insights['error']}")
                    else:
                        # Print common fields or type-specific fields
                        if insight_type == "Code":
                            print(f"    Purpose: {insights.get('purpose', 'N/A')}")
                            elements = insights.get("key_elements", [])
                            print(f"    Elements: {elements}")
                        elif insight_type == "Doc":
                            print(f"    Summary: {insights.get('summary', 'N/A')}")
                            features = insights.get("features", [])
                            print(f"    Features: {features}")
                        else:  # Fallback for unexpected types
                            print(f"    Insights: {insights}")
                    files_shown += 1

            if files_shown == 0:
                print("  (No successful AI insights found/analyzed)")
            elif len(result.get("file_tree", [])) > files_shown:
                # Check if there were more files than shown, even if some had no insights
                print("\n  ...")

        print("\nAnalysis complete.")

    except ValueError as e:
        # Handle invalid repo path error from analyzer init
        logger.error(f"Analysis failed: {e}")
        print(f"Error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.exception("An unexpected error occurred during analysis.")
        print(f"An unexpected error occurred during analysis: {e}")
        raise typer.Exit(code=1)


@app.command()
def generate(analysis_file: AnalysisFile = None):
    """Generate content based on repository analysis."""
    if analysis_file:
        logger.info(f"Generating content from analysis file: {analysis_file}")
        print(f"Generating content from analysis file: {analysis_file}...")
        # TODO: Load analysis data from file
    else:
        logger.info("Generating content (requires prior analysis)")
        print("Generating content... (requires prior analysis)")
        # TODO: Potentially run analysis first or use cached results

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
    logger.info(f"Showing logs from {log_file}. Lines={lines}, Follow={follow}")
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
