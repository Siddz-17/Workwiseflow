from abc import ABC, abstractmethod

class BaseAgent(ABC):
    """Abstract base class for all AI agents in the WorkflowWise system."""

    @abstractmethod
    async def process(self, data: dict) -> dict:
        """
        Process an incoming request or data payload.

        This method should be implemented by concrete agent classes to define
        their specific logic for handling tasks, queries, or events.

        Args:
            data (dict): The input data for the agent to process.
                         The structure of this dictionary will depend on the agent.

        Returns:
            dict: The result of the processing.
                  The structure of this dictionary will also depend on the agent.
        """
        pass

    @abstractmethod
    async def communicate(self, target_agent: str, message: dict) -> dict:
        """
        Communicate with another agent or component in the system.

        This method could involve sending messages via a message bus,
        making API calls, or other inter-component communication mechanisms.

        Args:
            target_agent (str): The identifier of the target agent or component.
            message (dict): The message payload to send.

        Returns:
            dict: The response received from the target agent/component, or a status
                  indicating the outcome of the communication attempt.
        """
        pass
