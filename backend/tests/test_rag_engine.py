import pytest

from document_processor import DocumentChunk
from vector_store import VectorStore
from rag_engine import RAGEngine


@pytest.fixture
def engine_with_docs(tmp_path):
    store = VectorStore(persist_directory=str(tmp_path / "vector_db"), collection_name="test_docs")
    store.add_documents([
        DocumentChunk(
            text="Machine learning is a subset of artificial intelligence.",
            metadata={'source': 'ml.txt', 'chunk_num': 0}
        )
    ])
    # No API key -> demo mode, so tests don't require network/credentials
    return RAGEngine(store, api_key=None)


def test_engine_keeps_no_server_side_history(engine_with_docs):
    assert not hasattr(engine_with_docs, 'conversation_history')


def test_query_demo_mode_returns_sources(engine_with_docs):
    result = engine_with_docs.query("What is machine learning?", n_results=1)

    assert result['model'] == 'demo'
    assert result['retrieved_chunks'] == 1
    assert result['sources'][0]['source'] == 'ml.txt'
    assert 'Demo Mode' in result['answer']


def test_query_is_stateless_across_calls(engine_with_docs):
    """Passing history explicitly must not leak into a later call that passes none"""
    history = [{'question': 'earlier question', 'answer': 'earlier answer'}]

    result_with_history = engine_with_docs.query("What is machine learning?", n_results=1, history=history)
    result_without_history = engine_with_docs.query("What is machine learning?", n_results=1, history=None)

    assert result_with_history['model'] == 'demo'
    assert result_without_history['model'] == 'demo'
    # demo mode doesn't use history at all, but the call must not raise or persist state
    assert not hasattr(engine_with_docs, 'conversation_history')


def test_query_no_relevant_chunks(tmp_path):
    empty_store = VectorStore(persist_directory=str(tmp_path / "empty_db"), collection_name="empty")
    engine = RAGEngine(empty_store, api_key=None)

    result = engine.query("anything", n_results=3)

    assert result['retrieved_chunks'] == 0
    assert result['sources'] == []
