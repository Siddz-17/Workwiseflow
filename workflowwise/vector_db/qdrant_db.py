import asyncio
from typing import List, Dict, Any
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import PointStruct # Explicit import for PointStruct
from workflowwise.vector_db.vector_db_interface import VectorDBInterface

class QdrantVectorDB(VectorDBInterface):
    def __init__(self, host: str = "localhost", port: int = 6333, in_memory: bool = False, api_key: str = None):
        if in_memory:
            self.client = QdrantClient(":memory:")
        else:
            # Pass API key if provided
            self.client = QdrantClient(host=host, port=port, api_key=api_key, prefer_grpc=True) # Added prefer_grpc for potential performance
        self.host = host
        self.port = port
        self.in_memory = in_memory
        self.api_key = api_key # Store api_key if needed for other operations or reconnections

    async def connect(self):
        try:
            # Qdrant client is generally ready after initialization.
            # For async, ensure operations that require IO are awaited if the client library demands it.
            # Here, we simulate an async check if necessary, or confirm connection status.
            # get_collections is synchronous in the current qdrant_client,
            # but we might wrap it or use an async version if available/needed.
            # For now, we assume initialization is sufficient for "connection".
            await asyncio.sleep(0.01) # Simulate async operation if needed
            # Example: self.client.get_collections() # This is sync, wrap if true async needed
            print(f"Successfully connected/initialized Qdrant client for {'in-memory' if self.in_memory else f'{self.host}:{self.port}'}.")
        except Exception as e:
            print(f"Failed to connect/initialize Qdrant client: {e}")
            raise

    async def disconnect(self):
        try:
            # The qdrant_client's close() method is synchronous.
            # If an async close becomes available, it should be used here.
            self.client.close()
            await asyncio.sleep(0.01) # Simulate async operation
            print("Successfully disconnected from Qdrant.")
        except Exception as e:
            print(f"Error disconnecting from Qdrant: {e}")

    async def _upsert_points(self, collection_name: str, points: List[PointStruct]):
        try:
            # The standard client's upsert is synchronous.
            # If using an async client or version, this call would be awaited.
            self.client.upsert(collection_name=collection_name, points=points)
            await asyncio.sleep(0.01) # Simulate async nature of I/O
            print(f"Successfully upserted {len(points)} points into collection '{collection_name}'.")
        except Exception as e:
            print(f"Error upserting points into collection '{collection_name}': {e}")
            raise

    async def upsert_vectors(self, collection_name: str, vectors: List[Dict[str, Any]], metadata: List[Dict[str, Any]]):
        if len(vectors) != len(metadata):
            raise ValueError("The number of vectors and metadata items must be the same.")

        points_to_upsert = []
        for vector_data, meta in zip(vectors, metadata):
            if "id" not in vector_data or "vector" not in vector_data:
                raise ValueError("Each vector dictionary must have 'id' and 'vector' keys.")

            points_to_upsert.append(PointStruct(
                id=vector_data["id"],
                vector=vector_data["vector"],
                payload=meta
            ))

        await self._upsert_points(collection_name=collection_name, points=points_to_upsert)
        print(f"Data prepared and upsert operation initiated for {len(points_to_upsert)} vectors in '{collection_name}'.")

    async def search(self, collection_name: str, query_vector: List[float], top_k: int = 5, with_payload: bool = True, score_threshold: float = None) -> List[Dict[str, Any]]:
        try:
            # The standard client's search is synchronous.
            search_results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=top_k,
                with_payload=with_payload, # Pass this along
                score_threshold=score_threshold # Pass this along
            )
            await asyncio.sleep(0.01) # Simulate async I/O

            formatted_results = []
            for hit in search_results:
                formatted_results.append({
                    "id": hit.id,
                    "score": hit.score,
                    "payload": hit.payload,
                    # "vector": hit.vector # Vector might be large, include if explicitly needed by interface consumer
                })
            print(f"Search completed in collection '{collection_name}'. Found {len(formatted_results)} results.")
            return formatted_results
        except Exception as e:
            print(f"Error searching in collection '{collection_name}': {e}")
            raise

    async def create_collection(self, collection_name: str, vector_size: int, distance_metric: str = "Cosine"):
        # Map string distance metric to Qdrant models.Distance
        # Supporting "Cosine", "Euclid", "Dot" as common examples
        distance_enum = models.Distance.COSINE
        if distance_metric.upper() == "EUCLID":
            distance_enum = models.Distance.EUCLID
        elif distance_metric.upper() == "DOT":
            distance_enum = models.Distance.DOTPRODUCT # Corrected to DOTPRODUCT

        try:
            # The standard client's recreate_collection is synchronous.
            self.client.recreate_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=vector_size, distance=distance_enum)
            )
            await asyncio.sleep(0.01) # Simulate async I/O
            print(f"Successfully created/recreated collection '{collection_name}' with vector size {vector_size} and distance {distance_metric}.")
        except Exception as e:
            print(f"Error creating collection '{collection_name}': {e}")
            raise

    async def delete_collection(self, collection_name: str):
        try:
            # The standard client's delete_collection is synchronous.
            self.client.delete_collection(collection_name=collection_name)
            await asyncio.sleep(0.01) # Simulate async I/O
            print(f"Successfully deleted collection '{collection_name}'.")
        except Exception as e:
            print(f"Error deleting collection '{collection_name}': {e}")
            raise


async def main_test(): # Renamed main to main_test and made it async
    # In-memory example
    db_in_memory = QdrantVectorDB(in_memory=True)
    await db_in_memory.connect()

    collection_name_memory = "test_collection_memory_async"
    vector_size_memory = 4

    print(f"\n--- In-Memory Async DB Operations ---")
    await db_in_memory.create_collection(collection_name=collection_name_memory, vector_size=vector_size_memory, distance_metric="Cosine")

    # Prepare data for upsert (using the public upsert_vectors method)
    vectors_to_upsert = [
        {"id": 1, "vector": [0.05, 0.61, 0.76, 0.74]},
        {"id": 2, "vector": [0.19, 0.81, 0.75, 0.11]},
        {"id": 3, "vector": [0.36, 0.55, 0.47, 0.94]},
    ]
    metadata_for_upsert = [
        {"city": "Berlin", "country": "Germany"},
        {"city": "London", "country": "UK"},
        {"city": "Moscow", "country": "Russia"},
    ]

    await db_in_memory.upsert_vectors(
        collection_name=collection_name_memory,
        vectors=vectors_to_upsert,
        metadata=metadata_for_upsert
    )

    # Search vectors
    query_vector_memory = [0.2, 0.1, 0.8, 0.7]
    search_results_memory = await db_in_memory.search(
        collection_name=collection_name_memory,
        query_vector=query_vector_memory,
        top_k=2
    )
    print(f"Async search results for in-memory DB: {search_results_memory}")

    await db_in_memory.delete_collection(collection_name_memory)
    await db_in_memory.disconnect()

    # To run the remote example, uncomment and ensure Qdrant is running at localhost:6333
    # print(f"\n--- Remote Async DB Operations (requires Qdrant at localhost:6333) ---")
    # db_remote = QdrantVectorDB(host="localhost", port=6333)
    # await db_remote.connect()
    # collection_name_remote = "test_collection_remote_async"
    # await db_remote.create_collection(collection_name_remote, vector_size=vector_size_memory)
    # remote_vectors = [{"id": i, "vector": [random.random() for _ in range(vector_size_memory)]} for i in range(5, 10)]
    # remote_metadata = [{"source": "remote_async"} for _ in range(len(remote_vectors))]
    # await db_remote.upsert_vectors(collection_name_remote, remote_vectors, remote_metadata)
    # search_results_remote = await db_remote.search(collection_name_remote, query_vector=[0.1,0.2,0.3,0.4], top_k=2)
    # print(f"Async search results for remote DB: {search_results_remote}")
    # await db_remote.delete_collection(collection_name_remote)
    # await db_remote.disconnect()


if __name__ == '__main__':
    asyncio.run(main_test()) # Use asyncio.run to execute the async main function
    print("QdrantVectorDB class implemented and basic async tests completed.")
