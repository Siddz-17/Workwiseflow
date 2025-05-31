import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from workflowwise.cli import main_workflow # main_workflow is the async orchestrator
from workflowwise.agents import QueryUnderstandingAgent, ContextOrchestrationAgent
from workflowwise.mcp_servers import DocumentManagementMCPServer

@pytest.mark.asyncio
@patch('builtins.input', side_effect=['test query about phoenix', 'exit']) # Simulate user input
@patch('workflowwise.cli.QueryUnderstandingAgent', autospec=True)
@patch('workflowwise.cli.ContextOrchestrationAgent', autospec=True)
@patch('workflowwise.cli.DocumentManagementMCPServer', autospec=True)
@patch('workflowwise.cli.MockVectorDB', autospec=True) # Mock our MockVectorDB for more control
async def test_cli_basic_flow(mock_vdb_class, mock_doc_mcp_class, mock_context_agent_class, mock_query_agent_class, mock_input, capsys):
    # Setup mock instances and their return values
    mock_query_agent_instance = mock_query_agent_class.return_value
    mock_query_agent_instance.process = AsyncMock(return_value={
        "status": "success",
        "original_query": "test query about phoenix",
        "extracted_keywords": ["test", "query", "phoenix"],
        "preliminary_intent": "information_retrieval",
        "session_id": "test_session"
    })

    mock_context_agent_instance = mock_context_agent_class.return_value
    mock_context_agent_instance.process = AsyncMock(return_value={"status": "success", "message": "Context updated."})

    mock_vdb_instance = mock_vdb_class.return_value
    mock_vdb_instance.connect = AsyncMock()
    mock_vdb_instance.disconnect = AsyncMock()
    mock_vdb_instance.search = AsyncMock(return_value=[
        {"id": "doc_001", "score": 0.9, "metadata": {"title": "Project Phoenix Overview"}}
    ])

    mock_doc_mcp_instance = mock_doc_mcp_class.return_value
    mock_doc_mcp_instance.connect = AsyncMock()
    mock_doc_mcp_instance.disconnect = AsyncMock()
    mock_doc_mcp_instance.send_data = AsyncMock(return_value={
        "status": "success",
        "document": {"id": "doc_001", "title": "Project Phoenix Overview", "content": "Mock content...", "source": "Confluence", "type": "document"}
    })

    # Run the main workflow
    await main_workflow()

    # Assertions
    mock_input.assert_any_call("\nEnter your query (or type 'exit' to quit): ")

    mock_query_agent_instance.process.assert_called_once()
    # Check if called with expected parts of the input
    call_args = mock_query_agent_instance.process.call_args[0][0] # First positional argument
    assert call_args['query_text'] == 'test query about phoenix'

    mock_context_agent_instance.process.assert_called_once()

    mock_vdb_instance.search.assert_called_once()
    # Check if search was called with keywords from query agent
    vdb_call_args = mock_vdb_instance.search.call_args[1] # Keyword arguments
    assert vdb_call_args['query_vector'] == ["test", "query", "phoenix"]

    mock_doc_mcp_instance.send_data.assert_called_once_with(
        {"action": "get_document_by_id", "doc_id": "doc_001"}
    )

    # Check output (optional, can be fragile)
    captured = capsys.readouterr()
    assert "Project Phoenix Overview" in captured.out
    assert "Mock content..." in captured.out
    assert "Starting WorkflowWise CLI." in captured.out # Check if CLI started
    assert "WorkflowWise CLI terminated." in captured.out # Check if CLI terminated
