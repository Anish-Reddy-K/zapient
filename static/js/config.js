/**
 * Configuration Module
 * Handles the configuration and creation of new AI agents
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
    
    // Files array to store uploaded files
    let uploadedFiles = [];
    
    /**
     * Initialize the configuration page
     */
    function initConfig() {
        setupFileUpload();
        setupFormSubmission();
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
            
            // First create the agent
            fetch('/api/agents', {
                method: 'POST',
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
                
                // If there are files to upload, upload them
                if (uploadedFiles.length > 0) {
                    const formData = new FormData();
                    uploadedFiles.forEach(file => {
                        formData.append('files', file);
                    });
                    
                    return fetch(`/api/agents/${agentName}/upload`, {
                        method: 'POST',
                        body: formData
                    });
                }
                
                return Promise.resolve({ message: 'No files to upload' });
            })
            .then(response => {
                if (response instanceof Response) {
                    return response.json();
                }
                return response;
            })
            .then(() => {
                // Show success message and redirect
                alert(`AI Agent "${agentName}" created successfully!`);
                window.location.href = '/my-agents';
            })
            .catch(error => {
                console.error('Error creating agent:', error);
                alert('There was an error creating your AI Agent: ' + error.message);
            });
        });
    }
    
    // Initialize the configuration page when DOM is loaded
    document.addEventListener('DOMContentLoaded', initConfig);
})();