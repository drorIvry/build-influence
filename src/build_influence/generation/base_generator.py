import litellm
from loguru import logger
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

from build_influence.config import config

litellm.drop_params = True


class BaseContentGenerator(ABC):
    """Abstract base class for content generators."""

    FILE_EXTENSION = "txt"  # Default file extension

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
        # Use the composer-specific model, falling back to the general LLM model
        composer_model = config.generation.get("model", config.llm.model)
        # Assuming provider is consistent across generation/refinement
        llm_provider = config.llm.get("provider")
        model_string = (
            f"{llm_provider}/{composer_model}" if llm_provider else composer_model
        )

        logger.debug(f"Sending content generation prompt to LLM ({model_string}):")
        logger.trace(prompt)  # Use trace for potentially long prompts
        try:
            logger.info(
                f"Using model: {model_string} to generate content",
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

    # New method to build refinement prompts
    def _build_refinement_prompt(
        self,
        original_content: str,
        feedback: str,
        content_type: str,
        # context_override: Optional[Dict] = None, # Keep for future use maybe
    ) -> Optional[str]:
        """
        Constructs a prompt specifically for refining existing content based
        on feedback.
        """
        platform_name = self.__class__.__name__.replace("Generator", "").lower()
        logger.debug(
            f"Building refinement prompt for platform: {platform_name}, "
            f"type: {content_type}"
        )

        prompt_lines = [
            (
                "You are an expert content writer tasked with refining "
                "content based on user feedback."
            ),
            f"The target platform is: {platform_name}",
            f"The desired content type is: {content_type}",
            "---",
            "ORIGINAL CONTENT:",
            original_content,
            "---",
            "USER FEEDBACK:",
            feedback,
            "---",
            "INSTRUCTIONS:",
            (
                "Rewrite the *entire* ORIGINAL CONTENT based *only* on the "
                "USER FEEDBACK provided."
            ),
            (
                f"Ensure the rewritten content remains suitable for the "
                f"{platform_name} platform and adheres to the requirements "
                f"of a '{content_type}' piece."
            ),
            (
                "Maintain the original tone and core message unless the "
                "feedback explicitly requests a change."
            ),
            (
                "Output *only* the complete rewritten content, without any "
                "preamble or explanation."
            ),
        ]

        # Consider adding essential context back if simple refinement fails
        # e.g., prompt_lines.insert(4, f"Project Name: {self.repo_name}")
        # e.g., prompt_lines.insert(5, "Key Features: ...")

        return "\\n".join(prompt_lines)

    # New method to handle regeneration based on feedback
    def regenerate_with_feedback(
        self,
        original_content: str,
        feedback: str,
        content_type: str,
        context_override: Optional[Dict] = None,  # Keep signature consistent
    ) -> Optional[str]:
        """
        Regenerates content based on user feedback.

        Args:
            original_content: The previously generated content.
            feedback: The user's natural language feedback.
            content_type: The type of content being regenerated.
            context_override: Optional context (currently unused in refinement).

        Returns:
            The regenerated content, or None if failed.
        """
        logger.info(
            f"Regenerating content for type '{content_type}' based on feedback."
        )
        logger.debug(f"Original content length: {len(original_content)}")
        logger.debug(f"Feedback: {feedback}")

        refinement_prompt = self._build_refinement_prompt(
            original_content=original_content,
            feedback=feedback,
            content_type=content_type,
            # context_override=context_override, # Pass if needed
        )

        if not refinement_prompt:
            logger.error("Failed to build refinement prompt.")
            return None

        # Use existing LLM call mechanism
        # TODO: Consider if different LLM parameters (e.g., lower temp?) are
        #       better for refinement tasks.
        regenerated_content = self._call_llm(refinement_prompt)

        if regenerated_content:
            logger.info("Successfully regenerated content based on feedback.")
        else:
            logger.error("LLM call failed during content regeneration.")

        return regenerated_content

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
