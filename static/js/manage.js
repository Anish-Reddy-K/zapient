/**
 * Manage Module
 * Handles the management of existing AI agents
 */

// Immediately invoked function expression (IIFE) to avoid polluting the global namespace
(function() {
    // DOM Elements
    const agentManageForm = document.getElementById('agentManageForm');
    const fileDropzone = document.getElementById('fileDropzone');
    const fileInput = document.getElementById('fileInput');
    const fileList = document.getElementById('fileList');
    const agentNameInput = document.getElementById('agentName');
    const agentPersonaInput = document.getElementById('agentPersona');
    const deleteButton = document.getElementById('deleteAgentBtn');
    
    // Files array to store uploaded files
    let uploadedFiles = [];
    
    // Original agent name (for tracking name changes)
    let originalAgentName = '';
    
    /**
     * Initialize the manage page
     */
    function initManage() {
        // Get the agent name from the URL path
        const pathParts = window.location.pathname.split('/');
        originalAgentName = decodeURIComponent(pathParts[pathParts.length - 1]);
        
        // Load agent data
        loadAgentData(originalAgentName);
        
        setupFileUpload();
        setupFormSubmission();
        setupDeleteButton();
    }
    
    /**
     * Load agent data from the server
     * @param {string} agentName - The name of the agent to load
     */
    function loadAgentData(agentName) {
        fetch(`/api/agents/${agentName}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Agent not found');
                }
                return response.json();
            })
            .then(data => {
                // Populate form fields
                agentNameInput.value = data.name;
                agentPersonaInput.value = data.persona;
                
                // Clear file list first
                fileList.innerHTML = '';
                uploadedFiles = [];
                
                // Load files
                if (data.files && data.files.length > 0) {
                    data.files.forEach(file => {
                        uploadedFiles.push(file);
                        addFileToUI(file);
                    });
                }
            })
            .catch(error => {
                console.error('Error loading agent data:', error);
                alert('Failed to load agent data. Redirecting to My Agents page.');
                window.location.href = '/my-agents';
            });
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
            const isDuplicate = uploadedFiles.some(f => f.name === file.name);
            
            if (!isDuplicate) {
                uploadedFiles.push(file);
                addFileToUI(file);
            }
        });
    }
    
    /**
     * Add a file to the UI list
     * @param {File|Object} file - The file to add to the UI
     */
    function addFileToUI(file) {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        
        // Determine icon based on file type
        let iconClass = 'fa-file';
        const fileName = file.name;
        
        if (fileName.match(/\.(jpg|jpeg|png|gif|bmp)$/i)) {
            iconClass = 'fa-file-image';
        } else if (fileName.match(/\.(pdf)$/i)) {
            iconClass = 'fa-file-pdf';
        } else if (fileName.match(/\.(doc|docx)$/i)) {
            iconClass = 'fa-file-word';
        } else if (fileName.match(/\.(xls|xlsx|csv)$/i)) {
            iconClass = 'fa-file-excel';
        } else if (fileName.match(/\.(txt|md|rtf)$/i)) {
            iconClass = 'fa-file-alt';
        }
        
        fileItem.innerHTML = `
            <i class="fas ${iconClass} file-icon"></i>
            <span class="file-name">${fileName}</span>
            <i class="fas fa-times file-remove" data-filename="${fileName}"></i>
        `;
        
        fileList.appendChild(fileItem);
        
        // Add event listener to remove button
        const removeBtn = fileItem.querySelector('.file-remove');
        removeBtn.addEventListener('click', function() {
            const fileName = this.getAttribute('data-filename');
            
            // If this is an existing file, delete it from the server
            const existingFile = uploadedFiles.find(f => f.name === fileName && !(f instanceof File));
            
            if (existingFile) {
                // Delete the file from the server
                fetch(`/api/agents/${originalAgentName}/files/${fileName}`, {
                    method: 'DELETE'
                })
                .then(response => response.json())
                .then(() => {
                    removeFile(fileName);
                    fileItem.remove();
                })
                .catch(error => {
                    console.error('Error deleting file:', error);
                    alert('Failed to delete file. Please try again.');
                });
            } else {
                // Just remove from local array and UI
                removeFile(fileName);
                fileItem.remove();
            }
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
        agentManageForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const agentName = agentNameInput.value;
            const agentPersona = agentPersonaInput.value;
            
            // First update the agent
            fetch(`/api/agents/${originalAgentName}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    name: agentName,
                    persona: agentPersona
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    throw new Error(data.error);
                }
                
                // Filter out only new files (not already on the server)
                const newFiles = uploadedFiles.filter(file => file instanceof File);
                
                // If there are new files to upload, upload them
                if (newFiles.length > 0) {
                    const formData = new FormData();
                    newFiles.forEach(file => {
                        formData.append('files', file);
                    });
                    
                    return fetch(`/api/agents/${agentName}/upload`, {
                        method: 'POST',
                        body: formData
                    });
                }
                
                return Promise.resolve({ message: 'No new files to upload' });
            })
            .then(response => {
                if (response instanceof Response) {
                    return response.json();
                }
                return response;
            })
            .then(() => {
                // Show success message and redirect
                alert(`AI Agent "${agentName}" updated successfully!`);
                window.location.href = '/my-agents';
            })
            .catch(error => {
                console.error('Error updating agent:', error);
                alert('There was an error updating your AI Agent: ' + error.message);
            });
        });
    }
    
    /**
     * Set up the delete button
     */
    function setupDeleteButton() {
        deleteButton.addEventListener('click', function() {
            if (confirm(`Are you sure you want to delete the agent "${originalAgentName}"? This cannot be undone.`)) {
                fetch(`/api/agents/${originalAgentName}`, {
                    method: 'DELETE'
                })
                .then(response => response.json())
                .then(() => {
                    alert(`AI Agent "${originalAgentName}" deleted successfully!`);
                    window.location.href = '/my-agents';
                })
                .catch(error => {
                    console.error('Error deleting agent:', error);
                    alert('There was an error deleting your AI Agent. Please try again.');
                });
            }
        });
    }
    
    // Initialize the manage page when DOM is loaded
    document.addEventListener('DOMContentLoaded', initManage);
})();