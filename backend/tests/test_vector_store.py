import pytest

from document_processor import DocumentChunk
from vector_store import VectorStore


def make_chunk(text, source, chunk_num=0):
    return DocumentChunk(text=text, metadata={'source': source, 'chunk_num': chunk_num})


@pytest.fixture
def store(tmp_path):
    return VectorStore(persist_directory=str(tmp_path / "vector_db"), collection_name="test_docs")


def test_add_and_search(store):
    chunks = [
        make_chunk("Machine learning enables computers to learn from data.", "doc_a.txt"),
        make_chunk("The Eiffel Tower is located in Paris, France.", "doc_b.txt"),
    ]

    added = store.add_documents(chunks)
    assert added == 2

    results = store.search("machine learning", n_results=1)
    assert len(results) == 1
    assert results[0]['metadata']['source'] == "doc_a.txt"


def test_get_stats_tracks_sources_without_sampling(store):
    chunks = [make_chunk(f"content {i}", f"doc_{i}.txt") for i in range(5)]
    store.add_documents(chunks)

    stats = store.get_stats()

    assert stats['total_chunks'] == 5
    assert stats['unique_sources'] == 5
    assert set(stats['sources']) == {f"doc_{i}.txt" for i in range(5)}


def test_delete_by_source_updates_stats(store):
    store.add_documents([
        make_chunk("alpha content", "alpha.txt"),
        make_chunk("beta content", "beta.txt"),
    ])

    deleted = store.delete_by_source("alpha.txt")

    assert deleted == 1
    stats = store.get_stats()
    assert stats['unique_sources'] == 1
    assert stats['sources'] == ["beta.txt"]


def test_clear_all_resets_sources(store):
    store.add_documents([make_chunk("some text", "doc.txt")])
    store.clear_all()

    stats = store.get_stats()
    assert stats['total_chunks'] == 0
    assert stats['unique_sources'] == 0


def test_query_embedding_cache_is_reused(store, monkeypatch):
    store.add_documents([make_chunk("caching behavior test content", "doc.txt")])

    calls = []
    original_encode = store.embedding_model.encode

    def counting_encode(*args, **kwargs):
        calls.append(1)
        return original_encode(*args, **kwargs)

    monkeypatch.setattr(store.embedding_model, "encode", counting_encode)

    store.search("repeated query")
    store.search("repeated query")

    assert len(calls) == 1


def test_hybrid_search_combines_scores(store):
    store.add_documents([
        make_chunk("Python is a popular programming language.", "prog.txt"),
        make_chunk("Bananas are a good source of potassium.", "fruit.txt"),
    ])

    results = store.hybrid_search("Python programming language", n_results=2)

    assert results[0]['metadata']['source'] == "prog.txt"
    assert 'hybrid_score' in results[0]
