from loguru import logger
from typing import Dict, Optional

from .base_generator import BaseContentGenerator


class MarkdownGenerator(BaseContentGenerator):
    """Generates content in Markdown format."""

    FILE_EXTENSION = "md"

    def _build_prompt(
        self,
        content_type: str,
        context_override: Optional[Dict] = None,
    ) -> str:
        """
        Constructs the prompt for the LLM to generate Markdown content.

        Args:
            content_type: The type of content (e.g., \
                'announcement', 'deepdive').
            context_override: Optional additional context to include.

        Returns:
            The fully constructed prompt string.
        """
        logger.debug(f"Building Markdown prompt for content_type='{content_type}'")

        # --- Prepare Context Sections ---
        # High-level features
        features = self.high_level_features.get("identified_features", [])
        features_str = "\n- ".join(f for f in features if f) if features else "N/A"

        # Analysis Summary (Example: File counts by type)
        file_tree = self.analysis_results.get("file_tree", [])
        code_files = sum(1 for f in file_tree if f.get("type") == "code")
        doc_files = sum(1 for f in file_tree if f.get("type") == "documentation")
        config_files = sum(1 for f in file_tree if f.get("type") == "configuration")
        analysis_summary = (
            f"- Code Files: {code_files}\n"
            f"- Documentation Files: {doc_files}\n"
            f"- Configuration Files: {config_files}"
        )

        # Interview Context
        interview_context_str = "N/A"
        if self.interview_data:
            interview_context_str = "\n".join(
                [
                    f"Q: {item['question']}\nA: {item['answer']}\n---\n"
                    for item in self.interview_data
                ]
            )

        # README Content
        readme_str = self.readme_content if self.readme_content else "N/A"
        # Truncate README if too long to avoid excessive prompt length
        max_readme_len = 1500
        if len(readme_str) > max_readme_len:
            readme_str = readme_str[:max_readme_len] + "... (truncated)"

        # --- Construct Prompt ---
        prompt = f"""
        **Goal:** Generate a draft '{content_type}' post in MARKDOWN format for the project '{self.repo_name}'.

        **Audience:** (You can infer this, e.g., other developers, potential users)

        **Key Information about '{self.repo_name}':**

        *High-Level Features:*
        {features_str}

        *Repository Analysis Summary:*
        {analysis_summary}

        *Developer Interview Context:*
        {interview_context_str}

        *Project README:*
        ```
        {readme_str}
        ```

        **Instructions:**
        1. Synthesize the provided information.
        2. Write a compelling '{content_type}' post in well-formatted Markdown.
        3. Ensure the tone is appropriate for the target audience and platform
           (general technical audience for Markdown).
        4. If generating a 'deepdive', elaborate on technical aspects. If
           'announcement', focus on highlights and purpose.
        5. Make sure the output is only the Markdown content, without any preamble
           or explanation.

        **Generated Markdown Post:**
        """.strip()

        logger.trace(f"Generated Markdown Prompt:\n{prompt}")
        return prompt

    def generate(
        self,
        content_type: str,
        context_override: Optional[Dict] = None,
    ) -> Optional[str]:
        """
        Generates Markdown content for a specific content type.

        Args:
            content_type: The type of content (e.g., 'announcement', 'deepdive').
            context_override: Optional additional context to include.

        Returns:
            The generated Markdown content as a string, or None if generation failed.
        """
        logger.info(
            f"Generating Markdown content for {content_type=} "
            f"for repo '{self.repo_name}'"
        )
        prompt = self._build_prompt(content_type, context_override)
        generated_content = self._call_llm(prompt)

        if generated_content:
            logger.info(f"Successfully generated Markdown content for {content_type}.")
            # TODO: Add Markdown specific post-processing/validation?
            return generated_content
        else:
            logger.error(f"Failed to generate Markdown content for {content_type}.")
            return None
