import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
import litellm
import json
from tqdm import tqdm

from loguru import logger

from build_influence.config import config
from build_influence.analysis.feature_identifier import FeatureIdentifier

litellm.drop_params = True
# Constants
MAX_FILE_SIZE_BYTES = 500 * 1024  # Limit file size (e.g., 500KB)


class RepositoryAnalyzer:
    """Analyzes a local code repository, using AI for code & doc insights."""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()
        if not self.repo_path.is_dir():
            err_msg = f"Repo path invalid or not a dir: {self.repo_path}"
            logger.error(err_msg)
            raise ValueError(f"Invalid repository path: {self.repo_path}")

        self.repo_name = self.repo_path.name
        self.excluded_dirs = set(config.analysis.excluded_dirs)
        self.excluded_files = set(config.analysis.excluded_files)
        self.max_files_to_analyze = config.analysis.max_files_to_parse
        self.files_analyzed_count = 0

        logger.info(f"Initialized RepositoryAnalyzer for: {self.repo_path}")
        logger.debug(f"Excluded dirs: {self.excluded_dirs}")
        logger.debug(f"Excluded files: {self.excluded_files}")
        logger.debug(f"Max files to analyze: {self.max_files_to_analyze}")

    def _is_excluded(self, path: Path) -> bool:
        """Check if a file or directory should be excluded."""
        if path.name in self.excluded_files:
            return True
        # Check if any part of the path is an excluded directory name
        try:
            relative_parts = path.relative_to(self.repo_path).parts
            for part in relative_parts:
                if part in self.excluded_dirs:
                    return True
        except ValueError:
            # Path is not relative to repo_path (shouldn't happen with rglob)
            logger.warning(
                f"Path {path} not relative to {self.repo_path}, cannot check."
            )
            return False  # Treat as not excluded
        return False

    def analyze(self) -> Dict[str, Any]:
        """Perform the full analysis including high-level feature ID."""
        logger.info(f"Starting analysis for {self.repo_name}...")
        self.files_analyzed_count = 0

        metadata = self._extract_metadata()
        file_tree = self._build_file_tree()

        # --- AI File Analysis Step (Code & Docs) ---
        max_files = self.max_files_to_analyze
        files_to_process = [
            f for f in file_tree if f["type"] in ("code", "documentation")
        ][:max_files]
        num_files_for_ai = len(files_to_process)
        logger.info(f"AI file analysis: {num_files_for_ai} files ")
        logger.info(f"(limit: {max_files}).")

        file_info_map = {info["absolute_path"]: info for info in file_tree}
        progress_desc = "AI File Analysis"
        for file_to_analyze in tqdm(
            files_to_process,
            desc=progress_desc,
            total=num_files_for_ai,
            unit="file",
        ):
            abs_path_str = file_to_analyze["absolute_path"]
            file_info = file_info_map.get(abs_path_str)
            if not file_info:
                logger.warning(f"Info missing for {abs_path_str} ")
                logger.warning("in AI loop.")
                continue
            if self.files_analyzed_count >= max_files:
                break

            file_type = file_info["type"]
            abs_path = Path(abs_path_str)
            file_rel_path = file_info["path"]
            analysis_func = None
            result_key = None
            if file_type == "code":
                analysis_func = self._analyze_code_file_with_ai
                result_key = "ai_code_insights"
            elif file_type == "documentation":
                analysis_func = self._analyze_doc_file_with_ai
                result_key = "ai_doc_insights"

            if analysis_func and result_key:
                try:
                    insights = analysis_func(abs_path)
                    file_info[result_key] = insights
                    self.files_analyzed_count += 1
                except Exception as e:
                    logger.error(f"AI analysis failed for {file_rel_path}:")
                    logger.error(f"{e}")
                    file_info[result_key] = {"error": str(e)}
        # -----------------------------------------
        logger.info("AI file analysis complete.")
        logger.info(f"Analyzed {self.files_analyzed_count} files.")

        # --- High-Level Feature Identification Step ---
        interim_result = {
            "repo_name": self.repo_name,
            "repo_path": str(self.repo_path),
            "metadata": metadata,
            "file_tree": file_tree,
            "files_analyzed_count": self.files_analyzed_count,
        }
        logger.info("Starting high-level feature identification...")
        feature_identifier = FeatureIdentifier()
        high_level_features = feature_identifier.identify_features(interim_result)
        logger.info("Completed high-level feature identification.")
        # --------------------------------------------

        # --- Final Result ---
        final_analysis_result: Dict[str, Any] = {
            **interim_result,
            "high_level_features": high_level_features,
        }

        logger.info(f"Analysis complete for {self.repo_name}.")
        return final_analysis_result

    def _extract_metadata(self) -> Dict[str, Any]:
        """Extract basic metadata (e.g., git info)."""
        logger.debug("Extracting repository metadata...")
        metadata = {"type": "unknown", "branches": [], "current_branch": None}

        # Try to detect git repository
        git_dir = self.repo_path / ".git"
        if git_dir.exists() and git_dir.is_dir():
            metadata["type"] = "git"
            try:
                # Get current branch
                cmd = ["git", "rev-parse", "--abbrev-ref", "HEAD"]
                result = subprocess.run(
                    cmd,
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                metadata["current_branch"] = result.stdout.strip()
                logger.debug(f"Git branch: {metadata['current_branch']}")

                # Get all branches
                cmd = ["git", "branch"]
                result = subprocess.run(
                    cmd,
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                branches = [b.strip().lstrip("* ") for b in result.stdout.splitlines()]
                metadata["branches"] = branches
                logger.debug(f"Git branches: {branches}")

            except subprocess.CalledProcessError as e:
                cmd_str = " ".join(getattr(e, "cmd", "?"))
                logger.warning(f"Git command failed ('{cmd_str}'): {e}")
            except FileNotFoundError:
                logger.warning("git command not found. Cannot extract git metadata.")
        else:
            logger.info("Not a git repository or .git not found.")

        # TODO: Extract description (e.g., from README)
        return metadata

    def _build_file_tree(self) -> List[Dict[str, Any]]:
        """Scan directory structure and build a list of files to consider."""
        logger.debug("Building file tree...")
        file_tree: List[Dict[str, Any]] = []
        potential_files_count = 0

        try:
            for item in self.repo_path.rglob("*"):
                potential_files_count += 1
                if not item.is_file() or self._is_excluded(item):
                    continue

                try:
                    relative_path = item.relative_to(self.repo_path)
                    file_info: Dict[str, Any] = {
                        "path": str(relative_path),
                        "absolute_path": str(item),
                        "size": item.stat().st_size,
                        "type": self._categorize_file(item),
                    }
                    file_tree.append(file_info)
                except ValueError:
                    logger.warning(f"Skipping file outside base path: {item}")
                except Exception as e:
                    logger.warning(f"Could not process file {item}: {e}")

        except Exception as e:
            logger.error(f"Error during file tree build: {e}", exc_info=True)

        file_count = len(file_tree)
        logger.info(
            f"Scanned {potential_files_count} items. "
            f"Found {file_count} relevant files."
        )
        # The actual limit is applied during the AI analysis step
        return file_tree

    def _categorize_file(self, file_path: Path) -> str:
        """Categorize a file based on its extension or name."""
        ext = file_path.suffix.lower()
        name = file_path.name.lower()
        code_ext = {
            ".py",
            ".js",
            ".ts",
            ".java",
            ".c",
            ".cpp",
            ".h",
            ".cs",
            ".go",
            ".rb",
            ".php",
            ".swift",
            ".kt",
            ".rs",
        }
        doc_ext = {".md", ".rst", ".txt"}
        cfg_ext = {".yaml", ".yml", ".json", ".xml", ".toml", ".ini", ".cfg"}
        data_ext = {".csv", ".xls", ".xlsx", ".db", ".sqlite"}
        img_ext = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".bmp", ".ico"}
        cfg_names = {"config", "settings", ".env", "dockerfile", "makefile"}
        license_names = {"license", "copying"}
        if ext in code_ext:
            return "code"
        if ext in doc_ext or name == "readme":
            return "documentation"
        if ext in cfg_ext or name in cfg_names:
            return "configuration"
        if ext in data_ext:
            return "data"
        if ext in img_ext:
            return "image"
        if name in license_names:
            return "license"
        logger.trace(f"Categorizing '{name}' as 'other'")
        return "other"

    def _analyze_file_content_with_ai(
        self,
        file_path: Path,
        prompt_template: str,
    ) -> Dict[str, Any]:
        """
        Generic helper to analyze file content using LiteLLM with a specific
        prompt.
        """
        insights: Dict[str, Any] = {"error": None}
        file_name = file_path.name

        try:
            if file_path.stat().st_size > MAX_FILE_SIZE_BYTES:
                kb_size = MAX_FILE_SIZE_BYTES // 1024
                logger.warning(f"Skipping large file: {file_name} (> {kb_size}KB)")
                insights["error"] = "File too large for AI analysis"
                return insights

            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                logger.warning(f"UTF-8 decode failed for {file_name}, trying default.")
                try:
                    content = file_path.read_text()
                except Exception as read_err:
                    err_msg = f"Failed to read file: {read_err}"
                    logger.error(f"{err_msg} ({file_name})")
                    insights["error"] = err_msg
                    return insights
            except Exception as read_err:
                err_msg = f"Failed to read file: {read_err}"
                logger.error(f"{err_msg} ({file_name})")
                insights["error"] = err_msg
                return insights

            if not content.strip():
                logger.debug(f"Skipping empty file: {file_name}")
                insights["error"] = "Empty file"
                return insights

            # --- Prepare the Prompt ---
            prompt = prompt_template.format(
                file_name=file_name,
                content=content,
            )
            messages = [
                {
                    "role": "user",
                    "content": prompt,
                },
            ]

            # --- Call LiteLLM ---
            # Use the analysis-specific model, falling back to the general LLM model
            analysis_model = config.analysis.get("model", config.llm.model)
            # Assuming provider is consistent
            llm_provider = config.llm.get("provider")
            model_string = (
                f"{llm_provider}/{analysis_model}" if llm_provider else analysis_model
            )

            logger.info(f"Using model: {model_string} to analyze {file_name}")
            # logger.debug(f"Sending {file_name} to LLM ({model_string})...")
            response = litellm.completion(
                model=model_string,
                messages=messages,
                # Keep general temp/tokens for now
                temperature=config.llm.temperature,
                max_tokens=config.llm.max_tokens,
            )

            # --- Process Response ---
            ai_response_content = response.choices[0].message.content
            # logger.debug(f"LLM response received for {file_name}.")
            # Too verbose

            try:
                json_start = ai_response_content.find("{")
                if json_start == -1:
                    json_start = ai_response_content.find("[")  # Try array
                    if json_start == -1:
                        err = "No JSON object/array found in AI response"
                        logger.warning(f"{err} for {file_name}")
                        raise json.JSONDecodeError(err, ai_response_content, 0)

                parsed_json = json.loads(ai_response_content[json_start:])

                # Return the parsed JSON directly
                insights = parsed_json
                # logger.debug(f"Parsed AI insights for {file_name}")
                # Too verbose

            except json.JSONDecodeError as json_e:
                err = f"Failed to decode AI JSON response: {json_e}"
                logger.warning(f"{err} for {file_name}")
                logger.warning(f"LLM Raw text was: {ai_response_content}")
                insights = {"error": err, "raw_response": ai_response_content}
            except Exception as parse_e:
                err = f"Error processing AI response: {parse_e}"
                logger.error(f"{err} for {file_name}")
                insights = {"error": err, "raw_response": ai_response_content}

        except litellm.exceptions.APIError as api_e:
            logger.error(f"LiteLLM API error for {file_name}: {api_e}")
            insights = {"error": f"AI API error: {api_e}"}
        except Exception as e:
            logger.exception(f"Unexpected AI analysis error for {file_name}")
            insights = {"error": f"Unexpected error: {e}"}

        return insights

    def _analyze_code_file_with_ai(self, file_path: Path) -> Dict[str, Any]:
        """Prepares prompt and calls generic AI analyzer for code files."""
        prompt_template = (
            "Analyze code file `{file_name}`. Respond ONLY with JSON: "
            '{{"purpose": "<summary>", "key_elements": ["func1", "ClassA"], '
            '"dependencies": ["import os"], "interesting_aspects": '
            '["uses xyz pattern"]}}. '
            "Use lists/null if empty. "
            "```\n{content}\n``` JSON Output:"
        )

        raw_insights = self._analyze_file_content_with_ai(file_path, prompt_template)

        # --- Debugging Log ---
        # logger.debug(
        #    f"Code file {file_path.name}: "
        #    f"Raw insights type: {type(raw_insights)}"
        # )
        # if isinstance(raw_insights, dict):
        #     logger.debug(
        #        f"Code file {file_path.name}: Raw insights keys: "
        #        f"{list(raw_insights.keys())}"
        #     )
        # ---------------------

        # Extract expected keys or return error
        if isinstance(raw_insights, dict) and raw_insights.get("error"):
            return raw_insights  # Return error dict as is
        elif isinstance(raw_insights, dict):
            try:
                # --- Detailed Extraction Logging ---
                # logger.debug(
                #    f"Attempting code key extraction from: {raw_insights!r}"
                # )
                purpose: Optional[str] = raw_insights.get("purpose")
                # logger.debug(f"Code Purpose extracted: {purpose!r}")
                elements: Optional[List[str]] = raw_insights.get("key_elements", [])
                # logger.debug(f"Code Elements extracted: {elements!r}")
                dependencies: Optional[List[str]] = raw_insights.get("dependencies", [])
                # logger.debug(
                #    f"Code Dependencies extracted: {dependencies!r}"
                # )
                aspects: Optional[List[str]] = raw_insights.get(
                    "interesting_aspects", []
                )
                # logger.debug(f"Code Aspects extracted: {aspects!r}")
                # --- End Detailed Logging ---

                return {
                    "purpose": purpose,
                    "key_elements": elements,
                    "dependencies": dependencies,
                    "interesting_aspects": aspects,
                }
            except Exception as e:
                logger.error(
                    f"Exception during code key extraction for "
                    f"{file_path.name}: {e!r}"
                )
                logger.error(f"Problematic code raw_insights: {raw_insights!r}")
                return {"error": f"Internal error processing AI code response: {e!r}"}
        else:
            logger.warning(
                f"Unexpected AI format for code {file_path.name}: "
                f"{type(raw_insights)}"
            )
            return {"error": "Unexpected AI response format"}

    def _analyze_doc_file_with_ai(self, file_path: Path) -> Dict[str, Any]:
        prompt_template = (
            "Analyze doc file `{file_name}`. Respond ONLY with JSON: "
            "{{'summary': '<purpose>', 'features': ['feat1'], "
            "'setup_steps': ['step1'], 'usage_examples': ['example1']}}. "
            "Use lists/null if empty. "
            "```\n{content}\n``` JSON Output:"
        )

        raw_insights = self._analyze_file_content_with_ai(
            file_path,
            prompt_template,
        )

        if isinstance(raw_insights, dict) and raw_insights.get("error"):
            return raw_insights  # Return error dict as is
        elif isinstance(raw_insights, dict):
            try:
                summary: Optional[str] = raw_insights.get("summary")
                features: Optional[List[str]] = raw_insights.get("features", [])
                setup_steps: Optional[List[str]] = raw_insights.get("setup_steps", [])
                usage_examples: Optional[List[str]] = raw_insights.get(
                    "usage_examples", []
                )

                return {
                    "summary": summary,
                    "features": features,
                    "setup_steps": setup_steps,
                    "usage_examples": usage_examples,
                }
            except Exception as e:
                logger.error(
                    f"Exception during doc key extraction for "
                    f"{file_path.name}: {e!r}"
                )
                logger.error(f"Problematic doc raw_insights: {raw_insights!r}")
                return {"error": f"Internal error processing AI doc response: {e!r}"}
        else:
            logger.warning(
                f"Unexpected AI format for doc {file_path.name}: "
                f"{type(raw_insights)}"
            )
            return {"error": "Unexpected AI response format"}


# Example usage (can be removed later)
if __name__ == "__main__":
    from build_influence.utils import setup_logging

    setup_logging()  # Setup logging first

    try:
        repo_to_analyze = "."
        analyzer = RepositoryAnalyzer(repo_to_analyze)
        result = analyzer.analyze()

        print("\n--- Analysis Result ---")
        print(f"Repo Name: {result['repo_name']}")
        print(f"Repo Path: {result['repo_path']}")
        print(f"Metadata: {result['metadata']}")
        print(f"AI Files Analyzed: {result['files_analyzed_count']}")
        print(
            f"Total Files in Tree: {len(result['file_tree'])} "
            f"(limit: {analyzer.max_files_to_analyze})"
        )

        # Print first few files with AI insights if available
        for i, file_info in enumerate(result["file_tree"][:5]):
            print(
                f"\n  File {i + 1}: {file_info['path']} "
                f"({file_info['type']}, {file_info['size']}b)"
            )
            insights = None
            if "ai_code_insights" in file_info:
                insights = file_info["ai_code_insights"]
                print("    [Code Insights]")
                if insights.get("error"):
                    print(f"      Error: {insights['error']}")
                else:
                    print(f"      Purpose: {insights.get('purpose', 'N/A')}")
                    print(f"      Elements: " f"{insights.get('key_elements', [])}")
            elif "ai_doc_insights" in file_info:
                insights = file_info["ai_doc_insights"]
                print("    [Doc Insights]")
                if insights.get("error"):
                    print(f"      Error: {insights['error']}")
                else:
                    print(f"      Summary: {insights.get('summary', 'N/A')}")
                    print(f"      Features: {insights.get('features', [])}")
                    # print(f"      Setup: {insights.get('setup_steps', [])}")
                    # print(
                    #    f"      Usage: {insights.get('usage_examples', [])}"
                    # )

        if len(result["file_tree"]) > 5:
            print("\n  ...")

    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        logger.exception("An unexpected error occurred during analysis example.")
        print(f"An unexpected error occurred: {e}")
