import pytest
import numpy as np
from workflowwise.services.embedding_service import EmbeddingService

# Basic test model, can be changed if a very small specific one is needed for tests
# and is guaranteed to be available. 'all-MiniLM-L6-v2' is common but might download.
# For true unit tests, SentenceTransformer itself should be mocked.
# However, for this initial test, we'll test with a real (small) model if possible,
# or handle its absence.
TEST_MODEL_NAME = 'paraphrase-MiniLM-L3-v2' # A relatively small model

@pytest.fixture(scope="module")
def embedding_service():
    """Fixture to provide an EmbeddingService instance."""
    try:
        service = EmbeddingService(model_name=TEST_MODEL_NAME)
        if not service.model: # If model download failed or other init issue
            pytest.skip(f"Skipping embedding tests: SentenceTransformer model {TEST_MODEL_NAME} could not be loaded.")
        return service
    except Exception as e: # Catch other potential import/init errors for SentenceTransformer
        pytest.skip(f"Skipping embedding tests due to EmbeddingService init error: {e}")


def test_embedding_service_initialization(embedding_service: EmbeddingService):
    assert embedding_service is not None
    assert embedding_service.model is not None
    assert embedding_service.get_dimension() > 0 # Should have a positive dimension

def test_generate_single_embedding(embedding_service: EmbeddingService):
    text = "This is a test sentence."
    embedding = embedding_service.generate_embeddings(text)
    assert embedding is not None
    assert isinstance(embedding, np.ndarray)
    assert embedding.shape == (embedding_service.get_dimension(),)

def test_generate_multiple_embeddings(embedding_service: EmbeddingService):
    texts = ["First sentence.", "Second sentence, slightly longer."]
    embeddings = embedding_service.generate_embeddings(texts)
    assert embeddings is not None
    assert isinstance(embeddings, np.ndarray) # SentenceTransformer returns a single numpy array for multiple inputs
    assert embeddings.shape == (len(texts), embedding_service.get_dimension())

def test_embedding_consistency(embedding_service: EmbeddingService):
    text = "Consistent sentence for testing."
    embedding1 = embedding_service.generate_embeddings(text)
    embedding2 = embedding_service.generate_embeddings(text)
    assert np.array_equal(embedding1, embedding2)

def test_get_dimension(embedding_service: EmbeddingService):
    dimension = embedding_service.get_dimension()
    assert isinstance(dimension, int)
    assert dimension > 0
    # For 'paraphrase-MiniLM-L3-v2', dimension is 384.
    # For 'all-MiniLM-L6-v2', dimension is also 384.
    # This is a check to ensure it matches expected if model is known.
    if TEST_MODEL_NAME in ['all-MiniLM-L6-v2', 'paraphrase-MiniLM-L3-v2']:
        assert dimension == 384

def test_embedding_service_model_load_failure():
    # Test behavior when a non-existent model is specified
    # This might log errors but should ideally not crash __init__
    # The current EmbeddingService logs an error and sets self.model to None.
    service = EmbeddingService(model_name="non-existent-model-for-testing-12345")
    assert service.model is None
    assert service.generate_embeddings("test") is None # Should return None if model failed to load
    # Dimension might return a default/assumed value or raise error depending on implementation
    # Current implementation returns an assumed dimension with a warning.
    assert service.get_dimension() > 0 # Check it returns some dimension
