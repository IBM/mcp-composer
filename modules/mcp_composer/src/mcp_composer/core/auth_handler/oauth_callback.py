# oauth_callback.py
from urllib.parse import urlparse

from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()
# pylint: disable=W0718


def register_oauth_callback(self, settings, auth_provider):
    """
    Dynamically register the OAuth callback route and user profile tool.
    """
    callback_path = urlparse(settings.callback_path).path

    @self.custom_route(callback_path, methods=["GET"])
    async def callback_handler(request: Request):
        code = request.query_params.get("code")
        state = request.query_params.get("state")

        if not code or not state:
            raise HTTPException(400, "Missing code or state parameter")

        try:
            redirect_uri = await auth_provider.handle_callback(code, state)
            return RedirectResponse(status_code=302, url=redirect_uri)
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Unexpected error during OAuth callback", exc_info=e)
            return JSONResponse(
                status_code=500,
                content={
                    "error": "server_error",
                    "error_description": "Unexpected error",
                },
            )
