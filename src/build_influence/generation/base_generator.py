import litellm
from loguru import logger
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

from build_influence.config import config


class BaseContentGenerator(ABC):
    """Abstract base class for content generators."""

    def __init__(
        self,
        analysis_results: Dict[str, Any],
        interview_data: Optional[List[Dict[str, str]]] = None,
        readme_content: Optional[str] = None,
        # config_override: Optional[Dict[str, Any]] = None # TODO: Add later
    ):
        """
        Initializes the BaseContentGenerator.

        Args:
            analysis_results: Dict loaded from analysis_results.json.
            interview_data: List of interview Q&A dicts, or None.
            readme_content: Content of the README file as a string, or None.
            # config_override: Optional dict to override specific configs.
        """
        self.analysis_results = analysis_results
        self.interview_data = interview_data
        self.readme_content = readme_content
        self.llm_model = config.llm.model
        self.llm_provider = config.llm.provider
        self.repo_name = self.analysis_results.get("repo_name", "the project")
        # TODO: Maybe use Box for analysis_results for easier access?
        self.high_level_features = self.analysis_results.get("high_level_features", {})
        # TODO: Incorporate user preferences from config (tone, style, etc.)

    def _call_llm(
        self, prompt: str, max_tokens: int = 1000, temperature: float = 0.7
    ) -> Optional[str]:
        """
        Helper method to call the LLM using LiteLLM.

        Args:
            prompt: The complete prompt string to send to the LLM.
            max_tokens: Maximum number of tokens for the response.
            temperature: The sampling temperature for generation.

        Returns:
            The generated content as a string, or None if an error occurred.
        """
        logger.debug(f"Sending content generation prompt to LLM ({self.llm_model}):")
        logger.trace(prompt)  # Use trace for potentially long prompts
        try:
            model_string = (
                f"{self.llm_provider}/{self.llm_model}"
                if self.llm_provider
                else self.llm_model
            )
            response = litellm.completion(
                model=model_string,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = response.choices[0].message.content.strip()
            logger.debug("Received response from LLM.")
            logger.trace(f"LLM Response: {content}")
            return content
        except litellm.exceptions.APIError as e:
            logger.error(f"LiteLLM API Error during content generation: {e}")
            return None
        except Exception:
            logger.exception("Unexpected error calling LiteLLM for content generation.")
            return None

    @abstractmethod
    def _build_prompt(
        self,
        content_type: str,
        context_override: Optional[Dict] = None,
    ) -> str:
        """
        Constructs the prompt for the LLM based on the generator's target \
        format/platform.

        Args:
            content_type: The type of content \
                (e.g., 'announcement', 'deepdive').
            context_override: Optional additional context to include.

        Returns:
            The fully constructed prompt string.
        """
        pass

    @abstractmethod
    def generate(
        self,
        content_type: str,
        context_override: Optional[Dict] = None,
    ) -> Optional[str]:
        """
        Generates content for the generator's specific target \
        format/platform.

        Args:
            content_type: The type of content \
                (e.g., 'announcement', 'deepdive').
            context_override: Optional additional context to include.

        Returns:
            The generated content as a string, or None if generation failed.
        """
        pass
