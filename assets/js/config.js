/**
 * Configuration Module
 * Handles the configuration and creation of AI agents
 */

// Immediately invoked function expression (IIFE) to avoid polluting the global namespace
(function() {
    // DOM Elements
    const agentConfigForm = document.getElementById('agentConfigForm');
    const fileDropzone = document.getElementById('fileDropzone');
    const fileInput = document.getElementById('fileInput');
    const fileList = document.getElementById('fileList');
    const agentNameInput = document.getElementById('agentName');
    const agentPersonaInput = document.getElementById('agentPersona');
    const submitButton = document.querySelector('.primary-btn');
    
    // Current agent being edited (if any)
    let currentAgentId = null;
    
    // Files array to store uploaded files
    let uploadedFiles = [];
    
    /**
     * Initialize the configuration page
     */
    function initConfig() {
        // Check if we're editing an existing agent
        checkForExistingAgent();
        
        setupFileUpload();
        setupFormSubmission();
    }
    
    /**
     * Check if we're editing an existing agent
     */
    function checkForExistingAgent() {
        // Get the agent ID from the URL query parameters
        const urlParams = new URLSearchParams(window.location.search);
        const agentId = urlParams.get('agent');
        
        if (agentId) {
            // We're editing an existing agent
            currentAgentId = agentId;
            loadAgentData(agentId);
            
            // Update the title and button text
            document.querySelector('.config-title').textContent = 'Manage Your AI Agent';
            document.querySelector('.config-subtitle').textContent = 'Update your AI agent settings and knowledge sources';
            submitButton.textContent = 'Update Agent';
        }
    }
    
    /**
     * Load existing agent data
     * @param {string} agentId - The ID of the agent to load
     */
    function loadAgentData(agentId) {
        try {
            // Get agents from localStorage
            const agentsFolder = JSON.parse(localStorage.getItem('agentsFolder'));
            
            if (!agentsFolder || !agentsFolder.agents || !agentsFolder.agents[agentId]) {
                console.error('Agent not found:', agentId);
                return;
            }
            
            const agent = agentsFolder.agents[agentId];
            const config = JSON.parse(agent.configFile.content);
            
            // Fill in the form fields
            agentNameInput.value = config.name;
            agentPersonaInput.value = config.persona;
            
            // Load files
            agent.files.forEach(file => {
                addFileToUI(file);
                uploadedFiles.push(file);
            });
        } catch (error) {
            console.error('Error loading agent data:', error);
        }
    }
    
    /**
     * Set up the file upload functionality
     */
    function setupFileUpload() {
        // Click on dropzone to trigger file input
        fileDropzone.addEventListener('click', function() {
            fileInput.click();
        });
        
        // Handle file selection through the input
        fileInput.addEventListener('change', function(e) {
            handleFiles(e.target.files);
        });
        
        // Handle drag and drop events
        fileDropzone.addEventListener('dragover', function(e) {
            e.preventDefault();
            e.stopPropagation();
            fileDropzone.style.borderColor = 'var(--color-accent)';
        });
        
        fileDropzone.addEventListener('dragleave', function(e) {
            e.preventDefault();
            e.stopPropagation();
            fileDropzone.style.borderColor = 'var(--color-supporting)';
        });
        
        fileDropzone.addEventListener('drop', function(e) {
            e.preventDefault();
            e.stopPropagation();
            fileDropzone.style.borderColor = 'var(--color-supporting)';
            
            if (e.dataTransfer.files.length > 0) {
                handleFiles(e.dataTransfer.files);
            }
        });
    }
    
    /**
     * Handle the files that were selected or dropped
     * @param {FileList} files - The files to handle
     */
    function handleFiles(files) {
        const filesArray = Array.from(files);
        
        filesArray.forEach(file => {
            // Check if file is already in the list
            const isDuplicate = uploadedFiles.some(f => f.name === file.name && f.size === file.size);
            
            if (!isDuplicate) {
                uploadedFiles.push(file);
                addFileToUI(file);
            }
        });
    }
    
    /**
     * Add a file to the UI list
     * @param {File} file - The file to add to the UI
     */
    function addFileToUI(file) {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        
        // Determine icon based on file type
        let iconClass = 'fa-file';
        if (file.type && file.type.includes('image')) {
            iconClass = 'fa-file-image';
        } else if (file.type && file.type.includes('pdf')) {
            iconClass = 'fa-file-pdf';
        } else if (file.type && file.type.includes('word') || (file.name && (file.name.endsWith('.doc') || file.name.endsWith('.docx')))) {
            iconClass = 'fa-file-word';
        } else if (file.type && file.type.includes('excel') || (file.name && (file.name.endsWith('.xls') || file.name.endsWith('.xlsx')))) {
            iconClass = 'fa-file-excel';
        } else if (file.type && file.type.includes('text')) {
            iconClass = 'fa-file-alt';
        }
        
        fileItem.innerHTML = `
            <i class="fas ${iconClass} file-icon"></i>
            <span class="file-name">${file.name}</span>
            <i class="fas fa-times file-remove" data-filename="${file.name}"></i>
        `;
        
        fileList.appendChild(fileItem);
        
        // Add event listener to remove button
        const removeBtn = fileItem.querySelector('.file-remove');
        removeBtn.addEventListener('click', function() {
            const fileName = this.getAttribute('data-filename');
            removeFile(fileName);
            fileItem.remove();
        });
    }
    
    /**
     * Remove a file from the uploaded files array
     * @param {string} fileName - The name of the file to remove
     */
    function removeFile(fileName) {
        uploadedFiles = uploadedFiles.filter(file => file.name !== fileName);
    }
    
    /**
     * Set up the form submission
     */
    function setupFormSubmission() {
        agentConfigForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const agentName = agentNameInput.value;
            const agentPersona = agentPersonaInput.value;
            
            const agentData = {
                name: agentName,
                persona: agentPersona,
                files: uploadedFiles.map(file => ({
                    name: file.name,
                    size: file.size || 0,
                    type: file.type || '',
                    lastModified: file.lastModified || Date.now()
                }))
            };
            
            // Save or update agent data
            if (currentAgentId) {
                updateAgentData(currentAgentId, agentData);
            } else {
                saveAgentData(agentData);
            }
        });
    }
    
    /**
     * Save the agent data for a new agent
     * @param {Object} agentData - The agent data to save
     */
    function saveAgentData(agentData) {
        // In a real app with server-side code, we would save to the filesystem
        // For this client-side demo, we'll use localStorage but structure it as if we were saving to a folder
        try {
            // Generate a unique ID for the agent
            const agentId = 'agent_' + Date.now();
            
            // Create a structure that mimics file system organization
            const agentFolder = {
                id: agentId,
                configFile: {
                    name: 'config.json',
                    content: JSON.stringify({
                        id: agentId,
                        name: agentData.name,
                        persona: agentData.persona,
                        createdAt: new Date().toISOString(),
                        updatedAt: new Date().toISOString(),
                        createdBy: sessionStorage.getItem('currentUser') || 'Unknown User'
                    })
                },
                files: agentData.files
            };
            
            // Get existing agents folder structure or initialize
            const agentsFolder = JSON.parse(localStorage.getItem('agentsFolder')) || { agents: {} };
            
            // Add new agent folder
            agentsFolder.agents[agentId] = agentFolder;
            
            // Save back to localStorage
            localStorage.setItem('agentsFolder', JSON.stringify(agentsFolder));
            
            // Show success message and redirect
            alert(`AI Agent "${agentData.name}" created successfully!`);
            window.location.href = 'my-agents.html';
        } catch (error) {
            console.error('Error saving agent data:', error);
            alert('There was an error creating your AI Agent. Please try again.');
        }
    }
    
    /**
     * Update an existing agent
     * @param {string} agentId - The ID of the agent to update
     * @param {Object} agentData - The updated agent data
     */
    function updateAgentData(agentId, agentData) {
        try {
            // Get existing agents
            const agentsFolder = JSON.parse(localStorage.getItem('agentsFolder'));
            
            if (!agentsFolder || !agentsFolder.agents || !agentsFolder.agents[agentId]) {
                console.error('Agent not found:', agentId);
                alert('Agent not found. Creating a new one instead.');
                saveAgentData(agentData);
                return;
            }
            
            // Get the existing agent data to preserve original createdAt
            const existingAgent = agentsFolder.agents[agentId];
            const existingConfig = JSON.parse(existingAgent.configFile.content);
            
            // Update agent config
            agentsFolder.agents[agentId].configFile.content = JSON.stringify({
                id: agentId,
                name: agentData.name,
                persona: agentData.persona,
                createdAt: existingConfig.createdAt, // Keep original creation date
                updatedAt: new Date().toISOString(),
                createdBy: existingConfig.createdBy // Keep original creator
            });
            
            // Update files
            agentsFolder.agents[agentId].files = agentData.files;
            
            // Save back to localStorage
            localStorage.setItem('agentsFolder', JSON.stringify(agentsFolder));
            
            // Show success message and redirect
            alert(`AI Agent "${agentData.name}" updated successfully!`);
            window.location.href = 'my-agents.html';
        } catch (error) {
            console.error('Error updating agent data:', error);
            alert('There was an error updating your AI Agent. Please try again.');
        }
    }
    
    // Initialize the configuration page when DOM is loaded
    document.addEventListener('DOMContentLoaded', initConfig);
})();