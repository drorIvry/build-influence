# Build Influence

`build-influence` is a Python command-line tool designed to analyze local code repositories, conduct AI-powered interviews about the codebase, and generate social media content (like blog posts or tweets) based on the analysis and interview insights.

## Features

- **Repository Analysis:** Scans local code repositories to understand structure, languages, key files, and potential points of interest.
- **AI-Powered Interviews:** Uses an LLM to ask targeted questions about the analyzed repository to gather deeper insights and narrative angles.
- **Content Generation:** Creates content drafts tailored for different platforms (Markdown, Dev.to, Twitter, LinkedIn) based on the analysis and interview data.
- **Content Publication:** (Experimental/Future) Publishes generated content directly to configured platforms.
- **Configurable:** Uses a `config.yaml` file and environment variables for flexible configuration of LLMs, output directories, and platform credentials.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd build-influence
    ```
2.  **Create a virtual environment (recommended):**
    ```bash
    python3.12 -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

Configuration is handled via `config.yaml` and environment variables (which take precedence).

1.  **Create `config.yaml`:** Copy `config.example.yaml` (if it exists) or create a new `config.yaml` file in the project root.
2.  **Review `src/build_influence/config/loader.py`:** This file shows all configurable options and their corresponding environment variables.
3.  **Set Environment Variables:** For sensitive data like API keys, it's recommended to use environment variables (e.g., by creating a `.env` file). Key variables include:

    - `LLM_API_KEY`: Your primary LLM provider API key (e.g., Anthropic).
    - `LLM_MODEL`: The specific LLM model to use (defaults to `claude-3.5-sonnet-20240620`).
    - `DEVTO_API_KEY`: API key for Dev.to publication.
    - `TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_TOKEN_SECRET`: Credentials for Twitter/X publication.
    - `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`: Credentials for LinkedIn publication.
    - `LOG_LEVEL`, `LOG_FILE`: Logging configuration.
    - `OUTPUT_DIR_BASE`: Base directory for output files (defaults to `./output`).

    Load environment variables by creating a `.env` file in the project root:

    ```dotenv
    OPENAI_API_KEY=your_openai_key
    DEVTO_API_KEY=your_devto_key
    # ... other variables
    ```

## Usage

The tool is run via the `build-influence` command (or `python -m build_influence.cli` if installed differently).

```bash
build-influence --help
```

**Common Workflow:**

1.  **Analyze a Repository:**

    ```bash
    build-influence analyze path/to/your/repo
    # Example: analyze the current directory
    # build-influence analyze .
    ```

    This creates an analysis JSON file in the configured analysis output directory (e.g., `output/analysis/your_repo_name_analysis.json`).

2.  **Conduct an Interview:**

    ```bash
    build-influence interview your_repo_name
    ```

    This uses the analysis file generated in step 1 to ask questions. The interview log is saved (e.g., `output/interviews/your_repo_name_interview.json`).

3.  **Generate Content:**

    ```bash
    # Generate for all platforms
    build-influence generate your_repo_name

    # Generate only for a specific platform (e.g., markdown)
    build-influence generate your_repo_name --platform markdown

    # Generate a specific content type (if implemented by the generator)
    # build-influence generate your_repo_name --platform devto announcement
    ```

    Content files are saved in the configured content output directory (e.g., `output/content/your_repo_name/`).

4.  **Publish Content (Use with caution):**
    ```bash
    build-influence publish path/to/generated/content.md --platform devto
    ```
    This attempts to publish the specified content file to the target platform using configured credentials.

**Other Commands:**

- `build-influence configure`: (Currently placeholder) Intended for interactive configuration.
- `build-influence logs`: View application logs.
  ```bash
  build-influence logs --lines 50 # Show last 50 lines
  build-influence logs --follow   # Tail logs
  ```

## Development

- **Code Style:** Follows Black formatting and isort for imports.
- **Testing:** Uses pytest. Run tests with `pytest`.
- **Dependencies:** Managed in `requirements.txt`.
