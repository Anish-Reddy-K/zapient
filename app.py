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

# Dictionary to track file processing status
file_processing_status = {}

# Initialize file processing status from existing data
def initialize_file_processing_status():
    """Initialize file processing status for all existing files across all agents"""
    if not os.path.exists(DATA_DIR):
        return
        
    for username_dir in os.listdir(DATA_DIR):
        user_dir = os.path.join(DATA_DIR, username_dir)
        if not os.path.isdir(user_dir):
            continue
            
        agents_dir = os.path.join(user_dir, 'AGENTS')
        if not os.path.exists(agents_dir):
            continue
            
        for agent_name in os.listdir(agents_dir):
            agent_dir = os.path.join(agents_dir, agent_name)
            if not os.path.isdir(agent_dir):
                continue
                
            # Check if agent config exists
            config_file = os.path.join(agent_dir, 'config.json')
            if not os.path.exists(config_file):
                continue
                
            # Load agent config
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
            except:
                continue
                
            # Get uploads directory
            uploads_dir = os.path.join(agent_dir, 'uploads')
            processed_dir = os.path.join(agent_dir, 'processed')
            
            if not os.path.exists(uploads_dir):
                continue
                
            # Check each file in uploads
            for filename in os.listdir(uploads_dir):
                if not os.path.isfile(os.path.join(uploads_dir, filename)):
                    continue
                    
                # Generate status key
                status_key = f"{username_dir}_{agent_name}_{filename}"
                
                # Check if file is processed
                processed_file = os.path.join(processed_dir, f"{Path(filename).stem}.json")
                if os.path.exists(processed_file):
                    # File is successfully processed
                    file_processing_status[status_key] = {
                        'status': 'success',
                        'message': 'Processing completed successfully'
                    }
                else:
                    # Check if agent has processing completed flag
                    if config.get('processing_complete', False):
                        if not config.get('files_processed', False):
                            # Processing completed with errors
                            file_processing_status[status_key] = {
                                'status': 'error',
                                'message': 'Processing failed'
                            }
                        else:
                            # This is a new file waiting to be processed
                            file_processing_status[status_key] = {
                                'status': 'pending',
                                'message': 'Waiting to be processed'
                            }
                    else:
                        # Agent is still processing
                        file_processing_status[status_key] = {
                            'status': 'processing',
                            'message': 'Processing in progress'
                        }

# Initialize file processing status on startup
initialize_file_processing_status()

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
    
    # Get the list of files
    uploads_dir = os.path.join(agent_dir, 'uploads')
    files = []
    
    if os.path.exists(uploads_dir):
        for file_name in os.listdir(uploads_dir):
            file_path = os.path.join(uploads_dir, file_name)
            if os.path.isfile(file_path):
                # Check processing status for this file
                status_key = f"{username}_{agent_name}_{file_name}"
                processing_status = file_processing_status.get(status_key, {
                    'status': 'unknown',
                    'message': 'Status unknown'
                })
                
                files.append({
                    "name": file_name,
                    "size": os.path.getsize(file_path),
                    "type": "application/pdf" if file_name.lower().endswith('.pdf') else "",
                    "lastModified": os.path.getmtime(file_path),
                    "processing_status": processing_status.get('status', 'unknown')
                })
    
    config['files'] = files
    
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
    
    # Clean up processing status entries for this agent
    keys_to_remove = []
    for key in file_processing_status:
        if key.startswith(f"{username}_{agent_name}_"):
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        file_processing_status.pop(key, None)
    
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
        
        # Initialize processing status
        status_key = f"{username}_{agent_name}_{filename}"
        file_processing_status[status_key] = {
            'status': 'pending',
            'message': 'File uploaded, awaiting processing'
        }
        
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
        config['processing_status'] = 'in_progress'
        
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
            args=(username, agent_name, agent_dir, file_names, file_processing_status, config_file, api_key)
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
    
    # Get status for specific files
    file_status = {}
    for key, status in file_processing_status.items():
        if key.startswith(f"{username}_{agent_name}_"):
            filename = key.split('_', 2)[2]
            file_status[filename] = status
    
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
    
    # Remove from status tracking
    status_key = f"{username}_{agent_name}_{filename}"
    if status_key in file_processing_status:
        del file_processing_status[status_key]
    
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