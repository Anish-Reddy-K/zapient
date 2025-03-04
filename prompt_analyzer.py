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
    try:
        import google.generativeai as genai
    except ImportError:
        logging.error("Gemini python package (google-generativeai) is not installed.")
        return {
            "original_query": user_query,
            "sub_queries": [user_query],
            "keywords": []
        }

    # Configure Gemini
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

        # Attempt to parse JSON directly
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
        # Fallback structure on error
        return {
            "original_query": user_query,
            "sub_queries": [user_query],
            "keywords": []
        }


def analyze_prompt_background(
    api_key: Optional[str],
    data_dir: str,
    username: str,
    agent_name: str,
    conversation_id: str,
    user_query: str
):
    """
    Runs the analyze_prompt_with_gemini function in the background,
    then attaches the results to the appropriate chat_history.json.
    """
    if not api_key:
        # No API key => skip
        return

    # 1) Do the analysis
    analysis_result = analyze_prompt_with_gemini(api_key, user_query)
    # Example structure of analysis_result:
    # {
    #   "original_query": "...",
    #   "sub_queries": [...],
    #   "keywords": [...]
    # }

    # 2) Save the results in chat_history.json
    chat_file = os.path.join(data_dir, username, 'AGENTS', agent_name, 'chat_history.json')
    if not os.path.exists(chat_file):
        logging.warning("Chat history file not found, cannot store analysis.")
        return

    with open(chat_file, 'r') as f:
        chat_data = json.load(f)

    # Find the correct conversation
    conversations = chat_data.get("conversations", [])
    conversation = next((c for c in conversations if c["conversation_id"] == conversation_id), None)
    if not conversation:
        logging.warning(f"Conversation {conversation_id} not found, cannot store analysis.")
        return

    # Store analysis in a dedicated "analysis" section
    if "analysis" not in conversation:
        conversation["analysis"] = []
    conversation["analysis"].append(analysis_result)

    # Write back out
    chat_data["conversations"] = conversations
    with open(chat_file, 'w') as f:
        json.dump(chat_data, f, indent=2)