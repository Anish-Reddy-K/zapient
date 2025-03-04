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
    
    // Allowed file types
    const allowedFileTypes = [
        'application/pdf',
        '.pdf'
    ];
    
    // For tracking the current agent's status
    let currentAgentName = null;
    let processingStatusInterval = null;
    let processingComplete = false;
    let processingSuccessMessage = null;
    
    /**
     * Initialize the configuration page
     */
    function initConfig() {
        setupFileUpload();
        setupFormSubmission();
        preloadTemplateData();
    }

    /**
     * Pre-load template data from URL parameters if present
     */
    function preloadTemplateData() {
        // Parse URL query parameters
        const urlParams = new URLSearchParams(window.location.search);
        const templateName = urlParams.get('name');
        const templatePersona = urlParams.get('persona');
        
        // If template parameters exist, pre-fill the form
        if (templateName) {
            agentNameInput.value = templateName;
        }
        
        if (templatePersona) {
            agentPersonaInput.value = templatePersona;
        }
    }
    
    /**
     * Check if file type is allowed
     * @param {File} file - The file to check
     * @returns {boolean} - Whether the file type is allowed
     */
    function isFileTypeAllowed(file) {
        // Check if mime type is in allowed list
        if (allowedFileTypes.includes(file.type)) {
            return true;
        }
        
        // If mime type check fails, check file extension
        const fileName = file.name.toLowerCase();
        return allowedFileTypes.some(type => {
            if (type.startsWith('.')) {
                return fileName.endsWith(type);
            }
            return false;
        });
    }
    
    /**
     * Set up the file upload functionality
     */
    function setupFileUpload() {
        // Set the accept attribute on file input
        fileInput.setAttribute('accept', '.pdf,application/pdf');
        
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
        let rejectedFiles = [];
        
        filesArray.forEach(file => {
            // First check if file type is allowed
            if (!isFileTypeAllowed(file)) {
                rejectedFiles.push(file.name);
                return;
            }
            
            // Check if file is already in the list
            const isDuplicate = uploadedFiles.some(f => f.name === file.name && f.size === file.size);
            
            if (!isDuplicate) {
                uploadedFiles.push(file);
                addFileToUI(file);
            }
        });
        
        // Show alert if any files were rejected
        if (rejectedFiles.length > 0) {
            alert(`The following files were not added because they are not supported: ${rejectedFiles.join(', ')}\nOnly PDF files are supported.`);
        }
    }
    
    /**
     * Add a file to the UI list
     * @param {File} file - The file to add to the UI
     */
    /**
     * Add a file to the UI list
     * @param {File} file - The file to add to the UI
     */
    function addFileToUI(file) {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        fileItem.dataset.filename = file.name;
        
        fileItem.innerHTML = `
            <i class="fas fa-file-pdf file-icon"></i>
            <span class="file-name">${file.name}</span>
            <span class="file-status status-pending" style="margin-left: auto; margin-right: 10px; font-size: 0.8rem; color: #6b7280;">
                Ready
            </span>
            <i class="fas fa-times file-remove" data-filename="${file.name}"></i>
        `;
        
        fileList.appendChild(fileItem);
        
        // Add event listener to remove button
        const removeBtn = fileItem.querySelector('.file-remove');
        removeBtn.addEventListener('click', function() {
            const fileName = this.getAttribute('data-filename');
            
            // If we have a current agent name and this is a newly uploaded file
            if (currentAgentName && processingComplete) {
                // Try to delete the file from the server
                fetch(`/api/agents/${currentAgentName}/files/${fileName}`, {
                    method: 'DELETE'
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Failed to delete file from server');
                    }
                    return response.json();
                })
                .then(() => {
                    // Remove from local array and UI
                    removeFile(fileName);
                    fileItem.remove();
                })
                .catch(error => {
                    console.error('Error deleting file:', error);
                    // Still remove from UI since the user expects it
                    removeFile(fileName);
                    fileItem.remove();
                });
            } else {
                // Just remove from local array and UI
                removeFile(fileName);
                fileItem.remove();
            }
        });
    }
    
    /**
     * Update file status in the UI
     * @param {string} filename - The name of the file
     * @param {string} status - The status of the file
     * @param {string} message - The status message
     */
    function updateFileStatus(filename, status, message) {
        const fileItem = document.querySelector(`.file-item[data-filename="${filename}"]`);
        if (!fileItem) return;
        
        const statusSpan = fileItem.querySelector('.file-status');
        if (!statusSpan) return;
        
        // Remove all previous status classes
        statusSpan.className = 'file-status';
        
        let statusText = message || status;
        let statusColor = '#6b7280'; // Default gray
        let statusClass = '';
        
        switch(status) {
            case 'ready':
                statusText = 'Ready';
                statusColor = '#6b7280'; // Gray
                statusClass = 'status-pending';
                break;
            case 'pending':
                statusText = 'Pending';
                statusColor = '#6b7280'; // Gray
                statusClass = 'status-pending';
                break;
            case 'processing':
                statusText = 'Processing...';
                statusColor = '#3b82f6'; // Blue
                statusClass = 'status-processing';
                break;
            case 'success':
                statusText = 'Processed';  // Changed from "Complete" to "Processed"
                statusColor = '#10b981'; // Green
                statusClass = 'status-success';
                break;
            case 'error':
                statusText = 'Error';
                statusColor = '#ef4444'; // Red
                statusClass = 'status-error';
                break;
        }
        
        statusSpan.textContent = statusText;
        statusSpan.style.color = statusColor;
        statusSpan.classList.add(statusClass);
        
        // Update icon based on status
        const iconSpan = fileItem.querySelector('.file-icon');
        if (iconSpan) {
            // Reset classes first
            iconSpan.className = 'fas file-icon';
            
            if (status === 'processing') {
                iconSpan.classList.add('fa-spinner', 'fa-spin');
            } else if (status === 'success') {
                iconSpan.classList.add('fa-check-circle');
            } else if (status === 'error') {
                iconSpan.classList.add('fa-exclamation-circle');
            } else {
                // Default icon for ready, pending
                iconSpan.classList.add('fa-file-pdf');
            }
        }
    }
    
    /**
     * Remove a file from the uploaded files array
     * @param {string} fileName - The name of the file to remove
     */
    function removeFile(fileName) {
        uploadedFiles = uploadedFiles.filter(file => file.name !== fileName);
    }
    
    /**
     * Start monitoring processing status
     */
    function startProcessingStatusMonitor(agentName) {
        if (!agentName) return;
        
        currentAgentName = agentName;
        processingComplete = false;
        
        // Check immediately
        checkProcessingStatus();
        
        // Set up interval to check every 2 seconds
        processingStatusInterval = setInterval(checkProcessingStatus, 2000);
    }
    
    /**
     * Stop monitoring processing status
     */
    function stopProcessingStatusMonitor() {
        if (processingStatusInterval) {
            clearInterval(processingStatusInterval);
            processingStatusInterval = null;
        }
    }
    
    /**
     * Check processing status of files
     */
    function checkProcessingStatus() {
        if (!currentAgentName) return;
        
        fetch(`/api/agents/${currentAgentName}/processing-status`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to fetch processing status');
                }
                return response.json();
            })
            .then(data => {
                // Update processing status in the UI
                if (data.file_status) {
                    Object.entries(data.file_status).forEach(([filename, status]) => {
                        updateFileStatus(filename, status.status, status.message);
                    });
                }
                
                // Check if processing is complete
                if (data.processing_complete && !processingComplete) {
                    processingComplete = true;
                    
                    // Update UI to reflect completion
                    submitButton.disabled = false;
                    submitButton.textContent = 'Confirm Agent Creation';
                    
                    // Remove any existing message
                    if (processingSuccessMessage && processingSuccessMessage.parentNode) {
                        processingSuccessMessage.remove();
                    }
                    
                    // Show a success message above the button
                    showProcessingCompleteMessage(data.files_processed);
                    
                    // Stop monitoring
                    stopProcessingStatusMonitor();
                }
            })
            .catch(error => {
                console.error('Error checking processing status:', error);
            });
    }
    
    /**
     * Show processing complete message
     * @param {boolean} success - Whether processing was successful
     */
    function showProcessingCompleteMessage(success) {
        // Remove any existing message
        if (processingSuccessMessage && processingSuccessMessage.parentNode) {
            processingSuccessMessage.remove();
        }
        
        // Create a success message above the confirm button
        processingSuccessMessage = document.createElement('div');
        processingSuccessMessage.className = success ? 'success-message' : 'warning-message';
        processingSuccessMessage.style.cssText = `
            margin-bottom: 1rem;
            padding: 0.75rem;
            border-radius: 0.25rem;
            background-color: ${success ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)'};
            border: 1px solid ${success ? '#10b981' : '#f59e0b'};
            color: ${success ? '#10b981' : '#f59e0b'};
            font-size: 0.9rem;
            text-align: center;
        `;
        
        processingSuccessMessage.innerHTML = `
            <i class="fas ${success ? 'fa-check-circle' : 'fa-exclamation-triangle'}" style="margin-right: 0.5rem;"></i>
            ${success ? 'All files have been successfully processed!' : 'Processing completed with some issues.'}
        `;
        
        // Insert the message before the buttons row
        const buttonsRow = document.querySelector('.buttons-row');
        if (buttonsRow) {
            buttonsRow.parentNode.insertBefore(processingSuccessMessage, buttonsRow);
        }
    }
    
    /**
     * Set up the form submission
     */
    function setupFormSubmission() {
        agentConfigForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // If processing is already complete and button is in "Confirm" state
            if (processingComplete && submitButton.textContent === 'Confirm Agent Creation') {
                // Go to the My AI Agents page
                window.location.href = '/my-agents';
                return;
            }
            
            // Disable submit button to prevent multiple submissions
            submitButton.disabled = true;
            submitButton.textContent = 'Creating...';
            
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
                
                // Start monitoring this agent's status
                startProcessingStatusMonitor(agentName);
                
                // If there are files to upload, upload them
                if (uploadedFiles.length > 0) {
                    const formData = new FormData();
                    uploadedFiles.forEach(file => {
                        formData.append('files', file);
                        // Update status to processing immediately in the UI
                        updateFileStatus(file.name, 'processing', 'Processing...');
                    });
                    
                    // Update button to reflect file processing
                    submitButton.textContent = 'Processing Files...';
                    
                    return fetch(`/api/agents/${agentName}/upload`, {
                        method: 'POST',
                        body: formData
                    });
                } else {
                    // No files to process, enable button immediately
                    submitButton.disabled = false;
                    submitButton.textContent = 'Confirm Agent Creation';
                    
                    // Show a simple completion message
                    showProcessingCompleteMessage(true);
                    return Promise.resolve({ message: 'No files to upload' });
                }
            })
            .then(response => {
                if (response instanceof Response) {
                    return response.json();
                }
                return response;
            })
            .catch(error => {
                console.error('Error creating agent:', error);
                alert('There was an error creating your AI Agent: ' + error.message);
                
                // Re-enable submit button
                submitButton.disabled = false;
                submitButton.textContent = 'Create Agent';
            });
        });
    }
    
    // Initialize the configuration page when DOM is loaded
    document.addEventListener('DOMContentLoaded', initConfig);
    
    // Expose the status monitoring function for external access
    window.startProcessingStatusMonitor = startProcessingStatusMonitor;
})();