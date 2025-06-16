import pytest
from datetime import datetime
from unittest.mock import patch # For controlling datetime.now()

from workflowwise.agents import LearningAgent

pytestmark = pytest.mark.asyncio

@pytest.fixture
def agent():
    """Fixture to create a LearningAgent instance."""
    return LearningAgent()

async def test_submit_feedback_valid(agent: LearningAgent):
    """Test submitting a valid feedback entry."""
    session_id = "test_session_001"
    doc_id = "doc_abc"
    query_text = "What is WorkflowWise?"
    feedback_type = "helpful"
    comment_text = "Very clear explanation."

    # Mock datetime.now() to control the timestamp
    mock_now = datetime(2023, 10, 26, 12, 0, 0)
    with patch('workflowwise.agents.learning_agent.datetime') as mock_datetime:
        mock_datetime.now.return_value = mock_now

        data = {
            "action": "submit_feedback",
            "session_id": session_id,
            "query": query_text,
            "document_id": doc_id,
            "feedback_type": feedback_type,
            "comment": comment_text
        }
        result = await agent.process(data)

    assert result["status"] == "success"
    assert result["message"] == "Feedback submitted successfully."

    assert session_id in agent.feedback_store
    assert len(agent.feedback_store[session_id]) == 1

    feedback_entry = agent.feedback_store[session_id][0]
    assert feedback_entry["document_id"] == doc_id
    assert feedback_entry["query"] == query_text
    assert feedback_entry["feedback_type"] == feedback_type
    assert feedback_entry["comment"] == comment_text
    assert feedback_entry["timestamp"] == mock_now.isoformat()

async def test_submit_feedback_multiple_for_session(agent: LearningAgent):
    """Test submitting multiple feedback entries for the same session."""
    session_id = "test_session_002"

    feedback_data_1 = {
        "action": "submit_feedback", "session_id": session_id, "document_id": "doc_001",
        "feedback_type": "helpful", "query": "Query 1"
    }
    feedback_data_2 = {
        "action": "submit_feedback", "session_id": session_id, "document_id": "doc_002",
        "feedback_type": "not_helpful", "query": "Query 1", "comment": "Not relevant."
    }

    await agent.process(feedback_data_1)
    await agent.process(feedback_data_2)

    assert session_id in agent.feedback_store
    assert len(agent.feedback_store[session_id]) == 2
    assert agent.feedback_store[session_id][0]["document_id"] == "doc_001"
    assert agent.feedback_store[session_id][1]["document_id"] == "doc_002"


async def test_submit_feedback_missing_required_fields(agent: LearningAgent):
    """Test submitting feedback with missing required fields."""
    # Missing document_id
    data_missing_doc_id = {
        "action": "submit_feedback", "session_id": "s1",
        "feedback_type": "helpful", "query": "q1"
    }
    result = await agent.process(data_missing_doc_id)
    assert result["status"] == "error"
    assert "Missing required fields" in result["message"]
    assert "document_id" in result["message"]
    assert not agent.feedback_store.get("s1") # Ensure no feedback was stored

    # Missing session_id
    data_missing_session = {
        "action": "submit_feedback", "document_id": "d1",
        "feedback_type": "helpful", "query": "q1"
    }
    result = await agent.process(data_missing_session)
    assert result["status"] == "error"
    assert "session_id" in result["message"]

    # Missing feedback_type
    data_missing_type = {
        "action": "submit_feedback", "session_id": "s1", "document_id": "d1",
        "query": "q1"
    }
    result = await agent.process(data_missing_type)
    assert result["status"] == "error"
    assert "feedback_type" in result["message"]

async def test_get_feedback_empty(agent: LearningAgent):
    """Test getting feedback for a session with no entries."""
    session_id = "non_existent_session"
    data = {"action": "get_feedback", "session_id": session_id}
    result = await agent.process(data)

    assert result["status"] == "success"
    assert result["feedback_data"] == []
    assert "No feedback found" in result["message"]

async def test_get_feedback_with_data(agent: LearningAgent):
    """Test submitting feedback and then retrieving it."""
    session_id = "test_session_003"
    feedback_data_to_submit = {
        "action": "submit_feedback", "session_id": session_id, "document_id": "doc_xyz",
        "feedback_type": "incorrect_info", "query": "Is this true?", "comment": "The sky is green."
    }

    # Mock timestamp for predictable comparison
    mock_now = datetime(2023, 10, 26, 15, 0, 0)
    with patch('workflowwise.agents.learning_agent.datetime') as mock_datetime:
        mock_datetime.now.return_value = mock_now
        await agent.process(feedback_data_to_submit)

    data_to_get = {"action": "get_feedback", "session_id": session_id}
    result = await agent.process(data_to_get)

    assert result["status"] == "success"
    assert len(result["feedback_data"]) == 1

    retrieved_entry = result["feedback_data"][0]
    assert retrieved_entry["document_id"] == "doc_xyz"
    assert retrieved_entry["feedback_type"] == "incorrect_info"
    assert retrieved_entry["comment"] == "The sky is green."
    assert retrieved_entry["timestamp"] == mock_now.isoformat()

async def test_get_feedback_missing_session_id(agent: LearningAgent):
    """Test get_feedback action when session_id is not provided."""
    data = {"action": "get_feedback"} # Missing session_id
    result = await agent.process(data)
    assert result["status"] == "error"
    assert "Missing 'session_id'" in result["message"]

async def test_unknown_action(agent: LearningAgent):
    """Test processing with an unknown action."""
    data = {"action": "some_other_action", "payload": "data"}
    result = await agent.process(data)
    assert result["status"] == "error"
    assert "Unknown action" in result["message"]

async def test_communicate_not_implemented(agent: LearningAgent):
    """Test that communicate method returns a 'not implemented' message."""
    result = await agent.communicate("FeedbackAggregator", {"data": "summary"})
    assert result["status"] == "error"
    assert "Communication not implemented" in result["message"]
