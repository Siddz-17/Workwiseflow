from typing import List, Dict, Any, Optional
from datetime import datetime
from .base_agent import BaseAgent

class LearningAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        # session_id -> list of feedback entries
        self.feedback_store: Dict[str, List[Dict[str, Any]]] = {}
        print("LearningAgent initialized with an in-memory feedback store.")

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        action = data.get("action")
        results: Dict[str, Any] = {"status": "success"}

        if action == "submit_feedback":
            session_id = data.get("session_id")
            document_id = data.get("document_id")
            feedback_type = data.get("feedback_type")
            query = data.get("query") # Optional but good to store

            if not all([session_id, document_id, feedback_type]):
                missing_fields = [field for field, value in {
                    "session_id": session_id,
                    "document_id": document_id,
                    "feedback_type": feedback_type
                }.items() if not value]
                return {
                    "status": "error",
                    "message": f"Missing required fields for submit_feedback: {', '.join(missing_fields)}"
                }

            feedback_entry = {
                "document_id": document_id,
                "query": query,
                "feedback_type": feedback_type,
                "comment": data.get("comment", ""), # Optional comment
                "timestamp": datetime.now().isoformat()
            }

            if session_id not in self.feedback_store:
                self.feedback_store[session_id] = []

            self.feedback_store[session_id].append(feedback_entry)
            print(f"LearningAgent: Feedback received for session {session_id}, doc {document_id}: {feedback_type}")
            results["message"] = "Feedback submitted successfully."

        elif action == "get_feedback":
            session_id = data.get("session_id")
            if not session_id:
                return {"status": "error", "message": "Missing 'session_id' for get_feedback action."}

            feedback_data = self.feedback_store.get(session_id, [])
            results["feedback_data"] = feedback_data
            print(f"LearningAgent: Retrieved {len(feedback_data)} feedback entries for session {session_id}.")
            if not feedback_data:
                 results["message"] = "No feedback found for this session."
            else:
                 results["message"] = "Feedback data retrieved."


        else:
            results["status"] = "error"
            results["message"] = f"Unknown action: {action}"
            print(f"LearningAgent: Unknown action '{action}'.")

        return results

    async def communicate(self, target_agent: str, message: Dict[str, Any]) -> Dict[str, Any]:
        # This agent might, in the future, send aggregated feedback to a model tuning agent
        # or trigger alerts based on frequent negative feedback.
        print(f"LearningAgent: Communicate method called to target '{target_agent}' with message '{message}', but it's not fully implemented.")
        return {"status": "error", "message": "Communication not implemented for this agent at this time."}

# Example Usage (for testing purposes)
async def main_test():
    import asyncio
    agent = LearningAgent()

    print("\n--- Testing LearningAgent ---")

    # Test 1: Submit Feedback
    feedback_data_1 = {
        "action": "submit_feedback",
        "session_id": "session_abc_123",
        "query": "What is Project Phoenix?",
        "document_id": "doc_001",
        "feedback_type": "helpful",
        "comment": "This document clearly answered my query."
    }
    feedback_result_1 = await agent.process(feedback_data_1)
    print(f"\nSubmit Feedback Result 1:\n{feedback_result_1}")

    feedback_data_2 = {
        "action": "submit_feedback",
        "session_id": "session_abc_123", # Same session
        "query": "How to manage Q3 strategy?",
        "document_id": "doc_002",
        "feedback_type": "not_helpful",
        "comment": "Too vague, did not provide actionable steps for Q3."
    }
    feedback_result_2 = await agent.process(feedback_data_2)
    print(f"\nSubmit Feedback Result 2:\n{feedback_result_2}")

    feedback_data_3 = { # Test missing field
        "action": "submit_feedback",
        "session_id": "session_xyz_789",
        # "document_id": "doc_003", # Missing document_id
        "feedback_type": "incorrect_info",
    }
    feedback_result_3 = await agent.process(feedback_data_3)
    print(f"\nSubmit Feedback Result 3 (missing field):\n{feedback_result_3}")


    # Test 2: Get Feedback for a session
    get_feedback_data_1 = {
        "action": "get_feedback",
        "session_id": "session_abc_123"
    }
    get_feedback_result_1 = await agent.process(get_feedback_data_1)
    print(f"\nGet Feedback Result (session_abc_123):\n{get_feedback_result_1}")

    # Test 3: Get Feedback for a session with no feedback
    get_feedback_data_2 = {
        "action": "get_feedback",
        "session_id": "session_new_456"
    }
    get_feedback_result_2 = await agent.process(get_feedback_data_2)
    print(f"\nGet Feedback Result (session_new_456 - no feedback):\n{get_feedback_result_2}")

    # Test 4: Unknown Action
    unknown_action_data = {
        "action": "unknown_action_test",
        "payload": "some data"
    }
    unknown_action_result = await agent.process(unknown_action_data)
    print(f"\nUnknown Action Result:\n{unknown_action_result}")

    # Test 5: Communicate (as it's not implemented fully)
    communication_result = await agent.communicate("ModelTuningAgent", {"feedback_summary": "Summary data..."})
    print(f"\nCommunication Result:\n{communication_result}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main_test())
