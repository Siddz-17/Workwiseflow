from .base_agent import BaseAgent
import logging
import re # For simple keyword extraction

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QueryUnderstandingAgent(BaseAgent):
    def __init__(self, agent_id: str = "query_understanding_agent"):
        self.agent_id = agent_id
        logger.info(f"{self.agent_id} initialized.")

    async def process(self, data: dict) -> dict:
        """
        Processes a user query to extract keywords and basic intent.
        For now, it performs simple keyword extraction.

        Args:
            data (dict): Expected to contain 'query_text' (str) and 'session_id' (str).

        Returns:
            dict: Contains 'original_query', 'extracted_keywords', 'preliminary_intent', and 'session_id'.
        """
        query_text = data.get("query_text")
        session_id = data.get("session_id")

        if not query_text:
            logger.error("No query_text provided to QueryUnderstandingAgent.")
            return {
                "error": "Missing query_text",
                "original_query": query_text,
                "session_id": session_id
            }

        logger.info(f"Processing query for session {session_id}: '{query_text}'")

        # Simple keyword extraction: split by space and take non-stopwords (very basic)
        # A more advanced approach would involve NLP libraries like spaCy or NLTK
        stopwords = set(["a", "an", "the", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of"])
        words = re.findall(r'\b\w+\b', query_text.lower()) # Corrected regex
        keywords = [word for word in words if word not in stopwords and len(word) > 2]

        # Placeholder for intent recognition
        preliminary_intent = "information_retrieval" # Default intent
        if "compare" in keywords or "vs" in query_text.lower():
            preliminary_intent = "comparison"
        elif "how to" in query_text.lower() or "guide" in keywords:
            preliminary_intent = "instructional_seeking"

        logger.info(f"Extracted keywords: {keywords}, Preliminary intent: {preliminary_intent}")

        return {
            "original_query": query_text,
            "extracted_keywords": list(set(keywords)), # Unique keywords
            "preliminary_intent": preliminary_intent,
            "session_id": session_id,
            "status": "success"
        }

    async def communicate(self, target_agent: str, message: dict) -> dict:
        # In a real system, this would involve a message bus or direct API calls.
        # For now, it's a placeholder.
        logger.info(f"{self.agent_id} attempting to communicate with {target_agent} with message: {message}")
        # Simulate sending message and getting a response
        return {"status": "communication_not_implemented", "target": target_agent}
