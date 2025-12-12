"""
IPC (Inter-Process Communication) module for bot-to-API communication.
Uses Unix domain sockets for fast, local communication between the bot and web API.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

SOCKET_PATH = "/tmp/k17_bot_ipc.sock"

class IPCServer:
    """IPC Server that runs in the bot process"""
    
    def __init__(self, ctf_manager):
        self.ctf_manager = ctf_manager
        self.server: Optional[asyncio.Server] = None
        
    async def start(self):
        """Start the IPC server"""
        # Remove existing socket if it exists
        try:
            Path(SOCKET_PATH).unlink()
        except FileNotFoundError:
            pass
        
        self.server = await asyncio.start_unix_server(
            self._handle_client,
            path=SOCKET_PATH
        )
        logger.info(f"✅ IPC Server started on {SOCKET_PATH}")
        
    async def stop(self):
        """Stop the IPC server"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("IPC Server stopped")
    
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming IPC requests"""
        try:
            data = await reader.read(4096)
            if not data:
                return
            
            request = json.loads(data.decode())
            logger.debug(f"IPC Request: {request}")
            
            response = await self._process_request(request)
            
            writer.write(json.dumps(response).encode())
            await writer.drain()
            
        except Exception as e:
            logger.error(f"IPC Error: {e}")
            error_response = {"status": "error", "message": str(e)}
            writer.write(json.dumps(error_response).encode())
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def _process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process IPC request and return response"""
        action = request.get("action")
        
        if action == "get_cache":
            return {
                "status": "success",
                "data": self.ctf_manager.get_cache()
            }
        
        elif action == "get_cache_message":
            message_id = request.get("message_id")
            data = self.ctf_manager.get_cache_message(message_id)
            if data:
                return {"status": "success", "data": data}
            return {"status": "error", "message": "Message not found in cache"}
        
        elif action == "update_counter":
            message_id = request.get("message_id")
            value = request.get("value")
            success = await self.ctf_manager.update_counter(message_id, value)
            if success:
                return {"status": "success"}
            return {"status": "error", "message": "Failed to update counter"}
        
        elif action == "trigger_update":
            await self.ctf_manager.update_leaderboards()
            return {"status": "success", "message": "Leaderboards updated"}
        
        elif action == "reload_cache":
            await self.ctf_manager.initialize()
            return {"status": "success", "message": "Cache reloaded from database"}
        
        elif action == "create_message":
            channel_id = request.get("channel_id")
            message_type = request.get("message_type", "counter")
            initial_counter = request.get("initial_counter", 0)
            ctfd_domain = request.get("ctfd_domain")
            ctfd_api_key = request.get("ctfd_api_key")
            forum_channel_id = request.get("forum_channel_id", 0)
            
            result = await self.ctf_manager.create_tracked_message(
                channel_id, message_type, initial_counter, ctfd_domain, ctfd_api_key, forum_channel_id
            )
            if result.get("success"):
                return {"status": "success", "data": result}
            return {"status": "error", "message": result.get("error", "Failed to create message")}
        
        elif action == "delete_message":
            message_id = request.get("message_id")
            delete_discord = request.get("delete_discord_message", True)
            
            result = await self.ctf_manager.delete_tracked_message(
                message_id, delete_discord
            )
            if result.get("success"):
                return {"status": "success", "message": result.get("message")}
            return {"status": "error", "message": result.get("error", "Failed to delete message")}
        
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}


class IPCClient:
    """IPC Client for the web API to communicate with the bot"""
    
    @staticmethod
    async def send_request(action: str, **kwargs) -> Dict[str, Any]:
        """Send a request to the IPC server"""
        try:
            reader, writer = await asyncio.open_unix_connection(SOCKET_PATH)
            
            request = {"action": action, **kwargs}
            writer.write(json.dumps(request).encode())
            await writer.drain()
            
            data = await reader.read(4096)
            response = json.loads(data.decode())
            
            writer.close()
            await writer.wait_closed()
            
            return response
            
        except FileNotFoundError:
            logger.error("IPC socket not found. Is the bot running?")
            return {"status": "error", "message": "Bot is not running or IPC not available"}
        except Exception as e:
            logger.error(f"IPC Client Error: {e}")
            return {"status": "error", "message": str(e)}
