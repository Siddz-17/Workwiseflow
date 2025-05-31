import pytest
from workflowwise.agents import ContextOrchestrationAgent

@pytest.mark.asyncio
async def test_coa_initialization():
    agent = ContextOrchestrationAgent(agent_id="test_coa", max_history_len=5)
    assert agent.agent_id == "test_coa"
    assert agent.max_history_len == 5

@pytest.mark.asyncio
async def test_coa_update_and_get_context():
    agent = ContextOrchestrationAgent(max_history_len=3)
    session_id = "s1"

    update1 = {"type": "query", "text": "hello"}
    res1 = await agent.process({"session_id": session_id, "action": "update_context", "context_update": update1})
    assert res1["status"] == "success"

    context_res1 = await agent.process({"session_id": session_id, "action": "get_context"})
    assert context_res1["status"] == "success"
    assert len(context_res1["context"]) == 1
    assert context_res1["context"][0] == update1

    update2 = {"type": "result", "data": "world"}
    await agent.process({"session_id": session_id, "action": "update_context", "context_update": update2})

    context_res2 = await agent.process({"session_id": session_id, "action": "get_context"})
    assert len(context_res2["context"]) == 2
    assert context_res2["context"][1] == update2

@pytest.mark.asyncio
async def test_coa_context_history_limit():
    agent = ContextOrchestrationAgent(max_history_len=2)
    session_id = "s2"

    await agent.process({"session_id": session_id, "action": "update_context", "context_update": "item1"})
    await agent.process({"session_id": session_id, "action": "update_context", "context_update": "item2"})
    await agent.process({"session_id": session_id, "action": "update_context", "context_update": "item3"})

    context_res = await agent.process({"session_id": session_id, "action": "get_context"})
    assert len(context_res["context"]) == 2
    assert context_res["context"][0] == "item2" # Oldest (item1) should be gone
    assert context_res["context"][1] == "item3"

@pytest.mark.asyncio
async def test_coa_missing_session_id():
    agent = ContextOrchestrationAgent()
    result = await agent.process({"action": "get_context"})
    assert result["status"] == "failure"
    assert result["error"] == "Missing session_id"

@pytest.mark.asyncio
async def test_coa_unknown_action():
    agent = ContextOrchestrationAgent()
    session_id = "s3"
    await agent.process({"session_id": session_id, "action": "update_context", "context_update": "item1"}) # ensure context exists
    result = await agent.process({"session_id": session_id, "action": "unknown_action"})
    assert result["status"] == "failure"
    assert "Unknown action" in result["error"]
