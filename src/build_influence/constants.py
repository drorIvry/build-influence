from typing import Dict, Type

from build_influence.generation import (
    BaseContentGenerator,
    MarkdownGenerator,
    DevtoGenerator,
    TwitterGenerator,
    LinkedinGenerator,
)

# Mapping from platform name to Generator class
AVAILABLE_GENERATORS: Dict[str, Type[BaseContentGenerator]] = {
    "markdown": MarkdownGenerator,
    "devto": DevtoGenerator,
    "twitter": TwitterGenerator,
    "linkedin": LinkedinGenerator,
    # Add other generators here as they are created
}

# Default content types per platform
DEFAULT_CONTENT_TYPES = {
    "markdown": "announcement",
    "devto": "deepdive",
    "twitter": "thread_intro",
    "linkedin": "post_summary",
}
