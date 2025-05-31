from .base_agent import BaseAgent
from workflowwise.services.embedding_service import EmbeddingService
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QueryUnderstandingAgent(BaseAgent):
    def __init__(self, agent_id: str = "query_understanding_agent"):
        self.agent_id = agent_id
        self.embedding_service = EmbeddingService()
        logger.info(f"{self.agent_id} initialized. Embedding service ready: {self.embedding_service is not None and self.embedding_service.model is not None}")

    async def process(self, data: dict) -> dict:
        query_text = data.get("query_text")
        session_id = data.get("session_id")

        if not query_text:
            logger.error("No query_text provided to QueryUnderstandingAgent.")
            return {"error": "Missing query_text", "original_query": query_text, "session_id": session_id, "status": "failure"}

        logger.info(f"Processing query for session {session_id}: '{query_text}'")

        # Placeholder for future advanced query processing
        logger.debug("Future: Apply advanced query parsing, entity extraction, or rephrasing here before embedding.")

        stopwords = set(["a", "an", "the", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of"])
        words = re.findall(r'\b\w+\b', query_text.lower()) # Corrected regex
        keywords = [word for word in words if word not in stopwords and len(word) > 2]

        preliminary_intent = "information_retrieval"
        if "compare" in keywords or "vs" in query_text.lower():
            preliminary_intent = "comparison"
        elif "how to" in query_text.lower() or "guide" in keywords:
            preliminary_intent = "instructional_seeking"

        query_embedding = None
        if self.embedding_service and self.embedding_service.model:
            try:
                embedding_result = self.embedding_service.generate_embeddings(query_text)
                if embedding_result is not None:
                    query_embedding = embedding_result.tolist()
                    logger.info(f"Generated query embedding for: '{query_text}'")
                else:
                    logger.error(f"Failed to generate embedding for query: '{query_text}'")
            except Exception as e:
                logger.error(f"Exception during embedding generation: {e}", exc_info=True)
        else:
            logger.error("Embedding service not available or model not loaded in QueryUnderstandingAgent.")

        logger.info(f"Extracted keywords: {keywords}, Preliminary intent: {preliminary_intent}")

        current_status = "success"
        if not query_embedding:
            current_status = "partial_success_no_embedding"
            logger.warning(f"Query understanding for '{query_text}' resulted in no embedding.")

        return {
            "original_query": query_text,
            "extracted_keywords": list(set(keywords)),
            "preliminary_intent": preliminary_intent,
            "query_embedding": query_embedding,
            "session_id": session_id,
            "status": current_status
        }

    async def communicate(self, target_agent: str, message: dict) -> dict:
        logger.info(f"{self.agent_id} attempting to communicate with {target_agent} with message: {message}")
        return {"status": "communication_not_implemented", "target": target_agent}
