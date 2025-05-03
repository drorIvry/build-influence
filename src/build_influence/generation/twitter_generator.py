from loguru import logger
from typing import Dict, Optional

from .base_generator import BaseContentGenerator


class TwitterGenerator(BaseContentGenerator):
    """Generates content suitable for Twitter (X)."""

    def _build_prompt(
        self,
        content_type: str,
        context_override: Optional[Dict] = None,
    ) -> str:
        """
        Constructs the prompt for generating Twitter content.
        """
        logger.debug(f"Building Twitter prompt for content_type='{content_type}'")

        # --- Prepare Context Sections (Concise) ---
        features = self.high_level_features.get("identified_features", [])
        # Use comma separation for brevity
        features_str = (
            ", ".join(f for f in features if f) if features else "key features"
        )

        # Keep analysis summary very brief
        analysis_summary = (
            f"{len(self.analysis_results.get('file_tree', []))} total files analyzed."
        )

        # Interview Context - maybe just key points?
        interview_summary = "N/A"
        if self.interview_data:
            # Example: just take first answer if available
            first_answer = self.interview_data[0].get("answer")
            if first_answer:
                # Truncate interview answer
                interview_summary = f"Key takeaway: {first_answer[:100]}..."

        # README - Extremely truncated or just presence
        readme_summary = "Not found"
        if self.readme_content:
            readme_summary = self.readme_content[:150] + "... (truncated)"

        # --- Construct Twitter Prompt ---
        prompt = f"""
**Goal:** Generate a short Tweet ('{content_type}') for the project '{self.repo_name}'. Output MUST be 280 characters or less.

**Platform:** Twitter/X (Concise, engaging, use relevant hashtags)

**Key Information about '{self.repo_name}':**
- Features: {features_str}
- Analysis: {analysis_summary}
- Context: {interview_summary}
- README Snippet: {readme_summary}

**Instructions:**
1. Create a concise and engaging Tweet based on the key info.
2. Adhere strictly to the 280-character limit.
3. Include 1-3 relevant hashtags (e.g., #OpenSource, #DevTool, #Python).
4. If '{content_type}' is 'announcement', focus on the most exciting update.
5. Output *only* the Tweet text.

**Generated Tweet:**
"""

        logger.trace(f"Generated Twitter Prompt:\n{prompt}")
        return prompt

    def generate(
        self,
        content_type: str,
        context_override: Optional[Dict] = None,
    ) -> Optional[str]:
        """
        Generates Twitter content, ensuring length constraints.
        """
        logger.info(
            f"Generating Twitter content for {content_type=} for '{self.repo_name}'"
        )
        prompt = self._build_prompt(content_type, context_override)
        # Use lower max_tokens for Twitter
        generated_content = self._call_llm(
            prompt,
            max_tokens=1500,
            temperature=0.6,
        )

        if generated_content:
            # Basic length validation
            max_len = 280
            if len(generated_content) > max_len:
                logger.warning(
                    f"Generated Twitter content exceeds {max_len} chars. \
                    Truncating... ({len(generated_content)} chars)"
                )
                # Simple truncation, could be smarter
                generated_content = generated_content[: max_len - 3] + "..."

            logger.info(f"Successfully generated Twitter content for {content_type}.")
            return generated_content
        else:
            logger.error(f"Failed to generate Twitter content for {content_type}.")
            return None
