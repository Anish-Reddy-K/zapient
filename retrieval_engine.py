# retrieval_engine.py

import os
import re
import json
import math
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

# For local embeddings + semantic search (pip install sentence-transformers)
from sentence_transformers import SentenceTransformer, util

#########################
# Configuration
#########################

# You can customize these defaults as needed:
LARGE_CHUNK_SIZE = 600     # approximate # of characters for "large" chunks
SMALL_CHUNK_SIZE = 300     # approximate # of characters for "small" chunks
CHUNK_OVERLAP = 50         # overlap in characters between consecutive chunks
TOP_K_SEMANTIC = 10        # # of chunks to retrieve for semantic search
TOP_K_KEYWORD = 25         # # of chunks to retrieve for keyword-based search

# Which SentenceTransformer embedding model
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

#########################
# Retrieval Classes & Functions
#########################

class ChunkData:
    """
    Holds the chunk's text, plus metadata about which doc/page/chunk_index it came from.
    """
    def __init__(self, text: str, doc_filename: str, page_number: int, chunk_index: int):
        self.text = text
        self.doc_filename = doc_filename
        self.page_number = page_number
        self.chunk_index = chunk_index


class RetrievalEngine:
    """
    Builds two sets of chunks (large and small) from the processed JSONs in an agent's
    'processed' folder, then provides:
    - semantic_search() on large chunks
    - keyword_search() on small chunks
    """

    def __init__(self, agent_processed_dir: str):
        """
        agent_processed_dir: path to the 'processed' folder for that agent,
                             containing .json files of extracted PDF data.
        """
        self.agent_processed_dir = agent_processed_dir
        self.model = SentenceTransformer(EMBEDDING_MODEL_NAME)

        self.large_chunks: List[ChunkData] = []
        self.small_chunks: List[ChunkData] = []
        self.large_embeddings = None

        # Build up chunk lists from processed JSON
        self._build_large_and_small_chunks()

        # Precompute embeddings for large chunks
        if self.large_chunks:
            texts = [chunk.text for chunk in self.large_chunks]
            self.large_embeddings = self.model.encode(texts, convert_to_tensor=True)

    def _build_large_and_small_chunks(self):
        """
        Reads each processed .json in the agent's processed dir, extracts page text,
        and splits into large & small overlapping chunks.
        """
        if not os.path.isdir(self.agent_processed_dir):
            return

        processed_files = [f for f in os.listdir(self.agent_processed_dir)
                           if f.lower().endswith('.json')]

        for proc_file in processed_files:
            proc_path = os.path.join(self.agent_processed_dir, proc_file)
            try:
                with open(proc_path, 'r', encoding='utf-8') as f:
                    doc = json.load(f)
            except Exception as e:
                logging.error(f"Could not read {proc_path}: {e}")
                continue

            # doc should have 'content': [ { page_number, text, tables }, ... ]
            content_list = doc.get('content', [])
            for page_data in content_list:
                page_num = page_data.get('page_number', -1)
                page_text = page_data.get('text', "")

                # 1) Large chunks for semantic search
                large_page_chunks = self._split_text_into_chunks(
                    page_text, chunk_size=LARGE_CHUNK_SIZE, overlap=CHUNK_OVERLAP
                )
                for idx, chunk_text in enumerate(large_page_chunks):
                    chunk = ChunkData(chunk_text, proc_file, page_num, idx)
                    self.large_chunks.append(chunk)

                # 2) Small chunks for keyword search
                small_page_chunks = self._split_text_into_chunks(
                    page_text, chunk_size=SMALL_CHUNK_SIZE, overlap=CHUNK_OVERLAP
                )
                for idx, chunk_text in enumerate(small_page_chunks):
                    chunk = ChunkData(chunk_text, proc_file, page_num, idx)
                    self.small_chunks.append(chunk)

    def _split_text_into_chunks(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """
        Simple character-based chunking with overlap. 
        For more advanced usage, you might do token-based chunking or etc.
        """
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk_text = text[start:end]
            chunks.append(chunk_text)
            start += (chunk_size - overlap)
        return chunks

    def semantic_search(self, query: str, top_k: int = TOP_K_SEMANTIC) -> List[ChunkData]:
        """
        Return the top_k large chunks by embedding cosine similarity to the query.
        """
        if not self.large_chunks or self.large_embeddings is None:
            return []

        query_emb = self.model.encode(query, convert_to_tensor=True)
        scores = util.pytorch_cos_sim(query_emb, self.large_embeddings)[0]
        top_results = scores.topk(k=min(top_k, len(scores)), largest=True)

        top_indices = top_results[1].cpu().numpy().tolist()
        # top_scores = top_results[0].cpu().numpy().tolist()  # If you want the actual scores
        result = []
        for idx in top_indices:
            result.append(self.large_chunks[idx])
        return result

    def keyword_search(self, query: str, top_k: int = TOP_K_KEYWORD) -> List[ChunkData]:
        """
        Naive approach: Count how many keywords from the query appear in each small chunk.
        Return the top_k with the highest matches.
        """
        if not self.small_chunks:
            return []

        query_lower = query.lower()
        # Just split by non-alphanumeric to get "words"
        keywords = re.split(r'\W+', query_lower)
        keywords = [k for k in keywords if k]  # remove empty entries

        chunk_scores = []
        for i, chunk in enumerate(self.small_chunks):
            text_lower = chunk.text.lower()
            score = 0
            for kw in keywords:
                if kw in text_lower:
                    score += 1
            chunk_scores.append((score, i))

        # sort descending by score
        chunk_scores.sort(key=lambda x: x[0], reverse=True)

        top_hits = chunk_scores[: min(top_k, len(chunk_scores))]
        result = []
        for (score, idx) in top_hits:
            result.append(self.small_chunks[idx])

        return result


def save_retrieval_results(
    data_dir: str,
    username: str,
    agent_name: str,
    conversation_id: str,
    query: str,
    semantic_chunks: List[ChunkData],
    keyword_chunks: List[ChunkData]
):
    """
    Saves retrieval results to retrieval_results.json under the agent's folder,
    in a structure like:
    {
      "conversation_id": {
        "some user query": {
          "semantic_chunks": [...],
          "keyword_chunks": [...]
        }
      }
    }
    """
    agent_dir = os.path.join(data_dir, username, 'AGENTS', agent_name)
    retrieval_file = os.path.join(agent_dir, 'retrieval_results.json')

    # Load or create
    if os.path.exists(retrieval_file):
        try:
            with open(retrieval_file, 'r', encoding='utf-8') as f:
                retrieval_data = json.load(f)
        except Exception as e:
            logging.error(f"Could not load retrieval_results.json: {e}")
            retrieval_data = {}
    else:
        retrieval_data = {}

    if conversation_id not in retrieval_data:
        retrieval_data[conversation_id] = {}

    # Convert chunk objects to dict for safe JSON
    def chunk_to_dict(ch: ChunkData) -> dict:
        return {
            "text": ch.text,
            "doc_filename": ch.doc_filename,
            "page_number": ch.page_number,
            "chunk_index": ch.chunk_index
        }

    semantic_list = [chunk_to_dict(ch) for ch in semantic_chunks]
    keyword_list = [chunk_to_dict(ch) for ch in keyword_chunks]

    retrieval_data[conversation_id][query] = {
        "semantic_chunks": semantic_list,
        "keyword_chunks": keyword_list
    }

    with open(retrieval_file, 'w', encoding='utf-8') as f:
        json.dump(retrieval_data, f, indent=2)