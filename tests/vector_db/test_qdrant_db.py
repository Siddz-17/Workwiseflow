import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY # ANY is useful for some argument checks
from qdrant_client import models # For constructing mock return values and type hints

from workflowwise.vector_db.qdrant_db import QdrantVectorDB

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio

@patch('workflowwise.vector_db.qdrant_db.QdrantClient')
async def test_connect_in_memory(mock_qdrant_client_constructor):
    """Test connecting to an in-memory Qdrant instance."""
    mock_client_instance = MagicMock()
    mock_client_instance.get_collections = AsyncMock() # Simulate this call in connect
    mock_qdrant_client_constructor.return_value = mock_client_instance

    db = QdrantVectorDB(in_memory=True)
    await db.connect()

    mock_qdrant_client_constructor.assert_called_once_with(location=":memory:")
    assert db.client == mock_client_instance
    # In the actual connect method, we have a self.client.get_collections() call.
    # Let's ensure that's called if connect is more than just init.
    # Based on qdrant_db.py, connect() does not call get_collections(), __init__ does.
    # The QdrantVectorDB's connect is more of a conceptual check or a placeholder for future.
    # For now, the primary check is the constructor call and client assignment.
    # If connect becomes more complex, add assertions for those actions.
    # For example, if connect truly established a session or ran a health check:
    # mock_client_instance.some_connect_related_method.assert_called_once()


@patch('workflowwise.vector_db.qdrant_db.QdrantClient')
async def test_connect_host_port(mock_qdrant_client_constructor):
    """Test connecting to a Qdrant instance with host and port."""
    mock_client_instance = MagicMock()
    mock_client_instance.get_collections = AsyncMock() # Simulate this call in connect
    mock_qdrant_client_constructor.return_value = mock_client_instance

    db = QdrantVectorDB(host="localhost", port=1234, api_key="test_key", prefer_grpc=False)
    # The connect method itself in QdrantVectorDB is a simple sleep and print.
    # The actual client initialization happens in __init__.
    await db.connect() # This call mainly serves to ensure no errors and print.

    mock_qdrant_client_constructor.assert_called_once_with(host="localhost", port=1234, api_key="test_key", prefer_grpc=False)
    assert db.client == mock_client_instance

@patch('workflowwise.vector_db.qdrant_db.QdrantClient')
async def test_disconnect(mock_qdrant_client_constructor):
    """Test disconnecting from Qdrant."""
    mock_client_instance = MagicMock()
    mock_client_instance.close = MagicMock() # close is synchronous in qdrant_client
    mock_qdrant_client_constructor.return_value = mock_client_instance

    db = QdrantVectorDB(in_memory=True) # Init the client
    await db.connect() # Placeholder connect

    await db.disconnect()
    mock_client_instance.close.assert_called_once()

@patch('workflowwise.vector_db.qdrant_db.QdrantClient')
async def test_create_collection(mock_qdrant_client_constructor):
    """Test creating a collection."""
    mock_client_instance = MagicMock()
    # recreate_collection is synchronous in the client library
    mock_client_instance.recreate_collection = MagicMock()
    mock_qdrant_client_constructor.return_value = mock_client_instance

    db = QdrantVectorDB(in_memory=True)
    await db.connect()

    collection_name = "test_collection"
    vector_size = 128
    distance_metric = "Euclid" # Test non-default distance

    await db.create_collection(collection_name, vector_size, distance_metric=distance_metric)

    expected_vector_params = models.VectorParams(size=vector_size, distance=models.Distance.EUCLID)
    mock_client_instance.recreate_collection.assert_called_once_with(
        collection_name=collection_name,
        vectors_config=expected_vector_params
    )

@patch('workflowwise.vector_db.qdrant_db.QdrantClient')
async def test_upsert_vectors(mock_qdrant_client_constructor):
    """Test upserting vectors."""
    mock_client_instance = MagicMock()
    # upsert is synchronous in the client library
    mock_client_instance.upsert = MagicMock()
    mock_qdrant_client_constructor.return_value = mock_client_instance

    db = QdrantVectorDB(in_memory=True)
    await db.connect()

    collection_name = "test_upsert_coll"
    vectors_data = [
        {"id": "vec1", "vector": [0.1, 0.2, 0.3]},
        {"id": 2, "vector": [0.4, 0.5, 0.6]}
    ]
    metadata_list = [
        {"source": "docA"},
        {"source": "docB"}
    ]

    # This calls _upsert_points internally, which then calls client.upsert
    await db.upsert_vectors(collection_name, vectors_data, metadata_list)

    # Check that client.upsert was called with PointStruct objects
    # We need to ensure the points argument to client.upsert matches the expected structure.
    # It's a bit tricky to assert complex objects directly with MagicMock calls.
    # We can check the call_args or use a helper to validate.

    args, kwargs = mock_client_instance.upsert.call_args
    assert kwargs['collection_name'] == collection_name

    points_arg = kwargs['points']
    assert len(points_arg) == 2

    assert isinstance(points_arg[0], models.PointStruct)
    assert points_arg[0].id == "vec1"
    assert points_arg[0].vector == [0.1, 0.2, 0.3]
    assert points_arg[0].payload == {"source": "docA"}

    assert isinstance(points_arg[1], models.PointStruct)
    assert points_arg[1].id == 2
    assert points_arg[1].vector == [0.4, 0.5, 0.6]
    assert points_arg[1].payload == {"source": "docB"}


@patch('workflowwise.vector_db.qdrant_db.QdrantClient')
async def test_search(mock_qdrant_client_constructor):
    """Test searching vectors."""
    mock_client_instance = MagicMock()

    # Prepare mock search results from Qdrant client
    mock_hit1 = models.ScoredPoint(id="res_id1", version=1, score=0.95, payload={"title": "Result 1"}, vector=[0.1]*3)
    mock_hit2 = models.ScoredPoint(id=2, version=1, score=0.88, payload={"title": "Result 2"}, vector=[0.2]*3)
    # search is synchronous in the client library
    mock_client_instance.search = MagicMock(return_value=[mock_hit1, mock_hit2])
    mock_qdrant_client_constructor.return_value = mock_client_instance

    db = QdrantVectorDB(in_memory=True)
    await db.connect()

    collection_name = "test_search_coll"
    query_vector = [0.1, 0.1, 0.1]
    top_k_val = 2

    results = await db.search(collection_name, query_vector, top_k=top_k_val)

    mock_client_instance.search.assert_called_once_with(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=top_k_val,
        with_payload=True, # Default in QdrantVectorDB.search
        score_threshold=None # Default in QdrantVectorDB.search
    )

    assert len(results) == 2
    assert results[0]["id"] == "res_id1"
    assert results[0]["score"] == 0.95
    assert results[0]["payload"] == {"title": "Result 1"}

    assert results[1]["id"] == 2 # Check if int ID is handled
    assert results[1]["score"] == 0.88
    assert results[1]["payload"] == {"title": "Result 2"}
    # By default, our search method does not include the 'vector' in the final result.


@patch('workflowwise.vector_db.qdrant_db.QdrantClient')
async def test_delete_collection(mock_qdrant_client_constructor):
    """Test deleting a collection."""
    mock_client_instance = MagicMock()
    # delete_collection is synchronous
    mock_client_instance.delete_collection = MagicMock()
    mock_qdrant_client_constructor.return_value = mock_client_instance

    db = QdrantVectorDB(in_memory=True)
    await db.connect()

    collection_name = "test_delete_coll"
    await db.delete_collection(collection_name)

    mock_client_instance.delete_collection.assert_called_once_with(collection_name=collection_name)

@patch('workflowwise.vector_db.qdrant_db.QdrantClient')
async def test_upsert_vectors_value_error(mock_qdrant_client_constructor):
    """Test upsert_vectors raises ValueError if vectors and metadata lengths differ."""
    db = QdrantVectorDB(in_memory=True)
    await db.connect() # Client is mocked, no actual connection

    with pytest.raises(ValueError, match="The number of vectors and metadata items must be the same."):
        await db.upsert_vectors(
            collection_name="test_coll",
            vectors=[{"id": 1, "vector": [0.1, 0.2]}], # 1 vector
            metadata=[{"meta": "A"}, {"meta": "B"}]    # 2 metadata items
        )

    with pytest.raises(ValueError, match="Each vector dictionary must have 'id' and 'vector' keys."):
        await db.upsert_vectors(
            collection_name="test_coll",
            vectors=[{"id_missing": 1, "vector_data": [0.1, 0.2]}],
            metadata=[{"meta": "A"}]
        )

    with pytest.raises(ValueError, match="Each vector dictionary must have 'id' and 'vector' keys."):
        await db.upsert_vectors(
            collection_name="test_coll",
            vectors=[{"id": 1, "vector_missing": [0.1, 0.2]}],
            metadata=[{"meta": "A"}]
        )

# Further tests could include:
# - Error handling (e.g., if Qdrant client methods raise exceptions)
# - Different distance metrics in create_collection
# - search with score_threshold
# - Behavior when client is None (e.g., if connect failed or was not called)
# - The _upsert_points method directly if complex logic resided there (though it's simple now)
# - The QdrantVectorDB constructor's handling of the api_key and prefer_grpc parameters.
# - Test connect failure if QdrantClient constructor itself throws an error.
#   This would require mock_qdrant_client_constructor.side_effect = Exception("Connection Error")
#   and then asserting the behavior of QdrantVectorDB's __init__ or connect().
#   Currently, __init__ in QdrantVectorDB would raise the exception directly.
#   The connect() method in QdrantVectorDB has a try-except that re-raises, so that could be tested too.
#   For instance:
#   @patch('workflowwise.vector_db.qdrant_db.QdrantClient')
#   async def test_connect_failure_on_init(mock_qdrant_client_constructor):
#       mock_qdrant_client_constructor.side_effect = Exception("Init failed")
#       with pytest.raises(Exception, match="Init failed"):
#           QdrantVectorDB(in_memory=True) # Exception raised by QdrantClient constructor

#   @patch('workflowwise.vector_db.qdrant_db.QdrantClient')
#   async def test_connect_failure_simulated_in_connect_method(mock_qdrant_client_constructor):
#       mock_client_instance = MagicMock()
#       # Assuming connect() in QdrantVectorDB had a specific client call that could fail:
#       # mock_client_instance.some_critical_connect_method = AsyncMock(side_effect=Exception("Critical connect failed"))
#       # mock_qdrant_client_constructor.return_value = mock_client_instance
#       # db = QdrantVectorDB(in_memory=True)
#       # with pytest.raises(Exception, match="Critical connect failed"):
#       #    await db.connect()
#       # However, current connect() in QdrantVectorDB is mostly a print and sleep,
#       # and actual client init is in __init__().
#       # The try-except in connect() is around `await asyncio.sleep(0.01)` and print, not Qdrant calls.
#       pass # Test structure for connect failure needs specific scenario.

# Note: For Qdrant client methods that are synchronous (like `close`, `recreate_collection`, `upsert`, `search`, `delete_collection`
# in the version of `qdrant-client` these tests assume), we use `MagicMock`. If they were async, we would use `AsyncMock`.
# The `QdrantVectorDB` wrapper methods are `async` primarily to fit an async interface and use `await asyncio.sleep(0.01)`
# to simulate I/O. The tests correctly mock the *underlying synchronous calls* of the `qdrant-client` instance.
# If `qdrant-client` introduces an async client and our wrapper uses its `await`able methods,
# then the mocks for `db.client.*` methods would need to be `AsyncMock`.
# For now, `db.client.upsert = MagicMock()` is correct if `qdrant_client.upsert()` is sync.
# The current `QdrantVectorDB` calls synchronous qdrant_client methods, so `MagicMock` is appropriate for those.
# The `AsyncMock` on `db.client.recreate_collection = AsyncMock()` etc. in the original prompt might be if one *assumes*
# the underlying client methods are async. Let's stick to `MagicMock` for synchronous client methods based on current library.
# Correction: After reviewing `qdrant_db.py`, the `QdrantClient` methods like `upsert`, `search` etc. are indeed synchronous.
# The `await asyncio.sleep(0.01)` is what makes the wrapper methods async.
# So, the mocks for `db.client.method_name` should be `MagicMock` not `AsyncMock` for these calls.
# I've updated the test_create_collection, test_upsert_vectors, test_search, test_delete_collection to use MagicMock for client methods.
# The `db.client.get_collections = AsyncMock()` in `test_connect_in_memory` was an example, but `connect()` does not call it.
# `__init__` in `QdrantVectorDB` calls `QdrantClient()` which is synchronous itself.
# The `connect()` method in `QdrantVectorDB` is where an async health check could live.
# If `QdrantClient().get_collections()` was called by `QdrantVectorDB.connect()`, and if `get_collections()` was async, then `AsyncMock` would be right.
# But `get_collections()` is sync.
# The current `QdrantVectorDB.connect()` is:
# async def connect(self):
#     try:
#         await asyncio.sleep(0.01) # Simulate async operation if needed
#         print(...)
#     except Exception as e:
#         print(...)
#         raise
# This `connect` does not actually call any qdrant client methods that would need mocking for its own logic.
# The tests for `connect_in_memory` and `connect_host_port` correctly focus on the `QdrantClient` *constructor* call.
# The tests for other methods like `create_collection` correctly mock the respective synchronous methods of the `qdrant-client` instance.
# (Final check of QdrantVectorDB: the methods `_upsert_points`, `search`, `create_collection`, `delete_collection`
#  call the synchronous methods of the underlying `qdrant_client` instance, and then `await asyncio.sleep(0.01)`.
#  So, mocking those underlying methods with `MagicMock` is correct.)
