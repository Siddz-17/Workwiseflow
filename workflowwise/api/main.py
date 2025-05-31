from fastapi import FastAPI, HTTPException, Body, Request as FastAPIRequest
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os
import logging
import uuid

from workflowwise.agents import QueryUnderstandingAgent, ContextOrchestrationAgent
from workflowwise.mcp_servers import DocumentManagementMCPServer
from workflowwise.vector_db import PineconeDB
from workflowwise.services.embedding_service import EmbeddingService

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(
    title="WorkflowWise API",
    description="API for interacting with the WorkflowWise knowledge orchestrator.",
    version="0.1.0"
)

# --- Static Files Mounting ---
# Correctly determine path to 'static' directory, assuming 'static' is at the project root
# and this 'main.py' is in 'workflowwise/api/'
module_dir = os.path.dirname(os.path.abspath(__file__)) # workflowwise/api
project_root = os.path.abspath(os.path.join(module_dir, "..", "..")) # Project root
static_dir_path = os.path.join(project_root, "static")

if os.path.isdir(static_dir_path):
    app.mount("/static", StaticFiles(directory=static_dir_path), name="static")
    logger.info(f"Mounted static files from: {static_dir_path}")
else:
    logger.warning(f"Static files directory not found at {static_dir_path}. UI (index.html) will not be served from root.")


# --- Global Variables / Shared Resources ---
embedding_service: Optional[EmbeddingService] = None
query_agent: Optional[QueryUnderstandingAgent] = None
context_agent: Optional[ContextOrchestrationAgent] = None
vector_db: Optional[PineconeDB] = None
doc_mcp_server: Optional[DocumentManagementMCPServer] = None

PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "workflowwise-api-index")
USE_SERVERLESS_INDEX = os.getenv("USE_SERVERLESS_INDEX", "true").lower() == "true"
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

# --- Pydantic Models ---
class SearchQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="The search query text.")
    top_k: int = Field(default=5, gt=0, le=10, description="Number of results to return.") # Increased default to 5
    session_id: Optional[str] = Field(default=None, description="Optional session ID.")

class DocumentResult(BaseModel):
    id: str
    title: str
    score: float
    content_snippet: Optional[str] = None
    full_content_preview: Optional[str] = None
    source: Optional[str] = None
    type: Optional[str] = None

class SearchResponse(BaseModel):
    query: str
    results: List[DocumentResult]
    message: Optional[str] = None
    session_id: Optional[str] = None


# --- Application Startup Event ---
@app.on_event("startup")
async def startup_event():
    global embedding_service, query_agent, context_agent, vector_db, doc_mcp_server

    logger.info("FastAPI application startup...")

    embedding_service = EmbeddingService()
    if not embedding_service.model: logger.error("Failed to load embedding model.")
    else: logger.info("EmbeddingService initialized.")

    query_agent = QueryUnderstandingAgent()
    logger.info("QueryUnderstandingAgent initialized.")

    context_agent = ContextOrchestrationAgent()
    logger.info("ContextOrchestrationAgent initialized.")

    doc_mcp_server = DocumentManagementMCPServer()
    await doc_mcp_server.connect()
    logger.info("DocumentManagementMCPServer (stub) initialized and connected.")

    pinecone_api_key = os.getenv("PINECONE_API_KEY")
    pinecone_pod_env = os.getenv("PINECONE_ENVIRONMENT")

    if not pinecone_api_key:
        logger.error("PINECONE_API_KEY missing. PineconeDB cannot be initialized.")
    elif not USE_SERVERLESS_INDEX and not pinecone_pod_env:
        logger.error("PINECONE_ENVIRONMENT must be set for pod-based indexes. PineconeDB cannot be initialized.")
    else:
        try:
            vector_db = PineconeDB(api_key=pinecone_api_key, environment=pinecone_pod_env, index_name=PINECONE_INDEX_NAME)
            await vector_db.connect()

            if embedding_service and embedding_service.model:
                logger.info(f"Ensuring Pinecone index '{PINECONE_INDEX_NAME}' exists with dimension {embedding_service.get_dimension()}.")
                await vector_db.create_collection(
                    collection_name=PINECONE_INDEX_NAME,
                    vector_size=embedding_service.get_dimension(),
                    serverless=USE_SERVERLESS_INDEX,
                    cloud=PINECONE_CLOUD,
                    region=PINECONE_REGION
                )
                logger.info("PineconeDB initialized, connected, and index checked/created.")
            else:
                 logger.error("Cannot determine embedding dimension for Pinecone index creation as embedding service failed.")
                 vector_db = None # Prevent use if index cannot be guaranteed
        except Exception as e:
            logger.error(f"Error initializing or connecting to PineconeDB: {e}", exc_info=True)
            vector_db = None
    logger.info("FastAPI startup complete.")

# --- API Endpoints ---
@app.post("/api/search", response_model=SearchResponse)
async def search_documents_api(request: SearchQueryRequest = Body(...)): # Renamed to avoid conflict
    logger.info(f"Search request: Query='{request.query}', Top_K='{request.top_k}', Session_ID='{request.session_id}'")

    if not all([embedding_service, embedding_service.model, query_agent, vector_db, doc_mcp_server, doc_mcp_server.connected]):
        missing = []
        if not embedding_service or not embedding_service.model: missing.append("Embedding service")
        if not query_agent: missing.append("Query agent")
        if not vector_db: missing.append("Vector DB (Pinecone unavailable/misconfigured)")
        if not doc_mcp_server or not doc_mcp_server.connected: missing.append("Document MCP server")
        detail = f"One or more services are not available: {', '.join(missing)}."
        logger.error(detail)
        raise HTTPException(status_code=503, detail=detail)

    active_session_id = request.session_id or str(uuid.uuid4())

    q_understanding_input = {"query_text": request.query, "session_id": active_session_id}
    q_understanding_output = await query_agent.process(q_understanding_input)

    if q_understanding_output.get("status") == "failure" or not q_understanding_output.get("query_embedding"):
        detail = f"Failed to process query: {q_understanding_output.get('error', 'No embedding generated')}"
        logger.error(detail)
        raise HTTPException(status_code=500, detail=detail)

    query_embedding = q_understanding_output.get("query_embedding")

    try:
        vdb_search_results = await vector_db.search(
            collection_name=PINECONE_INDEX_NAME,
            query_vector=query_embedding,
            top_k=request.top_k
        )
    except Exception as e:
        logger.error(f"Error during Pinecone search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error searching vector database: {str(e)}")

    if not vdb_search_results:
        return SearchResponse(query=request.query, results=[], message="No relevant documents found.", session_id=active_session_id)

    output_results: List[DocumentResult] = []
    for res in vdb_search_results:
        doc_id, score, metadata = res.get("id"), res.get("score", 0.0), res.get("metadata", {})
        title, content_snippet = metadata.get("title", "N/A"), metadata.get("content_snippet", "")
        source, doc_type = metadata.get("source", "N/A"), metadata.get("type", "N/A")

        mcp_doc_data = await doc_mcp_server.send_data({"action": "get_document_by_id", "doc_id": doc_id})
        full_content_preview = content_snippet
        if mcp_doc_data.get("status") == "success" and mcp_doc_data.get("document"):
            full_content = mcp_doc_data["document"].get("content", "")
            full_content_preview = full_content[:200] + "..." if full_content else content_snippet

        output_results.append(DocumentResult(
            id=doc_id, title=title, score=score,
            content_snippet=content_snippet, full_content_preview=full_content_preview,
            source=source, type=doc_type
        ))

    return SearchResponse(query=request.query, results=output_results, session_id=active_session_id)

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_index_html_root(fastapi_request: FastAPIRequest): # Parameter name changed
    index_html_full_path = os.path.join(static_dir_path, "index.html")
    if os.path.exists(index_html_full_path):
        return FileResponse(index_html_full_path)
    else:
        logger.error(f"index.html not found at {index_html_full_path}. Ensure 'static' dir is at project root.")
        return HTMLResponse(content="<h1>Error: index.html not found</h1><p>Please ensure the 'static' directory with 'index.html' is correctly placed at the project root.</p>", status_code=404)

if __name__ == "__main__":
    import uvicorn
    print("Attempting to run Uvicorn server for WorkflowWise API...")
    print("Ensure required environment variables (e.g., PINECONE_API_KEY) are set.")
    print(f"Serving UI from: {static_dir_path}")
    uvicorn.run("workflowwise.api.main:app", host="0.0.0.0", port=8000, reload=True)
