import pytest
from workflowwise.mcp_servers import CommunicationMCPServer

@pytest.mark.asyncio
async def test_cm_mcp_connect_disconnect():
    server = CommunicationMCPServer()
    assert not server.connected
    await server.connect()
    assert server.connected
    await server.disconnect()
    assert not server.connected

@pytest.mark.asyncio
async def test_cm_mcp_search_messages():
    server = CommunicationMCPServer()
    await server.connect()
    response = await server.send_data({"action": "search_messages", "query": "Phoenix"})
    assert response["status"] == "success"
    assert response["count"] >= 1
    assert any("phoenix" in msg["text"].lower() for msg in response["results"])
    await server.disconnect()
