"""
Hello API Route

Example API route that returns JSON (Starlette-compatible).
"""

import json
import logging
from datetime import datetime
from starlette.requests import Request
from starlette.responses import JSONResponse
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def get(request: Request) -> JSONResponse:
    """
    Handle GET requests to /api/hello.
    
    Args:
        request: Starlette request object
        
    Returns:
        JSON response with greeting message
        
    Example:
        GET /api/hello -> {"message": "Hello from Bino!", "timestamp": "..."}
    """
    logger.info("Hello API endpoint called")
    
    # Get query parameters
    name = request.query_params.get("name", "World")
    
    response_data = {
        "message": f"Hello, {name}!",
        "timestamp": datetime.now().isoformat(),
        "framework": "Bino",
        "version": "0.1.0"
    }
    
    return JSONResponse(response_data)


async def post(request: Request) -> JSONResponse:
    """
    Handle POST requests to /api/hello.
    
    Args:
        request: Starlette request object
        
    Returns:
        JSON response with processed data
    """
    try:
        # Parse JSON body
        body = await request.json()
        name = body.get("name", "Anonymous")
        message = body.get("message", "Hello")
        
        logger.info(f"POST hello request from: {name}")
        
        response_data = {
            "received": {
                "name": name,
                "message": message
            },
            "response": f"{message}, {name}! Thanks for using Bino.",
            "timestamp": datetime.now().isoformat()
        }
        
        return JSONResponse(response_data, status_code=201)
        
    except json.JSONDecodeError:
        logger.warning("Invalid JSON in POST request")
        return JSONResponse(
            {"error": "Invalid JSON in request body"},
            status_code=400
        )
    except Exception as e:
        logger.error(f"Error processing POST request: {e}")
        return JSONResponse(
            {"error": "Internal server error"},
            status_code=500
        )


async def put(request: Request) -> JSONResponse:
    """
    Handle PUT requests to /api/hello.
    
    Args:
        request: Starlette request object
        
    Returns:
        JSON response confirming update
    """
    try:
        body = await request.json()
        
        response_data = {
            "message": "Resource updated successfully",
            "data": body,
            "timestamp": datetime.now().isoformat()
        }
        
        return JSONResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error processing PUT request: {e}")
        return JSONResponse(
            {"error": "Failed to process update"},
            status_code=500
        )


async def delete(request: Request) -> JSONResponse:
    """
    Handle DELETE requests to /api/hello.
    
    Args:
        request: Starlette request object
        
    Returns:
        JSON response confirming deletion
    """
    logger.info("DELETE hello request")
    
    response_data = {
        "message": "Resource deleted successfully",
        "timestamp": datetime.now().isoformat()
    }
    
    return JSONResponse(response_data, status_code=204)


# Helper functions for the route
def validate_hello_request(data: Dict[str, Any]) -> Dict[str, str]:
    """
    Validate hello request data.
    
    Args:
        data: Request data to validate
        
    Returns:
        Dictionary of validation errors (empty if valid)
        
    Example:
        >>> errors = validate_hello_request({"name": "John"})
        >>> len(errors) == 0
        True
    """
    errors = {}
    
    name = data.get("name", "")
    if not name or not isinstance(name, str):
        errors["name"] = "Name is required and must be a string"
    elif len(name) > 100:
        errors["name"] = "Name must be 100 characters or less"
    
    message = data.get("message", "")
    if message and len(message) > 500:
        errors["message"] = "Message must be 500 characters or less"
    
    return errors


def format_hello_response(name: str, custom_message: str = None) -> Dict[str, Any]:
    """
    Format standardized hello response.
    
    Args:
        name: Name to greet
        custom_message: Optional custom message
        
    Returns:
        Formatted response dictionary
    """
    base_message = custom_message or "Hello"
    
    return {
        "greeting": f"{base_message}, {name}!",
        "name": name,
        "timestamp": datetime.now().isoformat(),
        "api_version": "1.0"
    }


# Example middleware function (not used by default)
async def hello_middleware(request: Request, call_next):
    """
    Example middleware for hello routes.
    
    Args:
        request: Incoming request
        call_next: Next middleware/handler in chain
        
    Returns:
        Response from next handler
    """
    start_time = datetime.now()
    
    # Log request
    logger.info(f"Hello API request: {request.method} {request.url}")
    
    # Call next handler
    response = await call_next(request)
    
    # Log response time
    duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"Hello API response time: {duration:.3f}s")
    
    return response


if __name__ == "__main__":
    # Example usage for testing
    import asyncio
    from starlette.applications import Starlette
    from starlette.routing import Route
    
    async def test_hello_route():
        # Create mock request
        from starlette.testclient import TestClient
        
        app = Starlette(routes=[
            Route("/hello", get, methods=["GET"]),
            Route("/hello", post, methods=["POST"]),
        ])
        
        client = TestClient(app)
        
        # Test GET request
        response = client.get("/hello?name=TestUser")
        print(f"GET response: {response.json()}")
        
        # Test POST request
        response = client.post("/hello", json={"name": "TestUser", "message": "Hi"})
        print(f"POST response: {response.json()}")
    
    asyncio.run(test_hello_route())

# Unit tests as comments:
# 1. test_get_hello_with_name_param() - verify GET request with name parameter works
# 2. test_post_hello_with_json_body() - test POST request with JSON body processing
# 3. test_validation_errors() - verify request validation catches invalid data