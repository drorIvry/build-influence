from typing import Dict, Any, Optional
import litellm
import json
from loguru import logger

from build_influence.config import config

# Context Synthesis Limits
MAX_INSIGHTS_TO_INCLUDE = 15
MAX_CONTEXT_LENGTH = 4000
MAX_FEATURE_ID_TOKENS_OFFSET = 500

litellm.drop_params = True


class FeatureIdentifier:
    """Identifies high-level tech features using AI from analysis results."""

    def identify_features(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Synthesizes analysis data & uses LLM for high-level feature ID."""
        logger.info("Starting high-level feature identification...")

        synthesized_context = self._synthesize_context(analysis_result)
        if not synthesized_context:
            msg = "Could not synthesize context for feature ID. Skipping."
            logger.warning(msg)
            return {"error": "Could not synthesize context"}

        prompt = self._build_feature_prompt(synthesized_context)

        try:
            model = config.llm.model
            logger.debug(f"Sending context to LLM ({model}) for feature ID...")
            max_tokens = config.llm.max_tokens + MAX_FEATURE_ID_TOKENS_OFFSET

            logger.info(
                f"Using model: {model} to identify features",
            )

            response = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=config.llm.temperature,
                max_tokens=max_tokens,
                # api_key=config.llm.api_key,
            )

            ai_response_content = response.choices[0].message.content.strip()
            logger.debug("LLM feature ID response received.")
            logger.trace(f"Feature ID Raw Response: {ai_response_content!r}")

            # Robust JSON parsing
            try:
                # Strip markdown fences
                json_string = ai_response_content
                if json_string.startswith("```json"):
                    json_string = json_string[len("```json") :].strip()
                elif json_string.startswith("```"):
                    json_string = json_string[len("```") :].strip()
                if json_string.endswith("```"):
                    json_string = json_string[: -len("```")].strip()

                json_start = json_string.find("{")
                if json_start != -1:
                    parsed_json = json.loads(json_string[json_start:])
                else:
                    err = "No JSON object start found in feature ID response"
                    raise json.JSONDecodeError(err, json_string, 0)

                # Structure the output
                features = {
                    "identified_features": parsed_json.get("identified_features", []),
                    "architectural_patterns": parsed_json.get(
                        "architectural_patterns", []
                    ),
                    "target_audience": parsed_json.get("target_audience", "Unknown"),
                    "selling_points": parsed_json.get("selling_points", []),
                    "confidence_score": parsed_json.get("confidence_score", 0.5),
                }
                logger.info("Successfully identified high-level features.")
                return features

            except json.JSONDecodeError as json_e:
                err = f"Failed to decode feature ID JSON: {json_e}"
                logger.warning(err)
                logger.warning(f"LLM Raw text: {ai_response_content!r}")
                return {"error": err, "raw_response": ai_response_content}
            except Exception as parse_e:
                err = f"Error processing feature ID response: {parse_e}"
                logger.error(err, exc_info=True)
                return {"error": err, "raw_response": ai_response_content}

        except litellm.exceptions.APIError as api_e:
            logger.error(f"LiteLLM API error during feature ID: {api_e}")
            return {"error": f"AI API error: {api_e}"}
        except Exception as e:
            logger.exception("Unexpected error during feature identification.")
            return {"error": f"Unexpected error: {e}"}

    def _synthesize_context(self, analysis_result: Dict[str, Any]) -> Optional[str]:
        """Creates a concise text summary from the detailed analysis results."""
        context_parts = []
        repo_name = analysis_result.get("repo_name", "N/A")
        context_parts.append(f"Repo: {repo_name}")

        metadata = analysis_result.get("metadata", {})
        context_parts.append(f"Type: {metadata.get('type', 'N/A')}")

        important_insights = []
        files_processed = 0

        for file_info in analysis_result.get("file_tree", []):
            if files_processed >= MAX_INSIGHTS_TO_INCLUDE:
                break

            summary = None
            elements = None
            path = file_info.get("path", "?")

            if (insights := file_info.get("ai_doc_insights")) and not insights.get(
                "error"
            ):
                summary = insights.get("summary")
                if summary:
                    important_insights.append(f"- Doc ({path}): {summary}")
                    files_processed += 1
            elif (insights := file_info.get("ai_code_insights")) and not insights.get(
                "error"
            ):
                summary = insights.get("purpose")
                elements = insights.get("key_elements")
                # Shorten insight text slightly
                insight_text = (
                    f"- Code ({path}): {summary or 'N/A'}. Keys: {elements or 'N/A'}"
                )
                important_insights.append(insight_text[:200])  # Further limit length
                files_processed += 1

        if important_insights:
            context_parts.append("\nKey File Insights:")
            context_parts.extend(important_insights)
        else:
            context_parts.append("\nNo file summaries available.")

        synthesized = "\n".join(context_parts)
        if len(synthesized) > MAX_CONTEXT_LENGTH:
            logger.warning("Synthesized context too long, truncating.")
            synthesized = synthesized[:MAX_CONTEXT_LENGTH] + "... (truncated)"

        logger.debug(f"Synthesized context length: {len(synthesized)} chars")
        logger.trace(f"Synthesized Context:\n{synthesized}")
        return synthesized

    def _build_feature_prompt(self, context: str) -> str:
        """Builds the prompt for the LLM to identify high-level features."""
        prompt_header = "Analyze the context. Respond ONLY with JSON identifying:"
        prompt_fields = ' "identified_features" (list[str]), '
        prompt_fields += ' "architectural_patterns" (list[str]), '
        prompt_fields += ' "target_audience" (str), '
        prompt_fields += ' "selling_points" (list[str]), '
        prompt_fields += ' "confidence_score" (float 0.0-1.0).'

        prompt = f"""
Context:
{context}

{prompt_header}
{prompt_fields}
JSON Output:"""
        return prompt


# Example usage (can be removed later)
if __name__ == "__main__":
    from build_influence.utils import setup_logging

    setup_logging()  # Setup logging first

    # Create dummy analysis results for testing
    dummy_analysis = {
        "repo_name": "Dummy Project",
        "repo_path": "/fake/path/dummy_project",
        "metadata": {"type": "git", "current_branch": "main"},
        "file_tree": [
            {
                "path": "README.md",
                "type": "documentation",
                "ai_doc_insights": {
                    "summary": "This project does X and Y.",
                    "features": ["Feature A", "Feature B"],
                },
            },
            {
                "path": "src/main.py",
                "type": "code",
                "ai_code_insights": {
                    "purpose": "Main entry point, sets up server.",
                    "key_elements": ["main", "setup_server"],
                    "dependencies": ["flask", "os"],
                },
            },
            {
                "path": "src/utils.py",
                "type": "code",
                "ai_code_insights": {
                    "purpose": "Utility functions for data processing.",
                    "key_elements": ["process_data"],
                    "dependencies": ["pandas"],
                    "interesting_aspects": ["Uses numpy optimization"],
                },
            },
            {"path": "config.yaml", "type": "configuration"},
        ],
        "files_analyzed_count": 3,
    }

    identifier = FeatureIdentifier()
    features = identifier.identify_features(dummy_analysis)

    print("\n--- Identified High-Level Features ---")
    print(json.dumps(features, indent=2))
