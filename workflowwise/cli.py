import asyncio
import uuid
import os
from workflowwise.agents import QueryUnderstandingAgent, ContextOrchestrationAgent
from workflowwise.mcp_servers import DocumentManagementMCPServer
from workflowwise.vector_db import PineconeDB # Changed from MockVectorDB
from workflowwise.services.embedding_service import EmbeddingService
from workflowwise.data_models import UserQuery
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Sample documents for initial ingestion
SAMPLE_DOCUMENTS = [
    {"id": "doc_001", "title": "Project Phoenix Overview", "content": "Project Phoenix is a next-generation initiative focused on leveraging AI to enhance customer engagement. It involves cross-functional teams and aims for a Q4 launch.", "source": "Confluence", "type": "document"},
    {"id": "doc_002", "title": "Q3 Marketing Strategy", "content": "Our Q3 marketing strategy emphasizes digital channels, content marketing, and influencer collaborations. Key performance indicators include website traffic and conversion rates.", "source": "SharePoint", "type": "document"},
    {"id": "doc_003", "title": "Onboarding Guide for New Hires", "content": "This guide provides essential information for new hires, covering company policies, team structures, and available resources. Please complete the checklist within your first week.", "source": "HR Portal", "type": "document"},
    {"id": "doc_004", "title": "Engineering Best Practices", "content": "This document outlines software engineering best practices, including version control, code reviews, testing methodologies, and deployment procedures.", "source": "Dev Wiki", "type": "document"},
    {"id": "doc_005", "title": "Customer Support Handbook", "content": "The customer support handbook details procedures for handling inquiries, escalating issues, and ensuring customer satisfaction. Empathy and timely responses are key.", "source": "Support System", "type": "document"}
]
PINECONE_INDEX_NAME = "workflowwise-cli-index" # Specific index for this CLI example
# Determine if we want to use serverless or pod-based index from env var, default to True (serverless)
USE_SERVERLESS_INDEX = os.getenv("USE_SERVERLESS_INDEX", "true").lower() == "true"
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1") # Changed default to a common one like us-east-1 for aws

async def ingest_sample_data(db: PineconeDB, embed_service: EmbeddingService):
    logger.info(f"Checking/Creating Pinecone index '{PINECONE_INDEX_NAME}' with dimension {embed_service.get_dimension()}...")
    try:
        # Pass serverless configuration from environment or defaults
        await db.create_collection(
            collection_name=PINECONE_INDEX_NAME,
            vector_size=embed_service.get_dimension(),
            serverless=USE_SERVERLESS_INDEX,
            cloud=PINECONE_CLOUD,
            region=PINECONE_REGION
        )

        logger.info("Starting ingestion of sample documents...")
        vectors_to_upsert = []
        for doc in SAMPLE_DOCUMENTS:
            # For documents, it's often better to embed meaningful chunks or combined title+content.
            doc_text_for_embedding = f"{doc['title']}. {doc['content']}"
            embedding_array = embed_service.generate_embeddings(doc_text_for_embedding)

            if embedding_array is not None:
                # Ensure embedding_array is a 1D list of floats.
                # SentenceTransformer usually returns a single vector (ndarray) for a single string.
                if hasattr(embedding_array, 'ndim') and embedding_array.ndim == 1:
                    embedding_list = embedding_array.tolist()
                elif isinstance(embedding_array, list) and len(embedding_array) > 0 and isinstance(embedding_array[0], float): # Already a list of floats
                    embedding_list = embedding_array
                else: # If it's a list of lists (e.g., if texts was a list with one item)
                    embedding_list = embedding_array[0].tolist() if hasattr(embedding_array[0], 'tolist') else list(embedding_array[0])


                vectors_to_upsert.append({
                    "id": doc["id"],
                    "values": embedding_list,
                    "metadata": {
                        "title": doc["title"],
                        "source": doc["source"],
                        "type": doc["type"],
                        "content_snippet": doc["content"][:150] # Store a snippet in metadata
                    }
                })
            else:
                logger.warning(f"Could not generate embedding for doc_id: {doc['id']}")

        if vectors_to_upsert:
            logger.info(f"Upserting {len(vectors_to_upsert)} documents to Pinecone index '{PINECONE_INDEX_NAME}'.")
            upsert_result = await db.upsert_vectors(collection_name=PINECONE_INDEX_NAME, vectors=vectors_to_upsert)
            logger.info(f"Pinecone upsert result: {upsert_result}")
        else:
            logger.info("No vectors to upsert for sample data.")

    except Exception as e:
        logger.error(f"Error during sample data ingestion: {e}", exc_info=True)
        logger.error("Please ensure PINECONE_API_KEY and PINECONE_ENVIRONMENT (if using pod-based index) are correctly set.")
        logger.error(f"Also check Pinecone project settings for cloud '{PINECONE_CLOUD}' and region '{PINECONE_REGION}' if using serverless.")


async def main_workflow():
    session_id = str(uuid.uuid4())
    logger.info(f"Starting WorkflowWise CLI. Session ID: {session_id}")

    pinecone_api_key = os.getenv("PINECONE_API_KEY")
    # PINECONE_ENVIRONMENT is only strictly needed for pod-based indexes.
    # For serverless, cloud and region are specified in the spec.
    pinecone_pod_environment = os.getenv("PINECONE_ENVIRONMENT")

    if not pinecone_api_key:
        logger.error("PINECONE_API_KEY environment variable not set. Pinecone integration will fail.")
        return
    if not USE_SERVERLESS_INDEX and not pinecone_pod_environment:
        logger.error("PINECONE_ENVIRONMENT must be set when using Pod-based Pinecone indexes (USE_SERVERLESS_INDEX=false).")
        return

    embedding_service = EmbeddingService()
    if not embedding_service.model:
        logger.error("Failed to load embedding model. CLI cannot function effectively.")
        return

    query_agent = QueryUnderstandingAgent()
    context_agent = ContextOrchestrationAgent()
    doc_mcp_server = DocumentManagementMCPServer()

    vector_db = PineconeDB(api_key=pinecone_api_key, environment=pinecone_pod_environment, index_name=PINECONE_INDEX_NAME)

    try:
        await vector_db.connect()
        logger.info("Successfully initialized Pinecone client in main_workflow.")

        await ingest_sample_data(vector_db, embedding_service)
        await doc_mcp_server.connect()
    except Exception as e:
        logger.error(f"Failed to connect to Pinecone or ingest data: {e}", exc_info=True)
        logger.error("CLI cannot proceed without successful Pinecone connection and setup.")
        return

    try:
        while True:
            user_input_text = input("\nEnter your query (or type 'exit' to quit): ").strip()
            if user_input_text.lower() == 'exit':
                break
            if not user_input_text:
                print("Please enter a query.")
                continue

            current_query = UserQuery(query_text=user_input_text, user_id="cli_user", session_id=session_id)
            logger.info(f"User Query: {current_query.query_text}")

            q_understanding_input = {"query_text": current_query.query_text, "session_id": current_query.session_id}
            q_understanding_output = await query_agent.process(q_understanding_input)
            logger.info(f"Query Understanding Output: {q_understanding_output}")

            if q_understanding_output.get("status") == "failure" or not q_understanding_output.get("query_embedding"):
                logger.error(f"Error in Query Understanding or no embedding: {q_understanding_output.get('error', 'No embedding generated')}")
                print("Sorry, I couldn't understand or process your query properly to find relevant documents.")
                continue

            query_embedding = q_understanding_output.get("query_embedding")

            context_update_data = {
                "session_id": current_query.session_id, "action": "update_context",
                "context_update": {"type": "query_understanding_result", "data": q_understanding_output}
            }
            await context_agent.process(context_update_data)

            logger.info(f"Searching Pinecone with query embedding...")
            vdb_search_results = await vector_db.search(
                collection_name=PINECONE_INDEX_NAME,
                query_vector=query_embedding,
                top_k=3
            )
            logger.info(f"Pinecone Search Results: {vdb_search_results}")

            if not vdb_search_results:
                print("No relevant documents found in Vector DB for your query.")
                continue

            print("\n--- Search Results (from Pinecone, details from MCP stub) ---")
            retrieved_documents_info = []
            for vdb_res in vdb_search_results:
                doc_id = vdb_res.get("id")
                score = vdb_res.get("score")
                metadata = vdb_res.get("metadata", {})
                title = metadata.get("title", "N/A")

                mcp_request = {"action": "get_document_by_id", "doc_id": doc_id}
                doc_detail_response = await doc_mcp_server.send_data(mcp_request)

                full_content = "Full content not found in MCP."
                if doc_detail_response.get("status") == "success" and doc_detail_response.get("document"):
                    full_content = doc_detail_response.get("document", {}).get("content", full_content)

                retrieved_documents_info.append({
                    "id": doc_id, "title": title, "score": score,
                    "content_snippet": metadata.get("content_snippet", full_content[:100]+"..."),
                    "full_content_preview": full_content[:200] + "..."
                })

            if retrieved_documents_info:
                for i, doc_info in enumerate(retrieved_documents_info):
                    print(f"{i+1}. ID: {doc_info['id']}, Title: {doc_info['title']} (Score: {doc_info['score']:.4f})")
                    print(f"   Snippet: {doc_info['content_snippet']}")
            else:
                print("No documents could be fully retrieved or detailed.")
            print("---------------------------------------------------------------")

    except KeyboardInterrupt:
        logger.info("Exiting CLI via KeyboardInterrupt...")
    except Exception as e:
        logger.error(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
    finally:
        if 'vector_db' in locals() and vector_db: await vector_db.disconnect()
        if 'doc_mcp_server' in locals() and doc_mcp_server: await doc_mcp_server.disconnect()
        logger.info("WorkflowWise CLI terminated.")

def run_cli():
    required_env_vars = ["PINECONE_API_KEY"]
    if not USE_SERVERLESS_INDEX:
        required_env_vars.append("PINECONE_ENVIRONMENT") # Pod environment
    else: # For serverless, cloud and region are also important but have defaults
        pass # PINECONE_CLOUD, PINECONE_REGION have defaults

    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        print(f"ERROR: The following environment variables must be set: {', '.join(missing_vars)}")
        print("Example: export PINECONE_API_KEY='your-api-key'")
        if "PINECONE_ENVIRONMENT" in missing_vars:
             print("         export PINECONE_ENVIRONMENT='your-project-environment' (e.g. gcp-starter or a pod environment)")
        print(f"Additionally, for serverless (default, USE_SERVERLESS_INDEX=true), you might want to set PINECONE_CLOUD (default: {PINECONE_CLOUD}) and PINECONE_REGION (default: {PINECONE_REGION}).")
        return

    try:
        asyncio.run(main_workflow())
    except Exception as e:
        logger.error(f"CLI execution failed: {e}", exc_info=True)

if __name__ == "__main__":
    run_cli()
