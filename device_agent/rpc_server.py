"""
RPC Server for pi-mono Bridge communication.

Provides JSON-RPC interface over stdin/stdout for TypeScript bridge.
"""

import asyncio
import json
import logging
import sys
from typing import Any, Dict, Optional

from .config import Config
from .core.runtime import AgentRuntime
from .tools import get_default_tools

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


class RPCServer:
    """JSON-RPC server for bridge communication."""

    def __init__(self):
        self.runtime: Optional[AgentRuntime] = None
        self.running = False

    async def start(self):
        """Start the RPC server."""
        # Load configuration
        config = Config.from_env()

        # Create runtime
        self.runtime = AgentRuntime(config.to_agent_config())
        self.runtime.register_all(get_default_tools(self.runtime))

        # Initialize (but don't connect to MQTT yet)
        await self.runtime.init()

        self.running = True
        logger.info("RPC server started")

        # Process incoming requests
        await self.process_requests()

    async def process_requests(self):
        """Process incoming JSON-RPC requests from stdin."""
        loop = asyncio.get_event_loop()

        while self.running:
            try:
                # Read line from stdin
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                # Parse request
                try:
                    request = json.loads(line)
                except json.JSONDecodeError as e:
                    self.send_error(None, f"Invalid JSON: {e}")
                    continue

                # Handle request
                await self.handle_request(request)

            except Exception as e:
                logger.error(f"Error processing request: {e}")
                self.send_error(None, str(e))

    async def handle_request(self, request: Dict[str, Any]):
        """Handle a single RPC request."""
        request_id = request.get("id")

        # Handle special methods
        method = request.get("method")
        if method == "shutdown":
            self.running = False
            self.send_response(request_id, {"status": "shutting_down"})
            return

        if method == "ping":
            self.send_response(request_id, {"pong": True})
            return

        # Handle tool execution
        tool_name = request.get("tool")
        if tool_name:
            input_data = request.get("input", {})
            await self.execute_tool(request_id, tool_name, input_data)
            return

        self.send_error(request_id, "Unknown request type")

    async def execute_tool(self, request_id: str, tool_name: str, input_data: Dict):
        """Execute a tool and send response."""
        if not self.runtime:
            self.send_error(request_id, "Runtime not initialized")
            return

        try:
            result = await self.runtime.execute(tool_name, input_data)

            if result.success:
                self.send_response(request_id, {
                    "success": True,
                    "data": result.data,
                })
            else:
                self.send_response(request_id, {
                    "success": False,
                    "error": result.error,
                })
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            self.send_error(request_id, str(e))

    def send_response(self, request_id: Optional[str], data: Dict):
        """Send a JSON-RPC response."""
        response = {
            "id": request_id,
            "success": True,
            **data,
        }
        self.write_json(response)

    def send_error(self, request_id: Optional[str], error: str):
        """Send a JSON-RPC error."""
        response = {
            "id": request_id,
            "success": False,
            "error": error,
        }
        self.write_json(response)

    def write_json(self, data: Dict):
        """Write JSON to stdout."""
        print(json.dumps(data), flush=True)

    async def shutdown(self):
        """Shutdown the server."""
        self.running = False
        if self.runtime:
            await self.runtime.shutdown()
        logger.info("RPC server shutdown")


async def main():
    """Main entry point."""
    server = RPCServer()

    try:
        await server.start()
    except KeyboardInterrupt:
        pass
    finally:
        await server.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
