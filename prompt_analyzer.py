# prompt_analyzer.py

import os
import json
import logging
from typing import Optional
from threading import Thread

from retrieval_engine import (
    RetrievalEngine,
    save_retrieval_results
)

PROMPT_ANALYSIS_SYSTEM_PROMPT = """You are a specialized assistant for analyzing a user's query.
When given a single user query, you must return valid JSON with these fields:

{
  "original_query": "...",
  "sub_queries": [...],
  "keywords": [...]
}

Constraints:
1. If the query can be naturally split into multiple questions, do so.
2. Return only valid JSON. No additional commentary.
3. Do not enclose JSON in backticks.
"""

########################
# Gemini Setup
########################
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False
    logging.error("Gemini python package (google-generativeai) not installed.")


def analyze_prompt_with_gemini(api_key: str, user_query: str) -> dict:
    """
    Calls Gemini to analyze the user's query, splitting it into sub-queries
    and extracting keywords.
    Returns a dict of the form:
      {
        "original_query": "...",
        "sub_queries": [...],
        "keywords": [...]
      }
    or a fallback structure on error.
    """
    if not HAS_GEMINI:
        # fallback
        return {
            "original_query": user_query,
            "sub_queries": [user_query],
            "keywords": []
        }

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config={
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048,
        }
    )
    try:
        chat_session = model.start_chat(history=[])
        chat_session.send_message(PROMPT_ANALYSIS_SYSTEM_PROMPT)

        response = chat_session.send_message(f"User Query:\n{user_query}")
        response_text = response.text.strip()

        # Try direct parse
        try:
            analysis = json.loads(response_text)
            return analysis
        except json.JSONDecodeError:
            # Or substring extraction if there's extra text
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}')
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx + 1]
                return json.loads(json_str)
            else:
                raise ValueError("No valid JSON found in Gemini response.")

    except Exception as e:
        logging.error(f"Gemini prompt analysis error: {e}")
        return {
            "original_query": user_query,
            "sub_queries": [user_query],
            "keywords": []
        }


def perform_retrieval_for_analysis(
    data_dir: str,
    username: str,
    agent_name: str,
    conversation_id: str,
    analysis_result: dict
):
    """
    1) Build a retrieval engine from the agent's processed/ folder
    2) For each sub-query and original_query => do SEMANTIC search
    3) For the original_query => do KEYWORD search (once)
    4) Save (merge) results in retrieval_results.json
    """

    agent_processed_dir = os.path.join(data_dir, username, 'AGENTS', agent_name, 'processed')
    if not os.path.exists(agent_processed_dir):
        logging.warning(f"No processed folder for agent {agent_name}; skipping retrieval.")
        return

    engine = RetrievalEngine(agent_processed_dir)

    original_q = analysis_result.get("original_query", "").strip()
    sub_qs = analysis_result.get("sub_queries", [])

    # -------------------------------------------
    # (2) SEMANTIC search for each query
    all_queries = [original_q] + sub_qs
    for q in all_queries:
        q_str = q.strip()
        if not q_str:
            continue

        # top semantic chunks
        semantic_chunks = engine.semantic_search(q_str)
        # For sub-queries, we won't add keyword chunks => pass empty
        save_retrieval_results(
            data_dir=data_dir,
            username=username,
            agent_name=agent_name,
            conversation_id=conversation_id,
            query=q_str,
            semantic_chunks=semantic_chunks,
            keyword_chunks=[]  # no keyword results for sub-queries
        )

    # -------------------------------------------
    # (3) KEYWORD search only for the original query
    if original_q:
        keyword_chunks = engine.keyword_search(original_q)

        # We want to merge these keyword results with the existing semantic results
        # for the original query, which we just stored.
        # So let's load the existing retrieval_results.json and combine them.

        agent_dir = os.path.join(data_dir, username, 'AGENTS', agent_name)
        retrieval_file = os.path.join(agent_dir, 'retrieval_results.json')
        if os.path.exists(retrieval_file):
            try:
                with open(retrieval_file, 'r', encoding='utf-8') as f:
                    retrieval_data = json.load(f)
            except:
                retrieval_data = {}
        else:
            retrieval_data = {}

        if conversation_id not in retrieval_data:
            retrieval_data[conversation_id] = {}

        conv_dict = retrieval_data[conversation_id]
        existing_entry = conv_dict.get(original_q, {})

        existing_semantic = existing_entry.get("semantic_chunks", [])

        # Convert the new keyword chunks to dict form
        def chunk_to_dict(ch):
            return {
                "text": ch.text,
                "doc_filename": ch.doc_filename,
                "page_number": ch.page_number,
                "chunk_index": ch.chunk_index
            }
        keyword_list = [chunk_to_dict(ch) for ch in keyword_chunks]

        # Now combine them
        updated_obj = {
            "semantic_chunks": existing_semantic,  # from earlier
            "keyword_chunks": keyword_list
        }
        conv_dict[original_q] = updated_obj
        retrieval_data[conversation_id] = conv_dict

        # Save them back
        with open(retrieval_file, 'w', encoding='utf-8') as f:
            json.dump(retrieval_data, f, indent=2)


def analyze_prompt_background(
    api_key: Optional[str],
    data_dir: str,
    username: str,
    agent_name: str,
    conversation_id: str,
    user_query: str
):
    """
    1) Analyze the user's entire prompt with Gemini
    2) Store analysis in chat_history.json
    3) Perform retrieval
    """
    # 1) Prompt Analysis
    analysis_result = analyze_prompt_with_gemini(api_key or "", user_query)

    # 2) Save the analysis to chat_history.json
    chat_file = os.path.join(data_dir, username, 'AGENTS', agent_name, 'chat_history.json')
    if not os.path.exists(chat_file):
        logging.warning("Chat history file not found, cannot store analysis.")
        return

    with open(chat_file, 'r') as f:
        chat_data = json.load(f)

    conversations = chat_data.get("conversations", [])
    conversation = next((c for c in conversations if c["conversation_id"] == conversation_id), None)
    if not conversation:
        logging.warning(f"Conversation {conversation_id} not found, cannot store analysis.")
        return

    if "analysis" not in conversation:
        conversation["analysis"] = []
    conversation["analysis"].append(analysis_result)

    chat_data["conversations"] = conversations
    with open(chat_file, 'w') as f:
        json.dump(chat_data, f, indent=2)

    # 3) Perform retrieval
    perform_retrieval_for_analysis(
        data_dir=data_dir,
        username=username,
        agent_name=agent_name,
        conversation_id=conversation_id,
        analysis_result=analysis_result
    )