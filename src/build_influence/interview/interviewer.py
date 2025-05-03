import json
from typing import Dict, Any, List, Tuple
import litellm
from loguru import logger
import os
import time

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.text import Text

from build_influence.config import config


class Interviewer:
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
        high_level_features = self.analysis_results.get(
            "high_level_features",
            {},
        )
        self.features = high_level_features.get(
            "identified_features",
            [],
        )
        self.audience = high_level_features.get(
            "target_audience",
            "developers",
        )
        self.selling_points = high_level_features.get(
            "selling_points",
            [],
        )
        self.console = Console()  # Rich console instance
        # Load max questions from config
        self.max_questions = config.interview.get(
            "max_questions",
            7,
        )
        self.min_questions = 3

    def _clear_screen(self):
        """Clears the terminal screen."""
        # Simple cross-platform screen clearing
        os.system("cls" if os.name == "nt" else "clear")
        time.sleep(0.1)  # Small delay to prevent visual glitches

    def _call_llm(self, prompt: str, max_tokens: int = 300) -> str | None:
        """Helper method to call the LLM and handle basic errors."""
        logger.debug("Sending prompt to LLM:\n" + prompt)
        try:
            interview_model = config.interview.get("model", config.llm.model)
            # Assuming provider is consistent
            llm_provider = config.llm.get("provider")
            model_string = (
                f"{llm_provider}/{interview_model}" if llm_provider else interview_model
            )

            logger.info(
                f"Using model: {model_string} to interview",
            )

            response = litellm.completion(
                model=model_string,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.6,
            )
            content = response.choices[0].message.content.strip()
            logger.debug(f"Received response from LLM:\n{content}")
            return content
        except litellm.exceptions.APIError as e:
            logger.error(f"LiteLLM API Error during interview: {e}")
            self.console.print(
                f"[bold red]Error communicating with LLM: {e}[/bold red]"
            )
            return None
        except Exception:
            logger.exception("Unexpected error calling LiteLLM in interview.")
            self.console.print(
                "[bold red]An unexpected error occurred "
                "while contacting the LLM.[/bold red]"
            )
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
            # Basic cleaning - remove potential LLM artifacts
            # like Q:/A: prefixes or list markers
            if q.startswith("Q:") or q.startswith("A:"):
                continue
            while q and not q[0].isalnum():
                q = q[1:].strip()
            if q:
                cleaned_questions.append(q)
        return cleaned_questions

    def _display_summary(self):
        """Displays a summary of the interview Q&A in a table."""
        if not self.conversation_history:
            self.console.print(
                "[yellow]No questions were answered in the interview.[/yellow]"
            )
            return

        table = Table(
            title="Interview Summary",
            show_header=True,
            header_style="bold magenta",
            show_lines=True,  # Add row separators
        )
        table.add_column("Question", style="dim", width=40)
        table.add_column("Your Answer", style="cyan")

        for question, answer in self.conversation_history:
            table.add_row(question, answer)

        self.console.print(table)

    def conduct_interview(self) -> List[Tuple[str, str]]:
        """Conducts the interactive interview via the CLI using Rich."""
        logger.info(f"Starting interview for {self.repo_name}...")
        self._clear_screen()
        self.console.print(
            Panel(
                Text(
                    f"Starting Interview for {self.repo_name}",
                    style="bold cyan",
                ),
                title="Build Influence Interview",
                subtitle="Let's gather some context!",
                expand=False,
            )
        )
        self.console.print(
            "I'll ask some questions to understand the project better.",
        )
        self.console.print(
            "[dim]Type your answers freely. To finish early, "
            "type 'done', 'exit', or 'quit'.[/dim]"
        )

        initial_prompt = self._build_initial_prompt()
        initial_response = self._call_llm(initial_prompt, max_tokens=150)
        questions_to_ask = self._parse_questions(initial_response)

        if questions_to_ask:
            self.console.print(
                "[bold cyan]AI:[/bold cyan] Let's start! "
                "I'll ask questions based on the analysis."
            )
        else:
            self.console.print(
                "[bold yellow]Warning:[/bold yellow] Could not generate "
                "introductory question. Proceeding with defaults."
            )
            logger.warning(
                "Failed to generate initial interview question. "
                "LLM call likely failed."
            )
            # Fallback or default first question?
            # For now, just proceed and let the loop handle it
            questions_to_ask = [
                f"What was the main motivation for starting {self.repo_name}?",
                "What primary problem did you aim to solve with it?",
            ]

        question_count = 0
        while question_count < self.max_questions and questions_to_ask:
            self._clear_screen()  # Clear screen before each question
            current_question = questions_to_ask.pop(0)
            question_number_text = Text(
                f" Question {question_count + 1}/{self.max_questions} ",
                style="bold white on blue",
            )

            try:
                # Use Rich Prompt for input
                # 1. Print the panel containing the question first
                question_panel = Panel(
                    Text(current_question, style="bold yellow"),
                    title=question_number_text,
                    border_style="blue",
                    padding=(1, 2),
                )
                self.console.print(question_panel)
                # 2. Ask for input using a simple prompt string
                answer = Prompt.ask("> ")

            except KeyboardInterrupt:
                self.console.print(
                    "\n[bold yellow]Interview" + "interrupted by user.[/bold yellow]"
                )
                break  # Exit the loop gracefully

            answer_lower_stripped = answer.lower().strip()
            if answer_lower_stripped in ["done", "exit", "quit"]:
                confirm_exit = True
                if question_count < self.min_questions:
                    # Use Rich Confirm
                    confirm_exit = Confirm.ask(
                        Text(
                            "Exit interview early? " + "The insights might be limited.",
                            style="yellow",
                        ),
                        default=False,
                    )
                if confirm_exit:
                    logger.info("User ended the interview early.")
                    self.console.print(
                        Panel(
                            "Interview Finished Early",
                            style="bold yellow",
                            expand=False,
                        )
                    )
                    break
                else:
                    # Re-add the question and continue the loop
                    questions_to_ask.insert(0, current_question)
                    continue
            elif not answer.strip():
                # Use Rich print for feedback
                self.console.print(
                    "[yellow]Please provide an answer or "
                    "type an exit command.[/yellow]"
                )
                time.sleep(1.5)  # Give user time to read
                questions_to_ask.insert(0, current_question)  # Re-ask
                continue

            self.conversation_history.append((current_question, answer))
            question_count += 1

            # Generate follow-up if needed and capacity allows
            if question_count < self.max_questions and not questions_to_ask:
                followup_prompt = self._build_followup_prompt()
                followup_response = self._call_llm(
                    followup_prompt,
                    max_tokens=150,
                )
                new_questions = self._parse_questions(followup_response)
                if new_questions:
                    questions_to_ask = new_questions
                else:
                    logger.warning("LLM failed to provide follow-up question.")

        self._clear_screen()
        finish_message = "Interview Finished"
        finish_style = "bold green"
        if question_count >= self.max_questions:
            finish_message = f"Reached Question Limit ({self.max_questions})"
            finish_style = "bold yellow"
        elif not self.conversation_history and question_count == 0:
            finish_message = "Interview Aborted"
            finish_style = "bold red"

        self.console.print(
            Panel(
                finish_message,
                style=finish_style,
                expand=False,
            )
        )

        self._display_summary()  # Show the summary table

        # Ask for confirmation before returning results
        confirm_save = Confirm.ask(
            Text("\nDoes this summary look correct? Save results?", style="bold green"),
            default=True,
        )

        if confirm_save:
            log_msg = (
                f"Interview complete and confirmed. Collected "
                f"{len(self.conversation_history)} Q/A pairs."
            )
            logger.info(log_msg)
            self.console.print("[green]Interview results saved.[/green]")
            return self.conversation_history
        else:
            logger.info("User rejected the interview summary. Results discarded.")
            self.console.print("[yellow]Interview results discarded.[/yellow]")
            return []


# Example Usage (for testing) - Keep this as is for local testing
if __name__ == "__main__":
    from build_influence.utils import setup_logging

    # Setup basic console logging if not already configured by the app
    # This ensures Rich output works even when running the script directly
    try:
        logger.info("Setting up basic logging for direct script execution.")
        # Assuming setup_logging configures root logger appropriately
        setup_logging()
    except Exception as e:
        print(f"Failed basic logging setup: {e}")  # Fallback print

    # Use a console specifically for testing if needed
    test_console = Console()
    test_console.print("[bold magenta]--- Running Interviewer Test ---[/bold magenta]")

    analysis_file = "analysis_results.json"
    analysis_data = {}
    try:
        with open(analysis_file, "r") as f:
            analysis_data = json.load(f)
            logger.info(f"Loaded analysis results from {analysis_file}")
    except FileNotFoundError:
        logger.error(f"{analysis_file} not found. Using placeholder data.")
        test_console.print(
            f"[yellow]Warning: {analysis_file} not found. "
            "Using placeholder data.[/yellow]"
        )
    except json.JSONDecodeError:
        err_msg = f"Error decoding JSON: {analysis_file}. Using placeholder."
        logger.error(err_msg)
        test_console.print(f"[red]Error: {err_msg}[/red]")

    if not analysis_data:
        logger.warning("Using placeholder analysis data for interview test.")
        analysis_data = {
            "repo_name": "Placeholder Project",
            "high_level_features": {
                "identified_features": ["Feature A", "Feature B"],
                "target_audience": "Test Users",
                "selling_points": ["Point 1", "Point 2"],
            },
            # Add other necessary structure if your class relies on it
        }

    interviewer = Interviewer(analysis_data)
    try:
        interview_results = interviewer.conduct_interview()
        test_console.print(
            "\n[bold green]--- Interview Test Completed ---[/bold green]"
        )
        # Optionally print results if needed for debugging
        # test_console.print("Collected Results:")
        # test_console.print(interview_results)
    except Exception as e:
        logger.exception("Error during interview test execution.")
        test_console.print(
            f"[bold red]An error occurred during the " f"interview test: {e}[/bold red]"
        )
