import pytest
from unittest.mock import patch, MagicMock
import numpy as np # For creating a numpy array for the mock

# Functions to test
from workflowwise.embeddings.embedding_generator import generate_document_embedding, generate_query_embedding, MODEL_NAME

# Expected dimension for the specific model 'all-MiniLM-L6-v2'
EXPECTED_DIMENSION = 384

@patch('workflowwise.embeddings.embedding_generator.SentenceTransformer')
def test_generate_document_embedding_success(MockSentenceTransformer):
    """Test successful document embedding generation."""
    mock_model_instance = MagicMock()
    # Configure the mock 'encode' method to return a numpy array
    mock_model_instance.encode.return_value = np.array([0.1] * EXPECTED_DIMENSION)
    MockSentenceTransformer.return_value = mock_model_instance

    # Re-initialize the module's model variable if SentenceTransformer is loaded globally in the module
    # This is a bit tricky. If the model is loaded at module import time, the patch might need to be applied
    # before the module is imported by the test, or the module needs to be reloaded.
    # For simplicity, let's assume the functions use the 'model' variable that would be
    # an instance of the patched SentenceTransformer.
    # If 'model' is defined globally like 'model = SentenceTransformer(MODEL_NAME)',
    # we need to ensure our tests use the patched version.
    # A common way is to ensure the module is imported *after* the patch is applied for the test session,
    # or to have a helper function within the module to set/get the model, which we can then mock.
    # Given current structure, the global `model` in embedding_generator.py will be an instance of the *real*
    # SentenceTransformer if not handled.
    # A workaround for testing: patch the *global model object itself* if it's already loaded.

    # Let's patch the 'model' object directly within the embedding_generator module for these tests.
    with patch('workflowwise.embeddings.embedding_generator.model', mock_model_instance):
        test_text = "This is a test document."
        embedding = generate_document_embedding(test_text)

        mock_model_instance.encode.assert_called_once_with(test_text, convert_to_tensor=False)
        assert isinstance(embedding, list)
        assert len(embedding) == EXPECTED_DIMENSION
        assert all(isinstance(x, float) for x in embedding)

@patch('workflowwise.embeddings.embedding_generator.SentenceTransformer')
def test_generate_query_embedding_success(MockSentenceTransformer):
    """Test successful query embedding generation."""
    mock_model_instance = MagicMock()
    mock_model_instance.encode.return_value = np.array([0.2] * EXPECTED_DIMENSION)
    MockSentenceTransformer.return_value = mock_model_instance

    with patch('workflowwise.embeddings.embedding_generator.model', mock_model_instance):
        test_query = "This is a test query."
        embedding = generate_query_embedding(test_query)

        mock_model_instance.encode.assert_called_once_with(test_query, convert_to_tensor=False)
        assert isinstance(embedding, list)
        assert len(embedding) == EXPECTED_DIMENSION
        assert all(isinstance(x, float) for x in embedding)

@patch('workflowwise.embeddings.embedding_generator.SentenceTransformer')
def test_embedding_generation_encode_error(MockSentenceTransformer):
    """Test error handling when model.encode raises an exception."""
    mock_model_instance = MagicMock()
    mock_model_instance.encode.side_effect = Exception("Model encoding failed")
    MockSentenceTransformer.return_value = mock_model_instance

    with patch('workflowwise.embeddings.embedding_generator.model', mock_model_instance):
        # Test document embedding
        doc_embedding = generate_document_embedding("A document that will cause error.")
        assert doc_embedding == [] # Expecting empty list on error as per current implementation

        # Test query embedding
        query_embedding = generate_query_embedding("A query that will cause error.")
        assert query_embedding == [] # Expecting empty list on error

@patch('workflowwise.embeddings.embedding_generator.SentenceTransformer')
def test_embedding_empty_input_string(MockSentenceTransformer):
    """Test handling of empty input strings."""
    mock_model_instance = MagicMock()
    MockSentenceTransformer.return_value = mock_model_instance # Not strictly needed as encode won't be called

    # We are testing the input validation prior to the encode call.
    # So, we don't need to mock encode's return value here specifically,
    # but the model itself needs to be mocked if it's accessed.
    with patch('workflowwise.embeddings.embedding_generator.model', mock_model_instance):
        doc_embedding = generate_document_embedding("")
        assert doc_embedding == [] # Expecting empty list for empty string input

        query_embedding = generate_query_embedding("")
        assert query_embedding == []

        # Assert that encode was not called for empty strings
        mock_model_instance.encode.assert_not_called()

# It might also be useful to test the case where the model itself failed to load
# (i.e., `model` in embedding_generator.py is None).
def test_model_not_loaded():
    """Test behavior when the global model is None (failed to load)."""
    # Temporarily set the module's global 'model' to None
    with patch('workflowwise.embeddings.embedding_generator.model', None):
        doc_embedding = generate_document_embedding("Test document")
        assert doc_embedding == []

        query_embedding = generate_query_embedding("Test query")
        assert query_embedding == []

# Consider testing the model loading itself if it were more complex,
# but here SentenceTransformer(MODEL_NAME) is quite direct.
# If MODEL_NAME was invalid, SentenceTransformer would raise an error.
# Patching print to check log messages is also an option for more detailed tests.
# For example, to check `print(f"Error generating document embedding: {e}")`
# from unittest.mock import patch
# with patch('builtins.print') as mock_print:
#    generate_document_embedding("...")
#    mock_print.assert_any_call(expected_error_message_string)

# Test the actual model name constant (optional, very simple test)
def test_model_name_is_correct():
    assert MODEL_NAME == 'all-MiniLM-L6-v2'

# Note on patching global model:
# The `embedding_generator.py` initializes `model = SentenceTransformer(MODEL_NAME)` at the module level.
# When tests run, this line executes. If `SentenceTransformer` is patched using
# `@patch('workflowwise.embeddings.embedding_generator.SentenceTransformer')` at the test function level,
# the global `model` variable in `embedding_generator` might still hold the *real* model if the module
# was imported before the patch took effect for that specific test function's scope.
# Patching `workflowwise.embeddings.embedding_generator.model` directly as done in the tests above
# ensures that the `model` object used by the functions *during the test* is the mock object.
# This is a common pattern for testing modules with global state or resources initialized on import.This is a good start. I've created `tests/embeddings/test_embedding_generator.py` with the tests.
The key challenge with testing `embedding_generator.py` is that the `SentenceTransformer` model is loaded globally when the module is imported. To correctly mock this for unit tests, I've used `patch('workflowwise.embeddings.embedding_generator.model', mock_model_instance)` within each test that needs the model mocked. This directly replaces the global `model` object in the `embedding_generator` module with the `mock_model_instance` for the duration of that `with` block.

Next, I'll create the test files for the agents.
First, ensure `tests/agents/__init__.py` exists (it should from a previous step, but good to be sure).
