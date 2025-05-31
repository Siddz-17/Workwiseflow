from .vector_db_interface import VectorDBInterface
from typing import List, Dict, Any, Optional
import logging
import os

# Try to import Pinecone, handle if not installed (though it's in requirements)
try:
    from pinecone import Pinecone, Index, PodSpec, ServerlessSpec
    pinecone_available = True
except ImportError:
    pinecone_available = False
    Pinecone, Index, PodSpec, ServerlessSpec = None, None, None, None # Placeholder if not installed

logger = logging.getLogger(__name__)

class PineconeDB(VectorDBInterface):
    def __init__(self, api_key: Optional[str] = None, environment: Optional[str] = None, index_name: str = "workflowwise-index"):
        """
        Initializes the PineconeDB client.
        API key and environment can be provided or fetched from environment variables PINECONE_API_KEY and PINECONE_ENVIRONMENT.
        """
        if not pinecone_available:
            logger.error("Pinecone client library not found. Please install pinecone-client.")
            raise ImportError("Pinecone client library not found.")

        self.api_key = api_key or os.getenv("PINECONE_API_KEY")
        # Environment for PodSpec, or region for ServerlessSpec would be needed.
        # Pinecone client v3.x uses environment/region in spec, not directly in Pinecone() constructor.
        self.pinecone_pod_environment = environment or os.getenv("PINECONE_ENVIRONMENT")
        self.index_name = index_name
        self.pinecone_client: Optional[Pinecone] = None
        self.index: Optional[Index] = None

        if not self.api_key:
            logger.warning("Pinecone API key not provided or found in PINECONE_API_KEY environment variable.")
            # Not raising error here, connect() will fail if key is still missing.

        # Pinecone client initialization is lightweight, actual connection happens in connect()

    async def connect(self):
        """Connects to Pinecone and ensures the index is ready."""
        if not self.api_key:
            logger.error("Cannot connect to Pinecone: API key is missing.")
            raise ValueError("Pinecone API key is missing.")

        try:
            logger.info(f"Attempting to connect to Pinecone...")
            self.pinecone_client = Pinecone(api_key=self.api_key)
            logger.info("Pinecone client initialized.")
            # Further index-specific connection logic will be in methods like create_collection or when getting self.index
        except Exception as e:
            logger.error(f"Failed to initialize Pinecone client: {e}", exc_info=True)
            self.pinecone_client = None # Ensure client is None if init fails
            raise ConnectionError(f"Failed to initialize Pinecone client: {e}")

    async def _get_or_create_index(self, vector_size: Optional[int] = None, metric: str = 'cosine', serverless: bool = True, cloud: str = 'aws', region: str = 'us-west-2'):
        """
        Gets the Pinecone index, creating it if it doesn't exist.
        Allows choosing between serverless and pod-based specs.
        """
        if not self.pinecone_client:
            await self.connect()
            if not self.pinecone_client:
                 raise ConnectionError("Pinecone client not initialized. Cannot get or create index.")

        if self.index_name not in self.pinecone_client.list_indexes().names:
            if vector_size is None:
                logger.error(f"Index '{self.index_name}' does not exist and no vector_size provided to create it.")
                raise ValueError(f"Index '{self.index_name}' does not exist and vector_size is required for creation.")

            logger.info(f"Index '{self.index_name}' not found. Creating new index with dimension {vector_size} and metric {metric}.")
            try:
                if serverless:
                    spec = ServerlessSpec(cloud=cloud, region=region)
                    logger.info(f"Using ServerlessSpec: cloud='{cloud}', region='{region}'")
                else:
                    if not self.pinecone_pod_environment:
                        err_msg = "PINECONE_ENVIRONMENT must be set for pod-based indexes."
                        logger.error(err_msg)
                        raise ValueError(err_msg)
                    spec = PodSpec(environment=self.pinecone_pod_environment)
                    logger.info(f"Using PodSpec: environment='{self.pinecone_pod_environment}'")

                self.pinecone_client.create_index(
                    name=self.index_name,
                    dimension=vector_size,
                    metric=metric,
                    spec=spec
                )
                logger.info(f"Index '{self.index_name}' creation initiated. It may take some time to become ready.")
                # Add a small delay or check for readiness if needed, though SDK might handle some of this.
            except Exception as e:
                logger.error(f"Failed to create Pinecone index '{self.index_name}': {e}", exc_info=True)
                raise ConnectionError(f"Failed to create Pinecone index '{self.index_name}': {e}")
        else:
            logger.info(f"Index '{self.index_name}' already exists.")

        self.index = self.pinecone_client.Index(self.index_name)
        logger.info(f"Successfully connected to Pinecone index '{self.index_name}'. Status: {self.index.describe_index_stats()}")


    async def disconnect(self):
        logger.info("PineconeDB disconnect called (typically a no-op for client operations).")

    async def create_collection(self, collection_name: str, vector_size: int, metric: str = 'cosine', serverless: bool = True, cloud: str = 'aws', region: str = 'us-west-2'):
        if collection_name != self.index_name:
            logger.warning(f"Requested collection_name '{collection_name}' is different from PineconeDB index_name '{self.index_name}'. Using '{self.index_name}'.")

        await self._get_or_create_index(vector_size=vector_size, metric=metric, serverless=serverless, cloud=cloud, region=region)


    async def upsert_vectors(self, collection_name: str, vectors: List[Dict[str, Any]]):
        if collection_name != self.index_name:
            logger.warning(f"Requested collection_name '{collection_name}' is different from PineconeDB index_name '{self.index_name}'. Upserting to '{self.index_name}'.")

        if not self.index:
            # Attempt to create with default serverless, but vector_size might be unknown here.
            # This path is risky if create_collection wasn't called first.
            logger.warning(f"Index not explicitly created via create_collection. Attempting _get_or_create_index for '{self.index_name}'. Vector size must be known if index doesn't exist.")
            await self._get_or_create_index() # This might fail if index doesn't exist and vector_size is not passed.
            if not self.index:
                 raise ConnectionError("Pinecone index not available. Cannot upsert vectors.")

        pinecone_vectors = []
        for v in vectors:
            if not ('id' in v and 'values' in v):
                logger.error(f"Vector missing 'id' or 'values': {v}")
                continue
            pinecone_vectors.append({'id': v['id'], 'values': v['values'], 'metadata': v.get('metadata', {})})

        if not pinecone_vectors:
            logger.warning("No valid vectors to upsert.")
            return {"error": "No valid vectors to upsert.", "status": "failure"}

        try:
            logger.info(f"Upserting {len(pinecone_vectors)} vectors to index '{self.index_name}'...")
            upsert_response = self.index.upsert(vectors=pinecone_vectors)
            logger.info(f"Upsert response: {upsert_response}")
            return {"status": "success", "upserted_count": upsert_response.upserted_count}
        except Exception as e:
            logger.error(f"Failed to upsert vectors to Pinecone: {e}", exc_info=True)
            return {"error": str(e), "status": "failure"}


    async def search(self, collection_name: str, query_vector: List[float], top_k: int = 5, filter_dict: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if collection_name != self.index_name:
            logger.warning(f"Requested collection_name '{collection_name}' is different from PineconeDB index_name '{self.index_name}'. Searching in '{self.index_name}'.")

        if not self.index:
            logger.warning(f"Index not explicitly created. Attempting _get_or_create_index for '{self.index_name}'.")
            await self._get_or_create_index()
            if not self.index:
                 raise ConnectionError("Pinecone index not available. Cannot search.")

        try:
            logger.info(f"Searching index '{self.index_name}' with top_k={top_k}...")
            results = self.index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True,
                filter=filter_dict
            )
            logger.info(f"Search returned {len(results.matches)} matches.")

            formatted_results = []
            for match in results.matches:
                formatted_results.append({
                    "id": match.id,
                    "score": match.score,
                    "metadata": match.metadata or {}
                })
            return formatted_results
        except Exception as e:
            logger.error(f"Failed to search Pinecone: {e}", exc_info=True)
            return []

    async def delete_collection(self, collection_name: str):
        if not self.pinecone_client:
            await self.connect()
            if not self.pinecone_client:
                 raise ConnectionError("Pinecone client not initialized. Cannot delete collection.")

        if collection_name != self.index_name:
            logger.error(f"Cannot delete collection '{collection_name}'. This instance is configured for '{self.index_name}'.")
            return {"status": "failure", "error": "Mismatched collection name for deletion."}

        try:
            if self.index_name in self.pinecone_client.list_indexes().names:
                logger.info(f"Deleting index '{self.index_name}'...")
                self.pinecone_client.delete_index(self.index_name)
                logger.info(f"Index '{self.index_name}' deleted successfully.")
                self.index = None
                return {"status": "success"}
            else:
                logger.info(f"Index '{self.index_name}' not found. Nothing to delete.")
                return {"status": "not_found"}
        except Exception as e:
            logger.error(f"Failed to delete Pinecone index '{self.index_name}': {e}", exc_info=True)
            return {"error": str(e), "status": "failure"}
