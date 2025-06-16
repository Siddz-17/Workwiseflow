import re
from typing import List, Dict, Any
from .base_agent import BaseAgent

class SecurityComplianceAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.pii_patterns = {
            "EMAIL": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            # Basic North American phone number pattern, can be expanded
            "PHONE": r"(\b(?:(?:\+?1\s*(?:[.-]\s*)?)?(?:\(\s*([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9])\s*\)|([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9]))\s*(?:[.-]\s*)?)?([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9])\s*(?:[.-]\s*)?([0-9]{4})(?:\s*(?:#|x\.?|ext\.?|extension)\s*(\d+))?\b)"
        }
        self.sensitive_keywords = ["ProjectAlpha", "ProjectOmega", "TopSecretDocument", "ProjectTitan"]
        # Consider loading keywords from a config file or environment variables in a real app
        print("SecurityComplianceAgent initialized with PII patterns and sensitive keywords.")

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        action = data.get("action")
        results: Dict[str, Any] = {"status": "success"}

        if action == "analyze_documents":
            documents = data.get("documents", [])
            if not isinstance(documents, list):
                return {"status": "error", "message": "Mismatched type for 'documents', expected a list."}

            analysis_results = []
            for doc in documents:
                if not isinstance(doc, dict) or "id" not in doc or "content" not in doc:
                    analysis_results.append({
                        "doc_id": doc.get("id", "unknown_id"),
                        "issues_found": ["Invalid document structure provided."]
                    })
                    continue

                doc_id = doc["id"]
                content = doc["content"]
                issues_found = []

                # Search for PII
                for pii_type, pattern in self.pii_patterns.items():
                    for match in re.finditer(pattern, content):
                        issues_found.append(f"Found PII ({pii_type}): {match.group(0)}")

                # Search for sensitive keywords (case-sensitive for this example)
                # For case-insensitive: use keyword.lower() and content.lower()
                for keyword in self.sensitive_keywords:
                    if keyword in content:
                        issues_found.append(f"Found SENSITIVE_KEYWORD: {keyword}")

                analysis_results.append({"doc_id": doc_id, "issues_found": issues_found})

            results["analysis_results"] = analysis_results
            print(f"SecurityComplianceAgent: Analyzed {len(documents)} documents.")

        elif action == "analyze_query":
            query_text = data.get("query_text")
            if not isinstance(query_text, str):
                 return {"status": "error", "message": "Mismatched type for 'query_text', expected a string."}

            issues_found = []
            # Search for PII in query
            for pii_type, pattern in self.pii_patterns.items():
                for match in re.finditer(pattern, query_text):
                    issues_found.append(f"Found PII ({pii_type}) in query: {match.group(0)}")

            # Search for sensitive keywords in query
            for keyword in self.sensitive_keywords:
                if keyword in query_text:
                    issues_found.append(f"Found SENSITIVE_KEYWORD in query: {keyword}")

            results["query_analysis"] = {"issues_found": issues_found}
            print(f"SecurityComplianceAgent: Analyzed query.")

        else:
            results["status"] = "error"
            results["message"] = f"Unknown action: {action}"
            print(f"SecurityComplianceAgent: Unknown action '{action}'.")

        return results

    async def communicate(self, target_agent: str, message: Dict[str, Any]) -> Dict[str, Any]:
        # This agent might, in the future, communicate findings to an alerting agent
        # or request redaction from a document management agent.
        print(f"SecurityComplianceAgent: Communicate method called to target '{target_agent}' with message '{message}', but it's not fully implemented.")
        return {"status": "error", "message": "Communication not implemented for this agent at this time."}

# Example Usage (for testing purposes)
async def main_test():
    import asyncio
    agent = SecurityComplianceAgent()

    print("\n--- Testing SecurityComplianceAgent ---")

    # Test 1: Analyze Documents
    docs_to_analyze = {
        "action": "analyze_documents",
        "documents": [
            {"id": "doc1", "content": "Please email support@example.com for help with ProjectAlpha."},
            {"id": "doc2", "content": "Call us at (123) 456-7890 or +1 555 555 5555 for urgent matters regarding ProjectTitan."},
            {"id": "doc3", "content": "This document is clean and has no sensitive information."},
            {"id": "doc4", "content": "Another TopSecretDocument here. And another email test@domain.co.uk"}
        ]
    }
    doc_analysis_result = await agent.process(docs_to_analyze)
    print(f"\nDocument Analysis Result:\n{doc_analysis_result}")

    # Test 2: Analyze Query
    query_to_analyze = {
        "action": "analyze_query",
        "query_text": "What is the status of ProjectOmega? My phone is 987-654-3210."
    }
    query_analysis_result = await agent.process(query_to_analyze)
    print(f"\nQuery Analysis Result:\n{query_analysis_result}")

    # Test 3: Unknown Action
    unknown_action_data = {
        "action": "unknown_action_test",
        "payload": "some data"
    }
    unknown_action_result = await agent.process(unknown_action_data)
    print(f"\nUnknown Action Result:\n{unknown_action_result}")

    # Test 4: Communicate (as it's not implemented fully)
    communication_result = await agent.communicate("LoggingAgent", {"alert": "High severity issue found."})
    print(f"\nCommunication Result:\n{communication_result}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main_test())
