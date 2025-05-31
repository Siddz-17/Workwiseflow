import pytest
from workflowwise.agents import QueryUnderstandingAgent

@pytest.mark.asyncio
async def test_qua_initialization():
    agent = QueryUnderstandingAgent(agent_id="test_qua")
    assert agent.agent_id == "test_qua"

@pytest.mark.asyncio
async def test_qua_process_valid_query():
    agent = QueryUnderstandingAgent()
    data = {"query_text": "Tell me about project phoenix", "session_id": "session123"}
    result = await agent.process(data)

    assert result["status"] == "success"
    assert result["original_query"] == "Tell me about project phoenix"
    assert "phoenix" in result["extracted_keywords"]
    assert "project" in result["extracted_keywords"]
    assert "tell" not in result["extracted_keywords"] # stopword
    assert result["preliminary_intent"] == "information_retrieval"
    assert result["session_id"] == "session123"

@pytest.mark.asyncio
async def test_qua_process_missing_query_text():
    agent = QueryUnderstandingAgent()
    data = {"session_id": "session123"}
    result = await agent.process(data)
    assert result["error"] == "Missing query_text"
    assert result.get("status") != "success"

@pytest.mark.asyncio
async def test_qua_process_intent_detection():
    agent = QueryUnderstandingAgent()
    data = {"query_text": "how to setup workspace", "session_id": "session456"}
    result = await agent.process(data)
    assert result["status"] == "success"
    assert "setup" in result["extracted_keywords"]
    assert "workspace" in result["extracted_keywords"]
    assert result["preliminary_intent"] == "instructional_seeking"

@pytest.mark.asyncio
async def test_qua_communicate_placeholder():
    agent = QueryUnderstandingAgent()
    result = await agent.communicate("another_agent", {"message": "hello"})
    assert result["status"] == "communication_not_implemented"
