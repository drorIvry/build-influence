import json
from typing import Dict, Any, List, Tuple
import litellm
from loguru import logger
import typer

from build_influence.config import config

# Constants for interview flow control
MAX_INTERVIEW_QUESTIONS = 7
MIN_INTERVIEW_QUESTIONS = 3


class Interviewer:
    """Conducts an interactive interview using LLM based on repo analysis."""

    def __init__(self, analysis_results: Dict[str, Any]):
        """
        Initializes the Interviewer.

        Args:
            analysis_results: Dict containing analysis results from
                              analysis_results.json.
        """
        self.analysis_results = analysis_results
        self.llm_model = config.llm.model
        self.llm_provider = config.llm.provider
        self.conversation_history: List[Tuple[str, str]] = []
        self.repo_name = self.analysis_results.get("repo_name", "this project")
        # Extract features, handling potential missing keys
        high_level_features = self.analysis_results.get("high_level_features", {})
        self.features = high_level_features.get("identified_features", [])
        self.audience = high_level_features.get("target_audience", "developers")
        self.selling_points = high_level_features.get("selling_points", [])

    def _call_llm(self, prompt: str, max_tokens: int = 300) -> str | None:
        """Helper method to call the LLM and handle basic errors."""
        logger.debug("Sending prompt to LLM:")
        logger.debug(prompt)
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
                temperature=0.6,
            )
            content = response.choices[0].message.content.strip()
            logger.debug("Received response from LLM:")
            logger.debug(content)
            return content
        except litellm.exceptions.APIError as e:
            logger.error(f"LiteLLM API Error during interview: {e}")
            return None
        except Exception:
            logger.exception("Unexpected error calling LiteLLM in interview.")
            return None

    def _build_initial_prompt(self) -> str:
        """Builds the prompt for the LLM for initial interview questions."""
        feature_str = ", ".join(self.features) if self.features else "N/A"
        selling_points_str = (
            ", ".join(self.selling_points) if self.selling_points else "N/A"
        )
        prompt = f"""
        You are an expert technical interviewer starting a conversation about
        the code repository '{self.repo_name}'. Based on the following analysis
        summary, generate 1-2 insightful OPENING questions to kickstart a
        discussion about the project's context and goals.

        Analysis Summary:
        - Key Features: {feature_str}
        - Target Audience: {self.audience}
        - Selling Points: {selling_points_str}

        Focus the initial questions on:
        - The primary motivation or the core problem this project solves.
        - The intended impact or main goal for the target audience.

        Frame the questions conversationally. Output ONLY the question text,
        one question per line. Do not use numbering or bullet points.
        """
        return prompt.strip()

    def _build_followup_prompt(self) -> str:
        """Builds the prompt for the LLM for follow-up questions."""
        history_str = "\n".join(
            [f"Q: {q}\nA: {a}" for q, a in self.conversation_history]
        )
        feature_str = ", ".join(self.features) if self.features else "N/A"
        selling_points_str = (
            ", ".join(self.selling_points) if self.selling_points else "N/A"
        )

        prompt = f"""
        You are an expert technical interviewer continuing a conversation about
        the code repository '{self.repo_name}'.
        Here's a summary of the project analysis:
        - Key Features: {feature_str}
        - Target Audience: {self.audience}
        - Selling Points: {selling_points_str}

        Here is the conversation history so far:
        {history_str}

        Based on the analysis and the LATEST answer, generate ONE insightful
        follow-up question.

        Focus follow-up questions on:
        - Motivations & "Why" (Twitter/LinkedIn): Dig deeper into reasons
          behind choices mentioned in the previous answer.
        - Lessons Learned (Dev.to): Ask about challenges, trade-offs, or
          surprising aspects related to the previous answer.
        - Avoid repeating questions already asked.

        Frame the question conversationally. Output ONLY the single question
        text. Do not use numbering, bullet points, or introductory phrases like
        "Okay, my next question is...". If the conversation seems concluding
        or the previous answer was brief/uninformative, ask a concluding
        question like "Is there anything else interesting/challenging about
        this project you'd like to share?" or "What's one piece of advice
        for someone starting a similar project?".
        """
        return prompt.strip()

    def _parse_questions(self, llm_content: str | None) -> List[str]:
        """Parses questions from LLM response (expects one per line)."""
        if not llm_content:
            return []
        questions = [q.strip() for q in llm_content.split("\n") if q.strip()]
        cleaned_questions = []
        for q in questions:
            if q.startswith("Q:") or q.startswith("A:"):
                continue
            while q and not q[0].isalnum():
                q = q[1:].strip()
            if q:
                cleaned_questions.append(q)
        return cleaned_questions

    def conduct_interview(self) -> List[Tuple[str, str]]:
        """Conducts the interactive interview via the CLI using Typer."""
        logger.info(f"Starting interview for {self.repo_name}...")
        typer.secho(
            f"\n--- Starting Interview for {self.repo_name} ---", fg=typer.colors.CYAN
        )
        typer.echo("I'll ask questions to understand the project better.")
        typer.echo("Type answers freely. To finish, type 'done', 'exit', " "or 'quit'.")

        initial_prompt = self._build_initial_prompt()
        initial_response = self._call_llm(initial_prompt, max_tokens=150)
        questions_to_ask = self._parse_questions(initial_response)

        if not questions_to_ask:
            logger.warning("LLM failed initial questions. Using fallbacks.")
            questions_to_ask = [
                f"What was the main motivation for starting {self.repo_name}?",
                "What primary problem did you aim to solve?",
            ]

        question_count = 0
        while question_count < MAX_INTERVIEW_QUESTIONS and questions_to_ask:
            current_question = questions_to_ask.pop(0)

            prompt_text = (
                f"\n({question_count + 1}/{MAX_INTERVIEW_QUESTIONS}) "
                f"{current_question}"
            )
            answer = typer.prompt(
                prompt_text,
                default="",
                show_default=False,
            )

            answer_lower_stripped = answer.lower().strip()
            if answer_lower_stripped in ["done", "exit", "quit"]:
                confirm = True
                if question_count < MIN_INTERVIEW_QUESTIONS:
                    confirm = typer.confirm(
                        "Exit interview early?", default=False, abort=False
                    )
                if confirm:
                    logger.info("User ended the interview.")
                    typer.secho(
                        "\n--- Interview Finished Early ---", fg=typer.colors.YELLOW
                    )
                    break
                else:
                    questions_to_ask.insert(0, current_question)
                    continue
            elif not answer.strip():
                typer.echo("Please provide an answer or type an exit command.")
                questions_to_ask.insert(0, current_question)
                continue

            self.conversation_history.append((current_question, answer))
            question_count += 1

            # Generate follow-up if needed and capacity allows
            if question_count < MAX_INTERVIEW_QUESTIONS and not questions_to_ask:
                followup_prompt = self._build_followup_prompt()
                followup_response = self._call_llm(followup_prompt, max_tokens=150)
                new_questions = self._parse_questions(followup_response)
                if new_questions:
                    questions_to_ask = new_questions + questions_to_ask
                else:
                    logger.warning("LLM failed to provide follow-up question.")

        finish_color = typer.colors.GREEN
        if question_count >= MAX_INTERVIEW_QUESTIONS:
            typer.secho("\nReached question limit.", fg=typer.colors.YELLOW)
            typer.secho("--- Interview Finished ---", fg=finish_color)
        # Check conditions separately for clarity
        elif not questions_to_ask and question_count >= MIN_INTERVIEW_QUESTIONS:
            typer.secho("\n--- Interview Finished ---", fg=finish_color)

        log_msg = (
            f"Interview complete. Collected "
            f"{len(self.conversation_history)} Q/A pairs."
        )
        logger.info(log_msg)
        return self.conversation_history


# Example Usage (for testing)
if __name__ == "__main__":
    from build_influence.utils import setup_logging

    setup_logging()

    analysis_file = "analysis_results.json"
    analysis_data = {}
    try:
        with open(analysis_file, "r") as f:
            analysis_data = json.load(f)
            logger.info(f"Loaded analysis results from {analysis_file}")
    except FileNotFoundError:
        logger.error(f"{analysis_file} not found. Using placeholder data.")
    except json.JSONDecodeError:
        err_msg = f"Error decoding JSON: {analysis_file}. Using placeholder."
        logger.error(err_msg)

    if not analysis_data:
        logger.warning("Using placeholder analysis data for interview test.")
        analysis_data = {
            "repo_name": "Placeholder Project",
            "high_level_features": {
                "identified_features": [
                    "CLI Tool",
                    "Data Processing",
                    "API Integration",
                ],
                "target_audience": "Data Scientists",
                "selling_points": ["Easy to configure", "Fast processing"],
            },
        }

    typer.echo("Direct execution: Skipping interactive interview.")
    typer.echo("Run via the CLI 'interview' command for interactivity.")
    interviewer = Interviewer(analysis_data)
    initial_prompt = interviewer._build_initial_prompt()
    logger.info("Generated Initial Prompt (for testing):")
    logger.info(initial_prompt)
