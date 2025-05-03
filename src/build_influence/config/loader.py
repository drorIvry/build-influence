import os
import yaml
from dotenv import load_dotenv
from loguru import logger
from box import Box  # For dot notation access

DEFAULT_CONFIG_PATH = "config.yaml"


def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> Box:
    """
    Loads configuration prioritizing environment variables over YAML file.

    1. Loads the YAML configuration file.
    2. Sets up default dictionary structures if sections are missing.
    3. Overrides specific configuration values with environment variables if they exist.
    """
    load_dotenv()  # Load .env file variables into environment

    # 1. Load base config from YAML file
    try:
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)
            if config_data is None:
                config_data = {}  # Ensure config_data is a dict if file is empty
        logger.info(f"Loaded base configuration from {config_path}")
    except FileNotFoundError:
        logger.warning(f"Config file {config_path} not found. Using defaults/env vars.")
        config_data = {}
    except yaml.YAMLError as e:
        logger.error(
            f"Error parsing config file {config_path}: {e}. Using defaults/env vars."
        )
        config_data = {}

    # 2. Ensure default top-level keys exist
    config_data.setdefault("logging", {})
    config_data.setdefault("llm", {})
    config_data.setdefault("analysis", {})
    config_data.setdefault("generation", {})
    config_data.setdefault("interview", {})
    config_data.setdefault("preferences", {})
    config_data.setdefault("platforms", {})
    config_data.setdefault("output_dirs", {})

    # 3. Environment Variable Overrides
    logger.info("Applying environment variable overrides...")

    # --- Logging ---
    log_conf = config_data["logging"]
    log_conf["level"] = os.environ.get("LOG_LEVEL", log_conf.get("level", "INFO"))
    log_conf["file"] = os.environ.get(
        "LOG_FILE", log_conf.get("file", "logs/build_influence.log")
    )
    log_conf["rotation"] = os.environ.get(
        "LOG_ROTATION", log_conf.get("rotation", "10 MB")
    )
    log_conf["retention"] = os.environ.get(
        "LOG_RETENTION", log_conf.get("retention", "30 days")
    )

    # --- LLM ---
    # Determine the main model (priority: ENV -> YAML -> Default)
    default_main_model = "claude-3.5-sonnet-20240620"
    main_llm_model_from_yaml = config_data.get("llm", {}).get("model")
    main_llm_model = os.environ.get(
        "LLM_MODEL", main_llm_model_from_yaml or default_main_model
    )

    llm_conf = config_data["llm"]
    llm_conf["model"] = main_llm_model
    llm_conf["api_key"] = os.environ.get(
        "LLM_API_KEY", llm_conf.get("api_key")
    )  # e.g. ANTHROPIC_API_KEY
    llm_conf["max_tokens"] = int(
        os.environ.get("LLM_MAX_TOKENS", llm_conf.get("max_tokens", 4000))
    )
    llm_conf["temperature"] = float(
        os.environ.get("LLM_TEMPERATURE", llm_conf.get("temperature", 0.7))
    )
    llm_conf["provider"] = os.environ.get(
        "LLM_PROVIDER", llm_conf.get("provider")
    )  # e.g., 'anthropic', 'openai'

    # --- Analysis ---
    analysis_conf = config_data["analysis"]
    analysis_conf["model"] = os.environ.get(
        "ANALYSIS_LLM_MODEL", analysis_conf.get("model", main_llm_model)
    )
    analysis_conf["max_files_to_parse"] = int(
        os.environ.get(
            "ANALYSIS_MAX_FILES", analysis_conf.get("max_files_to_parse", 1000)
        )
    )

    # --- Generation (Composer) ---
    gen_conf = config_data["generation"]
    gen_conf["model"] = os.environ.get(
        "COMPOSER_LLM_MODEL", gen_conf.get("model", main_llm_model)
    )

    # --- Interview ---
    interview_conf = config_data["interview"]
    interview_conf["model"] = os.environ.get(
        "INTERVIEW_LLM_MODEL", interview_conf.get("model", main_llm_model)
    )
    interview_conf["max_questions"] = int(
        os.environ.get(
            "INTERVIEW_MAX_QUESTIONS", interview_conf.get("max_questions", 7)
        )
    )

    # --- Preferences ---
    pref_conf = config_data["preferences"]
    pref_conf["approval_workflow"] = os.environ.get(
        "PREF_APPROVAL", pref_conf.get("approval_workflow", "manual")
    )
    pref_conf["publication_frequency"] = os.environ.get(
        "PREF_FREQUENCY", pref_conf.get("publication_frequency", "manual")
    )

    # --- Publication Platforms ---
    pub_conf = config_data["platforms"]

    # Dev.to
    devto_platform_conf = pub_conf.setdefault("devto", {})
    devto_api_key_env = os.environ.get("DEVTO_API_KEY")
    if devto_api_key_env:
        devto_platform_conf["api_key"] = devto_api_key_env
        logger.debug("Overrode Dev.to API key from environment variable.")

    # Twitter/X
    twitter_platform_conf = pub_conf.setdefault("twitter", {})
    twitter_api_key_env = os.environ.get("TWITTER_API_KEY")
    twitter_api_secret_env = os.environ.get("TWITTER_API_SECRET")
    twitter_access_token_env = os.environ.get("TWITTER_ACCESS_TOKEN")
    twitter_access_token_secret_env = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

    if twitter_api_key_env:
        twitter_platform_conf["api_key"] = twitter_api_key_env
        logger.debug("Overrode Twitter API key from environment variable.")
    if twitter_api_secret_env:
        twitter_platform_conf["api_secret"] = twitter_api_secret_env
        logger.debug("Overrode Twitter API secret from environment variable.")
    if twitter_access_token_env:
        twitter_platform_conf["access_token"] = twitter_access_token_env
        logger.debug("Overrode Twitter access token from environment variable.")
    if twitter_access_token_secret_env:
        twitter_platform_conf["access_token_secret"] = twitter_access_token_secret_env
        logger.debug("Overrode Twitter access token secret from environment variable.")

    # LinkedIn (Add similar logic if/when implemented)
    linkedin_platform_conf = pub_conf.setdefault("linkedin", {})
    linkedin_client_id_env = os.environ.get("LINKEDIN_CLIENT_ID")
    linkedin_client_secret_env = os.environ.get("LINKEDIN_CLIENT_SECRET")
    # ... add access token handling etc.
    if linkedin_client_id_env:
        linkedin_platform_conf["client_id"] = linkedin_client_id_env
    if linkedin_client_secret_env:
        linkedin_platform_conf["client_secret"] = linkedin_client_secret_env

    # --- Output Directories ---
    output_dir_conf = config_data["output_dirs"]
    output_dir_conf["base"] = os.environ.get(
        "OUTPUT_DIR_BASE", output_dir_conf.get("base", "output")
    )
    output_dir_conf["analysis"] = os.environ.get(
        "OUTPUT_DIR_ANALYSIS",
        output_dir_conf.get(
            "analysis", os.path.join(output_dir_conf["base"], "analysis")
        ),
    )
    output_dir_conf["interviews"] = os.environ.get(
        "OUTPUT_DIR_INTERVIEWS",
        output_dir_conf.get(
            "interviews", os.path.join(output_dir_conf["base"], "interviews")
        ),
    )
    output_dir_conf["content"] = os.environ.get(
        "OUTPUT_DIR_CONTENT",
        output_dir_conf.get(
            "content", os.path.join(output_dir_conf["base"], "content")
        ),
    )

    # Convert final config to Box for dot notation access
    config = Box(config_data, default_box=True, default_box_attr=None)

    logger.info("Configuration loaded successfully.")

    # Validation Check (Example: ensure LLM API key is present)
    if not config.llm.api_key:
        logger.warning("LLM_API_KEY environment variable not set. LLM calls may fail.")
    # Example platform validation
    if not config.platforms.devto.api_key:
        logger.warning("DEVTO_API_KEY not found in config or environment.")
    if not config.platforms.twitter.api_key:
        logger.warning("TWITTER_API_KEY not found in config or environment.")

    return config


# Global config object (Load once on import)
config = load_config()

# Example usage (can be removed or kept for testing):
if __name__ == "__main__":
    from build_influence.utils import setup_logging  # Corrected import path

    setup_logging()  # Setup logging first using the loaded config
    print("--- Configuration Summary ---")
    print(f"LLM Model: {config.llm.model}")
    print(f"Log Level: {config.logging.level}")
    print(f"Log File: {config.logging.file}")
    print(f"Dev.to API Key Set: {bool(config.publication.devto.api_key)}")
    print(f"Twitter API Key Set: {bool(config.publication.twitter.api_key)}")
    print(f"Default Approval: {config.preferences.approval_workflow}")
    print(f"Analysis Output Dir: {config.output_dirs.analysis}")
    print("---------------------------")
