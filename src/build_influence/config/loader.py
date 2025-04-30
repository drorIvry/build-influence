import os
import yaml
from dotenv import load_dotenv
from loguru import logger
from box import Box  # For dot notation access

DEFAULT_CONFIG_PATH = "config.yaml"


def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> Box:
    """Loads configuration from YAML file and environment variables."""
    load_dotenv()  # Load .env file variables into environment

    # Load default config from file
    try:
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)
            if config_data is None:
                config_data = {}
        logger.info(f"Loaded configuration from {config_path}")
    except FileNotFoundError:
        logger.warning(f"Config {config_path} not found. Using defaults/env vars.")
        config_data = {}
    except yaml.YAMLError as e:
        logger.error(f"Error parsing config file {config_path}: {e}")
        config_data = {}

    # Basic structure if file was empty or missing
    config_data.setdefault("logging", {})
    config_data.setdefault("llm", {})
    config_data.setdefault("analysis", {})
    config_data.setdefault("generation", {})
    config_data.setdefault("preferences", {})
    config_data.setdefault("publication", {})

    # --- Environment Variable Overrides ---
    # Logging
    log_conf = config_data["logging"]
    log_conf["level"] = os.environ.get("LOG_LEVEL", log_conf.get("level", "INFO"))
    log_conf["file"] = os.environ.get(
        "LOG_FILE", log_conf.get("file", "logs/app.log")  # Shortened default
    )
    log_conf["rotation"] = os.environ.get(
        "LOG_ROTATION", log_conf.get("rotation", "10 MB")
    )
    log_conf["retention"] = os.environ.get(
        "LOG_RETENTION", log_conf.get("retention", "30 days")
    )

    # LLM
    llm_conf = config_data["llm"]
    llm_conf["model"] = os.environ.get(
        "LLM_MODEL",
        llm_conf.get("model", "claude-3.5-sonnet-20240620"),  # Updated default
    )
    llm_conf["max_tokens"] = int(
        os.environ.get("LLM_MAX_TOKENS", llm_conf.get("max_tokens", 1500))
    )
    llm_conf["temperature"] = float(
        os.environ.get("LLM_TEMPERATURE", llm_conf.get("temperature", 0.7))
    )
    llm_conf["api_key"] = os.environ.get("ANTHROPIC_API_KEY")  # Example

    # Analysis
    analysis_conf = config_data["analysis"]
    analysis_conf["max_files_to_parse"] = int(
        os.environ.get(
            "ANALYSIS_MAX_FILES", analysis_conf.get("max_files_to_parse", 1000)
        )
    )

    # Preferences
    pref_conf = config_data["preferences"]
    pref_conf["approval_workflow"] = os.environ.get(
        "PREF_APPROVAL", pref_conf.get("approval_workflow", "manual")
    )
    pref_conf["publication_frequency"] = os.environ.get(
        "PREF_FREQUENCY", pref_conf.get("publication_frequency", "manual")
    )

    # Publication API Keys
    pub_conf = config_data["publication"]
    pub_conf.setdefault("devto", {})["api_key"] = os.environ.get("DEVTO_API_KEY")
    twitter_conf = pub_conf.setdefault("twitter", {})
    twitter_conf["api_key"] = os.environ.get("TWITTER_API_KEY")
    twitter_conf["api_secret"] = os.environ.get("TWITTER_API_SECRET")
    twitter_conf["access_token"] = os.environ.get("TWITTER_ACCESS_TOKEN")
    twitter_conf["access_token_secret"] = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")
    pub_conf.setdefault("linkedin", {})  # API keys loaded similarly

    # Convert to Box for dot notation access
    config = Box(config_data, default_box=True, default_box_attr=None)

    logger.info("Environment variable overrides applied.")

    # Basic validation example
    if not config.llm.api_key:
        logger.warning("LLM API Key (e.g., ANTHROPIC_API_KEY) not set in env.")

    return config


# Global config object (Load once on import)
config = load_config()

# Example usage:
if __name__ == "__main__":
    from build_influence.utils.logging import setup_logging

    setup_logging()  # Setup logging first
    print(f"LLM Model: {config.llm.model}")
    print(f"Log Level: {config.logging.level}")
    print(f"Dev.to API Key Set: {bool(config.publication.devto.api_key)}")
    print(f"Default Approval: {config.preferences.approval_workflow}")
