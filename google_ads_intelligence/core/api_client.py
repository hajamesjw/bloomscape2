"""Google Ads API client with rate limiting and error handling."""

from typing import Optional, List, Dict, Any, Generator
from datetime import date
import time

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ..config import Config, DEFAULT_CONFIG
from ..utils.logging import get_logger
from ..utils.dates import date_to_string

logger = get_logger(__name__)


class APIError(Exception):
    """Base API error."""
    pass


class RateLimitError(APIError):
    """Rate limit exceeded."""
    pass


class AuthenticationError(APIError):
    """Authentication failed."""
    pass


class GoogleAdsClient:
    """
    Google Ads API client with rate limiting, retry logic, and caching.

    This is a wrapper around the official google-ads Python library that adds:
    - Automatic retry with exponential backoff
    - Rate limit tracking
    - Response caching
    - Structured logging
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or DEFAULT_CONFIG
        self._client = None
        self._operations_today = 0
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}

    def _get_client(self):
        """Lazily initialize the Google Ads client."""
        if self._client is None:
            try:
                from google.ads.googleads.client import GoogleAdsClient as GAClient

                credentials = {
                    "developer_token": self.config.developer_token,
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "refresh_token": self.config.refresh_token,
                    "use_proto_plus": True,
                }

                if self.config.login_customer_id:
                    credentials["login_customer_id"] = self.config.login_customer_id

                self._client = GAClient.load_from_dict(credentials)
                logger.info("Google Ads client initialized")
            except ImportError:
                logger.warning("google-ads library not installed, using mock client")
                self._client = MockGoogleAdsClient()
            except Exception as e:
                logger.error("Failed to initialize Google Ads client", error=str(e))
                raise AuthenticationError(f"Failed to initialize client: {e}")

        return self._client

    def _check_rate_limit(self):
        """Check if we're within rate limits."""
        if self._operations_today >= self.config.api.MAX_OPERATIONS_PER_DAY:
            raise RateLimitError("Daily API operation limit reached")

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if cache_key in self._cache:
            timestamp = self._cache_timestamps.get(cache_key, 0)
            if time.time() - timestamp < self.config.api.CACHE_TTL_SECONDS:
                logger.debug("Cache hit", key=cache_key)
                return self._cache[cache_key]
            else:
                # Expired
                del self._cache[cache_key]
                del self._cache_timestamps[cache_key]
        return None

    def _set_cache(self, cache_key: str, value: Any):
        """Set value in cache."""
        self._cache[cache_key] = value
        self._cache_timestamps[cache_key] = time.time()

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        retry=retry_if_exception_type((RateLimitError, ConnectionError)),
    )
    def execute_query(
        self,
        query: str,
        customer_id: Optional[str] = None,
        use_cache: bool = True,
    ) -> List[Any]:
        """
        Execute a GAQL query.

        Args:
            query: Google Ads Query Language query
            customer_id: Customer ID (uses config default if not provided)
            use_cache: Whether to use caching

        Returns:
            List of row results
        """
        self._check_rate_limit()

        customer_id = customer_id or self.config.customer_id
        cache_key = f"{customer_id}:{hash(query)}"

        if use_cache:
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                return cached

        client = self._get_client()

        try:
            ga_service = client.get_service("GoogleAdsService")
            response = ga_service.search(customer_id=customer_id, query=query)

            results = list(response)
            self._operations_today += 1

            if use_cache:
                self._set_cache(cache_key, results)

            logger.info(
                "Query executed",
                customer_id=customer_id,
                result_count=len(results),
                operations_today=self._operations_today,
            )

            return results

        except Exception as e:
            error_str = str(e)
            if "RATE_EXCEEDED" in error_str:
                logger.warning("Rate limit hit, will retry", error=error_str)
                raise RateLimitError(error_str)
            elif "AUTHENTICATION" in error_str or "AUTHORIZATION" in error_str:
                raise AuthenticationError(error_str)
            else:
                logger.error("Query failed", error=error_str, query=query[:100])
                raise APIError(error_str)

    def execute_query_stream(
        self,
        query: str,
        customer_id: Optional[str] = None,
    ) -> Generator[Any, None, None]:
        """
        Execute a GAQL query with streaming (for large result sets).

        Args:
            query: Google Ads Query Language query
            customer_id: Customer ID

        Yields:
            Row results one at a time
        """
        self._check_rate_limit()

        customer_id = customer_id or self.config.customer_id
        client = self._get_client()

        try:
            ga_service = client.get_service("GoogleAdsService")
            stream = ga_service.search_stream(customer_id=customer_id, query=query)

            for batch in stream:
                for row in batch.results:
                    yield row

            self._operations_today += 1

        except Exception as e:
            logger.error("Stream query failed", error=str(e))
            raise APIError(str(e))

    def mutate(
        self,
        operations: List[Dict[str, Any]],
        customer_id: Optional[str] = None,
        partial_failure: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute mutate operations (create/update/remove).

        Args:
            operations: List of operation dictionaries
            customer_id: Customer ID
            partial_failure: Whether to allow partial failures

        Returns:
            Mutation response with results
        """
        self._check_rate_limit()

        customer_id = customer_id or self.config.customer_id
        client = self._get_client()

        # Batch operations if needed
        batch_size = self.config.api.MAX_BATCH_SIZE
        all_results = []

        for i in range(0, len(operations), batch_size):
            batch = operations[i:i + batch_size]

            try:
                ga_service = client.get_service("GoogleAdsService")
                response = ga_service.mutate(
                    customer_id=customer_id,
                    mutate_operations=batch,
                    partial_failure=partial_failure,
                )

                all_results.extend(response.mutate_operation_responses)
                self._operations_today += 1

                logger.info(
                    "Mutate executed",
                    customer_id=customer_id,
                    operation_count=len(batch),
                    batch_index=i // batch_size,
                )

            except Exception as e:
                logger.error("Mutate failed", error=str(e), batch_index=i // batch_size)
                raise APIError(str(e))

        return {"results": all_results, "total_operations": len(operations)}

    def get_customer_id(self) -> str:
        """Get the configured customer ID."""
        return self.config.customer_id


class MockGoogleAdsClient:
    """Mock client for testing without API credentials."""

    def get_service(self, service_name: str):
        return MockService()


class MockService:
    """Mock service that returns empty results."""

    def search(self, customer_id: str, query: str):
        logger.warning("Using mock client - no real data")
        return []

    def search_stream(self, customer_id: str, query: str):
        logger.warning("Using mock client - no real data")
        return []

    def mutate(self, customer_id: str, mutate_operations: list, partial_failure: bool):
        logger.warning("Using mock client - no mutations executed")
        return type("Response", (), {"mutate_operation_responses": []})()
