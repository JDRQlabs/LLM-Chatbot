"""
Document Processing Pipeline for RAG

This script handles:
1. PDF extraction
2. Web page scraping
3. Text chunking
4. Embedding generation
5. Storage in pgvector

Can be triggered:
- On document upload
- As a scheduled job for batch processing
- On-demand via API
"""

import wmill
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional
import hashlib
import re
from openai import OpenAI


def main(
    knowledge_source_id: str,
    chatbot_id: str,
    openai_api_key: str = "",  # From Windmill variable
    chunk_size: int = 1000,  # Characters per chunk
    chunk_overlap: int = 200,  # Overlap between chunks
    db_resource: str = "f/development/business_layer_db_postgreSQL",
) -> Dict[str, Any]:
    """
    Process a knowledge source and create embeddings.
    
    Args:
        knowledge_source_id: UUID of the knowledge source
        chatbot_id: UUID of the chatbot
        openai_api_key: OpenAI API key for embeddings
        chunk_size: Size of each text chunk
        chunk_overlap: Overlap between consecutive chunks
        db_resource: Database resource path
    
    Returns:
        Processing results with stats
    """
    
    # Setup database
    raw_config = wmill.get_resource(db_resource)
    db_params = {
        "host": raw_config.get("host"),
        "port": raw_config.get("port"),
        "user": raw_config.get("user"),
        "password": raw_config.get("password"),
        "dbname": raw_config.get("dbname"),
        "sslmode": "disable",
    }
    
    conn = psycopg2.connect(**db_params)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # 1. Fetch knowledge source
        cur.execute(
            """
            SELECT * FROM knowledge_sources 
            WHERE id = %s AND chatbot_id = %s
            """,
            (knowledge_source_id, chatbot_id)
        )
        source = cur.fetchone()
        
        if not source:
            return {"success": False, "error": "Knowledge source not found"}
        
        # Update status to processing
        cur.execute(
            """
            UPDATE knowledge_sources 
            SET sync_status = 'processing', last_synced_at = NOW()
            WHERE id = %s
            """,
            (knowledge_source_id,)
        )
        conn.commit()
        
        # 2. Extract content based on source type
        content = extract_content(source)
        
        if not content:
            _mark_failed(cur, knowledge_source_id, "Failed to extract content")
            conn.commit()
            return {"success": False, "error": "Content extraction failed"}
        
        # 3. Chunk the content
        chunks = chunk_text(
            content,
            chunk_size=chunk_size,
            overlap=chunk_overlap
        )
        
        print(f"Created {len(chunks)} chunks from source")
        
        # 4. Generate embeddings
        embeddings = generate_embeddings(chunks, openai_api_key)
        
        if not embeddings:
            _mark_failed(cur, knowledge_source_id, "Failed to generate embeddings")
            conn.commit()
            return {"success": False, "error": "Embedding generation failed"}
        
        # 5. Delete old chunks (if re-processing)
        cur.execute(
            "DELETE FROM document_chunks WHERE knowledge_source_id = %s",
            (knowledge_source_id,)
        )
        
        # 6. Insert new chunks with embeddings
        inserted_count = 0
        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            # Extract metadata (page numbers, headers, etc.)
            metadata = extract_chunk_metadata(chunk_text, i, source)
            
            cur.execute(
                """
                INSERT INTO document_chunks (
                    knowledge_source_id,
                    chatbot_id,
                    content,
                    chunk_index,
                    embedding,
                    metadata
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    knowledge_source_id,
                    chatbot_id,
                    chunk_text,
                    i,
                    embedding,
                    metadata
                )
            )
            inserted_count += 1
        
        # 7. Update knowledge source status
        # Note: dimensions are hardcoded to 1536 for now, must match the embedding model used
        cur.execute(
            """
            UPDATE knowledge_sources 
            SET sync_status = 'synced',
                last_synced_at = NOW(),
                chunks_count = %s,
                embedding_model = 'text-embedding-ada-002',
                embedding_dimensions = 1536
            WHERE id = %s
            """,
            (len(chunks), knowledge_source_id)
        )
        
        conn.commit()
        
        return {
            "success": True,
            "chunks_created": len(chunks),
            "embeddings_generated": len(embeddings),
            "source_type": source["source_type"],
            "source_name": source["name"],
        }
        
    except Exception as e:
        print(f"Error processing document: {e}")
        conn.rollback()
        _mark_failed(cur, knowledge_source_id, str(e))
        conn.commit()
        return {"success": False, "error": str(e)}
        
    finally:
        cur.close()
        conn.close()


def extract_content(source: Dict[str, Any]) -> Optional[str]:
    """
    Extract text content from various source types.
    
    Args:
        source: Knowledge source record
    
    Returns:
        Extracted text content or None
    """
    source_type = source["source_type"]
    
    if source_type == "text":
        # Direct text input
        return source.get("content") or ""
    
    elif source_type == "pdf":
        # Extract text from PDF
        return extract_pdf_text(source["file_path"])
    
    elif source_type == "url":
        # Scrape web page
        return scrape_webpage(source["file_path"])  # file_path stores URL
    
    elif source_type == "doc":
        # Extract from Word doc
        return extract_doc_text(source["file_path"])
    
    return None


def extract_pdf_text(file_path: str) -> str:
    """
    Extract text from PDF file.
    
    Implementation options:
    - PyPDF2 (simple, pure Python)
    - pdfplumber (better for tables)
    - pymupdf (fastest)
    - Unstructured.io (best quality, slower)
    
    For MVP, using PyPDF2:
    """
    try:
        import PyPDF2
        
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                # Add page markers for metadata
                text += f"\n[PAGE {page_num + 1}]\n{page_text}\n"
        
        return text.strip()
        
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return ""


def scrape_webpage(url: str) -> str:
    """
    Scrape text from webpage.
    
    Implementation options:
    - BeautifulSoup + requests (simple)
    - trafilatura (better text extraction)
    - newspaper3k (for articles)
    
    For MVP, using trafilatura (best balance):
    """
    try:
        import trafilatura
        
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return ""
        
        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            output_format='txt'
        )
        
        return text or ""
        
    except Exception as e:
        print(f"Web scraping error: {e}")
        return ""


def extract_doc_text(file_path: str) -> str:
    """
    Extract text from Word document.
    
    Using python-docx:
    """
    try:
        import docx
        
        doc = docx.Document(file_path)
        text = "\n\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text.strip()
        
    except Exception as e:
        print(f"Doc extraction error: {e}")
        return ""


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200
) -> List[str]:
    """
    Split text into overlapping chunks.
    
    Strategy:
    1. Try to split on paragraph boundaries
    2. Fall back to sentence boundaries
    3. Hard split if needed (rare)
    
    Args:
        text: Text to chunk
        chunk_size: Target size of each chunk (characters)
        overlap: Overlap between chunks (characters)
    
    Returns:
        List of text chunks
    """
    if not text:
        return []
    
    # Clean text
    text = re.sub(r'\s+', ' ', text).strip()
    
    # If text is smaller than chunk_size, return as-is
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        # Calculate end position
        end = start + chunk_size
        
        # If this is the last chunk
        if end >= len(text):
            chunks.append(text[start:].strip())
            break
        
        # Try to find a good breaking point
        # 1. Look for paragraph break (double newline)
        break_point = text.rfind('\n\n', start, end)
        
        # 2. Look for single newline
        if break_point == -1 or break_point < start + chunk_size // 2:
            break_point = text.rfind('\n', start, end)
        
        # 3. Look for sentence end
        if break_point == -1 or break_point < start + chunk_size // 2:
            break_point = text.rfind('. ', start, end)
        
        # 4. Look for any space
        if break_point == -1 or break_point < start + chunk_size // 2:
            break_point = text.rfind(' ', start, end)
        
        # 5. Hard break (should be rare)
        if break_point == -1 or break_point < start + chunk_size // 2:
            break_point = end
        
        # Add chunk
        chunk = text[start:break_point].strip()
        if chunk:
            chunks.append(chunk)
        
        # Move start position (with overlap)
        start = break_point - overlap
        if start < 0:
            start = 0
    
    return chunks


def generate_embeddings(
    chunks: List[str],
    api_key: str,
    model: str = "text-embedding-ada-002"
) -> List[List[float]]:
    """
    Generate embeddings for text chunks using OpenAI.
    
    Args:
        chunks: List of text chunks
        api_key: OpenAI API key
        model: Embedding model to use
    
    Returns:
        List of embedding vectors
    """
    if not chunks or not api_key:
        return []
    
    try:
        client = OpenAI(api_key=api_key)
        
        # Batch embeddings for efficiency (OpenAI allows up to 2048 inputs)
        # For safety, batch in groups of 100
        embeddings = []
        batch_size = 100
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            
            response = client.embeddings.create(
                model=model,
                input=batch
            )
            
            batch_embeddings = [item.embedding for item in response.data]
            embeddings.extend(batch_embeddings)
        
        return embeddings
        
    except Exception as e:
        print(f"Embedding generation error: {e}")
        return []


def extract_chunk_metadata(
    chunk_text: str,
    chunk_index: int,
    source: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Extract metadata from chunk text.
    
    Metadata can include:
    - Page numbers (from PDF)
    - Headers/titles
    - URLs (from web pages)
    - Timestamps
    
    Args:
        chunk_text: The chunk text
        chunk_index: Index of this chunk
        source: Source record
    
    Returns:
        Metadata dict
    """
    metadata = {
        "chunk_index": chunk_index,
        "source_type": source["source_type"],
        "source_name": source["name"],
    }
    
    # Extract page number from PDF chunks
    page_match = re.search(r'\[PAGE (\d+)\]', chunk_text)
    if page_match:
        metadata["page"] = int(page_match.group(1))
    
    # For URLs, include the source
    if source["source_type"] == "url":
        metadata["url"] = source["file_path"]
    
    # Extract first line as potential title/header
    lines = chunk_text.split('\n')
    if lines:
        first_line = lines[0].strip()
        if len(first_line) < 100:  # Likely a header
            metadata["header"] = first_line
    
    return metadata


def _mark_failed(cur, knowledge_source_id: str, error_message: str):
    """Mark knowledge source as failed."""
    cur.execute(
        """
        UPDATE knowledge_sources 
        SET sync_status = 'failed',
            error_message = %s,
            last_synced_at = NOW()
        WHERE id = %s
        """,
        (error_message, knowledge_source_id)
    )