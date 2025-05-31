import asyncio
import uuid # For generating session IDs
from .agents import QueryUnderstandingAgent, ContextOrchestrationAgent
from .mcp_servers import DocumentManagementMCPServer # Using only DocManagement for this basic flow
from .vector_db import VectorDBInterface # For type hinting, no real implementation yet
from .data_models import UserQuery

# --- Mock VectorDB for this CLI ---
class MockVectorDB(VectorDBInterface):
    async def connect(self): print("MockVectorDB connected.")
    async def disconnect(self): print("MockVectorDB disconnected.")

    async def upsert_vectors(self, collection_name: str, vectors, metadata):
        print(f"MockVectorDB: Would upsert to {collection_name}")
        return {"status": "success"}

    async def search(self, collection_name: str, query_vector: list, top_k: int = 5) -> list:
        # Simulate search based on keywords in query_vector (which are mock keywords for now)
        print(f"MockVectorDB: Searching in {collection_name} for vector similar to '{query_vector}' (top {top_k})")
        # In a real scenario, query_vector would be an embedding.
        # Here, we'll assume query_vector is just a list of keywords from QueryUnderstandingAgent.

        mock_search_results = []
        # Ensure query_vector is treated as a list of strings for keyword checking
        keywords_to_check = [str(item).lower() for item in query_vector]

        if "phoenix" in keywords_to_check:
            mock_search_results.append({"id": "doc_001", "score": 0.9, "metadata": {"title": "Project Phoenix Overview"}})
        if "marketing" in keywords_to_check or "q3" in keywords_to_check:
            mock_search_results.append({"id": "doc_002", "score": 0.85, "metadata": {"title": "Q3 Marketing Strategy"}})
        if "onboarding" in keywords_to_check or "guide" in keywords_to_check:
            mock_search_results.append({"id": "doc_003", "score": 0.8, "metadata": {"title": "Onboarding Guide for New Hires"}})

        # Return only top_k results, simulating ranking
        return mock_search_results[:top_k]

    async def create_collection(self, collection_name: str, vector_size: int):
        print(f"MockVectorDB: Collection {collection_name} with vector size {vector_size} would be created.")
        return {"status": "success"}

    async def delete_collection(self, collection_name: str):
        print(f"MockVectorDB: Collection {collection_name} would be deleted.")
        return {"status": "success"}
# --- End Mock VectorDB ---

async def main_workflow():
    session_id = str(uuid.uuid4())
    print(f"Starting WorkflowWise CLI. Session ID: {session_id}")

    # Initialize components
    query_agent = QueryUnderstandingAgent()
    context_agent = ContextOrchestrationAgent()
    doc_mcp_server = DocumentManagementMCPServer()
    mock_vdb = MockVectorDB()

    # Connect to services (MCP and VDB)
    await doc_mcp_server.connect()
    await mock_vdb.connect() # Mock connection

    try:
        while True:
            user_input_text = input("\nEnter your query (or type 'exit' to quit): ")
            if user_input_text.lower() == 'exit':
                break

            if not user_input_text.strip():
                print("Please enter a query.")
                continue

            # 1. User Query
            current_query = UserQuery(query_text=user_input_text, user_id="cli_user", session_id=session_id)
            print(f"\n[Workflow Step 1] User Query: {current_query.query_text}")

            # 2. Query Understanding Agent
            q_understanding_input = {"query_text": current_query.query_text, "session_id": current_query.session_id}
            q_understanding_output = await query_agent.process(q_understanding_input)
            print(f"[Workflow Step 2] Query Understanding Output: {q_understanding_output}")

            if q_understanding_output.get("status") != "success":
                print(f"Error in Query Understanding: {q_understanding_output.get('error')}")
                continue

            extracted_keywords = q_understanding_output.get("extracted_keywords", [])

            # 3. Context Orchestration Agent (Update context)
            context_update_data = {
                "session_id": current_query.session_id,
                "action": "update_context",
                "context_update": {
                    "type": "query_understanding_result",
                    "original_query": current_query.query_text,
                    "keywords": extracted_keywords,
                    "intent": q_understanding_output.get("preliminary_intent")
                }
            }
            context_update_result = await context_agent.process(context_update_data)
            print(f"[Workflow Step 3] Context Update Result: {context_update_result}")

            # (Optional) Retrieve and display current context
            # context_get_data = {"session_id": current_query.session_id, "action": "get_context"}
            # current_session_context = await context_agent.process(context_get_data)
            # print(f"Current Session Context: {current_session_context.get('context')}")


            # 4. Simulated Vector DB Search
            # In a real system, we'd generate embeddings from query_text or keywords.
            # Here, we pass keywords directly to the mock VDB search.
            print(f"\n[Workflow Step 4] Simulating Vector DB Search with keywords: {extracted_keywords}")
            # The mock_vdb.search expects a list of strings (keywords) for its simulation
            vdb_search_results = await mock_vdb.search(collection_name="main_knowledge_base", query_vector=extracted_keywords, top_k=3)
            print(f"Vector DB Search Results (Simulated): {vdb_search_results}")

            if not vdb_search_results:
                print("No relevant documents found in Vector DB (Simulated).")
                continue

            # 5. Retrieval from MCP Server stubs
            print("\n[Workflow Step 5] Retrieving document details from Document MCP Server...")
            retrieved_documents = []
            for vdb_res in vdb_search_results:
                doc_id = vdb_res.get("id")
                if doc_id:
                    print(f"Fetching document ID: {doc_id}")
                    mcp_request = {"action": "get_document_by_id", "doc_id": doc_id}
                    doc_detail_response = await doc_mcp_server.send_data(mcp_request)
                    if doc_detail_response.get("status") == "success":
                        retrieved_documents.append(doc_detail_response.get("document"))
                    else:
                        print(f"Could not retrieve document {doc_id}: {doc_detail_response.get('status')}")

            # 6. Display results
            print("\n--- Search Results ---")
            if retrieved_documents:
                for i, doc in enumerate(retrieved_documents):
                    print(f"{i+1}. ID: {doc.get('id')}, Title: {doc.get('title')}")
                    print(f"   Source: {doc.get('source')}, Type: {doc.get('type')}")
                    print(f"   Content: {doc.get('content')[:100]}...") # Display snippet
            else:
                print("No documents found or retrieved.")
            print("----------------------")

    except KeyboardInterrupt:
        print("\nExiting CLI...")
    finally:
        # Disconnect services
        await doc_mcp_server.disconnect()
        await mock_vdb.disconnect() # Mock disconnection
        print("WorkflowWise CLI terminated.")

def run_cli():
    try:
        asyncio.run(main_workflow())
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # This allows running the CLI directly, e.g. python -m workflowwise.cli
    # Ensure your PYTHONPATH is set correctly if running from outside the root project directory.
    # To run from project root: python -m workflowwise.cli
    run_cli()
