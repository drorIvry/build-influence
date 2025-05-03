import httpx
from loguru import logger
import json  # For potential error parsing

# Note: Actual Twitter API interaction requires OAuth 1.0a or 2.0 auth.
# This implementation uses a Bearer Token (API Key) assumed for OAuth 2.0.
# Consider using requests-oauthlib or tweepy for complex auth flows.

from .base_publisher import BasePublisher, PublicationContent, PublishResult

TWITTER_API_URL_V2 = "https://api.twitter.com/2/tweets"


class TwitterPublisher(BasePublisher):
    """Publisher implementation for Twitter/X."""

    platform_name = "Twitter/X"

    def publish(
        self,
        content: PublicationContent,
        config: dict,
    ) -> PublishResult:
        """Publishes content to Twitter/X using its API v2 via Bearer Token."""
        # Extract the API key (Bearer Token) from the nested config
        twitter_config = config.get("twitter", {})
        api_key = twitter_config.get("api_key")

        if not api_key:
            log_msg = "Twitter API key not found in config['twitter']['api_key']."
            logger.error(log_msg)
            return PublishResult(
                success=False,
                message="Twitter API key missing.",
            )

        # Twitter API v2 expects JSON payload
        payload = {"text": content.body}

        # Construct headers with Bearer token
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "accept": "application/json",
        }

        tweet_preview = content.body[:100]  # For logging
        log_prefix = f"Publishing to {self.platform_name}"
        logger.info(f"{log_prefix}: '{tweet_preview}...'")

        with httpx.Client() as client:
            try:
                response = client.post(
                    TWITTER_API_URL_V2,
                    headers=headers,
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()

                # Success
                result_data = response.json()
                tweet_id = result_data.get("data", {}).get("id")
                # Placeholder URL, replace "user" with actual handle if available
                tweet_url = (
                    f"https://twitter.com/user/status/{tweet_id}" if tweet_id else None
                )

                success_msg = f"Published to {self.platform_name}. ID: {tweet_id}"
                logger.success(success_msg)
                return PublishResult(
                    success=True,
                    message=f"Published to {self.platform_name} successfully.",
                    url=tweet_url,
                )

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                base_error = f"Failed: {self.platform_name}. Status: {status_code}."
                error_message = base_error
                try:
                    error_detail = e.response.json()
                    if "errors" in error_detail:
                        details = json.dumps(error_detail["errors"])
                        error_message = f"{base_error} Details: {details}"
                    elif "detail" in error_detail:
                        detail_text = error_detail["detail"]
                        error_message = f"{base_error} Detail: {detail_text}"
                    else:
                        response_text = e.response.text
                        error_message = f"{base_error} Response: {response_text}"
                except Exception:
                    response_text = e.response.text  # Fallback if json parsing fails
                    error_message = f"{base_error} Response: {response_text}"
                logger.error(error_message)
                return PublishResult(success=False, message=error_message)

            except httpx.RequestError as e:
                error_message = f"Connection error ({self.platform_name}): {e}"
                logger.error(error_message)
                return PublishResult(success=False, message=error_message)

            except Exception as e:
                error_message = f"Unexpected error ({self.platform_name}): {e}"
                logger.exception(error_message)
                return PublishResult(success=False, message=error_message)
