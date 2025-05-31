from .base_mcp_server import BaseMCPServer
import logging
import asyncio # For simulating async operations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocumentManagementMCPServer(BaseMCPServer):
    def __init__(self, server_id: str = "doc_mgmt_mcp_server"):
        self.server_id = server_id
        self.connected = False
        self.mock_documents = {
            "doc_001": {"id": "doc_001", "title": "Project Phoenix Overview", "content": "This document outlines the main goals and scope of Project Phoenix.", "source": "Confluence", "type": "document"},
            "doc_002": {"id": "doc_002", "title": "Q3 Marketing Strategy", "content": "Our Q3 marketing strategy focuses on social media engagement and content creation.", "source": "SharePoint", "type": "document"},
            "doc_003": {"id": "doc_003", "title": "Onboarding Guide for New Hires", "content": "Welcome to the team! This guide will help you get started.", "source": "Confluence", "type": "document"}
        }
        logger.info(f"{self.server_id} initialized.")

    async def connect(self):
        logger.info(f"{self.server_id}: Attempting to connect...")
        await asyncio.sleep(0.1) # Simulate connection latency
        self.connected = True
        logger.info(f"{self.server_id}: Successfully connected.")

    async def disconnect(self):
        logger.info(f"{self.server_id}: Attempting to disconnect...")
        await asyncio.sleep(0.05) # Simulate disconnection latency
        self.connected = False
        logger.info(f"{self.server_id}: Successfully disconnected.")

    async def send_data(self, data: dict) -> dict:
        """
        Simulates sending data (e.g., a new document to be indexed - not fully implemented in stub).
        For now, it primarily handles requests for data.
        """
        if not self.connected:
            logger.error(f"{self.server_id}: Not connected. Cannot send data.")
            return {"error": "Not connected", "status": "failure"}

        action = data.get("action")
        if action == "get_document_by_id":
            doc_id = data.get("doc_id")
            logger.info(f"{self.server_id}: Received request for document ID: {doc_id}")
            await asyncio.sleep(0.05) # Simulate retrieval latency
            document = self.mock_documents.get(doc_id)
            if document:
                return {"status": "success", "document": document}
            else:
                return {"status": "not_found", "doc_id": doc_id}
        elif action == "search_documents":
            query = data.get("query", "").lower()
            logger.info(f"{self.server_id}: Received search request with query: '{query}'")
            await asyncio.sleep(0.1) # Simulate search latency
            results = [
                doc for doc in self.mock_documents.values()
                if query in doc["title"].lower() or query in doc["content"].lower()
            ]
            return {"status": "success", "results": results, "count": len(results)}
        else:
            logger.warning(f"{self.server_id}: Unknown action '{action}' or data format.")
            return {"error": "Unknown action or data format", "status": "failure"}

    async def receive_data(self) -> dict:
        # This stub doesn't proactively push data, so this method is a placeholder.
        logger.info(f"{self.server_id}: receive_data called, but stub does not proactively push data.")
        await asyncio.sleep(1) # Simulate waiting for data that never comes
        return {"status": "no_data_available"}
