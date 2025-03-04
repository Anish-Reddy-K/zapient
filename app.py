# app.py

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
import os
import json
import shutil
from werkzeug.utils import secure_filename
import datetime
import threading
import logging
from pathlib import Path
from dotenv import load_dotenv
import uuid
import re
import random

# Import the file processor module
from file_processor import process_agent_files

# NEW: We'll import prompt_analyzer if we want to reuse its Gemini logic
from prompt_analyzer import analyze_prompt_with_gemini

# NEW: We'll import our retrieval engine directly for synchronous retrieval
from retrieval_engine import RetrievalEngine

# Try to import Gemini for final LLM calls
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key_change_this_in_production'  # Change in production

# Base directory for data storage
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

# Create data directory if it doesn't exist
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Valid users for demo purposes (in a real app, you'd use a proper database)
VALID_USERS = [
    {"username": "admin", "password": "admin"},
    {"username": "test", "password": "test"}
]

########################
# files.json Management
########################

def create_files_json(username, agent_name):
    """Create an initial empty files.json for an agent"""
    agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
    files_json_path = os.path.join(agent_dir, 'files.json')
    
    files_data = {"files": []}
    
    with open(files_json_path, 'w') as f:
        json.dump(files_data, f, indent=2)
    
    return files_data

def get_files_json(username, agent_name):
    """Get (or create) files.json for an agent"""
    agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
    files_json_path = os.path.join(agent_dir, 'files.json')
    
    if not os.path.exists(files_json_path):
        return create_files_json(username, agent_name)
    
    try:
        with open(files_json_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return create_files_json(username, agent_name)

def update_file_status(username, agent_name, filename, status, message=None):
    """Update the status of a file in files.json"""
    files_data = get_files_json(username, agent_name)
    file_found = False
    
    for file in files_data['files']:
        if file['name'] == filename:
            file['processing_status'] = status
            file['error_message'] = message if message else None
            if status == 'success':
                file['processed'] = True
            file_found = True
            break
    
    if not file_found:
        logging.warning(f"File {filename} not found in files.json for agent {agent_name}")
    
    agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
    files_json_path = os.path.join(agent_dir, 'files.json')
    
    with open(files_json_path, 'w') as f:
        json.dump(files_data, f, indent=2)
    
    return files_data

def add_file_to_json(username, agent_name, file_info):
    """Add or update a file in files.json"""
    files_data = get_files_json(username, agent_name)
    for file in files_data['files']:
        if file['name'] == file_info['name']:
            file.update(file_info)
            break
    else:
        files_data['files'].append(file_info)
    
    agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
    files_json_path = os.path.join(agent_dir, 'files.json')
    
    with open(files_json_path, 'w') as f:
        json.dump(files_data, f, indent=2)
    
    return files_data

def remove_file_from_json(username, agent_name, filename):
    """Remove a file from files.json"""
    files_data = get_files_json(username, agent_name)
    files_data['files'] = [f for f in files_data['files'] if f['name'] != filename]
    
    agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
    files_json_path = os.path.join(agent_dir, 'files.json')
    
    with open(files_json_path, 'w') as f:
        json.dump(files_data, f, indent=2)
    
    return files_data

########################
# Authentication & Pages
########################

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = next((u for u in VALID_USERS if u['username'] == username and u['password'] == password), None)

        if user:
            session['username'] = username
            user_dir = os.path.join(DATA_DIR, username)
            agents_dir = os.path.join(user_dir, 'AGENTS')

            if not os.path.exists(user_dir):
                os.makedirs(user_dir)
            if not os.path.exists(agents_dir):
                os.makedirs(agents_dir)

            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error=True)

    return render_template('login.html', error=False)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/my-agents')
def my_agents():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('my-agents.html')

@app.route('/config')
def config():
    if 'username' not in session:
        return redirect(url_for('login'))
    agent_name = request.args.get('agent', '')
    return render_template('config.html', agent_name=agent_name)

@app.route('/manage/<agent_name>')
def manage(agent_name):
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('manage.html', agent_name=agent_name)

########################
# Agent CRUD / API
########################

@app.route('/api/agents', methods=['GET'])
def get_agents():
    if 'username' not in session:
        return jsonify({"error": "Not authenticated"}), 401

    username = session['username']
    agents_dir = os.path.join(DATA_DIR, username, 'AGENTS')
    if not os.path.exists(agents_dir):
        return jsonify({"agents": []})

    agents = []
    for agent_name in os.listdir(agents_dir):
        agent_dir = os.path.join(agents_dir, agent_name)
        config_file = os.path.join(agent_dir, 'config.json')

        if os.path.isdir(agent_dir) and os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
                agents.append(config)

    return jsonify({"agents": agents})

@app.route('/api/agents/<agent_name>', methods=['GET'])
def get_agent(agent_name):
    if 'username' not in session:
        return jsonify({"error": "Not authenticated"}), 401

    username = session['username']
    agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
    config_file = os.path.join(agent_dir, 'config.json')

    if not os.path.exists(config_file):
        return jsonify({"error": "Agent not found"}), 404

    with open(config_file, 'r') as f:
        config = json.load(f)

    # Ensure files.json is up to date
    files_data = get_files_json(username, agent_name)
    # If no files in files.json, attempt to detect existing uploads
    if not files_data['files']:
        uploads_dir = os.path.join(agent_dir, 'uploads')
        if os.path.exists(uploads_dir):
            for file_name in os.listdir(uploads_dir):
                file_path = os.path.join(uploads_dir, file_name)
                if os.path.isfile(file_path):
                    processed_file = os.path.join(agent_dir, 'processed', f"{Path(file_name).stem}.json")
                    processed = os.path.exists(processed_file)
                    file_info = {
                        "name": file_name,
                        "size": os.path.getsize(file_path),
                        "type": "application/pdf" if file_name.lower().endswith('.pdf') else "",
                        "lastModified": os.path.getmtime(file_path),
                        "processed": processed,
                        "processing_status": "success" if processed else "pending",
                        "error_message": None
                    }
                    add_file_to_json(username, agent_name, file_info)
        files_data = get_files_json(username, agent_name)

    config['files'] = files_data['files']
    return jsonify(config)

@app.route('/api/agents', methods=['POST'])
def create_agent():
    if 'username' not in session:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        data = request.json
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
            
        username = session['username']
        agent_name = data.get('name')
        agent_persona = data.get('persona', '')

        if not agent_name:
            return jsonify({"error": "Agent name is required"}), 400

        # Validate agent name
        if not re.match(r'^[a-zA-Z0-9_\- ]+$', agent_name):
            return jsonify({"error": "Agent name contains invalid characters. Use only letters, numbers, spaces, hyphens, and underscores."}), 400

        agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
        uploads_dir = os.path.join(agent_dir, 'uploads')
        processed_dir = os.path.join(agent_dir, 'processed')

        if os.path.exists(agent_dir):
            return jsonify({"error": "Agent with this name already exists"}), 400

        try:
            os.makedirs(agent_dir, exist_ok=True)
            os.makedirs(uploads_dir, exist_ok=True)
            os.makedirs(processed_dir, exist_ok=True)
        except OSError as e:
            logging.error(f"Error creating directories for agent {agent_name}: {str(e)}")
            return jsonify({"error": f"Failed to create agent directories: {str(e)}"}), 500

        config = {
            "name": agent_name,
            "persona": agent_persona,
            "createdAt": datetime.datetime.now().isoformat(),
            "updatedAt": datetime.datetime.now().isoformat(),
            "createdBy": username,
            "files_processed": False,
            "processing_complete": False
        }

        try:
            with open(os.path.join(agent_dir, 'config.json'), 'w') as f:
                json.dump(config, f, indent=2)
        except IOError as e:
            logging.error(f"Error creating config file for agent {agent_name}: {str(e)}")
            shutil.rmtree(agent_dir, ignore_errors=True)
            return jsonify({"error": f"Failed to create agent configuration: {str(e)}"}), 500

        # Create empty files.json
        try:
            create_files_json(username, agent_name)
        except Exception as e:
            logging.error(f"Error creating files.json for agent {agent_name}: {str(e)}")
            shutil.rmtree(agent_dir, ignore_errors=True)
            return jsonify({"error": f"Failed to initialize agent files: {str(e)}"}), 500

        return jsonify({"message": "Agent created successfully", "agent": config})
    
    except Exception as e:
        logging.error(f"Unexpected error creating agent: {str(e)}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/agents/<agent_name>', methods=['PUT'])
def update_agent(agent_name):
    if 'username' not in session:
        return jsonify({"error": "Not authenticated"}), 401

    data = request.json
    username = session['username']

    agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
    config_file = os.path.join(agent_dir, 'config.json')

    if not os.path.exists(config_file):
        return jsonify({"error": "Agent not found"}), 404

    with open(config_file, 'r') as f:
        config = json.load(f)

    # If "name" changed, rename the folder
    if 'name' in data and data['name'] != agent_name:
        new_agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', data['name'])
        os.rename(agent_dir, new_agent_dir)
        agent_dir = new_agent_dir
        config_file = os.path.join(agent_dir, 'config.json')

    config['name'] = data.get('name', config['name'])
    config['persona'] = data.get('persona', config['persona'])
    config['updatedAt'] = datetime.datetime.now().isoformat()

    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

    return jsonify({"message": "Agent updated successfully", "agent": config})

@app.route('/api/agents/<agent_name>', methods=['DELETE'])
def delete_agent(agent_name):
    if 'username' not in session:
        return jsonify({"error": "Not authenticated"}), 401

    username = session['username']
    agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)

    if not os.path.exists(agent_dir):
        return jsonify({"error": "Agent not found"}), 404

    shutil.rmtree(agent_dir)
    return jsonify({"message": "Agent deleted successfully"})

########################
# Upload / Processing
########################

@app.route('/api/agents/<agent_name>/upload', methods=['POST'])
def upload_files(agent_name):
    if 'username' not in session:
        return jsonify({"error": "Not authenticated"}), 401

    username = session['username']
    agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
    uploads_dir = os.path.join(agent_dir, 'uploads')
    config_file = os.path.join(agent_dir, 'config.json')

    if not os.path.exists(agent_dir):
        return jsonify({"error": "Agent not found"}), 404

    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)

    ALLOWED_EXTENSIONS = {'pdf'}

    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    uploaded_files = []
    rejected_files = []

    for file in request.files.getlist('files'):
        filename = secure_filename(file.filename)
        if not allowed_file(filename):
            rejected_files.append(filename)
            continue

        file_path = os.path.join(uploads_dir, filename)
        file.save(file_path)

        file_info = {
            "name": filename,
            "size": os.path.getsize(file_path),
            "type": file.content_type,
            "lastModified": os.path.getmtime(file_path),
            "processed": False,
            "processing_status": "pending",
            "error_message": None
        }
        add_file_to_json(username, agent_name, file_info)
        uploaded_files.append(file_info)

    # If new files were uploaded, reset config states and process in background
    if uploaded_files:
        with open(config_file, 'r') as f:
            config = json.load(f)
        config['files_processed'] = False
        config['processing_complete'] = False

        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)

        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            logging.warning("GEMINI_API_KEY not found. Advanced processing may be limited.")

        file_names = [file['name'] for file in uploaded_files]
        processing_thread = threading.Thread(
            target=process_agent_files,
            args=(username, agent_name, agent_dir, file_names, config_file, api_key)
        )
        processing_thread.daemon = True
        processing_thread.start()

    response = {
        "message": "Files uploaded successfully",
        "files": uploaded_files
    }
    if rejected_files:
        response["rejected_files"] = rejected_files
        response["rejection_reason"] = "Only PDF files are supported"

    return jsonify(response)

@app.route('/api/agents/<agent_name>/processing-status', methods=['GET'])
def get_processing_status(agent_name):
    if 'username' not in session:
        return jsonify({"error": "Not authenticated"}), 401

    username = session['username']
    agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
    config_file = os.path.join(agent_dir, 'config.json')

    if not os.path.exists(config_file):
        return jsonify({"error": "Agent not found"}), 404

    with open(config_file, 'r') as f:
        config = json.load(f)

    files_data = get_files_json(username, agent_name)
    file_status = {}
    for file in files_data['files']:
        file_status[file['name']] = {
            'status': file['processing_status'],
            'message': file.get('error_message') or ''
        }

    return jsonify({
        "agent_name": agent_name,
        "processing_complete": config.get('processing_complete', False),
        "files_processed": config.get('files_processed', False),
        "file_status": file_status
    })

@app.route('/api/agents/<agent_name>/files/<filename>', methods=['DELETE'])
def delete_file(agent_name, filename):
    if 'username' not in session:
        return jsonify({"error": "Not authenticated"}), 401

    username = session['username']
    file_path = os.path.join(DATA_DIR, username, 'AGENTS', agent_name, 'uploads', secure_filename(filename))
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    os.remove(file_path)
    processed_path = os.path.join(
        DATA_DIR, username, 'AGENTS', agent_name, 'processed',
        f"{Path(filename).stem}.json"
    )
    if os.path.exists(processed_path):
        os.remove(processed_path)

    remove_file_from_json(username, agent_name, filename)
    return jsonify({"message": "File deleted successfully"})

@app.route('/api/agents/<agent_name>/files/<filename>')
def get_file(agent_name, filename):
    if 'username' not in session:
        return jsonify({"error": "Not authenticated"}), 401
    username = session['username']
    uploads_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name, 'uploads')
    return send_from_directory(uploads_dir, secure_filename(filename))

@app.route('/api/current-user', methods=['GET'])
def get_current_user():
    if 'username' not in session:
        return jsonify({"error": "Not authenticated"}), 401
    return jsonify({"username": session['username']})

########################
# Chat Routes
########################

@app.route('/chat/<agent_name>')
def chat(agent_name):
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html', agent_name=agent_name)

@app.route('/api/agents/<agent_name>/chat-history', methods=['GET'])
def get_chat_history(agent_name):
    """
    Returns the JSON object containing 'conversations': [...],
    each with a conversation_id and a messages array.
    """
    if 'username' not in session:
        return jsonify({"error": "Not authenticated"}), 401

    username = session['username']
    chat_file = os.path.join(DATA_DIR, username, 'AGENTS', agent_name, 'chat_history.json')

    if not os.path.exists(chat_file):
        default_history = {"conversations": []}
        os.makedirs(os.path.dirname(chat_file), exist_ok=True)
        with open(chat_file, 'w') as f:
            json.dump(default_history, f, indent=2)
        return jsonify(default_history)

    try:
        with open(chat_file, 'r') as f:
            return jsonify(json.load(f))
    except json.JSONDecodeError:
        default_history = {"conversations": []}
        with open(chat_file, 'w') as f:
            json.dump(default_history, f, indent=2)
        return jsonify(default_history)

@app.route('/api/agents/<agent_name>/send-message', methods=['POST'])
def send_message(agent_name):
    """
    Handles the user message, does prompt analysis + retrieval,
    calls the LLM for a final answer grounded in the chunks,
    then returns + saves everything to chat_history.json.
    """
    if 'username' not in session:
        return jsonify({"error": "Not authenticated"}), 401

    data = request.get_json()
    user_message = data.get('message', '').strip()
    conversation_id = data.get('conversation_id') or "default"
    username = session['username']

    # 1) Load or create local chat file for this agent
    agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
    chat_file = os.path.join(agent_dir, 'chat_history.json')
    if not os.path.exists(chat_file):
        os.makedirs(os.path.dirname(chat_file), exist_ok=True)
        with open(chat_file, 'w') as f:
            json.dump({"conversations": []}, f, indent=2)

    with open(chat_file, 'r') as f:
        chat_history = json.load(f)

    conversations = chat_history.get("conversations", [])
    conversation = next((c for c in conversations if c["conversation_id"] == conversation_id), None)
    if not conversation:
        conversation = {
            "conversation_id": conversation_id,
            "messages": []
        }
        conversations.append(conversation)

    # 2) Append user message to conversation
    user_msg_obj = {
        "role": "user",
        "content": user_message
    }
    conversation["messages"].append(user_msg_obj)

    # 3) Now generate the final AI answer with retrieval
    api_key = os.environ.get('GEMINI_API_KEY')

    final_answer, citations = generate_answer_with_retrieval(
        api_key=api_key,
        user_query=user_message,
        username=username,
        agent_name=agent_name
    )

    # 4) Append AI's answer to conversation
    assistant_msg_obj = {
        "role": "assistant",
        "content": final_answer,
        "citations": citations
    }
    conversation["messages"].append(assistant_msg_obj)

    # Save chat history
    chat_history["conversations"] = conversations
    with open(chat_file, 'w') as f:
        json.dump(chat_history, f, indent=2)

    return jsonify({
        "conversation_id": conversation_id,
        "message": assistant_msg_obj
    })

@app.route('/api/agents/<agent_name>/clear-chat', methods=['POST'])
def clear_chat_history(agent_name):
    """
    Overwrites the agent's chat_history.json with an empty 'conversations' list.
    """
    if 'username' not in session:
        return jsonify({"error": "Not authenticated"}), 401

    username = session['username']
    chat_file = os.path.join(DATA_DIR, username, 'AGENTS', agent_name, 'chat_history.json')

    try:
        default_history = {"conversations": []}
        os.makedirs(os.path.dirname(chat_file), exist_ok=True)
        with open(chat_file, 'w') as f:
            json.dump(default_history, f, indent=2)
        return jsonify({"message": "Chat history cleared"})
    except Exception as e:
        logging.error(f"Error clearing chat history: {str(e)}")
        return jsonify({"error": str(e)}), 500


########################
# NEW HELPER FUNCTION
########################

def generate_answer_with_retrieval(api_key, user_query, username, agent_name):
    """
    1) Analyze the user query for sub-queries (Gemini or fallback)
    2) Use retrieval engine to fetch top chunks
    3) Call LLM with those chunks as context
    4) If no chunks found, return a fallback message
    5) Return final markdown answer + a list of citations
    """

    # 1) Analyze prompt for subqueries/keywords (using prompt_analyzer logic)
    analysis_result = analyze_prompt_with_gemini(api_key or "", user_query)
    sub_queries = analysis_result.get("sub_queries", [])
    if not sub_queries:
        # fallback to just the original query
        sub_queries = [user_query]

    # 2) Build retrieval engine
    agent_processed_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name, 'processed')
    if not os.path.exists(agent_processed_dir):
        # no processed docs
        return ("I'm sorry, but I have no documents to reference yet.", [])

    engine = RetrievalEngine(agent_processed_dir)

    # Gather top chunks from each sub-query (semantic search)
    all_chunks = []
    for q in sub_queries:
        chunks = engine.semantic_search(q, top_k=5)
        all_chunks.extend(chunks)

    # Deduplicate (doc_filename+page_number+chunk_index)
    unique_map = {}
    for ch in all_chunks:
        key = (ch.doc_filename, ch.page_number, ch.chunk_index)
        unique_map[key] = ch
    top_chunks = list(unique_map.values())
    # Limit total chunks
    top_chunks = top_chunks[:5]

    if not top_chunks:
        # No relevant text found
        no_answer = (
            "I could not find any relevant information in the uploaded documents. "
            "Sorry about that."
        )
        return (no_answer, [])

    # 3) Construct context text + citations
    context_text = ""
    citations = []
    for i, chunk in enumerate(top_chunks, start=1):
        context_text += f"Source [{i}]: (Doc: {chunk.doc_filename}, page {chunk.page_number})\n{chunk.text}\n\n"
        # We'll store a simple snippet for citations
        snippet = chunk.text[:100].strip().replace('\n', ' ')
        citations.append({
            "id": i,
            "file": chunk.doc_filename,
            "page": chunk.page_number,
            "text": snippet
        })

    # 4) Generate final answer using Gemini or fallback
    answer_text = call_llm_for_final_answer(api_key, user_query, context_text)

    return (answer_text, citations)

def call_llm_for_final_answer(api_key, user_query, context_text):
    """
    Calls Gemini with an instruction to incorporate the chunk text as context,
    or does a fallback if Gemini isn't available. Returns markdown answer.
    The LLM is asked to produce citations as [^1], [^2], etc. if it uses the sources.
    If no relevant info is found, it should say so.
    """

    system_prompt = """You are a retrieval-augmented AI assistant. 
You have access to chunks of text from various documents. 
Use ONLY that provided text as factual context. 
If the user’s question cannot be answered from the documents, say you couldn't find the answer in the docs.

Rules:
1) Answer in valid Markdown.
2) Cite each source you use as [^1], [^2], etc. in the text body.
3) If no relevant info is found, say "I couldn't find the answer in the docs."
"""

    if HAS_GEMINI and api_key:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                generation_config={
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 1024,
                }
            )
            chat = model.start_chat(history=[])
            chat.send_message(system_prompt)
            # Combine user query + context
            full_prompt = (
                f"Context:\n{context_text}\n\n"
                f"User Question: {user_query}\n\n"
                "Please provide your best answer following the rules."
            )
            response = chat.send_message(full_prompt)
            return response.text.strip()
        except Exception as e:
            logging.error(f"Gemini final LLM call error: {str(e)}")
            return fallback_llm_answer(user_query, context_text)
    else:
        return fallback_llm_answer(user_query, context_text)


def fallback_llm_answer(user_query, context_text):
    """
    Simple fallback that always tries to mimic a short answer
    or says we couldn't find anything. Real apps might call another LLM or a local model.
    """
    if not context_text.strip():
        return "I couldn't find an answer in the docs."
    return (
        "Fallback Answer (No Gemini API):\n\n"
        "Based on the provided context, here are some possible points:\n\n"
        f"---\n{context_text[:300]}...\n\n"
        "Please note this is a fallback."
    )

########################
# Example AI function
########################
def generate_ai_response(username, agent_name, user_message):
    """
    Legacy example function. (Not used in new flow.)
    """
    agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
    uploads_dir = os.path.join(agent_dir, 'uploads')
    files = []
    if os.path.exists(uploads_dir):
        files = [f for f in os.listdir(uploads_dir) if f.lower().endswith('.pdf')]
    
    if not files:
        return {
            "message": "I don't have any documents to reference. Please upload PDF files!",
            "citations": []
        }

    # (Old code omitted; replaced by real approach now)
    return {
        "message": "Legacy fallback response.",
        "citations": []
    }

if __name__ == '__main__':
    app.run(debug=True)