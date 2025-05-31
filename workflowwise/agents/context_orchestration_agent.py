from .base_agent import BaseAgent
from collections import deque
import logging
from typing import Dict, Any

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ContextOrchestrationAgent(BaseAgent):
    def __init__(self, agent_id: str = "context_orchestration_agent", max_history_len: int = 10):
        self.agent_id = agent_id
        # Store context per session_id
        self.session_contexts: Dict[str, deque] = {}
        self.max_history_len = max_history_len # Max number of recent items to keep in context
        logger.info(f"{self.agent_id} initialized with max history length {self.max_history_len}.")

    async def process(self, data: dict) -> dict:
        """
        Manages context for a session. For now, it stores recent processed queries/results.

        Args:
            data (dict): Expected to contain 'session_id' (str) and 'context_update' (Any).
                         'context_update' is the item to be added to the session's context.
                         It can also contain 'action' (str), e.g., 'get_context'.

        Returns:
            dict: Contains the current context for the session or status of update.
        """
        session_id = data.get("session_id")
        action = data.get("action", "update_context") # Default action

        if not session_id:
            logger.error("No session_id provided to ContextOrchestrationAgent.")
            return {"error": "Missing session_id", "status": "failure"}

        if session_id not in self.session_contexts:
            self.session_contexts[session_id] = deque(maxlen=self.max_history_len)
            logger.info(f"Initialized new context for session_id: {session_id}")

        if action == "update_context":
            context_update = data.get("context_update")
            if context_update is not None:
                self.session_contexts[session_id].append(context_update)
                logger.info(f"Updated context for session {session_id}. New context size: {len(self.session_contexts[session_id])}")
                return {"status": "success", "session_id": session_id, "message": "Context updated."}
            else:
                logger.warning(f"No context_update provided for session {session_id} with action 'update_context'.")
                return {"status": "failure", "session_id": session_id, "error": "No context_update provided."}

        elif action == "get_context":
            current_context = list(self.session_contexts[session_id])
            logger.info(f"Retrieved context for session {session_id}. Context: {current_context}")
            return {"status": "success", "session_id": session_id, "context": current_context}

        else:
            logger.warning(f"Unknown action '{action}' for session {session_id}.")
            return {"status": "failure", "session_id": session_id, "error": f"Unknown action: {action}"}


    async def communicate(self, target_agent: str, message: dict) -> dict:
        logger.info(f"{self.agent_id} attempting to communicate with {target_agent} with message: {message}")
        return {"status": "communication_not_implemented", "target": target_agent}
