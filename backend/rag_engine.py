"""
RAG Engine
Orchestrates retrieval and generation using Claude API
"""

import os
from typing import List, Dict, Optional
import anthropic
from vector_store import VectorStore


class RAGEngine:
    """RAG system combining retrieval with Claude API for generation"""
    
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
        
        self.conversation_history = []
    
    def query(self, 
              question: str, 
              n_results: int = 5,
              use_hybrid: bool = True,
              conversation_context: bool = True) -> Dict:
        """
        Query the RAG system
        
        Args:
            question: User question
            n_results: Number of relevant chunks to retrieve
            use_hybrid: Use hybrid search (semantic + keyword)
            conversation_context: Include conversation history
            
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
            answer = self._generate_with_claude(question, context, conversation_context)
            model = "claude-sonnet-4-20250514"
        else:
            answer = self._generate_demo_answer(question, relevant_chunks)
            model = "demo"
        
        # Step 4: Add to conversation history
        if conversation_context:
            self.conversation_history.append({
                'question': question,
                'answer': answer,
                'sources': [chunk['metadata']['source'] for chunk in relevant_chunks]
            })
        
        # Step 5: Format response
        return {
            'answer': answer,
            'sources': self._format_sources(relevant_chunks),
            'retrieved_chunks': len(relevant_chunks),
            'model': model,
            'relevance_scores': [chunk['relevance_score'] for chunk in relevant_chunks]
        }
    
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
    
    def _generate_with_claude(self, question: str, context: str, use_history: bool) -> str:
        """Generate answer using Claude API"""
        
        # Build system prompt
        system_prompt = """You are a helpful AI assistant that answers questions based on provided documents.

INSTRUCTIONS:
1. Answer the question using ONLY the information from the provided context
2. If the context doesn't contain enough information, say so clearly
3. Cite sources by mentioning [Source X] when using information
4. Be concise but comprehensive
5. If multiple sources provide relevant information, synthesize them
6. Do not make up information not present in the context"""

        # Build user message
        user_message = f"""Context from documents:
{context}

Question: {question}

Please answer the question based on the context above. Cite your sources."""

        # Add conversation history if requested
        messages = []
        if use_history and self.conversation_history:
            # Add last 3 exchanges for context
            for exchange in self.conversation_history[-3:]:
                messages.append({
                    "role": "user",
                    "content": exchange['question']
                })
                messages.append({
                    "role": "assistant",
                    "content": exchange['answer']
                })
        
        # Add current question
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        try:
            # Call Claude API
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                system=system_prompt,
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
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        print("✓ Conversation history cleared")
    
    def get_conversation_summary(self) -> str:
        """Get a summary of the conversation"""
        if not self.conversation_history:
            return "No conversation history"
        
        summary = f"Conversation History ({len(self.conversation_history)} exchanges):\n\n"
        
        for i, exchange in enumerate(self.conversation_history, 1):
            summary += f"{i}. Q: {exchange['question'][:80]}...\n"
            summary += f"   Sources: {', '.join(set(exchange['sources']))}\n\n"
        
        return summary


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
    
    with open('/tmp/ml_doc.txt', 'w') as f:
        f.write(sample_text)
    
    # Process and store document
    processor = DocumentProcessor(chunk_size=300, chunk_overlap=50)
    chunks = processor.process_file('/tmp/ml_doc.txt')
    
    vector_store = VectorStore(persist_directory="/tmp/rag_demo_db")
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
