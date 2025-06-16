import uuid
from typing import List, Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from workflowwise.vector_db.qdrant_db import QdrantVectorDB
from workflowwise.embeddings.embedding_generator import generate_document_embedding, generate_query_embedding # generate_query_embedding for future use

# --- Configuration & Global State ---
app = FastAPI(title="WorkflowWise Web API")

qdrant_db_client: Optional[QdrantVectorDB] = None
COLLECTION_NAME = "web_knowledge_base_main" # Using a distinct name for web UI
VECTOR_SIZE = 384  # Must match the embedding model (e.g., all-MiniLM-L6-v2)

# --- Pydantic Models ---
class DocumentIngestRequest(BaseModel):
    id: Optional[str] = None
    content: str
    metadata: Optional[Dict[str, Any]] = {}

class DocumentIngestResponse(BaseModel):
    document_id: str
    status: str
    message: Optional[str] = None

class SearchQueryRequest(BaseModel):
    query_text: str
    top_k: Optional[int] = 5

class SearchResultDocument(BaseModel):
    id: str
    score: float
    payload: Optional[Dict[str, Any]] = {}
    # content: Optional[str] = None # If content is stored in payload and needs to be explicitly shown

class SearchQueryResponse(BaseModel):
    status: str
    results: List[SearchResultDocument] = []
    message: Optional[str] = None


# --- Event Handlers ---
@app.on_event("startup")
async def startup_event():
    global qdrant_db_client
    print("FastAPI app startup initiated...")
    try:
        # Using in-memory Qdrant for simplicity in this example.
        # Replace with host/port for a persistent Qdrant instance.
        # qdrant_db_client = QdrantVectorDB(host="localhost", port=6333)
        qdrant_db_client = QdrantVectorDB(in_memory=True)
        await qdrant_db_client.connect() # connect() is async
        print("Qdrant client connected successfully.")

        # Ensure the collection exists
        # Qdrant's recreate_collection is idempotent if parameters (vector_size, distance) are the same.
        # If you want to avoid recreating, you'd typically list collections and check.
        await qdrant_db_client.create_collection(
            collection_name=COLLECTION_NAME,
            vector_size=VECTOR_SIZE
            # distance parameter defaults to COSINE in our QdrantVectorDB implementation
        )
        print(f"Collection '{COLLECTION_NAME}' ensured/created with vector size {VECTOR_SIZE}.")

    except Exception as e:
        print(f"Error during startup: {e}")
        # Depending on severity, you might want to prevent app startup
        # For now, we'll let it start, but endpoints might fail.
        qdrant_db_client = None # Ensure client is None if connection failed


@app.on_event("shutdown")
async def shutdown_event():
    global qdrant_db_client
    print("FastAPI app shutdown initiated...")
    if qdrant_db_client:
        try:
            await qdrant_db_client.disconnect() # disconnect() is async
            print("Qdrant client disconnected successfully.")
        except Exception as e:
            print(f"Error during Qdrant client disconnection: {e}")
    else:
        print("Qdrant client was not initialized, no disconnection needed.")


# --- API Endpoints ---
@app.post("/documents/ingest", response_model=DocumentIngestResponse)
async def ingest_document(doc_request: DocumentIngestRequest):
    global qdrant_db_client
    if not qdrant_db_client or not qdrant_db_client.client: # Check if client object within QdrantVectorDB is also available
        raise HTTPException(status_code=503, detail="Vector DB client not available. Check server startup logs.")

    doc_id = doc_request.id if doc_request.id else str(uuid.uuid4())

    print(f"Received request to ingest document ID: {doc_id if doc_request.id else 'new_uuid_generated'}")

    try:
        embedding = generate_document_embedding(doc_request.content)
        if not embedding:
            # This case should be handled by an exception in generate_document_embedding if model is not loaded
            # or if input is invalid. If it can return empty list for other reasons, this is important.
            print(f"Error: Failed to generate embedding for document content: {doc_request.content[:100]}...")
            raise HTTPException(status_code=500, detail="Failed to generate document embedding.")

        vector_to_upsert = {"id": doc_id, "vector": embedding}

        # Ensure 'content' is part of metadata for potential retrieval, if not already there.
        # Also, ensure all metadata values are of types Qdrant can handle (str, int, float, bool, list of these).
        metadata_payload = doc_request.metadata.copy() if doc_request.metadata else {}
        if 'content' not in metadata_payload:
            metadata_payload['content'] = doc_request.content

        # Sanitize metadata (optional, but good practice for complex metadata)
        # For this example, we assume metadata is already Qdrant-compatible.

        print(f"Upserting vector for document ID: {doc_id} into collection '{COLLECTION_NAME}'")
        await qdrant_db_client.upsert_vectors(
            collection_name=COLLECTION_NAME,
            vectors=[vector_to_upsert],  # upsert_vectors expects a list of vector dicts
            metadata=[metadata_payload] # and a list of corresponding metadata dicts
        )
        print(f"Successfully upserted document ID: {doc_id}")
        return DocumentIngestResponse(document_id=doc_id, status="success", message="Document ingested successfully.")

    except HTTPException as http_exc:
        # Re-raise FastAPI's HTTPException directly
        raise http_exc
    except Exception as e:
        print(f"Unhandled error during document ingestion for ID {doc_id}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


# Placeholder for search endpoint (to be implemented in a future step)
@app.post("/search/query", response_model=SearchQueryResponse)
async def search_query(query_request: SearchQueryRequest):
    global qdrant_db_client
    if not qdrant_db_client or not qdrant_db_client.client:
         raise HTTPException(status_code=503, detail="Vector DB client not available.")

    print(f"Received search query: '{query_request.query_text}' with top_k={query_request.top_k}")

    query_embedding = generate_query_embedding(query_request.query_text)
    if not query_embedding:
        raise HTTPException(status_code=500, detail="Failed to generate query embedding.")

    try:
        search_results_raw = await qdrant_db_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_embedding,
            top_k=query_request.top_k
        )

        # Transform results to match SearchResultDocument model
        # Qdrant results are like: [{"id": ..., "score": ..., "payload": {...}, "vector": Optional[...]}]
        # Our SearchResultDocument expects: {"id": ..., "score": ..., "payload": {...}}

        formatted_results = [
            SearchResultDocument(
                id=str(hit.get("id")), # Ensure ID is string
                score=hit.get("score"),
                payload=hit.get("payload")
            ) for hit in search_results_raw
        ]

        print(f"Search completed. Found {len(formatted_results)} results.")
        return SearchQueryResponse(status="success", results=formatted_results)

    except Exception as e:
        print(f"Error during search: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


if __name__ == "__main__":
    print("Attempting to run Uvicorn server for WorkflowWise Web API...")
    # It's common to run uvicorn from the command line like: uvicorn workflowwise.web_ui.main_web:app --reload
    # But this allows direct execution for simplicity e.g. python -m workflowwise.web_ui.main_web
    uvicorn.run("main_web:app", host="0.0.0.0", port=8000, reload=True, workers=1)
