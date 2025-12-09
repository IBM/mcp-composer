import os
import time
import base64
import json
from typing import Any, Optional
import httpx
import urllib.parse
from mcp_composer.core.utils import ConfigKey, LoggerFactory
from mcp_composer.core.auth_handler.oauth_handler import resolve_env_value

logger = LoggerFactory.get_logger()

DEFAULT_TOKEN_EXPIRY = 3600
TOKEN_REFRESH_BUFFER = 60
MIN_VALIDITY_SECONDS = 600  # 10 minutes
DEFAULT_TIMEOUT = 30.0


class SolisJWTTokenGenerator:
    """
    Utility class for generating JWT tokens from IBM Solis using form-based authentication.
    
    Flow:
      1) POST email/password to LOGIN_URL with returnUrl
      2) Extract JWT from Set-Cookie header (ibm-solis-session)
      3) Cache JWT based on expiration time
      4) Return JWT token for use in Authorization headers
    """

    def __init__(self, auth_data: dict[str, Any] | None = None):
        self.auth_data = auth_data or {}
        self._cache_path: Optional[str] = None
        self._jwt_token: Optional[str] = None
        self._expires_at: float = 0.0

    def _get_cache_path(self) -> str:
        """Get the cache file path for JWT storage."""
        if self._cache_path is None:
            cache_dir = os.getcwd()
            self._cache_path = os.path.join(cache_dir, ".solis_jwt_cache.json")
        return self._cache_path

    def _load_cached_jwt(self) -> Optional[str]:
        """Load JWT from cache if valid."""
        cache_path = self._get_cache_path()
        if not os.path.isfile(cache_path):
            return None

        try:
            with open(cache_path, "r") as f:
                data = json.load(f)
            jwt_token = data.get("jwt")  # Keep "jwt" for compatibility with working version
            if not jwt_token:
                return None

            # Parse JWT expiration
            try:
                payload = jwt_token.split(".")[1]
                # Pad base64 if needed
                missing_padding = len(payload) % 4
                if missing_padding:
                    payload += '=' * (4 - missing_padding)
                payload_bytes = base64.urlsafe_b64decode(payload)
                payload_json = json.loads(payload_bytes)
                exp = payload_json.get("exp")
                if not exp:
                    return None

                # If token expires in less than MIN_VALIDITY_SECONDS, don't use it
                if exp - time.time() < MIN_VALIDITY_SECONDS:
                    return None

                return jwt_token
            except Exception as e:
                logger.debug(f"Error parsing cached JWT: {e}")
                return None
        except Exception as e:
            logger.debug(f"Error loading cached JWT: {e}")
            return None

    def _save_jwt(self, jwt_token: str) -> None:
        """Save JWT to cache."""
        cache_path = self._get_cache_path()
        try:
            with open(cache_path, "w") as f:
                json.dump({"jwt": jwt_token}, f)  # Keep "jwt" for compatibility with working version
        except Exception as e:
            logger.warning(f"Failed to save JWT to cache: {e}")

    def _parse_jwt_expiration(self, jwt_token: str) -> Optional[float]:
        """Parse expiration time from JWT token."""
        try:
            payload = jwt_token.split(".")[1]
            # Pad base64 if needed
            missing_padding = len(payload) % 4
            if missing_padding:
                payload += '=' * (4 - missing_padding)
            payload_bytes = base64.urlsafe_b64decode(payload)
            payload_json = json.loads(payload_bytes)
            exp = payload_json.get("exp")
            if exp:
                return float(exp)
        except Exception as e:
            logger.debug(f"Error parsing JWT expiration: {e}")
        return None

    def get_token_expiry(self) -> float:
        """Get the current token expiry time (buffered)."""
        return self._expires_at

    def get_current_token(self) -> Optional[str]:
        """Get the current cached token."""
        return self._jwt_token

    async def get_jwt_token(self, force: bool = False) -> str:
        """
        Get JWT token, using cache if available and valid.
        
        Args:
            force: If True, force a new token fetch even if cached token is valid
            
        Returns:
            JWT token string
        """
        # Check cache first unless forcing refresh
        if not force:
            cached_jwt = self._load_cached_jwt()
            if cached_jwt:
                logger.debug("Using cached JWT token")
                self._jwt_token = cached_jwt
                exp = self._parse_jwt_expiration(cached_jwt)
                if exp:
                    self._expires_at = exp - TOKEN_REFRESH_BUFFER
                return cached_jwt

        # Get authentication parameters
        # Support both USER_EMAIL and email for backward compatibility
        email = resolve_env_value(
            self.auth_data.get(ConfigKey.USER_EMAIL) or self.auth_data.get("email")
        )
        # Support both USER_PASSWORD and PASSWORD for backward compatibility
        password = resolve_env_value(
            self.auth_data.get(ConfigKey.USER_PASSWORD)
            or self.auth_data.get(ConfigKey.PASSWORD)
            or self.auth_data.get("password")
        )

        if not email or not password:
            missing = []
            if not email:
                missing.append("user_email (or email)")
            if not password:
                missing.append("user_password (or password)")
            
            error_msg = (
                f"Missing required authentication credentials: {', '.join(missing)}. "
                "Please provide these in the 'auth' section of your server configuration, "
                "or set them as environment variables (e.g., ENV_USER_EMAIL, ENV_USER_PASSWORD)."
            )
            raise ValueError(error_msg)

        login_url = self.auth_data.get(ConfigKey.LOGIN_URL)
        return_url = self.auth_data.get(ConfigKey.RETURN_URL)

        if not login_url or not return_url:
            raise ValueError("LOGIN_URL and return_url must be provided in auth_data")

        # Prepare form data
        post_data = f"returnUrl={return_url}&email={email}&password={password}".encode("utf-8")

        # Prepare headers (matching working version)
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (compatible; IBM-Solis-Client/1.0)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",  # Added to match working version
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        # Create a temporary client for the login request
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            # Make login request (don't follow redirects to capture Set-Cookie)
            # CRITICAL: follow_redirects=False is required to get Set-Cookie from 302 response
            try:
                resp = await client.post(
                    login_url,
                    content=post_data,
                    headers=headers,
                    follow_redirects=False  # CRITICAL: Must not follow redirects
                )
            except httpx.HTTPStatusError as e:
                # 302 redirect is expected for successful login
                if e.response.status_code == 302:
                    resp = e.response
                else:
                    raise

            logger.debug(f"Login response status: {resp.status_code}")


            # Extract JWT from Set-Cookie header
            jwt_token = None
            # Iterate through all Set-Cookie headers (httpx supports multiple values)
            for header_name, header_value in resp.headers.multi_items():
                if header_name.lower() == "set-cookie":
                    cookie = header_value
                    if cookie.startswith("ibm-solis-session="):
                        # Extract token value (before first semicolon)
                        jwt_token = cookie.split("=", 1)[1].split(";", 1)[0]
                        logger.debug(f"Found JWT token (length: {len(jwt_token)})")
                        break

            if not jwt_token:
                raise ValueError(
                    "Failed to obtain JWT token: 'ibm-solis-session' cookie not found in response. "
                    "Authentication may have failed."
                )

        # Cache the token
        self._save_jwt(jwt_token)
        self._jwt_token = jwt_token

        # Parse expiration
        exp = self._parse_jwt_expiration(jwt_token)
        if exp:
            self._expires_at = exp - TOKEN_REFRESH_BUFFER
            logger.debug(f"Token acquired; expires at {exp} (buffered by {TOKEN_REFRESH_BUFFER}s)")
        else:
            # Fallback: assume default expiry if can't parse
            self._expires_at = time.time() + DEFAULT_TOKEN_EXPIRY - TOKEN_REFRESH_BUFFER
            logger.debug("Token acquired; using default expiry (could not parse JWT exp)")

        return jwt_token


class SolisJWTClient(httpx.AsyncClient):
    """
    Async HTTP client for IBM Solis using form-based authentication with JWT Bearer tokens.
    
    Flow:
      1) POST email/password to LOGIN_URL with returnUrl
      2) Extract JWT from Set-Cookie header (ibm-solis-session)
      3) Cache JWT based on expiration time
      4) Attach JWT as Authorization Bearer header to subsequent requests
      5) Auto-refresh before expiry
    """

    def __init__(
        self,
        base_url: str,
        auth_data: dict[str, Any] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        if not base_url:
            raise ValueError("base_url cannot be empty")
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        self.auth_data = auth_data or {}
        self._token_generator = SolisJWTTokenGenerator(auth_data=auth_data)
        self._resolved_login_url: Optional[str] = None

        super().__init__(base_url=base_url, timeout=timeout, headers=headers or {}, **kwargs)

    async def _refresh_token(self, force: bool = False) -> None:
        """Refresh internal JWT token if missing/expired."""
        await self._token_generator.get_jwt_token(force=force)
        # Token and expiry are now tracked in the generator

    # ----------------- public override -----------------

    async def request(self, method: str, url: httpx.URL | str, **kwargs: Any) -> httpx.Response:
        """
        Make an authenticated request, auto-refreshing the JWT token unless we're calling the login URL.
        """
        # Cache login URL once to avoid repeated env lookups
        if self._resolved_login_url is None and self.auth_data:
            self._resolved_login_url = resolve_env_value(self.auth_data.get(ConfigKey.LOGIN_URL))

        url_str = str(url)
        # Check if this is a login request (shouldn't recurse into refresh)
        is_login_url = self._resolved_login_url and url_str.startswith(self._resolved_login_url)

        if is_login_url:
            # Direct calls to the login URL shouldn't recurse into refresh
            return await super().request(method, url, **kwargs)

        # Refresh token if needed (check generator's state)
        current_token = self._token_generator.get_current_token()
        expires_at = self._token_generator.get_token_expiry()

        if not current_token or time.time() >= expires_at:
            await self._refresh_token()
            current_token = self._token_generator.get_current_token()

        # Merge headers safely
        headers = (kwargs.pop("headers", {}) or {}).copy()
        headers["Authorization"] = f"Bearer {current_token}"
        headers.setdefault("Accept", "application/json")

        # Only set JSON Content-Type if caller didn't specify and is sending a body
        if "Content-Type" not in headers and any(k in kwargs for k in ("data", "json", "files")):
            headers["Content-Type"] = "application/json"

        # Make the request
        response = await super().request(method, url, headers=headers, **kwargs)

        # If we get a 401, try refreshing token and retry once
        if response.status_code == 401:
            logger.debug("Received 401, refreshing token and retrying")
            await self._refresh_token(force=True)
            current_token = self._token_generator.get_current_token()
            headers["Authorization"] = f"Bearer {current_token}"
            response = await super().request(method, url, headers=headers, **kwargs)

        return response
