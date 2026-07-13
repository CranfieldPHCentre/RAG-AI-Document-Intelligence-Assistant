import os

import pytest

from document_processor import DocumentProcessor


@pytest.fixture
def processor():
    return DocumentProcessor(chunk_size=100, chunk_overlap=20)


def test_clean_text_normalizes_curly_quotes(processor):
    text = "“Hello” and ‘world’"
    cleaned = processor._clean_text(text)
    assert cleaned == '"Hello" and \'world\''


def test_clean_text_collapses_whitespace(processor):
    cleaned = processor._clean_text("a   b\n\nc\t d")
    assert cleaned == "a b c d"


def test_process_text_file_creates_chunks(tmp_path, processor):
    filepath = tmp_path / "sample.txt"
    filepath.write_text("Sentence one. Sentence two. Sentence three.")

    chunks = processor.process_file(str(filepath))

    assert len(chunks) > 0
    assert all(c.metadata['source'] == 'sample.txt' for c in chunks)


def test_process_file_missing_raises(processor):
    with pytest.raises(FileNotFoundError):
        processor.process_file("does_not_exist.txt")


def test_process_file_unsupported_extension_raises(tmp_path, processor):
    filepath = tmp_path / "sample.exe"
    filepath.write_text("data")

    with pytest.raises(ValueError):
        processor.process_file(str(filepath))


def test_chunks_respect_overlap(tmp_path):
    processor = DocumentProcessor(chunk_size=50, chunk_overlap=10)
    filepath = tmp_path / "long.txt"
    filepath.write_text("word " * 200)

    chunks = processor.process_file(str(filepath))

    assert len(chunks) > 1
    for i, chunk in enumerate(chunks):
        assert chunk.metadata['chunk_num'] == i


def test_get_document_stats(tmp_path, processor):
    filepath = tmp_path / "sample.txt"
    filepath.write_text("Some content here for stats testing.")
    chunks = processor.process_file(str(filepath))

    stats = processor.get_document_stats(chunks)

    assert stats['total_chunks'] == len(chunks)
    assert stats['sources'] == ['sample.txt']
    assert stats['total_characters'] > 0
