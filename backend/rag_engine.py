"""
RAG Engine
Orchestrates retrieval and generation using Claude API
"""

import os
from typing import List, Dict, Optional, Iterator
import anthropic
from vector_store import VectorStore

CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAX_HISTORY_TURNS_FOR_PROMPT = 3


class RAGEngine:
    """RAG system combining retrieval with Claude API for generation.

    Stateless: callers pass their own conversation `history` per request instead
    of the engine keeping global state, so it scales across concurrent users/processes
    without per-user history bleeding between requests.
    """

    def __init__(self, vector_store: VectorStore, api_key: Optional[str] = None):
        """
        Initialize RAG engine

        Args:
            vector_store: VectorStore instance
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
        """
        self.vector_store = vector_store

        # Initialize Claude client
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        if self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
            self.has_api = True
            print("✓ Claude API initialized")
        else:
            self.client = None
            self.has_api = False
            print("⚠ No API key found - running in demo mode")

    def query(self,
              question: str,
              n_results: int = 5,
              use_hybrid: bool = True,
              history: Optional[List[Dict]] = None) -> Dict:
        """
        Query the RAG system

        Args:
            question: User question
            n_results: Number of relevant chunks to retrieve
            use_hybrid: Use hybrid search (semantic + keyword)
            history: Prior {question, answer} turns supplied by the caller, used for
                     conversational context (the engine itself keeps no state)

        Returns:
            Dict with answer, sources, and metadata
        """
        # Step 1: Retrieve relevant documents
        if use_hybrid:
            relevant_chunks = self.vector_store.hybrid_search(question, n_results=n_results)
        else:
            relevant_chunks = self.vector_store.search(question, n_results=n_results)

        if not relevant_chunks:
            return {
                'answer': "I couldn't find any relevant information in the documents to answer your question.",
                'sources': [],
                'retrieved_chunks': 0,
                'model': 'none'
            }

        # Step 2: Construct context from retrieved chunks
        context = self._build_context(relevant_chunks)

        # Step 3: Generate answer using Claude
        if self.has_api:
            answer = self._generate_with_claude(question, context, history)
            model = CLAUDE_MODEL
        else:
            answer = self._generate_demo_answer(question, relevant_chunks)
            model = "demo"

        # Step 4: Format response
        return {
            'answer': answer,
            'sources': self._format_sources(relevant_chunks),
            'retrieved_chunks': len(relevant_chunks),
            'model': model,
            'relevance_scores': [chunk['relevance_score'] for chunk in relevant_chunks]
        }

    def query_stream(self,
                      question: str,
                      n_results: int = 5,
                      use_hybrid: bool = True,
                      history: Optional[List[Dict]] = None) -> Iterator[Dict]:
        """
        Same as query(), but yields incremental events so the caller can stream the
        answer to the client as it's generated instead of waiting for the full response:
          {'type': 'sources', 'sources': [...], 'retrieved_chunks': int, 'relevance_scores': [...], 'model': str}
          {'type': 'delta', 'text': str}            (one or more)
          {'type': 'done'} | {'type': 'error', 'message': str}
        """
        if use_hybrid:
            relevant_chunks = self.vector_store.hybrid_search(question, n_results=n_results)
        else:
            relevant_chunks = self.vector_store.search(question, n_results=n_results)

        if not relevant_chunks:
            yield {
                'type': 'sources', 'sources': [], 'retrieved_chunks': 0,
                'relevance_scores': [], 'model': 'none'
            }
            yield {'type': 'delta', 'text': "I couldn't find any relevant information in the documents to answer your question."}
            yield {'type': 'done'}
            return

        context = self._build_context(relevant_chunks)
        model = CLAUDE_MODEL if self.has_api else "demo"

        yield {
            'type': 'sources',
            'sources': self._format_sources(relevant_chunks),
            'retrieved_chunks': len(relevant_chunks),
            'relevance_scores': [chunk['relevance_score'] for chunk in relevant_chunks],
            'model': model
        }

        if not self.has_api:
            yield {'type': 'delta', 'text': self._generate_demo_answer(question, relevant_chunks)}
            yield {'type': 'done'}
            return

        try:
            messages = self._build_messages(question, context, history)
            with self.client.messages.stream(
                model=CLAUDE_MODEL,
                max_tokens=1500,
                system=self._system_prompt(),
                messages=messages
            ) as stream:
                for text in stream.text_stream:
                    yield {'type': 'delta', 'text': text}
            yield {'type': 'done'}
        except Exception as e:
            yield {'type': 'error', 'message': str(e)}
    
    def _build_context(self, chunks: List[Dict]) -> str:
        """Build context string from retrieved chunks"""
        context_parts = []
        
        for i, chunk in enumerate(chunks, 1):
            source = chunk['metadata']['source']
            text = chunk['text']
            score = chunk.get('relevance_score', 0)
            
            context_parts.append(
                f"[Source {i}: {source} (Relevance: {score:.2f})]\n{text}\n"
            )
        
        return "\n".join(context_parts)
    
    def _system_prompt(self) -> str:
        return """You are a helpful AI assistant that answers questions based on provided documents.

INSTRUCTIONS:
1. Answer the question using ONLY the information from the provided context
2. If the context doesn't contain enough information, say so clearly
3. Cite sources by mentioning [Source X] when using information
4. Be concise but comprehensive
5. If multiple sources provide relevant information, synthesize them
6. Do not make up information not present in the context"""

    def _build_messages(self, question: str, context: str, history: Optional[List[Dict]]) -> List[Dict]:
        """Build the Claude messages list from caller-supplied history plus the current turn"""
        user_message = f"""Context from documents:
{context}

Question: {question}

Please answer the question based on the context above. Cite your sources."""

        messages = []
        if history:
            for exchange in history[-MAX_HISTORY_TURNS_FOR_PROMPT:]:
                messages.append({"role": "user", "content": exchange['question']})
                messages.append({"role": "assistant", "content": exchange['answer']})

        messages.append({"role": "user", "content": user_message})
        return messages

    def _generate_with_claude(self, question: str, context: str, history: Optional[List[Dict]]) -> str:
        """Generate answer using Claude API"""
        messages = self._build_messages(question, context, history)

        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1500,
                system=self._system_prompt(),
                messages=messages
            )

            return response.content[0].text

        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    def _generate_demo_answer(self, question: str, chunks: List[Dict]) -> str:
        """Generate a demo answer when API key is not available"""
        
        answer_parts = [
            f"**Demo Mode Response** (Configure API key for full Claude-powered answers)\n",
            f"\n**Question:** {question}\n",
            f"\n**Relevant Information Found:**\n"
        ]
        
        for i, chunk in enumerate(chunks[:3], 1):
            source = chunk['metadata']['source']
            text = chunk['text'][:200]  # First 200 chars
            score = chunk.get('relevance_score', 0)
            
            answer_parts.append(
                f"\n[Source {i}: {source}] (Relevance: {score:.2f})"
            )
            answer_parts.append(f"{text}...\n")
        
        answer_parts.append(
            "\n*To get AI-generated answers with Claude, add your ANTHROPIC_API_KEY to the .env file*"
        )
        
        return "".join(answer_parts)
    
    def _format_sources(self, chunks: List[Dict]) -> List[Dict]:
        """Format source information for display"""
        sources = []
        
        for chunk in chunks:
            sources.append({
                'source': chunk['metadata']['source'],
                'relevance': round(chunk.get('relevance_score', 0), 3),
                'chunk_id': chunk['id'],
                'preview': chunk['text'][:150] + "..." if len(chunk['text']) > 150 else chunk['text']
            })
        
        return sources


class PromptTemplates:
    """Collection of prompt templates for different use cases"""
    
    @staticmethod
    def summarization(context: str, question: str) -> str:
        return f"""Based on the following information, provide a concise summary:

{context}

Focus on: {question}"""
    
    @staticmethod
    def comparison(context: str, items: List[str]) -> str:
        return f"""Compare the following items based on the context:

Items to compare: {', '.join(items)}

Context:
{context}

Provide a structured comparison."""
    
    @staticmethod
    def extraction(context: str, extract_type: str) -> str:
        return f"""Extract {extract_type} from the following text:

{context}

Provide the information in a structured format."""


if __name__ == "__main__":
    # Example usage
    import tempfile
    from document_processor import DocumentProcessor

    print("="*60)
    print("RAG Engine Example")
    print("="*60)
    
    # Create sample document
    sample_text = """
    Machine Learning Basics
    
    Machine learning is a subset of artificial intelligence that enables systems to learn 
    and improve from experience without being explicitly programmed. There are three main 
    types of machine learning:
    
    1. Supervised Learning: The algorithm learns from labeled training data
    2. Unsupervised Learning: The algorithm finds patterns in unlabeled data
    3. Reinforcement Learning: The algorithm learns through trial and error
    
    Popular machine learning frameworks include TensorFlow, PyTorch, and scikit-learn.
    These tools make it easier to build and deploy machine learning models.
    """
    
    sample_path = os.path.join(tempfile.gettempdir(), 'ml_doc.txt')
    with open(sample_path, 'w') as f:
        f.write(sample_text)

    # Process and store document
    processor = DocumentProcessor(chunk_size=300, chunk_overlap=50)
    chunks = processor.process_file(sample_path)

    vector_store = VectorStore(persist_directory=os.path.join(tempfile.gettempdir(), "rag_demo_db"))
    vector_store.add_documents(chunks)
    
    # Initialize RAG engine (without API key for demo)
    rag = RAGEngine(vector_store)
    
    # Query the system
    print("\n" + "="*60)
    print("Query: What are the types of machine learning?")
    print("="*60)
    
    result = rag.query("What are the types of machine learning?")
    
    print(f"\nAnswer:\n{result['answer']}\n")
    print(f"Retrieved chunks: {result['retrieved_chunks']}")
    print(f"Model: {result['model']}")
    
    print("\nSources:")
    for i, source in enumerate(result['sources'], 1):
        print(f"{i}. {source['source']} (Relevance: {source['relevance']})")
