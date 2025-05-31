from abc import ABC, abstractmethod

class BaseMCPServer(ABC):
    @abstractmethod
    async def connect(self):
        pass

    @abstractmethod
    async def disconnect(self):
        pass

    @abstractmethod
    async def send_data(self, data: dict) -> dict:
        pass

    @abstractmethod
    async def receive_data(self) -> dict:
        pass
