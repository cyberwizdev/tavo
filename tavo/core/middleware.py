"""
Tavo Middleware

Middleware for handling HMR, request logging, and development features
in the Tavo full-stack application.
"""

import logging
import time
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp
from starlette.routing import Route

logger = logging.getLogger(__name__)

class TavoMiddleware(BaseHTTPMiddleware):
    """
    Custom middleware for Tavo application to handle:
    - Request logging
    - HMR WebSocket headers for development
    - Response time tracking
    - Custom headers for Tavo-specific features
    """
    
    def __init__(self, app: ASGIApp, hmr_enabled: bool = True):
        """
        Initialize the Tavo middleware.
        
        Args:
            app: The Starlette ASGI application
            hmr_enabled: Whether HMR is enabled (default: True for development)
        """
        super().__init__(app)
        self.hmr_enabled = hmr_enabled
        self.logger = logger

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Process incoming requests and outgoing responses.
        
        Args:
            request: Incoming HTTP request
            call_next: The next middleware or endpoint in the chain
            
        Returns:
            Response object with potential modifications
        """
        # Log request start
        start_time = time.time()
        self.logger.debug(f"Request started: {request.method} {request.url.path}")

        try:
            # Add HMR headers for development
            if self.hmr_enabled and request.url.path.startswith("/"):
                response = await self._handle_hmr_request(request, call_next)
            else:
                response = await call_next(request)

            # Add custom Tavo headers
            response.headers["X-Tavo-Version"] = "{{PROJECT_NAME}}-v1.0.0"
            response.headers["X-Response-Time"] = f"{(time.time() - start_time) * 1000:.2f}ms"

            # Log request completion
            self.logger.debug(
                f"Request completed: {request.method} {request.url.path} "
                f"Status: {response.status_code} "
                f"Time: {response.headers['X-Response-Time']}"
            )

            return response

        except Exception as e:
            self.logger.error(f"Error processing request {request.url.path}: {e}")
            raise

    async def _handle_hmr_request(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Handle HMR-specific logic for development mode.
        
        Args:
            request: Incoming HTTP request
            call_next: The next middleware or endpoint
            
        Returns:
            Modified response with HMR headers if applicable
        """
        response = await call_next(request)

        # Only inject HMR headers for HTML responses in development
        if (
            self.hmr_enabled
            and response.status_code == 200
            and "text/html" in response.headers.get("content-type", "")
            and request.headers.get("host", "").startswith("localhost")
        ):
            response.headers["X-Tavo-HMR"] = "enabled"
            response.headers["X-Tavo-HMR-WebSocket"] = "ws://localhost:3001"

        return response

    def enable_hmr(self) -> None:
        """Enable HMR support."""
        self.hmr_enabled = True
        self.logger.info("HMR enabled in middleware")

    def disable_hmr(self) -> None:
        """Disable HMR support."""
        self.hmr_enabled = False
        self.logger.info("HMR disabled in middleware")

    def get_middleware_stats(self) -> dict:
        """
        Get middleware statistics.
        
        Returns:
            Dictionary with middleware processing statistics
        """
        # TODO: Implement actual stats collection
        return {
            "requests_processed": 0,
            "average_response_time": 0.0,
            "hmr_requests": 0,
            "errors": 0
        }


# Convenience function to create middleware instance
def create_tavo_middleware(app: ASGIApp, hmr_enabled: bool = True) -> TavoMiddleware:
    """
    Create and configure Tavo middleware.
    
    Args:
        app: Starlette ASGI application
        hmr_enabled: Whether to enable HMR support
        
    Returns:
        Configured TavoMiddleware instance
    """
    return TavoMiddleware(app, hmr_enabled=hmr_enabled)


if __name__ == "__main__":
    # Example usage for testing
    from starlette.applications import Starlette
    from starlette.responses import HTMLResponse

    async def test_endpoint(request: Request) -> Response:
        return HTMLResponse("Test response")

    # Create a test app
    test_app = Starlette(routes=[Route("/test", test_endpoint)])
    middleware = create_tavo_middleware(test_app, hmr_enabled=True)

    print("Tavo middleware initialized for testing")
    print(f"Middleware stats: {middleware.get_middleware_stats()}")

# Unit tests as comments:
# 1. test_middleware_request_logging() - verify request logging works
# 2. test_hmr_headers_injection() - test HMR headers are added correctly in dev mode
# 3. test_response_time_tracking() - verify response time header accuracy
# 4. test_hmr_toggle() - test enabling/disabling HMR
# 5. test_error_handling() - verify proper error logging and propagation