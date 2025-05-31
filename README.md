# WorkflowWise

WorkflowWise is an intelligent enterprise knowledge orchestrator. This project aims to leverage agentic AI, MCP (Multi-Component Protocol) servers, and vector databases to address knowledge fragmentation in hybrid workplaces.

**Core Problem:** Employees often waste significant time searching for information across disconnected systems like Confluence, SharePoint, Slack, and project management tools.

**Vision:** WorkflowWise will provide a unified interface to enterprise knowledge, featuring:
- Semantic search capabilities.
- Persistent contextual memory across user sessions.
- Proactive knowledge gap identification and suggestions.
- Secure federated search with role-based access control.
- Multi-modal knowledge processing (text, recordings, presentations, code).

## Current Status

This repository contains the initial framework and foundational components of WorkflowWise. This includes:
- Basic directory structure.
- Core abstract base classes for Agents, MCP Servers, and Vector DB interface.
- Initial agent implementations:
    - `QueryUnderstandingAgent`: For basic query parsing and intent detection.
    - `ContextOrchestrationAgent`: For managing session context.
- Stub implementations for MCP Servers:
    - `DocumentManagementMCPServer`: Simulates connection to document systems (e.g., Confluence, SharePoint).
    - `CommunicationMCPServer`: Simulates connection to communication platforms (e.g., Slack, Teams).
- A mock Vector Database interface for simulated semantic search.
- A basic Command Line Interface (CLI) (`workflowwise/cli.py`) to demonstrate the initial search workflow.
- Initial unit and integration tests using `pytest`.

## Project Structure

```
workflowwise/
├── agents/                 # AI Agent implementations
│   ├── __init__.py
│   ├── base_agent.py
│   ├── query_understanding_agent.py
│   └── context_orchestration_agent.py
├── mcp_servers/            # MCP Server implementations (stubs for now)
│   ├── __init__.py
│   ├── base_mcp_server.py
│   ├── communication_mcp_server.py
│   └── document_management_mcp_server.py
├── vector_db/              # Vector database interaction logic
│   ├── __init__.py
│   └── vector_db_interface.py
├── data_models/            # Data structures and Pydantic models
│   ├── __init__.py
│   └── knowledge_item.py
├── tests/                  # Unit and integration tests
│   ├── __init__.py
│   ├── agents/
│   └── mcp_servers/
│   └── test_cli_workflow.py
├── cli.py                  # Main CLI application runner
├── __main__.py             # Allows running CLI with 'python -m workflowwise'
└── requirements.txt        # Python dependencies
docs/                       # Project documentation (future)
README.md                   # This file
pytest.ini                  # Pytest configuration
.git/                       # Git repository data
```

## Setup and Running

1.  **Clone the repository (if you haven't already):**
    ```bash
    # git clone <repository_url>
    # cd workflowwise_project_root
    ```

2.  **Create a virtual environment and activate it (recommended):**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: `requirements.txt` currently lists `pytest` and `pytest-asyncio` for testing, and `fastapi`/`uvicorn`/`aiohttp` as placeholders for potential future API/async needs. Specific vector DB clients like `pinecone-client` or `weaviate-client` are commented out and should be chosen and uncommented as needed.)*

4.  **Run the CLI:**
    From the project root directory:
    ```bash
    python -m workflowwise
    ```
    This will start the interactive command-line interface. Type your queries and type 'exit' to quit.

5.  **Run tests:**
    From the project root directory:
    ```bash
    pytest
    ```

## Next Steps & Future Development

- Integrate a real Vector Database (e.g., Pinecone, Weaviate, Qdrant).
- Implement embedding generation for documents and queries.
- Develop more sophisticated AI agents (Security & Compliance, Learning Agent).
- Build out MCP server connectors for actual enterprise systems.
- Design and implement a user interface (Web UI or more advanced CLI).
- Expand multi-modal data processing capabilities.
- Implement robust error handling, logging, and monitoring.

## Contributing
(Details to be added as the project matures.)
