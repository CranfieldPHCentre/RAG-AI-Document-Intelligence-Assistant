"""
Shared service singletons (embedding/vector store, RAG engine, document processor).

Initialized once by create_app() and imported directly by route modules, instead of
being bolted onto the Flask app object as dynamic attributes (which Flask doesn't
declare and static type checkers correctly flag as unknown attributes).
"""

from document_processor import DocumentProcessor
from vector_store import VectorStore
from rag_engine import RAGEngine
from config import Config

document_processor = DocumentProcessor(chunk_size=Config.CHUNK_SIZE, chunk_overlap=Config.CHUNK_OVERLAP)
vector_store = VectorStore(persist_directory=Config.VECTOR_DB_PATH)
rag_engine = RAGEngine(vector_store)
