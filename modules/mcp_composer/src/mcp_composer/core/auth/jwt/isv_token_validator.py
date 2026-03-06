"""
ISV Token Validator for IBM Solis Platform Authentication.

This module provides ISV (Independent Software Vendor) token validation
for the Solis Composer. It extracts platform session cookies from incoming
requests and exchanges them for ISV tokens via IBM's authentication service.

Environment-based configuration:
- test: Cookie 'mcsp-glb-iam-test', URL 'https://aws.login.test.saas.ibm.com/...'
- dev: Cookie 'mcsp-glb-iam-dev', URL 'https://aws.login.dev.saas.ibm.com/...'
- prod: Cookie 'mcsp-glb-iam', URL 'https://aws.login.saas.ibm.com/...'
"""

import os
import time
import httpx
from typing import Optional, Dict, Any, Tuple, List
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.authentication import AuthenticationBackend, AuthCredentials, BaseUser
from starlette.requests import HTTPConnection
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken
from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()


class ISVUser(AuthenticatedUser):
    """User object for ISV authenticated requests, compatible with MCP's AuthenticatedUser."""

    def __init__(self, token_data: Dict[str, Any]):
        # Create an AccessToken object for MCP compatibility
        access_token_obj = AccessToken(
            token=token_data.get("access_token", ""),
            client_id="isv-authenticated-client",
            scopes=["authenticated"],
            expires_at=int(time.time()) + token_data.get("expires_in", 7200),
        )

        # Initialize parent AuthenticatedUser
        super().__init__(access_token_obj)
        self.token_data = token_data


class ISVAuthBackend(AuthenticationBackend):
    """Authentication backend for ISV token validation."""

    def __init__(self, validator: "ISVTokenValidator"):
        self.validator = validator

    async def authenticate(self, conn: HTTPConnection) -> Optional[Tuple[AuthCredentials, BaseUser]]:
        """
        Authenticate the request using ISV token validation.

        Args:
            conn: HTTP connection

        Returns:
            Tuple of (credentials, user) or None if authentication fails
        """
        # Log incoming request details
        logger.info("=" * 80)
        logger.info("INCOMING REQUEST")
        logger.info("=" * 80)

        # Access request properties through conn.scope
        scope = conn.scope
        logger.info("Method: %s", scope.get("method", "N/A"))
        logger.info("Path: %s", scope.get("path", "N/A"))
        logger.info("Query String: %s", scope.get("query_string", b"").decode("utf-8"))
        logger.info("Client: %s", scope.get("client", "N/A"))
        logger.info("Server: %s", scope.get("server", "N/A"))

        # Log all headers
        logger.info("-" * 80)
        logger.info("REQUEST HEADERS:")
        logger.info("-" * 80)
        headers = dict(scope.get("headers", []))
        for header_name_bytes, header_value_bytes in headers.items():
            header_name = (
                header_name_bytes.decode("utf-8") if isinstance(header_name_bytes, bytes) else str(header_name_bytes)
            )
            header_value = (
                header_value_bytes.decode("utf-8") if isinstance(header_value_bytes, bytes) else str(header_value_bytes)
            )

            # Redact sensitive headers
            if header_name.lower() in ["authorization", "cookie"]:
                # Show only first/last few characters
                if len(header_value) > 20:
                    redacted = f"{header_value[:10]}...{header_value[-10:]}"
                else:
                    redacted = "***REDACTED***"
                logger.info("%s: %s", header_name, redacted)
            else:
                logger.info("%s: %s", header_name, header_value)

        logger.info("=" * 80)

        try:
            # Validate request and get token
            token_data = await self.validator.validate_request(conn)

            # Create user object
            user = ISVUser(token_data)

            # Return credentials and user
            credentials = AuthCredentials(["authenticated"])
            logger.info("✓ Authentication successful")
            logger.info("=" * 80)
            return credentials, user

        except Exception as e:
            logger.warning("✗ Authentication failed: %s", str(e))
            logger.info("=" * 80)
            raise


class ISVEnvironmentConfig:
    """
    Environment-specific configuration for ISV authentication.

    Configuration can be customized via environment variables:
    - ISV_COOKIE_NAME: Override the cookie name (optional)
    - ISV_ENDPOINT_URL: Override the endpoint URL (optional)
    - ISV_ENVIRONMENT: Set environment (test/dev/prod) for defaults

    If custom values are not provided, defaults are determined by environment.
    """

    BASE_URL_TEMPLATE = "https://aws.login.{env}.saas.ibm.com/security/auth/isv/token"
    PROD_URL = "https://aws.login.saas.ibm.com/security/auth/isv/token"

    def __init__(
        self, environment: str = "test", cookie_name: Optional[str] = None, endpoint_url: Optional[str] = None
    ):
        """
        Initialize environment configuration.

        Args:
            environment: Deployment environment ('test', 'dev', or 'prod')
            cookie_name: Override cookie name (uses environment variable ISV_COOKIE_NAME or auto-determined)
            endpoint_url: Override endpoint URL (uses environment variable ISV_ENDPOINT_URL or auto-determined)
        """

        self.environment = environment.lower()

        # Cookie name: Priority order: 1) Parameter, 2) Env var, 3) Auto-determined
        self.cookie_name = cookie_name or os.getenv("ISV_COOKIE_NAME") or self._get_default_cookie_name()

        # Endpoint URL: Priority order: 1) Parameter, 2) Env var, 3) Auto-determined
        self.endpoint_url = endpoint_url or os.getenv("ISV_ENDPOINT_URL") or self._get_default_endpoint_url()

        logger.info(
            "ISV Environment Config: env=%s, cookie=%s, url=%s", self.environment, self.cookie_name, self.endpoint_url
        )

    def _get_default_cookie_name(self) -> str:
        """
        Get default platform session cookie name based on environment.

        Returns:
            Cookie name string:
            - 'mcsp-glb-iam' for prod
            - 'mcsp-glb-iam-{env}' for test/dev
        """
        if self.environment == "prod":
            return "mcsp-glb-iam"
        return f"mcsp-glb-iam-{self.environment}"

    def _get_default_endpoint_url(self) -> str:
        """
        Get default ISV token endpoint URL based on environment.

        Returns:
            Environment-specific ISV token endpoint URL
        """
        if self.environment == "prod":
            return self.PROD_URL
        return self.BASE_URL_TEMPLATE.format(env=self.environment)


class ISVTokenCache:
    """
    Thread-safe token cache with TTL-based expiration.

    Caches ISV tokens and user instances to reduce API calls to the authentication service.
    Tokens are stored with their expiration time and automatically
    invalidated when expired.
    """

    def __init__(self, ttl: int = 7200):
        """
        Initialize token cache.

        Args:
            ttl: Time-to-live in seconds (default: 7200 = 2 hours)
        """
        self._cache: Dict[str, Tuple[str, float]] = {}
        self._instance_cache: Dict[str, Tuple[List[Dict[str, Any]], float]] = {}
        self.ttl = ttl
        logger.debug("ISV Token Cache initialized with TTL: %d seconds", ttl)

    def get(self, session_id: str) -> Optional[str]:
        """
        Get cached token if valid.

        Args:
            session_id: Platform session ID (cache key)

        Returns:
            Cached access token or None if not found/expired
        """
        if session_id in self._cache:
            token, expiry = self._cache[session_id]
            current_time = time.time()

            if current_time < expiry:
                remaining = int(expiry - current_time)
                logger.debug("Using cached ISV token (expires in %d seconds)", remaining)
                return token

            # Token expired, remove from cache
            del self._cache[session_id]
            logger.debug("Cached token expired, removed from cache")

        return None

    def set(self, session_id: str, token: str, expires_in: int):
        """
        Cache token with expiration.

        Args:
            session_id: Platform session ID (cache key)
            token: ISV access token
            expires_in: Token lifetime in seconds from ISV response
        """
        # Use the minimum of ISV expires_in and configured TTL
        effective_ttl = min(expires_in, self.ttl)
        expiry = time.time() + effective_ttl

        self._cache[session_id] = (token, expiry)
        logger.debug("Cached ISV token (TTL: %d seconds, expires at: %.0f)", effective_ttl, expiry)

    def get_instances(self, session_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached user instances if valid.

        Args:
            session_id: Platform session ID (cache key)

        Returns:
            Cached user instances list or None if not found/expired
        """
        if session_id in self._instance_cache:
            instances, expiry = self._instance_cache[session_id]
            current_time = time.time()

            if current_time < expiry:
                remaining = int(expiry - current_time)
                logger.debug("Using cached user instances (expires in %d seconds)", remaining)
                return instances

            # Instances expired, remove from cache
            del self._instance_cache[session_id]
            logger.debug("Cached instances expired, removed from cache")

        return None

    def set_instances(self, session_id: str, instances: List[Dict[str, Any]], expires_in: int):
        """
        Cache user instances with expiration.

        Args:
            session_id: Platform session ID (cache key)
            instances: User instances data (list of instance dicts)
            expires_in: Cache lifetime in seconds
        """
        # Use the minimum of provided expires_in and configured TTL
        effective_ttl = min(expires_in, self.ttl)
        expiry = time.time() + effective_ttl

        self._instance_cache[session_id] = (instances, expiry)
        logger.debug("Cached user instances (TTL: %d seconds, expires at: %.0f)", effective_ttl, expiry)

    def clear(self):
        """Clear all cached tokens and instances."""
        token_count = len(self._cache)
        instance_count = len(self._instance_cache)
        self._cache.clear()
        self._instance_cache.clear()
        logger.debug("Cleared %d cached tokens and %d cached instances", token_count, instance_count)


class ISVTokenValidator:
    """
    Validates requests using IBM ISV token authentication.

    This class handles the complete authentication flow:
    1. Extract platform session cookie from request
    2. Check cache for valid token
    3. Exchange cookie for ISV token if needed
    4. Return validated token or raise appropriate HTTP error
    """

    def __init__(
        self,
        environment: str = "test",
        cache_enabled: bool = True,
        cache_ttl: int = 7200,
        timeout: float = 30.0,
        fetch_instances: bool = True,
    ):
        """
        Initialize ISV token validator.

        Args:
            environment: Deployment environment ('test', 'dev', 'prod')
            cache_enabled: Enable token caching
            cache_ttl: Cache time-to-live in seconds
            timeout: HTTP request timeout in seconds
            fetch_instances: Enable automatic user instance fetching during authentication
        """
        self.config = ISVEnvironmentConfig(environment)
        self.cache = ISVTokenCache(cache_ttl) if cache_enabled else None
        self.timeout = timeout
        self.fetch_instances = fetch_instances

        # TEMPORARY: Use stable test Instance API for dev and stage environments
        # TODO: Remove this workaround once dev and stage Instance APIs are stable
        # Currently dev/stage Instance APIs return GraphQL errors, so we default to test
        if environment.lower() in ["dev", "stage"]:
            default_instance_url = "https://api.solis.test.saas.ibm.com/api/graphql"
            logger.warning(
                "TEMPORARY: Using test Instance API for %s environment due to instability. "
                "This should be removed once %s Instance API is stable.",
                environment,
                environment
            )
        else:
            # For test and prod, use their respective Instance APIs
            default_instance_url = f"https://api.solis.{environment.lower()}.saas.ibm.com/api/graphql" if environment.lower() == "test" else "https://api.solis.saas.ibm.com/api/graphql"
        
        self.instance_api_url = os.getenv("ISV_INSTANCE_API_URL", default_instance_url)

        # Derive the correct cookie name for the Instance API environment
        # This is critical: the cookie name must match the API environment, not the ISV token environment
        self.instance_cookie_name = self._derive_cookie_name_from_url(self.instance_api_url)

        logger.info("=" * 60)
        logger.info("ISV Token Validator Initialized")
        logger.info("=" * 60)
        logger.info("Environment: %s", environment)
        logger.info("ISV Token Cookie name: %s", self.config.cookie_name)
        logger.info("ISV Token Endpoint URL: %s", self.config.endpoint_url)
        logger.info("Instance API URL: %s", self.instance_api_url)
        logger.info("Instance API Cookie name: %s", self.instance_cookie_name)
        logger.info("Cache enabled: %s", cache_enabled)
        if cache_enabled:
            logger.info("Cache TTL: %d seconds", cache_ttl)
        logger.info("Fetch instances: %s", fetch_instances)
        logger.info("Request timeout: %.1f seconds", timeout)
        logger.info("=" * 60)

    def _derive_cookie_name_from_url(self, api_url: str) -> str:
        """
        Derive the correct cookie name from the Instance API URL.

        This is critical for cross-environment scenarios where:
        - ISV token endpoint is in one environment (e.g., dev)
        - Instance API is in another environment (e.g., test for stability)

        Args:
            api_url: The Instance API URL

        Returns:
            Cookie name matching the API environment

        Examples:
            >>> validator._derive_cookie_name_from_url("https://api.solis.test.saas.ibm.com/api/graphql")
            'mcsp-glb-iam-test'
            >>> validator._derive_cookie_name_from_url("https://api.solis.dev.saas.ibm.com/api/graphql")
            'mcsp-glb-iam-dev'
            >>> validator._derive_cookie_name_from_url("https://api.solis.prod.saas.ibm.com/api/graphql")
            'mcsp-glb-iam'
        """
        # Extract environment from URL
        if ".test.saas.ibm.com" in api_url:
            return "mcsp-glb-iam-test"
        elif ".dev.saas.ibm.com" in api_url:
            return "mcsp-glb-iam-dev"
        elif ".prod.saas.ibm.com" in api_url or "api.solis.saas.ibm.com" in api_url:
            return "mcsp-glb-iam"
        else:
            # Default to test for unknown URLs
            logger.warning("Could not determine environment from URL: %s, defaulting to test", api_url)
            return "mcsp-glb-iam-test"

    def extract_session_cookie(self, cookie_header: str) -> Optional[str]:
        """
        Extract platform session cookie from Cookie header.

        Args:
            cookie_header: Raw Cookie header value from request

        Returns:
            Session ID or None if not found

        Example:
            >>> validator = ISVTokenValidator('test')
            >>> header = "session=abc; mcsp-glb-iam-test=xyz123; other=val"
            >>> validator.extract_session_cookie(header)
            'xyz123'
        """
        if not cookie_header:
            logger.debug("Cookie header is empty")
            return None

        # Parse cookies from header
        cookies = {}
        for cookie in cookie_header.split(";"):
            cookie = cookie.strip()
            if "=" in cookie:
                name, value = cookie.split("=", 1)
                cookies[name.strip()] = value.strip()

        session_id = cookies.get(self.config.cookie_name)

        if session_id:
            logger.debug("Extracted session cookie '%s' (length: %d)", self.config.cookie_name, len(session_id))
        else:
            logger.warning(
                "Session cookie '%s' not found in request. Available cookies: %s",
                self.config.cookie_name,
                list(cookies.keys()),
            )

        return session_id

    async def exchange_cookie_for_token(self, session_id: str) -> Dict[str, Any]:
        """
        Exchange platform session cookie for ISV token.

        Makes a POST request to the ISV token endpoint with the session cookie.

        Args:
            session_id: Platform session ID from cookie (required)

        Returns:
            ISV token response dict with 'access_token', 'token_type', 'expires_in'

        Raises:
            HTTPException(403): Authentication failed
            HTTPException(503): Service unavailable
        """
        request_body = {"grant_type": "urn:ibm:params:oauth:grant-type:isv-cookie", "cookie": session_id}

        logger.info("Exchanging cookie for ISV token")
        logger.debug("ISV endpoint: %s", self.config.endpoint_url)
        logger.debug("Request body: %s", {**request_body, "cookie": "***REDACTED***"})

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.config.endpoint_url,
                    json=request_body,
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                )

                logger.debug("ISV response status: %d", response.status_code)

                # Parse response
                try:
                    response_data = response.json()
                except Exception as e:
                    logger.error("Failed to parse ISV response as JSON: %s", e)
                    logger.debug("Response text: %s", response.text[:500])
                    from starlette.exceptions import HTTPException

                    raise HTTPException(status_code=503, detail="Invalid response from authentication service")

                # Check for success response
                if response.status_code == 200 and "access_token" in response_data:
                    logger.info("ISV token obtained successfully")
                    logger.debug(
                        "Token type: %s, expires in: %d seconds",
                        response_data.get("token_type", "Bearer"),
                        response_data.get("expires_in", 0),
                    )
                    return response_data

                # Handle error responses
                error_msg = response_data.get("message", "Authentication failed")
                success = response_data.get("success", None)

                logger.warning(
                    "ISV token exchange failed: status=%d, success=%s, message=%s",
                    response.status_code,
                    success,
                    error_msg,
                )

                from starlette.exceptions import HTTPException

                raise HTTPException(status_code=403, detail=f"Authentication failed: {error_msg}")

        except httpx.TimeoutException:
            logger.error("ISV endpoint timeout after %.1f seconds", self.timeout)
            from starlette.exceptions import HTTPException

            raise HTTPException(status_code=503, detail="Authentication service unavailable (timeout)")
        except httpx.RequestError as e:
            logger.error("ISV endpoint request error: %s", e)
            from starlette.exceptions import HTTPException

            raise HTTPException(status_code=503, detail="Authentication service unavailable")

    async def fetch_user_instances(
        self, session_cookie: str, filter_by_product_id: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch user instances using the platform session cookie via GraphQL API.

        Fetches only essential fields and returns a flattened list of instances.
        Each instance contains:
        - id: Instance identifier
        - subscriptionId: Subscription identifier
        - name: Instance name
        - dashboardURL: URL to access the instance dashboard
        - subscription: Nested object with subscriptionName and productId

        Args:
            session_cookie: Platform session cookie value
            filter_by_product_id: Optional list of product IDs to filter

        Returns:
            Flattened list of user instances with essential fields only

        Example Response:
            [
                {
                    "id": "20251128-1445-2831-7084-4a9a364b8b6b",
                    "subscriptionId": "20240430-2249-3023-2003-c61c1ea9c579",
                    "name": "solisams",
                    "dashboardURL": "https://console-aws-cacentral1.lakehouse.dev.saas.ibm.com/...",
                    "subscription": {
                        "subscriptionName": "watsonx.data",
                        "productId": "lakehouse"
                    }
                },
                {
                    "id": "20260116-2134-3895-9036-5d9421c3f567",
                    "subscriptionId": "20260116-2133-4804-900c-3c7949c207e6",
                    "name": "SolisDemo",
                    "dashboardURL": "https://rel03.rel.guardium.security.ibm.com?...",
                    "subscription": {
                        "subscriptionName": "Guardium Data Security Center SaaS",
                        "productId": "gi"
                    }
                }
            ]
        """
        # Validate session cookie
        if not session_cookie:
            logger.warning("Empty session cookie provided")
            return []

        # GraphQL query - products is a JSON field, not an object
        query = """
        query GetInstances($filterByProductId: [String!]) {
            getInstances(filterByProductId: $filterByProductId) {
                cohort
                products
            }
        }
        """

        # Variables (empty if no filter)
        variables: Dict[str, Any] = {}
        if filter_by_product_id:
            variables["filterByProductId"] = filter_by_product_id

        logger.info("Fetching user instances from Solis API")
        logger.debug("Instance API URL: %s", self.instance_api_url)
        logger.debug("Instance API Cookie name: %s", self.instance_cookie_name)
        logger.debug("Filter by product IDs: %s", filter_by_product_id)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.instance_api_url,
                    json={"query": query, "variables": variables},
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        # CRITICAL: Use the cookie name that matches the Instance API environment
                        "Cookie": f"{self.instance_cookie_name}={session_cookie}",
                    },
                )

                logger.debug("Instance API response status: %d", response.status_code)

                if response.status_code == 200:
                    data = response.json()

                    # Check for GraphQL errors
                    if "errors" in data:
                        logger.error("GraphQL errors in response: %s", data["errors"])
                        return []

                    # Extract instances from response
                    get_instances = data.get("data", {}).get("getInstances", [])

                    if not get_instances:
                        logger.warning("No instances returned from API")
                        return []

                    # Flatten the nested structure into a simple array
                    # Response structure: [{"cohort": "...", "products": {"productId": [instances]}}]
                    flattened_instances = []

                    for cohort_group in get_instances:
                        products_by_id = cohort_group.get("products", {})

                        # Iterate through each product type (lakehouse, gi, etc.)
                        for product_id, instances_list in products_by_id.items():
                            if isinstance(instances_list, list):
                                for instance in instances_list:
                                    # Extract essential fields with nested subscription
                                    subscription_data = instance.get("subscription", {})
                                    flattened_instance = {
                                        "id": instance.get("id"),
                                        "state": instance.get(
                                            "state", "active"
                                        ),  # Include state field, default to "active"
                                        "subscriptionId": instance.get("subscriptionId"),
                                        "name": instance.get("name"),
                                        "dashboardURL": instance.get("dashboardURL"),
                                        "subscription": {
                                            "subscriptionName": subscription_data.get("subscriptionName"),
                                            "productId": subscription_data.get("productId", product_id),
                                        },
                                    }
                                    flattened_instances.append(flattened_instance)

                    logger.info("Successfully fetched and flattened %d user instances", len(flattened_instances))
                    logger.debug(
                        "Flattened instances: %s",
                        flattened_instances[:2] if len(flattened_instances) > 2 else flattened_instances,
                    )

                    return flattened_instances
                else:
                    logger.error("Failed to fetch instances: status=%d", response.status_code)
                    logger.debug("Response: %s", response.text[:500])
                    return []

        except httpx.TimeoutException:
            logger.error("Instance API timeout after %.1f seconds", self.timeout)
            return []
        except httpx.RequestError as e:
            logger.error("Instance API request error: %s", e)
            return []
        except Exception as e:
            logger.error("Failed to fetch user instances: %s", e)
            return []

    async def validate_request(self, request) -> Dict[str, Any]:
        """
        Validate incoming request and return ISV token with user instances.

        Complete validation flow:
        1. Extract Cookie header from request
        2. Parse and find platform session cookie
        3. Check cache for valid token and instances
        4. Exchange cookie for ISV token if needed
        5. Fetch user instances if enabled
        6. Cache the token and instances
        7. Return combined token and instance data

        Args:
            request: Incoming HTTP request object

        Returns:
            Dict with 'access_token', 'token_type', 'expires_in', 'user_instances', and optionally 'cached'

        Raises:
            HTTPException(401): Missing or invalid cookie
            HTTPException(403): Authentication failed
            HTTPException(503): Service unavailable
        """
        logger.debug("Validating ISV token request with instance fetching: %s", self.fetch_instances)

        # Extract Cookie header or check for custom header
        cookie_header = request.headers.get("cookie", "")
        session_id = None

        if cookie_header:
            # Extract session cookie from Cookie header
            session_id = self.extract_session_cookie(cookie_header)
        else:
            # Check if session ID is sent as a custom header (alternative method)
            session_id = request.headers.get(self.config.cookie_name, "")
            if not session_id:
                logger.warning("Missing required cookie: %s", self.config.cookie_name)
                from starlette.exceptions import HTTPException

                raise HTTPException(
                    status_code=401, detail=f"Missing Cookie header or '{self.config.cookie_name}' header"
                )

        if not session_id:
            logger.warning("Missing platform session cookie: %s", self.config.cookie_name)
            from starlette.exceptions import HTTPException

            raise HTTPException(status_code=401, detail=f"Missing platform session cookie: {self.config.cookie_name}")

        # Check cache for token
        token_cached = False
        if self.cache:
            cached_token = self.cache.get(session_id)
            if cached_token:
                logger.debug("Using cached ISV token")
                token_response = {"access_token": cached_token, "token_type": "Bearer", "cached": True}
                token_cached = True
            else:
                # Exchange cookie for ISV token
                token_response = await self.exchange_cookie_for_token(session_id)
                # Cache the token
                if "expires_in" in token_response:
                    self.cache.set(session_id, token_response["access_token"], token_response["expires_in"])
                token_response["cached"] = False
        else:
            # No cache, exchange directly
            token_response = await self.exchange_cookie_for_token(session_id)
            token_response["cached"] = False

        # Fetch user instances if enabled
        user_instances: List[Dict[str, Any]] = []
        if self.fetch_instances:
            # Check cache for instances
            if self.cache:
                cached_instances = self.cache.get_instances(session_id)
                if cached_instances:
                    logger.debug("Using cached user instances")
                    user_instances = cached_instances  # type: ignore
                else:
                    # Fetch fresh instances
                    user_instances = await self.fetch_user_instances(session_id)

                    # Cache instances (same TTL as token)
                    if user_instances and "expires_in" in token_response:
                        expires_in = token_response.get("expires_in", 7200)
                        # Ensure expires_in is an integer
                        if isinstance(expires_in, (int, float)):
                            self.cache.set_instances(
                                session_id,
                                user_instances,  # type: ignore
                                int(expires_in),
                            )
            else:
                # No cache, fetch directly
                user_instances = await self.fetch_user_instances(session_id)

        # Add instances to response
        token_response["user_instances"] = user_instances  # type: ignore

        if user_instances:
            logger.info("Authentication complete with %d user instances", len(user_instances))
        else:
            logger.info("Authentication complete (no instances fetched)")

        return token_response


class ISVTokenVerifier:
    """
    FastMCP-compatible ISV token verifier.

    This class wraps ISVTokenValidator to provide a callable interface
    compatible with FastMCP's authentication system. It can be passed
    directly to MCPComposer's auth parameter.

    Example:
        >>> verifier = ISVTokenVerifier(environment='test')
        >>> composer = MCPComposer(name='my-app', auth=verifier)
    """

    def __init__(
        self,
        environment: str = "test",
        cache_enabled: bool = True,
        cache_ttl: int = 7200,
        timeout: float = 30.0,
        required_scopes: Optional[List[str]] = None,
        fetch_instances: bool = True,
    ):
        """
        Initialize ISV token verifier.

        NOTE: This class is maintained for backward compatibility but is deprecated
        for new implementations. For tool-level authentication, use ISVTokenValidator
        directly with ToolAuthenticationMiddleware.

        Args:
            environment: Deployment environment ('test', 'dev', 'prod')
            cache_enabled: Enable token caching
            cache_ttl: Cache time-to-live in seconds
            timeout: HTTP request timeout in seconds
            required_scopes: List of OAuth scopes required for requests (optional)
            fetch_instances: Enable automatic user instance fetching during authentication
        """
        self.validator = ISVTokenValidator(
            environment=environment,
            cache_enabled=cache_enabled,
            cache_ttl=cache_ttl,
            timeout=timeout,
            fetch_instances=fetch_instances,
        )

        # Required by FastMCP's AuthProvider interface
        self.required_scopes = required_scopes or []
        self.base_url = None

        logger.info("ISVTokenVerifier ready for FastMCP integration")

    def get_middleware(self) -> List[Middleware]:
        """
        Get HTTP application-level middleware for ISV authentication.

        This method is required by FastMCP to integrate authentication
        into the HTTP application. We use our custom ISVAuthBackend
        instead of the default BearerAuthBackend.

        NOTE: This returns connection-level authentication middleware.
        For tool-level authentication, use ToolAuthenticationMiddleware instead
        and pass auth=None to MCPComposer.

        Returns:
            List of Starlette Middleware instances
        """
        from mcp.server.auth.middleware.auth_context import AuthContextMiddleware

        return [
            Middleware(AuthenticationMiddleware, backend=ISVAuthBackend(self.validator)),
            Middleware(AuthContextMiddleware),
        ]

    def get_routes(self, mcp_path: str = "/mcp"):
        """
        Get authentication routes for FastMCP integration.

        This method is required by FastMCP's SSE transport to set up
        authentication routes. For ISV token authentication, we don't
        need additional routes as authentication is handled via cookies
        in the request headers.

        Args:
            mcp_path: Base path for MCP endpoints

        Returns:
            Empty list (no additional routes needed for cookie-based auth)
        """
        logger.debug("ISV authentication uses cookie-based auth, no additional routes needed")
        return []

    def _get_resource_url(self, path: Optional[str] = None):
        """
        Get the resource URL for the protected endpoint.

        This method is required by FastMCP's authentication system.
        For ISV token authentication, we don't need to advertise a specific
        resource URL since authentication is cookie-based.

        Args:
            path: The path where the resource endpoint is mounted (e.g., "/mcp")

        Returns:
            None (no specific resource URL needed for cookie-based auth)
        """
        logger.debug("ISV authentication doesn't require resource URL advertisement")
        return None

    async def __call__(self, request) -> Dict[str, Any]:
        """
        Verify request using ISV token validation.

        This method is called by FastMCP for each incoming request
        that requires authentication.

        Args:
            request: Incoming HTTP request

        Returns:
            User context dict with ISV token information

        Raises:
            HTTPException: On authentication failure
        """
        return await self.validator.validate_request(request)
