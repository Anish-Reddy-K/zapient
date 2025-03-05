"""
File Processing Module
---------------------
Combines functionality to process PDF documents for AI agents. 
Extracts content, tables, and advanced metadata using Gemini API.
"""

import os
import json
import hashlib
import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, TypedDict
from dataclasses import dataclass, asdict

# External libraries for PDF processing
import PyPDF2
import pdfplumber
import pandas as pd

# LLM integration for advanced metadata
try:
    import google.generativeai as genai
    from tenacity import retry, stop_after_attempt, wait_exponential
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False
    logging.warning("Gemini API not available. Advanced metadata extraction disabled.")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# =============================================================================
# TYPE DEFINITIONS AND CONSTANTS
# =============================================================================
class Entities(TypedDict):
    equipment: List[str]
    standards: List[str]
    units: List[str]

class AdvancedMetadata(TypedDict):
    intent: str
    semantic_queries: List[str]
    keywords: List[str]
    entities: Entities
    key_sections: List[str]

@dataclass
class TableMetadata:
    table_id: int
    page_number: int
    bbox: List[float]
    rows: int
    columns: int
    headers: List[str]
    context_headings: List[str]
    text_before: str
    text_after: str

@dataclass
class DocumentMetadata:
    filename: str
    file_path: str
    file_hash: str
    extraction_date: str
    title: str
    author: str
    subject: str
    creator: str
    creation_date: str
    page_count: int
    total_tables: int
    pages_with_tables: int

# System prompt for LLM
SYSTEM_PROMPT = """You are a specialized oil/gas document analyst tasked with extracting structured metadata from technical documents. 

IMPORTANT: You must respond with ONLY a valid JSON object and no other text. The JSON object should contain these components:

1. Intent Classification (exactly one): "Safety", "Equipment", "Regulatory", "Technical", or "Other"
2. Semantic Search Queries (exactly 3)
3. Keywords/Phrases (exactly 10)
4. Entities:
   - equipment: List equipment names/types
   - standards: List industry standards
   - units: List measurement units
5. Key Sections: List main document sections

Return ONLY valid JSON matching this schema:
{
  "intent": "string",
  "semantic_queries": ["string", "string", "string"],
  "keywords": ["string", "string", "string", "string", "string", "string", "string", "string", "string", "string"],
  "entities": {
    "equipment": ["string"],
    "standards": ["string"],
    "units": ["string"]
  },
  "key_sections": ["string"]
}"""

# =============================================================================
# FILE STATUS MANAGEMENT FUNCTIONS
# =============================================================================
def update_file_status(username, agent_name, filename, status, message=None):
    """Update the status of a file in files.json"""
    agent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', username, 'AGENTS', agent_name)
    files_json_path = os.path.join(agent_dir, 'files.json')
    
    if not os.path.exists(files_json_path):
        # If files.json doesn't exist, create it
        files_data = {
            "files": []
        }
    else:
        # Load existing files.json
        try:
            with open(files_json_path, 'r') as f:
                files_data = json.load(f)
        except json.JSONDecodeError:
            # If file is corrupted, create a new one
            files_data = {
                "files": []
            }
    
    # Find the file in the list
    file_found = False
    for file in files_data['files']:
        if file['name'] == filename:
            file['processing_status'] = status
            if message:
                file['error_message'] = message
            else:
                file['error_message'] = None
            
            # If status is 'success', mark as processed
            if status == 'success':
                file['processed'] = True
            
            file_found = True
            break
    
    if not file_found:
        # If file not found, add it with the given status
        logging.warning(f"File {filename} not found in files.json for agent {agent_name}, adding it")
        files_data['files'].append({
            "name": filename,
            "processing_status": status,
            "processed": status == 'success',
            "error_message": message
        })
    
    # Save the updated data
    with open(files_json_path, 'w') as f:
        json.dump(files_data, f, indent=2)
    
    return files_data

# =============================================================================
# BASIC EXTRACTION FUNCTIONS
# =============================================================================
def generate_file_hash(file_path: Path) -> str:
    """Generate SHA-256 hash of file for tracking changes."""
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)
    return hasher.hexdigest()

def extract_pdf_metadata(pdf_reader: PyPDF2.PdfReader) -> Dict[str, Any]:
    """Extract basic PDF metadata."""
    metadata = pdf_reader.metadata if pdf_reader.metadata else {}
    return {
        'title': metadata.get('/Title', ''),
        'author': metadata.get('/Author', ''),
        'subject': metadata.get('/Subject', ''),
        'creator': metadata.get('/Creator', ''),
        'creation_date': metadata.get('/CreationDate', ''),
        'page_count': len(pdf_reader.pages)
    }

def get_table_context(page: Any, table_bbox: Tuple[float, float, float, float], 
                     text_blocks: List[Dict]) -> Dict[str, Any]:
    """Extract context around a table including headings and surrounding text."""
    table_top, table_bottom = table_bbox[1], table_bbox[3]
    context = {
        'potential_headings': [],
        'text_before': [],
        'text_after': []
    }
    
    for block in text_blocks:
        block_bbox = block.get('bbox')
        if not block_bbox:
            continue
            
        block_bottom = block_bbox[3]
        block_top = block_bbox[1]
        text = block.get('text', '').strip()
        
        if not text:
            continue
        
        if block_bottom < table_top and block_bottom >= table_top - 50:
            context['potential_headings'].append({
                'text': text,
                'distance': table_top - block_bottom
            })
        elif block_bottom < table_top:
            context['text_before'].append(text)
        elif block_top > table_bottom:
            context['text_after'].append(text)
    
    context['potential_headings'].sort(key=lambda x: x['distance'])
    headings = [h['text'] for h in context['potential_headings'][:2]]
    
    return {
        'headings': headings,
        'text_before': ' '.join(context['text_before'][-2:]),
        'text_after': ' '.join(context['text_after'][:2])
    }

def process_table(table: List[List[Any]], table_bbox: Tuple[float, float, float, float], 
                 page: Any, page_num: int, table_idx: int) -> Dict[str, Any]:
    """Process a single table and its context."""
    # Convert empty strings and whitespace-only strings to None
    cleaned_table = []
    for row in table:
        cleaned_row = []
        for cell in row:
            if cell is None or (isinstance(cell, str) and cell.strip() == ''):
                cleaned_row.append(None)
            else:
                cleaned_row.append(cell)
        cleaned_table.append(cleaned_row)
    
    # Create DataFrame from cleaned table
    df = pd.DataFrame(cleaned_table)
    
    # Remove completely empty rows and columns
    df = df.replace('', None).dropna(how='all', axis=1).dropna(how='all', axis=0)
    
    # Assign default column names if DataFrame is not empty
    if not df.empty and len(df.columns) > 0:
        df.columns = [f'Column_{i+1}' for i in range(len(df.columns))]
    
    text_blocks = page.extract_words(x_tolerance=3, y_tolerance=3, keep_blank_chars=False)
    context = get_table_context(page, table_bbox, text_blocks)
    
    rows = len(df) if not df.empty else 0
    columns = len(df.columns) if not df.empty else 0
    headers = df.columns.tolist() if not df.empty else []
    
    table_metadata = TableMetadata(
        table_id=table_idx + 1,
        page_number=page_num,
        bbox=list(table_bbox),
        rows=rows,
        columns=columns,
        headers=headers,
        context_headings=context['headings'],
        text_before=context['text_before'],
        text_after=context['text_after']
    )
    
    return {
        'metadata': asdict(table_metadata),
        'data': df.values.tolist() if not df.empty else []
    }

def extract_page_content(page: Any, page_num: int) -> Dict[str, Any]:
    """Extract content from a single page."""
    tables = []
    page_tables = page.extract_tables()
    
    if page_tables:
        table_positions = page.find_tables()
        for idx, (table, position) in enumerate(zip(page_tables, table_positions)):
            table_data = process_table(table, position.bbox, page, page_num, idx)
            tables.append(table_data)
    
    return {
        'page_number': page_num,
        'text': page.extract_text().strip(),
        'tables': tables
    }

def extract_document_content(pdf_path: Path) -> Optional[Dict[str, Any]]:
    """Extract content and metadata from a PDF file."""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            basic_metadata = extract_pdf_metadata(pdf_reader)
        
        with pdfplumber.open(pdf_path) as pdf:
            content = []
            all_tables = []
            
            for page_num, page in enumerate(pdf.pages, 1):
                page_content = extract_page_content(page, page_num)
                content.append(page_content)
                all_tables.extend(page_content['tables'])
            
            doc_metadata = DocumentMetadata(
                filename=pdf_path.name,
                file_path=str(pdf_path),
                file_hash=generate_file_hash(pdf_path),
                extraction_date=datetime.now().isoformat(),
                title=basic_metadata['title'],
                author=basic_metadata['author'],
                subject=basic_metadata['subject'],
                creator=basic_metadata['creator'],
                creation_date=basic_metadata['creation_date'],
                page_count=basic_metadata['page_count'],
                total_tables=len(all_tables),
                pages_with_tables=sum(1 for page in content if page['tables'])
            )
            
            return {
                'metadata': asdict(doc_metadata),
                'content': content
            }
            
    except Exception as e:
        logging.error(f"Error processing {pdf_path}: {str(e)}")
        return None

# =============================================================================
# ADVANCED METADATA EXTRACTION
# =============================================================================
if HAS_GEMINI:
    def setup_gemini(api_key: str) -> genai.GenerativeModel:
        """Initialize and return Gemini model."""
        genai.configure(api_key=api_key)
        
        # Configure the model with recommended settings
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
        }
        
        return genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=generation_config
        )

    def validate_metadata(metadata: Dict[str, Any]) -> None:
        """Validate metadata structure and content."""
        required_fields = {
            'intent': str,
            'semantic_queries': list,
            'keywords': list,
            'entities': dict,
            'key_sections': list
        }
        
        # Check required fields and types
        for field, expected_type in required_fields.items():
            if field not in metadata:
                raise ValueError(f"Missing required field: {field}")
            if not isinstance(metadata[field], expected_type):
                raise TypeError(f"Invalid type for {field}")
        
        # Validate specific constraints
        if metadata['intent'] not in {'Safety', 'Equipment', 'Regulatory', 'Technical', 'Other'}:
            raise ValueError("Invalid intent classification")
        
        if len(metadata['semantic_queries']) != 3:
            raise ValueError("Must have exactly 3 semantic queries")
            
        if len(metadata['keywords']) != 10:
            raise ValueError("Must have exactly 10 keywords")
            
        required_entity_types = {'equipment', 'standards', 'units'}
        if not all(et in metadata['entities'] for et in required_entity_types):
            raise ValueError("Missing required entity types")

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=5))
    def extract_metadata(model: genai.GenerativeModel, text: str) -> Dict[str, Any]:
        """Extract metadata from document text using Gemini chat."""
        try:
            # Try to use chat API first
            try:
                # Start a new chat session
                chat = model.start_chat(history=[])
                
                # Send system prompt first
                chat.send_message(SYSTEM_PROMPT)
                
                # Send document text and get response
                response = chat.send_message(f"Document Text:\n{text}")
                response_text = response.text.strip()
            except Exception as chat_error:
                logging.warning(f"Chat API failed, falling back to generate_content: {str(chat_error)}")
                # Fallback to generate_content if chat API fails
                response = model.generate_content([
                    SYSTEM_PROMPT, 
                    f"Document Text:\n{text}"
                ])
                response_text = response.text.strip()
            
            # Try to find JSON in the response
            try:
                # First try direct JSON parsing
                metadata = json.loads(response_text)
            except json.JSONDecodeError:
                # If that fails, try to find JSON-like structure
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}')
                
                if start_idx != -1 and end_idx != -1:
                    json_str = response_text[start_idx:end_idx + 1]
                    try:
                        metadata = json.loads(json_str)
                    except json.JSONDecodeError:
                        logging.error(f"Could not extract valid JSON from response")
                        raise
                else:
                    logging.error("No JSON structure found in response")
                    raise ValueError("Response does not contain JSON structure")
            
            # Validate response structure
            validate_metadata(metadata)
            
            return metadata
            
        except Exception as e:
            logging.error(f"Error in metadata extraction: {str(e)}")
            raise

    def truncate_text(text: str, max_length: int = 30000) -> str:
        """Truncate text to max_length while keeping whole sentences."""
        if len(text) <= max_length:
            return text
            
        # Find the last sentence boundary before max_length
        truncated = text[:max_length]
        last_period = truncated.rfind('.')
        if last_period != -1:
            return truncated[:last_period + 1]
        return truncated

# =============================================================================
# INTEGRATED PROCESSING FUNCTIONS
# =============================================================================
def process_document_full(
    pdf_path: Path,
    processed_dir: Path,
    api_key: str,
    username: str = None,
    agent_name: str = None,
    filename: str = None
) -> Dict[str, str]:
    """
    Process a PDF document with both basic and advanced extraction.
    
    Returns a dictionary with processing status information.
    """
    result = {
        'status': 'error',
        'message': '',
        'output_path': ''
    }
    
    try:
        # Create directory if it doesn't exist
        processed_dir.mkdir(exist_ok=True)
        
        # Check if file is already processed
        output_path = processed_dir / f"{pdf_path.stem}.json"
        if output_path.exists():
            # File already processed, return success
            result['status'] = 'success'
            result['message'] = f"File {pdf_path.name} already processed"
            result['output_path'] = str(output_path)
            
            # Update file status if username and agent_name are provided
            if username and agent_name and filename:
                update_file_status(username, agent_name, filename, 'success')
                
            return result
        
        # Step 1: Basic extraction
        logging.info(f"Starting extraction for {pdf_path.name}")
        
        # Update status if username and agent_name are provided
        if username and agent_name and filename:
            update_file_status(username, agent_name, filename, 'processing', 'Extracting document content')
        
        document = extract_document_content(pdf_path)
        if not document:
            result['message'] = f"Failed to extract content from {pdf_path.name}"
            
            # Update status if username and agent_name are provided
            if username and agent_name and filename:
                update_file_status(username, agent_name, filename, 'error', f"Failed to extract content from {pdf_path.name}")
                
            return result
        
        # Default fallback metadata in case Gemini fails
        fallback_metadata = {
            "intent": "Technical",
            "semantic_queries": [
                "What is this document about?",
                "What are the safety procedures?",
                "What regulations apply?"
            ],
            "keywords": [
                "technical", "document", "safety", "procedure", 
                "equipment", "maintenance", "operation", "specification",
                "standard", "regulation"
            ],
            "entities": {
                "equipment": ["generic equipment"],
                "standards": ["industry standards"],
                "units": ["standard units"]
            },
            "key_sections": ["Main document sections"]
        }
        
        # Step 2: Try advanced extraction with Gemini
        gemini_success = False
        if HAS_GEMINI and api_key:
            logging.info(f"Performing advanced extraction for {pdf_path.name}")
            
            # Update status if username and agent_name are provided
            if username and agent_name and filename:
                update_file_status(username, agent_name, filename, 'processing', 'Performing advanced metadata extraction')
                
            try:
                # Extract text content from all pages
                full_text = ' '.join(
                    page['text'] for page in document['content']
                    if page.get('text')
                )
                
                # Truncate text if too long
                full_text = truncate_text(full_text)
                
                # Setup Gemini model
                model = setup_gemini(api_key)
                
                # Extract advanced metadata
                advanced_metadata = extract_metadata(model, full_text)
                
                # Add advanced metadata to document
                document['advanced_metadata'] = advanced_metadata
                gemini_success = True
                
            except Exception as e:
                logging.error(f"Advanced processing failed for {pdf_path.name}: {str(e)}")
                document['advanced_processing_error'] = str(e)
                # Use fallback metadata
                document['advanced_metadata'] = fallback_metadata
                document['used_fallback_metadata'] = True
        else:
            document['advanced_processing_error'] = "Gemini API not available or API key not provided"
            document['advanced_metadata'] = fallback_metadata
            document['used_fallback_metadata'] = True
            
        # Save complete document
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(document, f, ensure_ascii=False, indent=2)
            
        result['status'] = 'success'
        if gemini_success:
            result['message'] = f"Successfully processed {pdf_path.name} with Gemini AI"
        else:
            result['message'] = f"Successfully processed {pdf_path.name} with basic extraction"
        result['output_path'] = str(output_path)
        
        # Update file status if username and agent_name are provided
        if username and agent_name and filename:
            update_file_status(username, agent_name, filename, 'success', result['message'])
        
    except Exception as e:
        logging.error(f"Error processing {pdf_path}: {str(e)}")
        result['message'] = str(e)
        
        # Update file status if username and agent_name are provided
        if username and agent_name and filename:
            update_file_status(username, agent_name, filename, 'error', str(e))
    
    return result

def process_files_batch(
    files: List[Path],
    processed_dir: Path,
    api_key: str,
    username: str = None,
    agent_name: str = None
) -> Dict[str, Dict[str, str]]:
    """
    Process a batch of PDF files.
    
    Returns a dictionary with results for each file.
    """
    results = {}
    
    for file_path in files:
        if file_path.suffix.lower() == '.pdf':
            logging.info(f"Processing {file_path.name}")
            results[file_path.name] = process_document_full(
                file_path, processed_dir, api_key, 
                username=username, agent_name=agent_name, filename=file_path.name
            )
        else:
            logging.warning(f"Skipping non-PDF file: {file_path.name}")
            results[file_path.name] = {
                'status': 'skipped',
                'message': 'Not a PDF file'
            }
            
            # Update file status if username and agent_name are provided
            if username and agent_name:
                update_file_status(username, agent_name, file_path.name, 'error', 'Not a PDF file')
    
    return results

# =============================================================================
# BACKGROUND PROCESSING FUNCTION
# =============================================================================
def process_agent_files(
    username: str,
    agent_name: str,
    agent_dir: str,
    files: List[str],
    config_file: str,
    api_key: str = None
):
    """Process files for an agent in the background."""
    try:
        # Setup paths
        uploads_dir = os.path.join(agent_dir, 'uploads')
        processed_dir = os.path.join(agent_dir, 'processed')
        
        # Create directories if they don't exist
        os.makedirs(processed_dir, exist_ok=True)
        
        # Get file paths as Path objects
        file_paths = [Path(os.path.join(uploads_dir, f)) for f in files]
        
        # Update status for all files to 'processing'
        for filename in files:
            update_file_status(username, agent_name, filename, 'processing', 'Processing document content')
        
        # Process files
        results = process_files_batch(
            file_paths,
            Path(processed_dir),
            api_key,
            username=username,
            agent_name=agent_name
        )
        
        # We don't need to update file status here as process_document_full already does it
        
        # Update agent config to indicate processing is complete
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        config['files_processed'] = True
        config['processing_complete'] = True
        config['processing_results'] = results
        
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        logging.info(f"Completed processing {len(files)} files for agent {agent_name}")
            
    except Exception as e:
        logging.error(f"Error in file processing thread: {str(e)}")
        
        # Update status for all files to 'error'
        for filename in files:
            update_file_status(username, agent_name, filename, 'error', f"Processing error: {str(e)}")
        
        # Update agent config to indicate processing failed
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            config['files_processed'] = False
            config['processing_complete'] = True
            config['processing_error'] = str(e)
            
            with open(config_file, 'w') as f:
                json.dump(config, f)
        except Exception as config_error:
            logging.error(f"Error updating agent config: {str(config_error)}")