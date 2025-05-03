from loguru import logger
from typing import Dict, Optional

from .base_generator import BaseContentGenerator


class LinkedinGenerator(BaseContentGenerator):
    """Generates content suitable for LinkedIn posts."""

    def _build_prompt(
        self,
        content_type: str,
        context_override: Optional[Dict] = None,
    ) -> str:
        """
        Constructs the prompt for generating LinkedIn content.
        """
        logger.debug(f"Building LinkedIn prompt for content_type='{content_type}'")

        # --- Prepare Context Sections (Professional Tone) ---
        features = self.high_level_features.get("identified_features", [])
        # Use bullet points for professionalism
        features_str = "\n* ".join(f for f in features if f) if features else "N/A"

        # Analysis Summary - More detailed than Twitter
        file_tree = self.analysis_results.get("file_tree", [])
        code_files = sum(1 for f in file_tree if f.get("type") == "code")
        doc_files = sum(1 for f in file_tree if f.get("type") == "documentation")
        config_files = sum(1 for f in file_tree if f.get("type") == "configuration")
        analysis_summary = (
            f"* Code Files: {code_files}\n"
            f"* Documentation Files: {doc_files}\n"
            f"* Configuration Files: {config_files}"
        )

        # Interview Context - Full Q&A seems appropriate
        interview_context_str = "No interview data available."
        if self.interview_data:
            interview_context_str = "\n".join(
                [
                    f"Q: {item['question']}\nA: {item['answer']}"
                    for item in self.interview_data
                ]
            )

        # README Content - Include a good chunk
        readme_str = self.readme_content if self.readme_content else "N/A"
        max_readme_len = 1200
        if len(readme_str) > max_readme_len:
            readme_str = readme_str[:max_readme_len] + "... (truncated)"

        # --- Construct LinkedIn Prompt ---
        prompt = f"""
**Goal:** Generate a professional LinkedIn post ('{content_type}') about the project '{self.repo_name}'.

**Platform:** LinkedIn (Professional tone, slightly more formal, value-oriented)

**Key Information about '{self.repo_name}':**

*Key Features/Achievements:*
{features_str}

*Project Structure Summary:*
{analysis_summary}

*Developer Insights (from Interview):*
{interview_context_str}

*Project Overview (from README):*
```
{readme_str}
```

**Instructions:**
1. Write a professional LinkedIn post summarizing the project/update.
2. Focus on the value proposition, achievements, or key learnings.
3. Maintain a professional and engaging tone suitable for LinkedIn.
4. Use appropriate formatting (bullet points, maybe bolding key terms).
5. If '{content_type}' is 'announcement', highlight the launch/update
   professionally. If 'deepdive', focus on technical achievements or
   learnings.
6. Consider adding relevant professional hashtags (e.g., #SoftwareDevelopment,
   #Tech, #ProjectManagement).
7. Output *only* the LinkedIn post text.

**Generated LinkedIn Post:**
""".strip()

        logger.trace(f"Generated LinkedIn Prompt:\n{prompt}")
        return prompt

    def generate(
        self,
        content_type: str,
        context_override: Optional[Dict] = None,
    ) -> Optional[str]:
        """
        Generates LinkedIn post content.
        """
        logger.info(
            f"Generating LinkedIn content for {content_type=} for '{self.repo_name}'"
        )
        prompt = self._build_prompt(content_type, context_override)
        # Use the base class method to call LLM
        generated_content = self._call_llm(prompt)

        if generated_content:
            logger.info(f"Successfully generated LinkedIn content for {content_type}.")
            # TODO: Add LinkedIn specific post-processing?
            return generated_content
        else:
            logger.error(f"Failed to generate LinkedIn content for {content_type}.")
            return None
