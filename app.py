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
import datetime
import random

# Import the file processor module
from file_processor import process_agent_files

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key_change_this_in_production'  # Change this in production

# Base directory for data storage
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

# Create data directory if it doesn't exist
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Valid users for demo purposes (in a real app, you'd use a database)
VALID_USERS = [
    {"username": "admin", "password": "admin"},
    {"username": "test", "password": "test"}
]

# File.json management functions
def create_files_json(username, agent_name):
    """Create an initial empty files.json for an agent"""
    agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
    files_json_path = os.path.join(agent_dir, 'files.json')
    
    # Create initial empty files.json
    files_data = {
        "files": []
    }
    
    with open(files_json_path, 'w') as f:
        json.dump(files_data, f, indent=2)
    
    return files_data

def get_files_json(username, agent_name):
    """Get the content of files.json for an agent, create if not exists"""
    agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
    files_json_path = os.path.join(agent_dir, 'files.json')
    
    if not os.path.exists(files_json_path):
        return create_files_json(username, agent_name)
    
    try:
        with open(files_json_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        # If file is corrupted, create a new one
        return create_files_json(username, agent_name)

def update_file_status(username, agent_name, filename, status, message=None):
    """Update the status of a file in files.json"""
    files_data = get_files_json(username, agent_name)
    
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
        # If file not found, log a warning
        logging.warning(f"File {filename} not found in files.json for agent {agent_name}")
    
    # Save the updated data
    agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
    files_json_path = os.path.join(agent_dir, 'files.json')
    
    with open(files_json_path, 'w') as f:
        json.dump(files_data, f, indent=2)
    
    return files_data

def add_file_to_json(username, agent_name, file_info):
    """Add a file to files.json or update if exists"""
    files_data = get_files_json(username, agent_name)
    
    # Check if file already exists
    for file in files_data['files']:
        if file['name'] == file_info['name']:
            # Update existing file
            file.update(file_info)
            break
    else:
        # File doesn't exist, add it
        files_data['files'].append(file_info)
    
    # Save the updated data
    agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
    files_json_path = os.path.join(agent_dir, 'files.json')
    
    with open(files_json_path, 'w') as f:
        json.dump(files_data, f, indent=2)
    
    return files_data

def remove_file_from_json(username, agent_name, filename):
    """Remove a file from files.json"""
    files_data = get_files_json(username, agent_name)
    
    # Remove the file from the list
    files_data['files'] = [file for file in files_data['files'] if file['name'] != filename]
    
    # Save the updated data
    agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
    files_json_path = os.path.join(agent_dir, 'files.json')
    
    with open(files_json_path, 'w') as f:
        json.dump(files_data, f, indent=2)
    
    return files_data

# Routes
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

        # Check credentials
        user = next((user for user in VALID_USERS if user['username'] == username and user['password'] == password), None)

        if user:
            session['username'] = username

            # Create user directory if it doesn't exist
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

    # Get agent name from query parameter if coming back from creating an agent
    agent_name = request.args.get('agent', '')

    return render_template('config.html', agent_name=agent_name)

@app.route('/manage/<agent_name>')
def manage(agent_name):
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('manage.html', agent_name=agent_name)

# API routes
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

    # Get files data from files.json
    files_data = get_files_json(username, agent_name)
    
    # If no files in files.json, check uploads directory
    if not files_data['files']:
        uploads_dir = os.path.join(agent_dir, 'uploads')
        if os.path.exists(uploads_dir):
            for file_name in os.listdir(uploads_dir):
                file_path = os.path.join(uploads_dir, file_name)
                if os.path.isfile(file_path):
                    # Check if file is processed
                    processed_file = os.path.join(agent_dir, 'processed', f"{Path(file_name).stem}.json")
                    processed = os.path.exists(processed_file)
                    
                    # Add file to files.json
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
        
        # Reload files_data after potential updates
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
        agent_persona = data.get('persona')

        if not agent_name:
            return jsonify({"error": "Agent name is required"}), 400
        
        # Check if agent name contains invalid characters
        if not re.match(r'^[a-zA-Z0-9_\- ]+$', agent_name):
            return jsonify({"error": "Agent name contains invalid characters. Use only letters, numbers, spaces, hyphens and underscores."}), 400

        # Create agent directory
        agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
        uploads_dir = os.path.join(agent_dir, 'uploads')
        processed_dir = os.path.join(agent_dir, 'processed')

        if os.path.exists(agent_dir):
            return jsonify({"error": "Agent with this name already exists"}), 400

        # Create directories with error handling
        try:
            os.makedirs(agent_dir, exist_ok=True)
            os.makedirs(uploads_dir, exist_ok=True)
            os.makedirs(processed_dir, exist_ok=True)
        except OSError as e:
            logging.error(f"Error creating directories for agent {agent_name}: {str(e)}")
            return jsonify({"error": f"Failed to create agent directories: {str(e)}"}), 500

        # Create config file
        config = {
            "name": agent_name,
            "persona": agent_persona if agent_persona else "",
            "createdAt": datetime.datetime.now().isoformat(),
            "updatedAt": datetime.datetime.now().isoformat(),
            "createdBy": username,
            "files_processed": False,
            "processing_complete": False
        }

        try:
            with open(os.path.join(agent_dir, 'config.json'), 'w') as f:
                json.dump(config, f)
        except IOError as e:
            logging.error(f"Error creating config file for agent {agent_name}: {str(e)}")
            # Clean up the created directories
            shutil.rmtree(agent_dir, ignore_errors=True)
            return jsonify({"error": f"Failed to create agent configuration: {str(e)}"}), 500

        # Create files.json
        try:
            create_files_json(username, agent_name)
        except Exception as e:
            logging.error(f"Error creating files.json for agent {agent_name}: {str(e)}")
            # Clean up the created directories
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

    # Read existing config
    with open(config_file, 'r') as f:
        config = json.load(f)

    # Update fields
    if 'name' in data and data['name'] != agent_name:
        # Rename agent directory if name changes
        new_agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', data['name'])
        os.rename(agent_dir, new_agent_dir)
        agent_dir = new_agent_dir
        config_file = os.path.join(agent_dir, 'config.json')

    config['name'] = data.get('name', config['name'])
    config['persona'] = data.get('persona', config['persona'])
    config['updatedAt'] = datetime.datetime.now().isoformat()

    # Write updated config
    with open(config_file, 'w') as f:
        json.dump(config, f)

    return jsonify({"message": "Agent updated successfully", "agent": config})

@app.route('/api/agents/<agent_name>', methods=['DELETE'])
def delete_agent(agent_name):
    if 'username' not in session:
        return jsonify({"error": "Not authenticated"}), 401

    username = session['username']
    agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)

    if not os.path.exists(agent_dir):
        return jsonify({"error": "Agent not found"}), 404

    # Delete agent directory and all contents
    shutil.rmtree(agent_dir)

    return jsonify({"message": "Agent deleted successfully"})

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

    # Define allowed file extensions
    ALLOWED_EXTENSIONS = {'pdf'}

    # Function to check if file extension is allowed
    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    uploaded_files = []
    rejected_files = []

    for file in request.files.getlist('files'):
        filename = secure_filename(file.filename)

        # Check if file extension is allowed
        if not allowed_file(filename):
            rejected_files.append(filename)
            continue

        file_path = os.path.join(uploads_dir, filename)
        file.save(file_path)

        # Add file to files.json
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

        uploaded_files.append({
            "name": filename,
            "size": os.path.getsize(file_path),
            "type": file.content_type,
            "lastModified": os.path.getmtime(file_path),
            "processing_status": "pending"
        })

    # Start processing files in background if files were uploaded
    if uploaded_files:
        # Update agent config
        with open(config_file, 'r') as f:
            config = json.load(f)

        config['files_processed'] = False
        config['processing_complete'] = False # Reset processing complete when new files are uploaded

        with open(config_file, 'w') as f:
            json.dump(config, f)

        # Always get API key for advanced processing
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            logging.warning("GEMINI_API_KEY not found in environment variables. Advanced processing will be limited.")

        # Start background thread for processing
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

    # Read config to get processing status
    with open(config_file, 'r') as f:
        config = json.load(f)

    # Get file status from files.json
    files_data = get_files_json(username, agent_name)
    
    # Convert to the expected format for the frontend
    file_status = {}
    for file in files_data['files']:
        file_status[file['name']] = {
            'status': file['processing_status'],
            'message': file['error_message'] if 'error_message' in file and file['error_message'] else ''
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

    # Also remove processed file
    processed_path = os.path.join(DATA_DIR, username, 'AGENTS', agent_name, 'processed', f"{Path(filename).stem}.json")

    if os.path.exists(processed_path):
        os.remove(processed_path)

    # Remove from files.json
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

    username = session['username']

    return jsonify({
        "username": username
    })

###### CHAT

@app.route('/chat/<agent_name>')
def chat(agent_name):
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html', agent_name=agent_name)

@app.route('/api/agents/<agent_name>/chat-history', methods=['GET'])
def get_chat_history(agent_name):
    if 'username' not in session:
        return jsonify({"error": "Not authenticated"}), 401

    username = session['username']
    chat_file = os.path.join(DATA_DIR, username, 'AGENTS', agent_name, 'chat_history.json')
    
    # Create default chat history if doesn't exist
    if not os.path.exists(chat_file):
        default_history = {
            "conversations": []
        }
        os.makedirs(os.path.dirname(chat_file), exist_ok=True)
        with open(chat_file, 'w') as f:
            json.dump(default_history, f, indent=2)
        return jsonify(default_history)
    
    try:
        with open(chat_file, 'r') as f:
            chat_history = json.load(f)
            return jsonify(chat_history)
    except json.JSONDecodeError:
        # If file is corrupted, create a new one
        default_history = {
            "conversations": []
        }
        with open(chat_file, 'w') as f:
            json.dump(default_history, f, indent=2)
        return jsonify(default_history)

@app.route('/api/agents/<agent_name>/send-message', methods=['POST'])
def send_message(agent_name):
    if 'username' not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        username = session['username']
        agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
        chat_file = os.path.join(agent_dir, 'chat_history.json')
        
        # Create agent dir if it doesn't exist
        if not os.path.exists(agent_dir):
            return jsonify({"error": "Agent not found"}), 404
        
        # Process the user message
        data = request.json
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
            
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({"error": "Message cannot be empty"}), 400
        
        # Create a conversation ID if starting a new conversation
        conversation_id = data.get('conversation_id')
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
        
        # Get existing chat history or create new
        if os.path.exists(chat_file):
            try:
                with open(chat_file, 'r') as f:
                    chat_history = json.load(f)
            except json.JSONDecodeError:
                chat_history = {"conversations": []}
        else:
            chat_history = {"conversations": []}
        
        # Find the conversation or create new one
        conversation = None
        for conv in chat_history["conversations"]:
            if conv["id"] == conversation_id:
                conversation = conv
                break
        
        if not conversation:
            conversation = {
                "id": conversation_id,
                "title": f"Conversation {len(chat_history['conversations']) + 1}",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "messages": []
            }
            chat_history["conversations"].append(conversation)
        else:
            conversation["updated_at"] = datetime.now().isoformat()
        
        # Add user message
        user_message_obj = {
            "id": str(uuid.uuid4()),
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat()
        }
        conversation["messages"].append(user_message_obj)
        
        # Generate fake AI response with citations for now
        # This will be replaced with actual LLM call later
        ai_response = generate_ai_response(username, agent_name, user_message)
        
        ai_message_obj = {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": ai_response["message"],
            "citations": ai_response["citations"],
            "timestamp": datetime.now().isoformat()
        }
        conversation["messages"].append(ai_message_obj)
        
        # Save updated chat history
        try:
            os.makedirs(os.path.dirname(chat_file), exist_ok=True)
            with open(chat_file, 'w') as f:
                json.dump(chat_history, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving chat history: {str(e)}")
            return jsonify({"error": f"Failed to save chat history: {str(e)}"}), 500
        
        return jsonify({
            "conversation_id": conversation_id,
            "message": ai_message_obj
        })
    
    except Exception as e:
        logging.error(f"Unexpected error in send_message: {str(e)}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/agents/<agent_name>/clear-chat', methods=['POST'])
def clear_chat_history(agent_name):
    if 'username' not in session:
        return jsonify({"error": "Not authenticated"}), 401

    username = session['username']
    chat_file = os.path.join(DATA_DIR, username, 'AGENTS', agent_name, 'chat_history.json')
    
    try:
        default_history = {"conversations": []}
        with open(chat_file, 'w') as f:
            json.dump(default_history, f, indent=2)
        return jsonify({"message": "Chat history cleared"})
    except Exception as e:
        logging.error(f"Error clearing chat history: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
def generate_ai_response(username, agent_name, user_message):
    """Generate a fake AI response with citations for now"""
    agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
    uploads_dir = os.path.join(agent_dir, 'uploads')
    
    # Get list of uploaded files
    files = []
    if os.path.exists(uploads_dir):
        files = [f for f in os.listdir(uploads_dir) if f.lower().endswith('.pdf')]
    
    # Default response if no files
    if not files:
        return {
            "message": "I don't have any documents to reference yet. Please upload some PDF files to help me provide better answers.",
            "citations": []
        }
    
    # Generate a response based on the query
    # Later this will be replaced with actual LLM integration
    
    # Sample responses with citation patterns for different query types
    responses = [
        {
            "message": f"Based on the documentation I've analyzed, I can provide some information on that topic. According to [1], the recommended approach is to follow standard procedures. Additionally, [2] mentions specific guidelines that should be considered.",
            "keywords": ["information", "documentation", "recommend", "guideline"]
        },
        {
            "message": f"The safety protocols detailed in [1] require regular inspections. This is further emphasized in [2] where compliance requirements are explained in detail.",
            "keywords": ["safety", "protocol", "comply", "requirement", "regulation"]
        },
        {
            "message": f"Looking at the technical specifications in [1], I can see that the system needs to operate within specific parameters. The maintenance schedule outlined in [2] suggests regular checks to ensure optimal performance.",
            "keywords": ["technical", "specification", "maintain", "performance", "system"]
        }
    ]
    
    # Select response based on keywords in user message
    user_message_lower = user_message.lower()
    best_response = responses[0]  # Default to first response
    best_match_count = 0
    
    for response in responses:
        match_count = sum(1 for keyword in response["keywords"] if keyword in user_message_lower)
        if match_count > best_match_count:
            best_match_count = match_count
            best_response = response
    
    # Generate random citations
    num_citations = min(len(files), 2)  # Up to 2 citations
    citations = []
    
    for i in range(num_citations):
        file = files[i % len(files)]
        page = random.randint(1, 20)  # Random page number
        citations.append({
            "id": i + 1,
            "file": file,
            "page": page,
            "text": f"Excerpt from {file}, page {page}"
        })
    
    # Replace citation markers with actual citation numbers
    message = best_response["message"]
    for i, citation in enumerate(citations):
        message = message.replace(f"[{i+1}]", f"[^{citation['id']}]")
    
    return {
        "message": message,
        "citations": citations
    }


if __name__ == '__main__':
    app.run(debug=True)