"""
Bino HMR WebSocket Server

HMR WebSocket server implementation used only during dev to notify browsers on rebuilds.
"""

import asyncio
import json
import logging
from typing import Set, Dict, Any, Optional
import websockets
from websockets.server import WebSocketServerProtocol
import time

logger = logging.getLogger(__name__)


class HMRWebSocketServer:
    """
    WebSocket server for Hot Module Replacement during development.
    """
    
    def __init__(self, host: str = "localhost", port: int = 3001):
        self.host = host
        self.port = port
        self.clients: Set[WebSocketServerProtocol] = set()
        self.server: Optional[websockets.WebSocketServer] = None
        self._running = False
    
    async def start(self) -> None:
        """Start the HMR WebSocket server."""
        if self._running:
            logger.warning("HMR server already running")
            return
        
        try:
            self.server = await websockets.serve(
                self._handle_client,
                self.host,
                self.port,
                ping_interval=20,
                ping_timeout=10
            )
            
            self._running = True
            logger.info(f"🔥 HMR WebSocket server started on ws://{self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"Failed to start HMR server: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the HMR WebSocket server."""
        if not self._running:
            return
        
        self._running = False
        
        # Close all client connections
        if self.clients:
            await asyncio.gather(
                *[client.close() for client in self.clients],
                return_exceptions=True
            )
            self.clients.clear()
        
        # Stop server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        logger.info("HMR server stopped")
    
    async def _handle_client(self, websocket: WebSocketServerProtocol, path: str) -> None:
        """
        Handle new WebSocket client connection.
        
        Args:
            websocket: WebSocket connection
            path: Request path
        """
        client_addr = websocket.remote_address
        logger.debug(f"HMR client connected: {client_addr}")
        
        self.clients.add(websocket)
        
        try:
            # Send welcome message
            await self._send_to_client(websocket, {
                "type": "connected",
                "message": "HMR client connected",
                "timestamp": time.time()
            })
            
            # Keep connection alive and handle messages
            async for message in websocket:
                await self._handle_client_message(websocket, message)
                
        except websockets.exceptions.ConnectionClosed:
            logger.debug(f"HMR client disconnected: {client_addr}")
        except Exception as e:
            logger.error(f"HMR client error: {e}")
        finally:
            self.clients.discard(websocket)
    
    async def _handle_client_message(self, websocket: WebSocketServerProtocol, message: str) -> None:
        """
        Handle message from HMR client.
        
        Args:
            websocket: Client WebSocket connection
            message: Message from client
        """
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "ping":
                await self._send_to_client(websocket, {"type": "pong"})
            elif msg_type == "reload-request":
                await self.broadcast({"type": "reload"})
            else:
                logger.debug(f"Unknown HMR message type: {msg_type}")
                
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from HMR client: {message}")
    
    async def _send_to_client(self, websocket: WebSocketServerProtocol, data: Dict[str, Any]) -> None:
        """Send data to specific client."""
        try:
            message = json.dumps(data)
            await websocket.send(message)
        except Exception as e:
            logger.error(f"Failed to send to HMR client: {e}")
    
    async def broadcast(self, data: Dict[str, Any]) -> None:
        """
        Broadcast message to all connected HMR clients.
        
        Args:
            data: Data to broadcast to clients
            
        Example:
            >>> await hmr_server.broadcast({"type": "reload", "reason": "file-change"})
        """
        if not self.clients:
            logger.debug("No HMR clients connected")
            return
        
        message = json.dumps(data)
        disconnected_clients = set()
        
        # Send to all clients
        for client in self.clients:
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.add(client)
            except Exception as e:
                logger.error(f"Failed to broadcast to client: {e}")
                disconnected_clients.add(client)
        
        # Remove disconnected clients
        self.clients -= disconnected_clients
        
        logger.debug(f"Broadcasted to {len(self.clients)} HMR clients")
    
    async def notify_file_change(self, file_path: Path, change_type: str) -> None:
        """
        Notify clients about file changes.
        
        Args:
            file_path: Path of changed file
            change_type: Type of change ("created", "modified", "deleted")
        """
        # Determine if this change should trigger a reload
        should_reload = self._should_trigger_reload(file_path, change_type)
        
        update_data = {
            "type": "file-change",
            "file": str(file_path),
            "changeType": change_type,
            "shouldReload": should_reload,
            "timestamp": time.time()
        }
        
        await self.broadcast(update_data)
        
        if should_reload:
            logger.info(f"File change triggered reload: {file_path}")
    
    def _should_trigger_reload(self, file_path: Path, change_type: str) -> bool:
        """
        Determine if file change should trigger browser reload.
        
        Args:
            file_path: Changed file path
            change_type: Type of change
            
        Returns:
            True if reload should be triggered
        """
        # Always reload for certain file types
        reload_extensions = {".py", ".tsx", ".ts", ".jsx", ".js"}
        
        if file_path.suffix in reload_extensions:
            return True
        
        # CSS changes can be hot-swapped without full reload
        if file_path.suffix in {".css", ".scss", ".sass"}:
            return False
        
        # Config file changes should trigger reload
        config_files = {"package.json", "bino.config.json", "tsconfig.json"}
        if file_path.name in config_files:
            return True
        
        return False
    
    def get_client_count(self) -> int:
        """
        Get number of connected HMR clients.
        
        Returns:
            Number of connected clients
        """
        return len(self.clients)
    
    async def send_custom_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Send custom event to all clients.
        
        Args:
            event_type: Custom event type
            data: Event data
        """
        event_data = {
            "type": event_type,
            "timestamp": time.time(),
            **data
        }
        
        await self.broadcast(event_data)


def create_hmr_client_script(hmr_port: int) -> str:
    """
    Generate client-side HMR script for injection into HTML.
    
    Args:
        hmr_port: Port where HMR server is running
        
    Returns:
        JavaScript code for HMR client
        
    Example:
        >>> script = create_hmr_client_script(3001)
        >>> print(f"<script>{script}</script>")
    """
    return f"""
(function() {{
    const ws = new WebSocket('ws://localhost:{hmr_port}');
    
    ws.onopen = function() {{
        console.log('🔥 HMR connected');
    }};
    
    ws.onmessage = function(event) {{
        const data = JSON.parse(event.data);
        
        if (data.type === 'file-change' && data.shouldReload) {{
            console.log('🔄 Reloading due to file change:', data.file);
            window.location.reload();
        }} else if (data.type === 'reload') {{
            window.location.reload();
        }}
    }};
    
    ws.onclose = function() {{
        console.log('🔥 HMR disconnected');
        // Try to reconnect after 1 second
        setTimeout(() => window.location.reload(), 1000);
    }};
    
    ws.onerror = function(error) {{
        console.error('HMR error:', error);
    }};
}})();
"""


if __name__ == "__main__":
    # Example usage
    async def main():
        server = HMRWebSocketServer()
        
        try:
            await server.start()
            print(f"HMR server running on port {server.port}")
            print("Press Ctrl+C to stop")
            
            # Keep server running
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            print("Stopping HMR server...")
            await server.stop()
    
    asyncio.run(main())

# Unit tests as comments:
# 1. test_hmr_server_client_connection() - verify clients can connect and receive messages
# 2. test_broadcast_to_multiple_clients() - test broadcasting works with multiple connections
# 3. test_file_change_notification() - verify file change events are processed correctly