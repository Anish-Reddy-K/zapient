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

    data = request.json
    username = session['username']

    agent_name = data.get('name')
    agent_persona = data.get('persona')

    if not agent_name:
        return jsonify({"error": "Agent name is required"}), 400

    # Create agent directory
    agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
    uploads_dir = os.path.join(agent_dir, 'uploads')
    processed_dir = os.path.join(agent_dir, 'processed')

    if os.path.exists(agent_dir):
        return jsonify({"error": "Agent with this name already exists"}), 400

    os.makedirs(agent_dir)
    os.makedirs(uploads_dir)
    os.makedirs(processed_dir, exist_ok=True)

    # Create config file
    config = {
        "name": agent_name,
        "persona": agent_persona,
        "createdAt": datetime.datetime.now().isoformat(),
        "updatedAt": datetime.datetime.now().isoformat(),
        "createdBy": username,
        "files_processed": False,
        "processing_complete": False
    }

    with open(os.path.join(agent_dir, 'config.json'), 'w') as f:
        json.dump(config, f)

    # Create files.json
    create_files_json(username, agent_name)

    return jsonify({"message": "Agent created successfully", "agent": config})

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

if __name__ == '__main__':
    app.run(debug=True)