from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
import os
import json
import shutil
from werkzeug.utils import secure_filename
import datetime

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
    return render_template('config.html')

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
                files.append({
                    "name": file_name,
                    "size": os.path.getsize(file_path),
                    "type": "",  # File type would require additional logic
                    "lastModified": os.path.getmtime(file_path)
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
    
    if os.path.exists(agent_dir):
        return jsonify({"error": "Agent with this name already exists"}), 400
    
    os.makedirs(agent_dir)
    os.makedirs(uploads_dir)
    
    # Create config file
    config = {
        "name": agent_name,
        "persona": agent_persona,
        "createdAt": datetime.datetime.now().isoformat(),
        "updatedAt": datetime.datetime.now().isoformat(),
        "createdBy": username
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
    
    return jsonify({"message": "Agent deleted successfully"})

@app.route('/api/agents/<agent_name>/upload', methods=['POST'])
def upload_files(agent_name):
    if 'username' not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    username = session['username']
    agent_dir = os.path.join(DATA_DIR, username, 'AGENTS', agent_name)
    uploads_dir = os.path.join(agent_dir, 'uploads')
    
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
        
        uploaded_files.append({
            "name": filename,
            "size": os.path.getsize(file_path),
            "type": file.content_type,
            "lastModified": os.path.getmtime(file_path)
        })
    
    response = {
        "message": "Files uploaded successfully",
        "files": uploaded_files
    }
    
    if rejected_files:
        response["rejected_files"] = rejected_files
        response["rejection_reason"] = "Only PDF files are supported"
    
    return jsonify(response)

@app.route('/api/agents/<agent_name>/files/<filename>', methods=['DELETE'])
def delete_file(agent_name, filename):
    if 'username' not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    username = session['username']
    file_path = os.path.join(DATA_DIR, username, 'AGENTS', agent_name, 'uploads', secure_filename(filename))
    
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    
    os.remove(file_path)
    
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