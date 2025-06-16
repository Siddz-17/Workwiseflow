from typing import List
from sentence_transformers import SentenceTransformer
import numpy as np

# Define the model name
MODEL_NAME = 'all-MiniLM-L6-v2' # This model outputs 384-dimensional embeddings

# Initialize the model globally
# This means the model is loaded once when the module is first imported.
# For applications with many models or memory constraints, consider lazy loading
# or managing model instances within a class.
try:
    model = SentenceTransformer(MODEL_NAME)
    print(f"SentenceTransformer model '{MODEL_NAME}' loaded successfully.")
except Exception as e:
    print(f"Error loading SentenceTransformer model '{MODEL_NAME}': {e}")
    # Fallback or raise critical error if model loading fails
    model = None

def generate_document_embedding(document_text: str) -> List[float]:
    """
    Generates an embedding for a given document text.
    """
    if model is None:
        print("Error: SentenceTransformer model is not loaded.")
        return [] # Or raise an exception

    if not document_text or not isinstance(document_text, str):
        print("Error: Document text must be a non-empty string.")
        return [] # Or raise ValueError

    try:
        # Encode the document text. convert_to_numpy=True is default in newer versions.
        # .tolist() converts the numpy array to a Python list.
        embedding = model.encode(document_text, convert_to_tensor=False)
        if isinstance(embedding, np.ndarray):
            return embedding.tolist()
        else:
            # Should not happen with convert_to_tensor=False, but good to check
            print("Warning: model.encode did not return a numpy array as expected.")
            return list(map(float, embedding)) # Attempt conversion if it's some other iterable

    except Exception as e:
        print(f"Error generating document embedding: {e}")
        return [] # Or raise an exception

def generate_query_embedding(query_text: str) -> List[float]:
    """
    Generates an embedding for a given query text.
    For 'all-MiniLM-L6-v2', query and document embeddings are generated the same way.
    Some models might suggest prefixing queries (e.g., "query: " + query_text).
    """
    if model is None:
        print("Error: SentenceTransformer model is not loaded.")
        return [] # Or raise an exception

    if not query_text or not isinstance(query_text, str):
        print("Error: Query text must be a non-empty string.")
        return [] # Or raise ValueError

    try:
        # Encode the query text
        embedding = model.encode(query_text, convert_to_tensor=False)
        if isinstance(embedding, np.ndarray):
            return embedding.tolist()
        else:
            print("Warning: model.encode did not return a numpy array as expected.")
            return list(map(float, embedding))

    except Exception as e:
        print(f"Error generating query embedding: {e}")
        return [] # Or raise an exception

# Example Usage (for testing purposes)
if __name__ == '__main__':
    if model:
        print(f"\n--- Testing Embedding Generation (Model: {MODEL_NAME}) ---")

        sample_doc = "This is a sample document about project management and software development."
        doc_embedding = generate_document_embedding(sample_doc)

        if doc_embedding:
            print(f"\nDocument: \"{sample_doc}\"")
            print(f"Embedding (first 5 dims): {doc_embedding[:5]}")
            print(f"Embedding dimension: {len(doc_embedding)}") # Should be 384 for all-MiniLM-L6-v2

        sample_query = "What are the best practices for software project management?"
        query_embedding = generate_query_embedding(sample_query)

        if query_embedding:
            print(f"\nQuery: \"{sample_query}\"")
            print(f"Embedding (first 5 dims): {query_embedding[:5]}")
            print(f"Embedding dimension: {len(query_embedding)}")

        # Test empty input
        print("\nTesting with empty document text:")
        empty_doc_emb = generate_document_embedding("")
        if not empty_doc_emb:
            print("Correctly handled empty document text.")

        print("\nTesting with empty query text:")
        empty_query_emb = generate_query_embedding("")
        if not empty_query_emb:
            print("Correctly handled empty query text.")
    else:
        print("Cannot run tests: SentenceTransformer model failed to load.")

    # Example of how embeddings might be used with Qdrant (conceptual)
    # from qdrant_client import QdrantClient, models
    # client = QdrantClient(":memory:")
    # collection_name = "my_test_collection"
    # vector_size = len(doc_embedding) if doc_embedding else 384
    # client.recreate_collection(
    #     collection_name=collection_name,
    #     vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE)
    # )
    # if doc_embedding and query_embedding:
    #     client.upsert(
    #         collection_name=collection_name,
    #         points=[
    #             models.PointStruct(id=1, vector=doc_embedding, payload={"text": sample_doc}),
    #             models.PointStruct(id=2, vector=generate_document_embedding("Another document here."), payload={"text": "Another doc"}),
    #         ]
    #     )
    #     search_result = client.search(
    #         collection_name=collection_name,
    #         query_vector=query_embedding,
    #         limit=1
    #     )
    #     print(f"\nConceptual Qdrant search result: {search_result}")

    print("\nEmbedding generator module basic functionality testing complete.")
