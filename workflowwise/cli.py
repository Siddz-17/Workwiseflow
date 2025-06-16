import asyncio
import uuid # For generating session IDs
from .agents import QueryUnderstandingAgent, ContextOrchestrationAgent, SecurityComplianceAgent, LearningAgent
from .mcp_servers import DocumentManagementMCPServer # Using only DocManagement for this basic flow
# from .vector_db import VectorDBInterface # No longer needed directly here
from .vector_db.qdrant_db import QdrantVectorDB # Import QdrantVectorDB
from .data_models import UserQuery
from workflowwise.embeddings.embedding_generator import generate_document_embedding, generate_query_embedding

# --- Global Configuration ---
USE_IN_MEMORY_QDRANT = True # Set to False to use localhost:6333 Qdrant instance
# Note: If switching to a persistent Qdrant, ensure it's running. E.g., via Docker:
# docker run -p 6333:6333 -p 6334:6334 -v /path/to/qdrant_storage:/qdrant/storage qdrant/qdrant


async def main_workflow():
    session_id = str(uuid.uuid4())
    print(f"Starting WorkflowWise CLI. Session ID: {session_id}")

    # Initialize components
    query_agent = QueryUnderstandingAgent()
    context_agent = ContextOrchestrationAgent()
    security_agent = SecurityComplianceAgent()
    learning_agent = LearningAgent()
    doc_mcp_server = DocumentManagementMCPServer()

    if USE_IN_MEMORY_QDRANT:
        print("Using In-Memory Qdrant for CLI.")
        qdrant_vdb = QdrantVectorDB(in_memory=True)
    else:
        print("Using Qdrant on localhost:6333 for CLI.")
        qdrant_vdb = QdrantVectorDB(host="localhost", port=6333)


    # Connect to services (MCP and VDB)
    await doc_mcp_server.connect()
    await qdrant_vdb.connect()

    # Define collection parameters - ensure these are consistent
    COLLECTION_NAME = "main_knowledge_base_cli" # Standardized name
    VECTOR_SIZE = 384 # Common size for sentence-transformers like all-MiniLM-L6-v2

    try:
        print(f"\nEnsuring collection '{COLLECTION_NAME}' exists with vector size {VECTOR_SIZE}...")
        # create_collection is generally idempotent if params are the same.
        await qdrant_vdb.create_collection(collection_name=COLLECTION_NAME, vector_size=VECTOR_SIZE)

        # Conditional Dummy Data Upsertion
        load_dummy_data = False
        try:
            # Accessing the underlying QdrantClient instance via qdrant_vdb.client
            if qdrant_vdb.client:
                collection_info = await qdrant_vdb.client.get_collection(collection_name=COLLECTION_NAME)
                points_count = collection_info.points_count
                print(f"Collection '{COLLECTION_NAME}' currently has {points_count} points.")
                if points_count == 0:
                    load_dummy_data = True
                    print(f"Collection '{COLLECTION_NAME}' is empty. Proceeding to load dummy data.")
                else:
                    print(f"Collection '{COLLECTION_NAME}' already contains data ({points_count} points). Skipping dummy data loading.")
            else:
                print("Warning: Qdrant client not available on QdrantVectorDB instance. Cannot check points count.")
                if USE_IN_MEMORY_QDRANT: # Fallback for in-memory if client check fails
                    print("Attempting to load dummy data as a fallback for in-memory DB (client check failed).")
                    load_dummy_data = True
        except Exception as e:
            print(f"Could not get collection info for '{COLLECTION_NAME}'. Error: {e}")
            if USE_IN_MEMORY_QDRANT: # Fallback for in-memory if get_collection fails
                 print("Attempting to load dummy data as a fallback for in-memory DB (collection info error).")
                 load_dummy_data = True
            else:
                print("Skipping dummy data loading due to error and not using in-memory DB.")

        if load_dummy_data:
            print("\nGenerating and upserting dummy documents (with PII/Keywords for testing)...")
            doc_text_1 = "Project Phoenix aims to overhaul legacy systems. Contact lead.dev@example.com for ProjectAlpha details."
            doc_text_2 = "The Q3 marketing strategy for ProjectTitan. Call (123) 456-7890 for our secret sauce."
            doc_text_3 = "This comprehensive onboarding guide for new software engineers. TopSecretDocument here. No PII."

            dummy_docs_data = [
                {"id": "doc_001", "text_chunk": doc_text_1, "title": "Project Phoenix Overview (contains PII & Keyword)"},
                {"id": "doc_002", "text_chunk": doc_text_2, "title": "Q3 Marketing Strategy (contains PII & Keyword)"},
                {"id": "doc_003", "text_chunk": doc_text_3, "title": "Onboarding Guide (contains Keyword)"}
            ]

            qdrant_vectors_to_upsert = []
            qdrant_metadata_to_upsert = []

            for doc_data in dummy_docs_data:
                embedding = generate_document_embedding(doc_data["text_chunk"])
                if embedding:
                    qdrant_vectors_to_upsert.append({"id": doc_data["id"], "vector": embedding})
                    qdrant_metadata_to_upsert.append({"title": doc_data["title"], "text_chunk": doc_data["text_chunk"]})
                else:
                    print(f"Warning: Could not generate embedding for dummy document ID {doc_data['id']}. Skipping.")

            if qdrant_vectors_to_upsert:
                await qdrant_vdb.upsert_vectors(
                    collection_name=COLLECTION_NAME,
                    vectors=qdrant_vectors_to_upsert,
                    metadata=qdrant_metadata_to_upsert
                )
                print(f"Upserted {len(qdrant_vectors_to_upsert)} dummy documents with real embeddings to Qdrant.")
            else:
                print("No dummy documents were upserted due to embedding generation errors or empty data.")
        # --- End Conditional Dummy Data ---

        while True:
            user_input_text = input(f"\nEnter your query for collection '{COLLECTION_NAME}' (or type 'exit' to quit): ")
            if user_input_text.lower() == 'exit':
                break

            if not user_input_text.strip():
                print("Please enter a query.")
                continue

            # 1. User Query
            current_query = UserQuery(query_text=user_input_text, user_id="cli_user", session_id=session_id)
            print(f"\n[Workflow Step 1] User Query: {current_query.query_text}")

            # 2. Query Understanding Agent (remains the same for now)
            q_understanding_input = {"query_text": current_query.query_text, "session_id": current_query.session_id}
            q_understanding_output = await query_agent.process(q_understanding_input)
            print(f"[Workflow Step 2] Query Understanding Output: {q_understanding_output}")

            if q_understanding_output.get("status") != "success":
                print(f"Error in Query Understanding: {q_understanding_output.get('error')}")
                continue

            # extracted_keywords = q_understanding_output.get("extracted_keywords", []) # Still useful for context

            # 3. Context Orchestration Agent (remains the same)
            context_update_data = {
                "session_id": current_query.session_id,
                "action": "update_context",
                "context_update": {
                    "type": "query_understanding_result",
                    "original_query": current_query.query_text,
                    "keywords": q_understanding_output.get("extracted_keywords", []),
                    "intent": q_understanding_output.get("preliminary_intent")
                }
            }
            context_update_result = await context_agent.process(context_update_data)
            print(f"[Workflow Step 3] Context Update Result: {context_update_result}")


            # 4. Vector DB Search using Qdrant with real query embeddings
            print(f"\n[Workflow Step 4] Generating query embedding and performing Vector DB Search with Qdrant...")

            query_embedding = generate_query_embedding(current_query.query_text)
            vdb_search_results = [] # Initialize empty in case of embedding failure

            if query_embedding:
                vdb_search_results = await qdrant_vdb.search(
                    collection_name=COLLECTION_NAME,
                    query_vector=query_embedding,
                    top_k=3
                )
                print(f"Vector DB Search Results (Qdrant): {vdb_search_results}")
            else:
                print("Error generating query embedding. Skipping Qdrant search.")

            if not vdb_search_results: # This handles both embedding failure and no results from search
                print("No relevant documents found in Vector DB (Qdrant).")
                continue

            # 5. Retrieval from MCP Server
            print("\n[Workflow Step 5] Retrieving document details from Document MCP Server...")
            retrieved_mcp_documents = [] # Storing full documents from MCP
            if vdb_search_results: # Ensure there are results to process
                for vdb_res in vdb_search_results:
                    doc_id = vdb_res.get("id")
                    if doc_id:
                        print(f"  Fetching document ID from MCP: {doc_id}")
                        mcp_request = {"action": "get_document_by_id", "doc_id": doc_id}
                        doc_detail_response = await doc_mcp_server.send_data(mcp_request)

                        if doc_detail_response.get("status") == "success" and doc_detail_response.get("document"):
                            retrieved_mcp_documents.append(doc_detail_response.get("document"))
                        else:
                            print(f"  Could not retrieve document {doc_id} from MCP: Status {doc_detail_response.get('status')}, Error: {doc_detail_response.get('error')}")

            # 5.5 Security/Compliance Analysis
            if retrieved_mcp_documents:
                docs_for_security_analysis = []
                for doc in retrieved_mcp_documents:
                    # Ensure doc structure and that content is a string
                    if doc and isinstance(doc, dict) and "id" in doc and isinstance(doc.get("content"), str):
                        docs_for_security_analysis.append({"id": doc.get("id"), "content": doc.get("content", "")})
                    elif doc and isinstance(doc, dict) and "id" in doc: # Content might be missing or not string
                         docs_for_security_analysis.append({"id": doc.get("id"), "content": ""}) # Send empty string for analysis
                         print(f"Warning: Document ID {doc.get('id')} has missing or non-string content. Analyzing as empty string.")


                if docs_for_security_analysis:
                    print("\n[Workflow Step 5.5] Analyzing retrieved documents for security/compliance...")
                    security_analysis_input = {"action": "analyze_documents", "documents": docs_for_security_analysis}
                    security_analysis_result = await security_agent.process(security_analysis_input)

                    if security_analysis_result.get("status") == "success":
                        analysis_map = {res.get("doc_id"): res.get("issues_found", []) for res in security_analysis_result.get("analysis_results", [])}
                        for doc_id, issues in analysis_map.items():
                            if issues:
                                print(f"WARNING: Security/Compliance issues found in document ID {doc_id}:")
                                for issue in issues:
                                    print(f"  - {issue}")
                    else:
                        print(f"Security analysis failed: {security_analysis_result.get('message')}")

            # 6. Display results
            print("\n--- Search Results (Processed) ---")
            if retrieved_mcp_documents:
                for i, doc in enumerate(retrieved_mcp_documents):
                    title = doc.get('title', 'N/A')
                    source = doc.get('source', 'N/A') # Assuming these fields exist from MCP
                    doc_type = doc.get('type', 'N/A')
                    # Use the actual content from the MCP document for the snippet
                    content_snippet = doc.get('content', '')
                    if not isinstance(content_snippet, str): # Ensure content is string before slicing
                        content_snippet = str(content_snippet)
                    content_snippet = content_snippet[:100]

                    print(f"{i+1}. ID: {doc.get('id', 'N/A')}, Title: {title}")
                    if source != 'N/A' or doc_type != 'N/A':
                         print(f"   Source: {source}, Type: {doc_type}")
                    print(f"   Content Snippet: {content_snippet}...")
            else:
                print("No documents to display after attempting retrieval from MCP.")
            print("----------------------------------")

            # 7. Collect Feedback
            if retrieved_mcp_documents: # Only ask for feedback if there were results displayed
                print("\n--- Provide Feedback (Optional) ---")
                while True:
                    feedback_input = input("Enter doc number to give feedback (e.g., '1 helpful', '2 not_helpful some comment'), or 'done' if no feedback: ").strip().lower()
                    if feedback_input == 'done':
                        break

                    parts = feedback_input.split(maxsplit=2)
                    if not parts:
                        continue

                    try:
                        doc_index_str = parts[0]
                        doc_idx = int(doc_index_str) - 1 # User sees 1-based, convert to 0-based

                        if not (0 <= doc_idx < len(retrieved_mcp_documents)):
                            print(f"Invalid document number. Please enter a number between 1 and {len(retrieved_mcp_documents)}.")
                            continue

                        selected_doc = retrieved_mcp_documents[doc_idx]
                        doc_id_for_feedback = selected_doc.get("id")

                        if len(parts) < 2:
                            print("Please provide feedback type (e.g., '1 helpful', '2 not_helpful').")
                            continue

                        feedback_type = parts[1]
                        allowed_feedback_types = ["helpful", "not_helpful", "irrelevant", "incorrect_info"] # Added incorrect_info
                        if feedback_type not in allowed_feedback_types:
                            print(f"Invalid feedback type. Allowed types: {', '.join(allowed_feedback_types)}")
                            continue

                        comment = parts[2] if len(parts) > 2 else ""

                        feedback_data = {
                            "action": "submit_feedback",
                            "session_id": session_id,
                            "query": current_query.query_text,
                            "document_id": doc_id_for_feedback,
                            "feedback_type": feedback_type,
                            "comment": comment
                        }

                        # Assuming learning_agent is instantiated earlier
                        feedback_result = await learning_agent.process(feedback_data)
                        if feedback_result.get("status") == "success":
                            print(f"Feedback submitted for document {doc_index_str} ('{selected_doc.get('title', 'N/A')}').")
                        else:
                            print(f"Failed to submit feedback: {feedback_result.get('message')}")

                    except ValueError:
                        print("Invalid input format. Example: '1 helpful [optional comment]' or 'done'.")
                    except Exception as e:
                        print(f"Error processing feedback: {e}")
                print("-----------------------------------")

    except KeyboardInterrupt:
        print("\nExiting CLI...")
    except Exception as e: # Catch other exceptions during main loop
        print(f"\nAn unexpected error occurred in the main loop: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Disconnect services
        await doc_mcp_server.disconnect()
        if 'qdrant_vdb' in locals() and qdrant_vdb.client: # Check if initialized
            await qdrant_vdb.disconnect()
        print("WorkflowWise CLI terminated.")

def run_cli():
    try:
        asyncio.run(main_workflow())
    except Exception as e:
        print(f"An overall CLI error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # This allows running the CLI directly, e.g. python -m workflowwise.cli
    # Ensure your PYTHONPATH is set correctly if running from outside the root project directory.
    # To run from project root: python -m workflowwise.cli
    run_cli()
