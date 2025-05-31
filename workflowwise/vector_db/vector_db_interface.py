from abc import ABC, abstractmethod
from typing import List, Dict, Any

class VectorDBInterface(ABC):
    @abstractmethod
    async def connect(self):
        pass

    @abstractmethod
    async def disconnect(self):
        pass

    @abstractmethod
    async def upsert_vectors(self, collection_name: str, vectors: List[Dict[str, Any]], metadata: List[Dict[str, Any]]):
        pass

    @abstractmethod
    async def search(self, collection_name: str, query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def create_collection(self, collection_name: str, vector_size: int):
        pass

    @abstractmethod
    async def delete_collection(self, collection_name: str):
        pass
