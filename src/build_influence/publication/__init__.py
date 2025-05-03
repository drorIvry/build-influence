# Publication module

from typing import Type

from .base_publisher import BasePublisher, PublicationContent, PublishResult
from .linkedin_publisher import LinkedInPublisher
from .devto_publisher import DevToPublisher
from .twitter_publisher import TwitterPublisher

# Dictionary mapping platform names (lowercase) to publisher classes
_publisher_map = {
    "linkedin": LinkedInPublisher,
    "dev.to": DevToPublisher,
    "devto": DevToPublisher,  # Alias
    "twitter": TwitterPublisher,
    "x": TwitterPublisher,  # Alias
}


def get_publisher(platform_name: str) -> BasePublisher | None:
    """Factory function to get a publisher instance for the platform name."""
    publisher_class: Type[BasePublisher] | None = _publisher_map.get(
        platform_name.lower()
    )
    if publisher_class:
        return publisher_class()
    return None


__all__ = [
    "PublicationContent",
    "PublishResult",
    "LinkedInPublisher",
    "DevToPublisher",
    "TwitterPublisher",
    "get_publisher",
]
