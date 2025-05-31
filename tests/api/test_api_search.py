import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
import os
import numpy as np # For dummy embedding in mock

# Set mock Pinecone env vars for testing BEFORE importing main app
# These are critical for the app's startup logic not to immediately fail on PineconeDB init
os.environ["PINECONE_API_KEY"] = os.getenv("PINECONE_API_KEY", "test_pinecone_api_key")
os.environ["PINECONE_ENVIRONMENT"] = os.getenv("PINECONE_ENVIRONMENT", "test_pinecone_env_pod")
# Define serverless defaults as well, as app startup might check these based on USE_SERVERLESS_INDEX
os.environ["USE_SERVERLESS_INDEX"] = os.getenv("USE_SERVERLESS_INDEX", "true") # Default to serverless for tests if not set
os.environ["PINECONE_CLOUD"] = os.getenv("PINECONE_CLOUD", "aws")
os.environ["PINECONE_REGION"] = os.getenv("PINECONE_REGION", "us-west-1")


# Now import the app. This order is important.
from workflowwise.api.main import app

client = TestClient(app)

# Mock data that PineconeDB search might return
MOCK_PINECONE_SEARCH_RESULTS = [
    {"id": "doc_test_01", "score": 0.95, "metadata": {"title": "API Test Doc 1", "content_snippet": "Snippet for doc 1", "source": "TestSource", "type": "TestType"}},
    {"id": "doc_test_02", "score": 0.88, "metadata": {"title": "API Test Doc 2", "content_snippet": "Snippet for doc 2", "source": "TestSource", "type": "TestType"}},
]

# Mock data that DocumentManagementMCPServer might return
MOCK_MCP_DOC_FULL = {
    "doc_test_01": {"id": "doc_test_01", "title": "API Test Doc 1", "content": "Full content for API test document 1.", "source": "TestSource", "type": "TestDoc"},
    "doc_test_02": {"id": "doc_test_02", "title": "API Test Doc 2", "content": "Full content for API test document 2.", "source": "TestSource", "type": "TestDoc"},
}


@pytest.fixture(autouse=True) # Autouse to ensure services are mocked for all tests in this file
def mock_services_for_api_tests(): # Renamed fixture for clarity
    # This fixture will mock the services used by the API endpoint during app startup and request handling.
    # Using new_callable=AsyncMock for async methods of mocked classes.
    # embedding_service is used by QueryUnderstandingAgent, so mocking QUA is often enough unless ES is directly used by API.
    # For PineconeDB, we need to mock methods like connect, create_collection, and search.

    # Mocking EmbeddingService directly in case it's used by other parts of API or for full coverage
    mock_es_instance = MagicMock() # Using MagicMock for synchronous methods like get_dimension
    mock_es_instance.model = True # Simulate model is loaded
    mock_es_instance.get_dimension = MagicMock(return_value=384)
    # generate_embeddings is async in some contexts if SentenceTransformer was used with async, but here it's synchronous.
    # However, QueryUnderstandingAgent calls it, so QUA's mock is more direct for the search path.

    # Mocking QueryUnderstandingAgent
    mock_qa_instance = AsyncMock()
    mock_qa_instance.process = AsyncMock(return_value={
        "status": "success",
        "query_embedding": [0.1] * 384, # Dummy embedding
        "original_query": "test query", "extracted_keywords": ["test", "query"],
        "preliminary_intent": "information_retrieval", "session_id": "test_session_api"
    })

    # Mocking PineconeDB
    mock_vdb_instance = AsyncMock()
    mock_vdb_instance.search = AsyncMock(return_value=MOCK_PINECONE_SEARCH_RESULTS)
    mock_vdb_instance.connect = AsyncMock()
    mock_vdb_instance.create_collection = AsyncMock() # Called during startup
    mock_vdb_instance.disconnect = AsyncMock() # Called during shutdown (if app had shutdown events)

    # Mocking DocumentManagementMCPServer
    mock_dm_mcp_instance = AsyncMock()
    async def mock_send_data(data_dict): # This needs to be an async def for AsyncMock to handle it correctly as a coroutine
        action = data_dict.get("action")
        if action == "get_document_by_id":
            doc_id = data_dict.get("doc_id")
            return {"status": "success", "document": MOCK_MCP_DOC_FULL.get(doc_id, {})}
        return {"status": "failure", "error": "Unknown action"}
    mock_dm_mcp_instance.send_data = mock_send_data # Assign the async def
    mock_dm_mcp_instance.connected = True
    mock_dm_mcp_instance.connect = AsyncMock()
    mock_dm_mcp_instance.disconnect = AsyncMock()

    with patch('workflowwise.api.main.embedding_service', new=mock_es_instance), \
         patch('workflowwise.api.main.query_agent', new=mock_qa_instance), \
         patch('workflowwise.api.main.vector_db', new=mock_vdb_instance), \
         patch('workflowwise.api.main.doc_mcp_server', new=mock_dm_mcp_instance):
        yield mock_qa_instance, mock_vdb_instance, mock_dm_mcp_instance, mock_es_instance


def test_api_search_success(mock_services_for_api_tests):
    response = client.post("/api/search", json={"query": "test query", "top_k": 2})
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "test query" # QUA mock will return "test query" as original_query
    assert len(data["results"]) == 2
    assert data["results"][0]["id"] == "doc_test_01"
    assert data["results"][0]["title"] == "API Test Doc 1"
    assert "Full content for API test document 1" in data["results"][0]["full_content_preview"]
    assert data["results"][1]["id"] == "doc_test_02"

def test_api_search_no_query(mock_services_for_api_tests):
    response = client.post("/api/search", json={"query": "", "top_k": 2})
    assert response.status_code == 422

def test_api_search_vdb_fails(mock_services_for_api_tests):
    _, mock_vdb, _, _ = mock_services_for_api_tests
    mock_vdb.search = AsyncMock(side_effect=Exception("Pinecone unavailable"))

    response = client.post("/api/search", json={"query": "another query"})
    assert response.status_code == 500
    assert "Error searching vector database" in response.json()["detail"]

def test_api_search_query_understanding_fails(mock_services_for_api_tests):
    mock_qa, _, _, _ = mock_services_for_api_tests
    mock_qa.process = AsyncMock(return_value={"status": "failure", "error": "Understanding failed"})

    response = client.post("/api/search", json={"query": "problematic query"})
    assert response.status_code == 500
    assert "Failed to process query: Understanding failed" in response.json()["detail"]

def test_api_search_no_results_from_vdb(mock_services_for_api_tests):
    _, mock_vdb, _, _ = mock_services_for_api_tests
    mock_vdb.search = AsyncMock(return_value=[])

    response = client.post("/api/search", json={"query": "obscure query"})
    assert response.status_code == 200
    data = response.json()
    # The query in response should match the one sent, QUA mock might need adjustment if we want to test this part strictly matching input
    # For now, QUA mock returns its own "original_query", which is fine.
    # assert data["query"] == "obscure query"
    assert len(data["results"]) == 0
    assert data["message"] == "No relevant documents found."

def test_get_index_html(mock_services_for_api_tests): # Fixture ensures app startup with mocks
    temp_static_dir = "temp_static_test_dir_api"
    temp_index_html = os.path.join(temp_static_dir, "index.html")

    # Ensure directory exists
    os.makedirs(temp_static_dir, exist_ok=True)
    with open(temp_index_html, "w") as f:
        f.write("<html><body>Test API UI</body></html>")

    # Patch the static_dir_path in the main module where `app` is defined
    with patch('workflowwise.api.main.static_dir_path', new=temp_static_dir):
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "Test API UI" in response.text

    os.remove(temp_index_html)
    os.rmdir(temp_static_dir)
