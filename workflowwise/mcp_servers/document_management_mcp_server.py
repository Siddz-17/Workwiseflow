from .base_mcp_server import BaseMCPServer
import logging
import asyncio
import json
import os
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Path to the mock_documents.json file, assuming it's in 'data/' directory at the project root.
# This file (document_management_mcp_server.py) is in workflowwise/mcp_servers/
# So, ../../data/mock_documents.json from here.
DEFAULT_MOCK_DATA_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "mock_documents.json"
))

class DocumentManagementMCPServer(BaseMCPServer):
    def __init__(self, server_id: str = "doc_mgmt_mcp_server", data_path: str = DEFAULT_MOCK_DATA_PATH):
        self.server_id = server_id
        self.connected = False
        self.data_path = data_path
        self.mock_documents: Dict[str, Dict[str, Any]] = {} # Store by ID for quick lookup
        self._load_mock_data()
        # Initial log message moved to connect() to avoid pre-mature logging if loading fails.

    def _load_mock_data(self):
        try:
            if not os.path.exists(self.data_path):
                logger.error(f"Mock data file not found at {self.data_path}. Server will use an empty dataset.")
                self.mock_documents = {}
                return

            with open(self.data_path, 'r') as f:
                documents_list: List[Dict[str, Any]] = json.load(f)

            temp_docs = {}
            for doc in documents_list:
                if 'id' in doc:
                    temp_docs[doc['id']] = doc
                else:
                    logger.warning(f"Document missing 'id' in {self.data_path}, skipping: {doc.get('title', 'N/A')}")
            self.mock_documents = temp_docs
            logger.info(f"Successfully loaded {len(self.mock_documents)} documents from {self.data_path}")

        except FileNotFoundError:
            logger.error(f"Mock data file not found at {self.data_path}. Server will use an empty dataset.")
            self.mock_documents = {}
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {self.data_path}. Server will use an empty dataset.")
            self.mock_documents = {}
        except Exception as e:
            logger.error(f"An unexpected error occurred while loading mock data: {e}", exc_info=True)
            self.mock_documents = {}

    async def connect(self):
        logger.info(f"{self.server_id}: Attempting to connect...")
        # Re-attempt loading data on connect if it was empty, in case file appears later.
        if not self.mock_documents:
            logger.info(f"No documents loaded at init, trying to load again on connect from {self.data_path}")
            self._load_mock_data()

        await asyncio.sleep(0.01)
        self.connected = True
        logger.info(f"{self.server_id}: Successfully connected. Document count: {len(self.mock_documents)}")

    async def disconnect(self):
        logger.info(f"{self.server_id}: Attempting to disconnect...")
        await asyncio.sleep(0.01)
        self.connected = False
        logger.info(f"{self.server_id}: Successfully disconnected.")

    async def send_data(self, data: dict) -> dict:
        if not self.connected:
            logger.error(f"{self.server_id}: Not connected. Cannot send data.")
            return {"error": "Not connected", "status": "failure"}

        action = data.get("action")
        if action == "get_document_by_id":
            doc_id = data.get("doc_id")
            logger.info(f"{self.server_id}: Received request for document ID: {doc_id}")
            await asyncio.sleep(0.01)
            document = self.mock_documents.get(doc_id)
            if document:
                return {"status": "success", "document": document}
            else:
                logger.warning(f"Document ID {doc_id} not found in loaded mock_documents.")
                return {"status": "not_found", "doc_id": doc_id}
        elif action == "search_documents":
            query = data.get("query", "").lower()
            logger.info(f"{self.server_id}: Received mock search request with query: '{query}'")
            await asyncio.sleep(0.05)
            results = [
                doc for doc in self.mock_documents.values()
                if query in doc.get("title", "").lower() or query in doc.get("content", "").lower()
            ]
            return {"status": "success", "results": results, "count": len(results)}
        else:
            logger.warning(f"{self.server_id}: Unknown action '{action}' or data format.")
            return {"error": "Unknown action or data format", "status": "failure"}

    async def receive_data(self) -> dict:
        logger.info(f"{self.server_id}: receive_data called, but stub does not proactively push data.")
        await asyncio.sleep(0.1)
        return {"status": "no_data_available"}
