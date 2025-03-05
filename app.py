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

# Import the file processor module
from file_processor import process_agent_files

# Import our prompt analyzer and retrieval logic
from prompt_analyzer import analyze_prompt_with_gemini, perform_retrieval_for_analysis
from retrieval_engine import save_retrieval_results

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
    each with a conversation_id and a messages array, plus optional 'analysis' array if present.
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
# NEW: Send Message Flow
########################

@app.route('/api/agents/<agent_name>/send-message', methods=['POST'])
def send_message(agent_name):
    """
    Handles the user message:
      1) Append user message to chat_history
      2) Analyze prompt (splitting, keywords) => store analysis in chat_history
      3) Perform retrieval => store in retrieval_results.json
      4) Build final answer with citations from retrieval_results
      5) Append answer to chat_history
      6) Return answer + citations
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
        "content": user_message,
        "timestamp": datetime.datetime.now().isoformat()
    }
    conversation["messages"].append(user_msg_obj)

    # 3) Analyze prompt (Gemini or fallback)
    api_key = os.environ.get('GEMINI_API_KEY')
    analysis_result = analyze_prompt_with_gemini(api_key or "", user_message)

    # Store analysis in conversation["analysis"]
    if "analysis" not in conversation:
        conversation["analysis"] = []
    conversation["analysis"].append(analysis_result)

    # Save chat_history so far
    chat_history["conversations"] = conversations
    with open(chat_file, 'w') as f:
        json.dump(chat_history, f, indent=2)

    # 4) Perform retrieval with sub-queries and original query
    perform_retrieval_for_analysis(
        data_dir=DATA_DIR,
        username=username,
        agent_name=agent_name,
        conversation_id=conversation_id,
        analysis_result=analysis_result
    )

    # 5) Build final answer using the retrieval results
    final_answer, final_citations = build_final_answer_with_citations(
        api_key=api_key or "",
        analysis=analysis_result,
        username=username,
        agent_name=agent_name,
        conversation_id=conversation_id
    )

    # 6) Append AI's answer to conversation
    # NOTE: We store citations in chat_history so the UI can re-load them on refresh.
    assistant_msg_obj = {
        "role": "assistant",
        "content": final_answer,
        "citations": final_citations,
        "timestamp": datetime.datetime.now().isoformat()
    }
    conversation["messages"].append(assistant_msg_obj)

    # Save entire chat again
    chat_history["conversations"] = conversations
    with open(chat_file, 'w') as f:
        json.dump(chat_history, f, indent=2)

    return jsonify({
        "conversation_id": conversation_id,
        "message": assistant_msg_obj
    })


########################
# HELPER: Build final LLM answer
########################

def build_final_answer_with_citations(api_key, analysis, username, agent_name, conversation_id):
    """
    1) Load retrieval chunks from retrieval_results.json for all sub-queries and original_query
    2) Merge them, deduplicate
    3) Pass them to LLM as context
    4) Return the answer, plus a structured list of numbered citations
    """
    # -- Load retrieval results
    agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
    retrieval_file = os.path.join(agent_dir, 'retrieval_results.json')
    if not os.path.exists(retrieval_file):
        # No retrieval
        return ("I have no relevant documents to reference.", [])

    with open(retrieval_file, 'r', encoding='utf-8') as f:
        retrieval_data = json.load(f)

    conv_dict = retrieval_data.get(conversation_id, {})
    if not conv_dict:
        # No retrieval results for this conversation
        return ("I couldn't find any relevant info in the documents.", [])

    original_q = analysis.get("original_query", "").strip()
    sub_qs = analysis.get("sub_queries", [])

    # Collect chunk sets
    all_text_chunks = []
    for q in [original_q] + sub_qs:
        q_data = conv_dict.get(q.strip())
        if not q_data:
            continue
        semantic_chunks = q_data.get("semantic_chunks", [])
        keyword_chunks = q_data.get("keyword_chunks", [])
        combined = semantic_chunks + keyword_chunks
        for ch in combined:
            all_text_chunks.append((ch["doc_filename"], ch["page_number"], ch["text"]))

    # Deduplicate
    seen = set()
    unique_chunks = []
    for item in all_text_chunks:
        if item not in seen:
            seen.add(item)
            unique_chunks.append(item)

    if not unique_chunks:
        return ("I couldn't find relevant info from the docs.", [])

    # Build a context for the LLM, and also build final_citations for the UI
    context_lines = []
    final_citations = []
    for i, (doc_file, page_num, text) in enumerate(unique_chunks, start=1):
        snippet = text.strip().replace('\n', ' ')
        snippet = snippet[:400]
        context_lines.append(f"Reference [{i}]: File: {doc_file}, Page: {page_num}\nExcerpt: {snippet}")
        final_citations.append({
            "id": i,
            "file": doc_file,
            "page": page_num,
            "text": snippet[:100]
        })

    context_text = "\n\n".join(context_lines)

    answer_text = call_llm_with_numbered_citations(
        api_key=api_key,
        user_query=original_q,
        context_text=context_text
    )

    return (answer_text, final_citations)


def call_llm_with_numbered_citations(api_key, user_query, context_text):
    """
    We supply the context from retrieval, and ask the LLM to:
      - Provide citations in ascending order as [^1], [^2], etc.
      - Insert blank lines to separate paragraphs or bullet points.
      - If no relevant info is found, say so.

    We also instruct it not to reuse chunk numbering, but to always label them
    in the order used in the final answer (1, 2, 3...).
    """
    system_prompt = """You are a retrieval-augmented AI assistant. You have references enumerated as [1], [2], etc., each mapping to a distinct file/page excerpt.

IMPORTANT REQUIREMENTS:
1) Cite references strictly in ascending numerical order, using the format [^1], [^2], [^3], etc.
2) Each reference label in the text must match exactly with the references you use.
3) Separate paragraphs with blank lines.
4) Use bullet points and headings as appropriate.
5) If no relevant info is in the context, say so.

---"""

    full_prompt = (
        f"{system_prompt}\n"
        f"References:\n{context_text}\n\n"
        f"User Question: {user_query}\n\n"
        "Please provide your best answer, following all the requirements above."
    )

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
            response = chat.send_message(full_prompt)
            return response.text.strip()
        except Exception as e:
            logging.error(f"Gemini final LLM call error: {str(e)}")
            return fallback_llm_answer(user_query, context_text)
    else:
        return fallback_llm_answer(user_query, context_text)


def fallback_llm_answer(user_query, context_text):
    """
    Simple fallback if Gemini isn't available. 
    We'll just show the context and disclaim.
    """
    if not context_text.strip():
        return "I'm sorry, I couldn't find any relevant info in the docs."
    return (
        "Fallback Answer (No Gemini API)\n\n"
        "Based on these sources:\n"
        f"{context_text[:1000]}\n\n"
        "I would guess the answer is: <your own summary here>\n"
        "(*This is a fallback dummy answer*)"
    )


if __name__ == '__main__':
    app.run(debug=True)