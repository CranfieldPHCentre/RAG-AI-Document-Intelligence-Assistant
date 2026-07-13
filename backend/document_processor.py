"""
Document Processor
Handles multiple document formats and prepares text for vector embeddings
"""

import os
import re
from typing import List, Dict, Tuple
import hashlib
from datetime import datetime

# PDF processing
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

# DOCX processing
try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None


class DocumentChunk:
    """Represents a chunk of text from a document"""
    
    def __init__(self, text: str, metadata: Dict, chunk_id: str = None):
        self.text = text
        self.metadata = metadata
        self.chunk_id = chunk_id or self._generate_id(text, metadata)
    
    def _generate_id(self, text: str, metadata: Dict) -> str:
        """Generate unique ID for chunk"""
        content = f"{text}_{metadata.get('source', '')}_{metadata.get('page', 0)}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'id': self.chunk_id,
            'text': self.text,
            'metadata': self.metadata
        }


class DocumentProcessor:
    """Process various document formats and create text chunks"""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.supported_formats = ['.txt', '.pdf', '.docx', '.md']
    
    def process_file(self, filepath: str) -> List[DocumentChunk]:
        """
        Process a file and return text chunks
        
        Args:
            filepath: Path to the document file
            
        Returns:
            List of DocumentChunk objects
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        
        # Get file extension
        _, ext = os.path.splitext(filepath)
        ext = ext.lower()
        
        if ext not in self.supported_formats:
            raise ValueError(f"Unsupported file format: {ext}")
        
        # Extract text based on file type
        if ext == '.pdf':
            text, pages_metadata = self._process_pdf(filepath)
        elif ext == '.docx':
            text, pages_metadata = self._process_docx(filepath)
        else:  # .txt, .md
            text, pages_metadata = self._process_text(filepath)
        
        # Create chunks
        chunks = self._create_chunks(text, filepath, pages_metadata)
        
        print(f"✓ Processed {os.path.basename(filepath)}: {len(chunks)} chunks created")
        
        return chunks
    
    def _process_pdf(self, filepath: str) -> Tuple[str, List[Dict]]:
        """Extract text from PDF"""
        if PdfReader is None:
            raise ImportError("pypdf not installed. Run: pip install pypdf")
        
        reader = PdfReader(filepath)
        text = ""
        pages_metadata = []
        
        for page_num, page in enumerate(reader.pages, 1):
            page_text = page.extract_text()
            text += page_text + "\n\n"
            pages_metadata.append({
                'page': page_num,
                'length': len(page_text)
            })
        
        return text, pages_metadata
    
    def _process_docx(self, filepath: str) -> Tuple[str, List[Dict]]:
        """Extract text from DOCX"""
        if DocxDocument is None:
            raise ImportError("python-docx not installed. Run: pip install python-docx")
        
        doc = DocxDocument(filepath)
        text = ""
        pages_metadata = []
        
        for i, para in enumerate(doc.paragraphs, 1):
            para_text = para.text
            text += para_text + "\n"
            if para_text.strip():
                pages_metadata.append({
                    'paragraph': i,
                    'length': len(para_text)
                })
        
        return text, pages_metadata
    
    def _process_text(self, filepath: str) -> Tuple[str, List[Dict]]:
        """Extract text from TXT/MD files"""
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Estimate "pages" by line count
        lines = text.split('\n')
        pages_metadata = [{
            'line_count': len(lines),
            'length': len(text)
        }]
        
        return text, pages_metadata
    
    def _create_chunks(self, text: str, source: str, pages_metadata: List[Dict]) -> List[DocumentChunk]:
        """
        Split text into overlapping chunks
        
        Args:
            text: Full document text
            source: Source file path
            pages_metadata: Metadata about pages/sections
        """
        # Clean text
        text = self._clean_text(text)
        
        chunks = []
        start = 0
        chunk_num = 0
        
        while start < len(text):
            # Calculate end position
            end = start + self.chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings near the boundary
                search_start = max(start, end - 100)
                sentence_end = max(
                    text.rfind('. ', search_start, end),
                    text.rfind('! ', search_start, end),
                    text.rfind('? ', search_start, end),
                    text.rfind('\n\n', search_start, end)
                )
                
                if sentence_end != -1 and sentence_end > start:
                    end = sentence_end + 1
            
            # Extract chunk
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                metadata = {
                    'source': os.path.basename(source),
                    'chunk_num': chunk_num,
                    'start_pos': start,
                    'end_pos': end,
                    'timestamp': datetime.now().isoformat()
                }
                
                chunks.append(DocumentChunk(chunk_text, metadata))
                chunk_num += 1
            
            # Move start position (with overlap)
            start = end - self.chunk_overlap
            if start >= len(text):
                break
        
        return chunks
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters that might cause issues
        text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        
        # Normalize quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        
        return text.strip()
    
    def get_document_stats(self, chunks: List[DocumentChunk]) -> Dict:
        """Get statistics about processed document"""
        total_chars = sum(len(chunk.text) for chunk in chunks)
        avg_chunk_size = total_chars / len(chunks) if chunks else 0
        
        return {
            'total_chunks': len(chunks),
            'total_characters': total_chars,
            'avg_chunk_size': int(avg_chunk_size),
            'sources': list(set(chunk.metadata['source'] for chunk in chunks))
        }


class TextSplitter:
    """Alternative splitter using semantic boundaries"""
    
    @staticmethod
    def split_by_sentences(text: str, max_sentences: int = 5) -> List[str]:
        """Split text into chunks of sentences"""
        # Simple sentence splitter
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = []
        
        for sentence in sentences:
            current_chunk.append(sentence)
            
            if len(current_chunk) >= max_sentences:
                chunks.append(' '.join(current_chunk))
                current_chunk = []
        
        # Add remaining sentences
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    @staticmethod
    def split_by_paragraphs(text: str) -> List[str]:
        """Split text by paragraphs"""
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip()]


if __name__ == "__main__":
    # Example usage
    processor = DocumentProcessor(chunk_size=500, chunk_overlap=50)
    
    # Create a sample text file for testing
    sample_text = """
    This is a sample document for testing the document processor.
    
    The processor can handle multiple formats including PDF, DOCX, and plain text.
    It splits documents into overlapping chunks for better retrieval performance.
    
    Each chunk maintains metadata about its source and position in the original document.
    This helps with citation and context preservation during retrieval.
    """
    
    with open('/tmp/sample.txt', 'w') as f:
        f.write(sample_text)
    
    chunks = processor.process_file('/tmp/sample.txt')
    stats = processor.get_document_stats(chunks)
    
    print("\nDocument Statistics:")
    print(f"Total chunks: {stats['total_chunks']}")
    print(f"Total characters: {stats['total_characters']}")
    print(f"Average chunk size: {stats['avg_chunk_size']}")
    
    print("\nSample chunk:")
    print(chunks[0].to_dict())
