import pytest
from workflowwise.mcp_servers import DocumentManagementMCPServer

@pytest.mark.asyncio
async def test_dm_mcp_connect_disconnect():
    server = DocumentManagementMCPServer()
    assert not server.connected
    await server.connect()
    assert server.connected
    await server.disconnect()
    assert not server.connected

@pytest.mark.asyncio
async def test_dm_mcp_get_document_by_id_success():
    server = DocumentManagementMCPServer()
    await server.connect()
    response = await server.send_data({"action": "get_document_by_id", "doc_id": "doc_001"})
    assert response["status"] == "success"
    assert response["document"]["id"] == "doc_001"
    assert "Project Phoenix Overview" in response["document"]["title"]
    await server.disconnect()

@pytest.mark.asyncio
async def test_dm_mcp_get_document_by_id_not_found():
    server = DocumentManagementMCPServer()
    await server.connect()
    response = await server.send_data({"action": "get_document_by_id", "doc_id": "non_existent_doc"})
    assert response["status"] == "not_found"
    await server.disconnect()

@pytest.mark.asyncio
async def test_dm_mcp_search_documents():
    server = DocumentManagementMCPServer()
    await server.connect()
    response = await server.send_data({"action": "search_documents", "query": "Phoenix"})
    assert response["status"] == "success"
    assert response["count"] >= 1
    assert any("phoenix" in doc["title"].lower() for doc in response["results"])

    response_no_match = await server.send_data({"action": "search_documents", "query": "XYZNONEXISTENT"})
    assert response_no_match["status"] == "success"
    assert response_no_match["count"] == 0
    await server.disconnect()

@pytest.mark.asyncio
async def test_dm_mcp_send_data_not_connected():
    server = DocumentManagementMCPServer()
    response = await server.send_data({"action": "get_document_by_id", "doc_id": "doc_001"})
    assert response["status"] == "failure"
    assert response["error"] == "Not connected"
