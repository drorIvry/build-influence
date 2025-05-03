from loguru import logger
from typing import Dict, Optional

from .base_generator import BaseContentGenerator


class DevtoGenerator(BaseContentGenerator):
    """Generates content suitable for Dev.to articles."""

    FILE_EXTENSION = "md"

    def _build_prompt(
        self,
        content_type: str,
        context_override: Optional[Dict] = None,
    ) -> str:
        """
        Constructs the prompt for generating Dev.to content.
        """
        logger.debug(f"Building Dev.to prompt for content_type='{content_type}'")

        # --- Prepare Context Sections (Similar to Markdown) ---
        features = self.high_level_features.get("identified_features", [])
        features_str = "\n- ".join(f for f in features if f) if features else "N/A"

        file_tree = self.analysis_results.get("file_tree", [])
        code_files = sum(1 for f in file_tree if f.get("type") == "code")
        doc_files = sum(1 for f in file_tree if f.get("type") == "documentation")
        # Simplified summary for potentially shorter content
        analysis_summary = f"Code Files: {code_files}, Doc Files: {doc_files}"

        interview_context_str = "N/A"
        if self.interview_data:
            interview_context_str = "".join(
                [
                    f"Q: {item['question']}\nA: {item['answer']}\n---\n"
                    for item in self.interview_data
                ]
            )

        readme_str = self.readme_content if self.readme_content else "N/A"
        max_readme_len = 1000  # Shorter than Markdown perhaps
        if len(readme_str) > max_readme_len:
            readme_str = readme_str[:max_readme_len] + "... (truncated)"

        # --- Construct Dev.to Prompt ---
        prompt = f"""
**Goal:** Generate a draft Dev.to article ('{content_type}') for the project '{self.repo_name}'.

**Platform:** Dev.to (Markdown format expected, conversational tone encouraged)

**Key Information about '{self.repo_name}':**

*High-Level Features:*
{features_str}

*Repository Analysis Summary:*
{analysis_summary}

*Developer Interview Context:*
{interview_context_str}

*Project README (Truncated):*
```
{readme_str}
```

**Instructions:**
1. Create an engaging Dev.to article based on the context.
2. Use Markdown for formatting (headers, code blocks, lists).
3. Adapt the tone to be informative yet conversational, suitable for Dev.to.
    make it a bit quip-y and humorous, DON'T MAKE IT CREENGY!
4. Structure the article logically (intro, key points,
   conclusion/call to action).
5. Include code snippets and how to install and use the project.
6. if appropriate include a mermaid diagram
7. Use emojis to make the article more engaging but don't over do it.
8. Output only the article content in Markdown.

**Generated Dev.to Article (Markdown):**
""".strip()

        logger.trace(f"Generated Dev.to Prompt:\n{prompt}")
        return prompt

    def generate(
        self,
        content_type: str,
        context_override: Optional[Dict] = None,
    ) -> Optional[str]:
        """
        Generates Dev.to article content.
        """
        logger.info(
            f"Generating Dev.to {content_type=} for '{self.repo_name}'",
        )
        prompt = self._build_prompt(content_type, context_override)
        # Use the base class method to call LLM
        generated_content = self._call_llm(prompt)

        if generated_content:
            logger.info(
                f"Successfully generated Dev.to content for {content_type}.",
            )
            return generated_content
        else:
            logger.error(
                f"Failed to generate Dev.to content for {content_type}.",
            )
            return None
