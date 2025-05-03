import httpx
from loguru import logger

from .base_publisher import BasePublisher, PublicationContent, PublishResult

DEVTO_API_URL = "https://dev.to/api/articles"


class DevToPublisher(BasePublisher):
    """Publisher implementation for Dev.to."""

    platform_name = "Dev.to"

    def publish(
        self,
        content: PublicationContent,
        config: dict,
    ) -> PublishResult:
        """Publishes content to Dev.to using its API."""
        # Extract API key from nested config
        devto_config = config.get("platforms", {}).get("devto", {})
        api_key = devto_config.get("api_key")

        if not api_key:
            log_msg = (
                "Dev.to API key not found in config['platforms']['devto']['api_key']."
            )
            logger.error(log_msg)
            return PublishResult(
                success=False,
                message="Dev.to API key missing.",
            )

        headers = {
            "api-key": api_key,
            "Content-Type": "application/json",
            # As per Dev.to docs
            "accept": "application/vnd.forem.api-v1+json",
        }

        # Dev.to requires a title, use default if none provided
        title = content.title or "Untitled Post"

        # Dev.to expects the body in markdown format
        payload = {
            "article": {
                "title": title,
                "body_markdown": content.body,
                "published": True,  # Or False for draft
                "tags": content.tags,
                # Add optional fields like series, canonical_url if needed
            }
        }

        logger.info(f"Publishing article '{title}' to {self.platform_name}...")
        with httpx.Client() as client:
            try:
                response = client.post(
                    DEVTO_API_URL, headers=headers, json=payload, timeout=30.0
                )
                # Raise HTTPStatusError for bad responses (4xx or 5xx)
                response.raise_for_status()

                # Success
                result_data = response.json()
                article_url = result_data.get("url")
                success_log = f"Published to {self.platform_name}: {article_url}"
                logger.success(success_log)
                return PublishResult(
                    success=True,
                    message=f"Published to {self.platform_name} successfully.",
                    url=article_url,
                )

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                base_error = f"Failed: {self.platform_name}. Status: {status_code}."
                error_message = base_error
                try:
                    # Try to get more specific error details from response body
                    error_content = e.response.json()
                    error_detail = error_content.get("error", "No details.")
                    error_message += f" Details: {error_detail}"
                except Exception:
                    response_text = e.response.text  # Fallback if json parse fails
                    error_message += f" Response: {response_text}"
                logger.error(error_message)
                return PublishResult(success=False, message=error_message)

            except httpx.RequestError as e:
                error_message = f"Connection error ({self.platform_name}): {e}"
                logger.error(error_message)
                return PublishResult(success=False, message=error_message)

            except Exception as e:
                error_message = f"Unexpected error ({self.platform_name}): {e}"
                # Log stack trace for unexpected errors
                logger.exception(error_message)
                return PublishResult(success=False, message=error_message)
