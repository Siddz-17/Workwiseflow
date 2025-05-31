from .base_mcp_server import BaseMCPServer
import logging
import asyncio # For simulating async operations
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CommunicationMCPServer(BaseMCPServer):
    def __init__(self, server_id: str = "comm_mcp_server"):
        self.server_id = server_id
        self.connected = False
        self.mock_messages = {
            "msg_001": {"id": "msg_001", "user": "Alice", "channel": "general", "text": "Anyone know the status of Project Phoenix?", "timestamp": (datetime.utcnow() - timedelta(hours=1)).isoformat(), "source": "Slack", "type": "message"},
            "msg_002": {"id": "msg_002", "user": "Bob", "channel": "dev-team", "text": "Just pushed the latest updates for the UI module.", "timestamp": (datetime.utcnow() - timedelta(minutes=30)).isoformat(), "source": "Teams", "type": "message"},
            "msg_003": {"id": "msg_003", "user": "Alice", "channel": "general", "text": "Thanks Bob!", "timestamp": (datetime.utcnow() - timedelta(minutes=25)).isoformat(), "source": "Slack", "type": "message"}
        }
        logger.info(f"{self.server_id} initialized.")

    async def connect(self):
        logger.info(f"{self.server_id}: Attempting to connect...")
        await asyncio.sleep(0.1)
        self.connected = True
        logger.info(f"{self.server_id}: Successfully connected.")

    async def disconnect(self):
        logger.info(f"{self.server_id}: Attempting to disconnect...")
        await asyncio.sleep(0.05)
        self.connected = False
        logger.info(f"{self.server_id}: Successfully disconnected.")

    async def send_data(self, data: dict) -> dict:
        """
        Simulates sending/receiving messages.
        """
        if not self.connected:
            logger.error(f"{self.server_id}: Not connected. Cannot send data.")
            return {"error": "Not connected", "status": "failure"}

        action = data.get("action")
        if action == "get_message_by_id":
            msg_id = data.get("msg_id")
            logger.info(f"{self.server_id}: Received request for message ID: {msg_id}")
            await asyncio.sleep(0.05)
            message = self.mock_messages.get(msg_id)
            if message:
                return {"status": "success", "message": message}
            else:
                return {"status": "not_found", "msg_id": msg_id}
        elif action == "search_messages":
            query = data.get("query", "").lower()
            channel = data.get("channel")
            logger.info(f"{self.server_id}: Received message search request with query: '{query}' in channel: {channel}")
            await asyncio.sleep(0.1)

            results = []
            for msg in self.mock_messages.values():
                match_query = query in msg["text"].lower()
                match_channel = not channel or msg["channel"] == channel
                if match_query and match_channel:
                    results.append(msg)
            return {"status": "success", "results": results, "count": len(results)}
        else:
            logger.warning(f"{self.server_id}: Unknown action '{action}' or data format.")
            return {"error": "Unknown action or data format", "status": "failure"}

    async def receive_data(self) -> dict:
        logger.info(f"{self.server_id}: receive_data called, but stub does not proactively push data.")
        await asyncio.sleep(1)
        return {"status": "no_data_available"}
