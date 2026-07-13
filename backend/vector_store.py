"""
Vector Store
Manages embeddings and semantic search using ChromaDB
"""

import os
import tempfile
import threading
from typing import List, Dict, Optional
import chromadb
from sentence_transformers import SentenceTransformer
import numpy as np
from document_processor import DocumentChunk


class VectorStore:
    """Manages document embeddings and semantic search"""
    
    def __init__(self, persist_directory: str = "./vector_db", collection_name: str = "documents"):
        """
        Initialize vector store
        
        Args:
            persist_directory: Directory to store the vector database
            collection_name: Name of the collection
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name

        # SentenceTransformer.encode() is not guaranteed thread-safe; serialize access
        # since Flask can dispatch concurrent requests onto multiple threads
        self._encode_lock = threading.Lock()

        # Small LRU-ish cache for repeat query embeddings (chat UIs often re-ask/backtrack)
        self._query_embedding_cache = EmbeddingCache(cache_size=256)

        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(path=persist_directory)

        # Initialize embedding model
        print("Loading embedding model...")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        print("✓ Embedding model loaded")

        # Get or create collection
        try:
            self.collection = self.client.get_collection(name=collection_name)
            print(f"✓ Loaded existing collection: {collection_name}")
        except:
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            print(f"✓ Created new collection: {collection_name}")

        # Running set of known sources, kept in sync on add/delete/clear so get_stats()
        # doesn't have to (under)sample the collection to count unique sources
        self._sources = self._load_existing_sources()

    def _load_existing_sources(self) -> set:
        """Scan the (possibly pre-existing, persisted) collection once at startup"""
        count = self.collection.count()
        if count == 0:
            return set()

        existing = self.collection.get(include=["metadatas"])
        return {m.get('source', 'unknown') for m in existing['metadatas']}
    
    def add_documents(self, chunks: List[DocumentChunk]) -> int:
        """
        Add document chunks to the vector store
        
        Args:
            chunks: List of DocumentChunk objects
            
        Returns:
            Number of chunks added
        """
        if not chunks:
            return 0
        
        print(f"Generating embeddings for {len(chunks)} chunks...")
        
        # Extract texts and metadata
        texts = [chunk.text for chunk in chunks]
        ids = [chunk.chunk_id for chunk in chunks]
        metadatas = [chunk.metadata for chunk in chunks]
        
        # Generate embeddings
        with self._encode_lock:
            embeddings = self.embedding_model.encode(
                texts,
                show_progress_bar=True,
                convert_to_numpy=True
            ).tolist()

        # Add to collection
        self.collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )

        self._sources.update(m.get('source', 'unknown') for m in metadatas)

        print(f"✓ Added {len(chunks)} chunks to vector store")
        return len(chunks)
    
    def search(self, query: str, n_results: int = 5, filter_dict: Optional[Dict] = None) -> List[Dict]:
        """
        Search for relevant documents
        
        Args:
            query: Search query
            n_results: Number of results to return
            filter_dict: Optional metadata filter
            
        Returns:
            List of search results with relevance scores
        """
        # Generate query embedding (cached, since chat UIs often repeat/backtrack queries)
        cache_key = query.strip()
        cached = self._query_embedding_cache.get(cache_key)
        if cached is not None:
            query_embedding = cached
        else:
            with self._encode_lock:
                query_embedding = self.embedding_model.encode(
                    query,
                    convert_to_numpy=True
                ).tolist()
            self._query_embedding_cache.set(cache_key, query_embedding)

        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_dict
        )
        
        # Format results
        formatted_results = []
        for i in range(len(results['ids'][0])):
            formatted_results.append({
                'id': results['ids'][0][i],
                'text': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'distance': results['distances'][0][i],
                'relevance_score': 1 - results['distances'][0][i]  # Convert distance to similarity
            })
        
        return formatted_results
    
    def hybrid_search(self, query: str, n_results: int = 5) -> List[Dict]:
        """
        Combine semantic search with keyword matching
        
        Args:
            query: Search query
            n_results: Number of results to return
            
        Returns:
            List of reranked search results
        """
        # Get semantic search results
        semantic_results = self.search(query, n_results=n_results * 2)
        
        # Simple keyword scoring
        query_terms = set(query.lower().split())
        
        for result in semantic_results:
            text_terms = set(result['text'].lower().split())
            keyword_overlap = len(query_terms & text_terms) / len(query_terms)
            
            # Combine scores (70% semantic, 30% keyword)
            result['hybrid_score'] = (
                0.7 * result['relevance_score'] + 
                0.3 * keyword_overlap
            )
        
        # Sort by hybrid score
        semantic_results.sort(key=lambda x: x['hybrid_score'], reverse=True)
        
        return semantic_results[:n_results]
    
    def get_stats(self) -> Dict:
        """Get statistics about the vector store"""
        count = self.collection.count()

        return {
            'total_chunks': count,
            'unique_sources': len(self._sources),
            'sources': list(self._sources),
            'collection_name': self.collection_name
        }

    def delete_by_source(self, source: str) -> int:
        """Delete all chunks from a specific source"""
        # Get all IDs for this source
        results = self.collection.get(
            where={"source": source}
        )

        if results['ids']:
            self.collection.delete(ids=results['ids'])
            self._sources.discard(source)
            print(f"✓ Deleted {len(results['ids'])} chunks from {source}")
            return len(results['ids'])

        return 0

    def clear_all(self):
        """Clear all documents from the vector store"""
        self.client.delete_collection(name=self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        self._sources = set()
        self._query_embedding_cache.clear()
        print("✓ Cleared vector store")
    
    def get_similar_chunks(self, chunk_id: str, n_results: int = 3) -> List[Dict]:
        """Find chunks similar to a given chunk"""
        # Get the chunk
        chunk_data = self.collection.get(ids=[chunk_id])
        
        if not chunk_data['documents']:
            return []
        
        # Search using the chunk's text
        return self.search(chunk_data['documents'][0], n_results=n_results + 1)[1:]


class EmbeddingCache:
    """Simple insertion-ordered cache for embeddings, to avoid recomputation"""

    def __init__(self, cache_size: int = 1000):
        self.cache: Dict[str, List[float]] = {}
        self.cache_size = cache_size

    def get(self, text: str) -> Optional[List[float]]:
        """Get cached embedding"""
        return self.cache.get(text)

    def set(self, text: str, embedding: List[float]):
        """Cache embedding"""
        if len(self.cache) >= self.cache_size:
            # Remove oldest entry
            self.cache.pop(next(iter(self.cache)))

        self.cache[text] = embedding

    def clear(self):
        """Clear cache"""
        self.cache.clear()


if __name__ == "__main__":
    # Example usage
    from document_processor import DocumentProcessor
    
    print("="*60)
    print("Vector Store Example")
    print("="*60)
    
    # Create sample document
    sample_text = """
    Artificial Intelligence (AI) is transforming the world.
    Machine learning enables computers to learn from data.
    Deep learning uses neural networks with multiple layers.
    Natural language processing helps computers understand human language.
    Computer vision allows machines to interpret visual information.
    """
    
    sample_path = os.path.join(tempfile.gettempdir(), 'ai_sample.txt')
    with open(sample_path, 'w') as f:
        f.write(sample_text)

    # Process document
    processor = DocumentProcessor(chunk_size=200, chunk_overlap=50)
    chunks = processor.process_file(sample_path)

    # Create vector store and add documents
    vector_store = VectorStore(persist_directory=os.path.join(tempfile.gettempdir(), "test_vector_db"))
    vector_store.add_documents(chunks)
    
    # Search
    print("\n" + "="*60)
    print("Search Results for: 'machine learning'")
    print("="*60)
    
    results = vector_store.search("machine learning", n_results=3)
    
    for i, result in enumerate(results, 1):
        print(f"\nResult {i}:")
        print(f"Relevance: {result['relevance_score']:.3f}")
        print(f"Text: {result['text'][:100]}...")
        print(f"Source: {result['metadata']['source']}")
    
    # Get stats
    stats = vector_store.get_stats()
    print(f"\nVector Store Stats:")
    print(f"Total chunks: {stats['total_chunks']}")
    print(f"Unique sources: {stats['unique_sources']}")
