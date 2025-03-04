# prompt_analyzer.py

import os
import json
import logging
from typing import Optional
from threading import Thread

PROMPT_ANALYSIS_SYSTEM_PROMPT = """You are a specialized assistant for analyzing a user's query.
When given a single user query, you must return valid JSON with these fields:

{
  "original_query": "The user’s raw query string",
  "sub_queries": ["Each sub-query if the user query is multipart or has multiple angles."],
  "keywords": ["A short list of important keywords from the user’s query"]
}

Constraints:
1. If the query can be naturally split into multiple questions, do so.
2. Return only valid JSON. No additional commentary.
3. Do not enclose JSON in backticks.
"""

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False
    logging.error("Gemini python package (google-generativeai) not installed.")


# --- IMPORT OUR RETRIEVAL ENGINE CODE ---
from retrieval_engine import (
    RetrievalEngine,
    save_retrieval_results
)


def analyze_prompt_with_gemini(api_key: str, user_query: str) -> dict:
    """
    Calls Gemini to analyze the user's query, splitting it into sub-queries
    and extracting keywords. Returns a dict with:
    {
      "original_query": "...",
      "sub_queries": [...],
      "keywords": [...]
    }
    or a fallback structure on error.
    """
    if not HAS_GEMINI:
        # Fallback
        return {
            "original_query": user_query,
            "sub_queries": [user_query],
            "keywords": []
        }

    genai.configure(api_key=api_key)

    # Prepare the model
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
        # Start a chat with the system prompt
        chat_session = model.start_chat(history=[])
        chat_session.send_message(PROMPT_ANALYSIS_SYSTEM_PROMPT)

        # Send the user query for analysis
        response = chat_session.send_message(f"User Query:\n{user_query}")
        response_text = response.text.strip()

        # Attempt to parse JSON
        try:
            analysis = json.loads(response_text)
            return analysis
        except json.JSONDecodeError:
            # If direct parse fails, try substring extraction
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}')
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx + 1]
                analysis = json.loads(json_str)
                return analysis
            else:
                raise ValueError("No valid JSON found in the Gemini response.")

    except Exception as e:
        logging.error(f"Gemini prompt analysis error: {str(e)}")
        # fallback
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
    1) Build a retrieval engine from the processed PDF JSONs in:
         data_dir/username/AGENTS/agent_name/processed
    2) For each query in the analysis (including original_query),
       run semantic search (top 10 large chunks) & keyword search (top 25 small),
       then save results in retrieval_results.json
    """
    agent_processed_dir = os.path.join(data_dir, username, 'AGENTS', agent_name, 'processed')
    if not os.path.exists(agent_processed_dir):
        logging.warning(f"No processed folder found for agent {agent_name}, skipping retrieval.")
        return

    engine = RetrievalEngine(agent_processed_dir)

    # Gather all queries: original + sub-queries
    original_q = analysis_result.get("original_query", "")
    sub_qs = analysis_result.get("sub_queries", [])
    all_queries = [original_q] + sub_qs

    for q in all_queries:
        q_str = q.strip()
        if not q_str:
            continue

        # Semantic search for large chunks
        semantic_chunks = engine.semantic_search(q_str)
        # Keyword search for small chunks
        keyword_chunks = engine.keyword_search(q_str)

        # Save them
        save_retrieval_results(
            data_dir=data_dir,
            username=username,
            agent_name=agent_name,
            conversation_id=conversation_id,
            query=q_str,
            semantic_chunks=semantic_chunks,
            keyword_chunks=keyword_chunks
        )


def analyze_prompt_background(
    api_key: Optional[str],
    data_dir: str,
    username: str,
    agent_name: str,
    conversation_id: str,
    user_query: str
):
    """
    1) Analyze the user's prompt with Gemini (if available) to get sub-queries & keywords.
    2) Save the analysis in the chat_history.json for that conversation.
    3) Perform retrieval for each query in the analysis and save results to retrieval_results.json.
    """
    if not api_key:
        # If no API key, just do fallback analysis
        logging.warning("No GEMINI_API_KEY set; skipping real LLM-based analysis.")
    analysis_result = analyze_prompt_with_gemini(api_key or "", user_query)

    # 2) Save the analysis to the conversation in chat_history.json
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

    # 3) Perform retrieval for each query in the analysis and store results
    perform_retrieval_for_analysis(
        data_dir=data_dir,
        username=username,
        agent_name=agent_name,
        conversation_id=conversation_id,
        analysis_result=analysis_result
    )