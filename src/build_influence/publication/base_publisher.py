from abc import ABC, abstractmethod
from pydantic import BaseModel


class PublicationContent(BaseModel):
    """Model for the content to be published."""

    title: str | None = None  # Optional title (e.g., for blogs)
    body: str  # Main content body
    tags: list[str] = []  # Optional tags/keywords


class PublishResult(BaseModel):
    """Model for the result of a publication attempt."""

    success: bool
    message: str
    url: str | None = None  # URL of the published content if successful


class BasePublisher(ABC):
    """Abstract base class for content publishers."""

    platform_name: str = "Base"

    @abstractmethod
    def publish(self, content: PublicationContent, config: dict) -> PublishResult:
        """
        Publishes the given content to the specific platform.

        Args:
            content: The content to publish.
            config: Platform-specific configuration (e.g., API keys, tokens).

        Returns:
            A PublishResult indicating success/failure and an optional URL.
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"

    def __str__(self) -> str:
        return f"Publisher for {self.platform_name}"
