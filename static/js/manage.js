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
    
    // Processing status monitoring
    let statusInterval = null;
    let processingComplete = false;
    
    // Allowed file types
    const allowedFileTypes = [
        'application/pdf',
        '.pdf'
    ];
    
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
        
        // Start monitoring processing status
        startProcessingStatusMonitor();
    }
    
    /**

     * Start monitoring processing status
     */
    function startProcessingStatusMonitor() {
        // Check immediately
        checkProcessingStatus();
        
        // Set up interval to check every 2 seconds for better responsiveness
        statusInterval = setInterval(checkProcessingStatus, 2000);
    }
    
    /**
     * Stop monitoring processing status
     */
    function stopProcessingStatusMonitor() {
        if (statusInterval) {
            clearInterval(statusInterval);
            statusInterval = null;
        }
    }
    
    /**
     * Check processing status of files
     */
    function checkProcessingStatus() {
        fetch(`/api/agents/${originalAgentName}/processing-status`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to fetch processing status');
                }
                return response.json();
            })
            .then(data => {
                // Update processing status in the UI
                if (data.file_status) {
                    for (const [filename, status] of Object.entries(data.file_status)) {
                        updateFileStatus(filename, status.status, status.message);
                    }
                }
                
                // If processing is complete, stop monitoring
                if (data.processing_complete && !processingComplete) {
                    processingComplete = true;
                    stopProcessingStatusMonitor();
                }
            })
            .catch(error => {
                console.error('Error checking processing status:', error);
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
                statusText = 'Complete';
                statusColor = '#10b981'; // Green
                statusClass = 'status-success';
                break;
            case 'error':
                statusText = 'Error';
                statusColor = '#ef4444'; // Red
                statusClass = 'status-error';
                break;
            case 'unknown':
                statusText = 'Status Unknown';
                statusColor = '#6b7280'; // Gray
                statusClass = 'status-pending';
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
                // Default icon for ready, pending, unknown
                iconSpan.classList.add('fa-file-pdf');
            }
        }
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
                        // For existing files, create a lightweight file object
                        const fileObj = {
                            name: file.name,
                            size: file.size,
                            type: file.type || 'application/pdf',
                            isExisting: true
                        };
                        
                        uploadedFiles.push(fileObj);
                        addFileToUI(fileObj, file.processing_status || 'unknown');
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
            const isDuplicate = uploadedFiles.some(f => f.name === file.name);
            
            if (!isDuplicate) {
                uploadedFiles.push(file);
                addFileToUI(file, 'ready');
            }
        });
        
        // Show alert if any files were rejected
        if (rejectedFiles.length > 0) {
            alert(`The following files were not added because they are not supported: ${rejectedFiles.join(', ')}\nOnly PDF files are supported.`);
        }
    }
    
    /**
     * Add a file to the UI list
     * @param {File|Object} file - The file to add to the UI
     * @param {string} status - The processing status of the file
     */
    function addFileToUI(file, status = 'unknown') {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        fileItem.dataset.filename = file.name;
        
        // Determine icon class based on status
        let iconClass = 'fa-file-pdf';
        if (status === 'processing') {
            iconClass = 'fa-spinner fa-spin';
        } else if (status === 'success') {
            iconClass = 'fa-check-circle';
        } else if (status === 'error') {
            iconClass = 'fa-exclamation-circle';
        }
        
        // Determine status text and class
        let statusText = 'Unknown';
        let statusColor = '#6b7280';
        let statusClass = 'status-pending';
        
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
                statusText = 'Complete';
                statusColor = '#10b981'; // Green
                statusClass = 'status-success';
                break;
            case 'error':
                statusText = 'Error';
                statusColor = '#ef4444'; // Red
                statusClass = 'status-error';
                break;
        }
        
        fileItem.innerHTML = `
            <i class="fas ${iconClass} file-icon"></i>
            <span class="file-name">${file.name}</span>
            <span class="file-status ${statusClass}" style="margin-left: auto; margin-right: 10px; font-size: 0.8rem; color: ${statusColor};">
                ${statusText}
            </span>
            <i class="fas fa-times file-remove" data-filename="${file.name}"></i>
        `;
        
        fileList.appendChild(fileItem);
        
        // Add event listener to remove button
        const removeBtn = fileItem.querySelector('.file-remove');
        removeBtn.addEventListener('click', function() {
            const fileName = this.getAttribute('data-filename');
            
            // If this is an existing file, delete it from the server
            const existingFile = uploadedFiles.find(f => f.name === fileName && f.isExisting);
            
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
                        // Update status to processing immediately in the UI
                        updateFileStatus(file.name, 'processing', 'Processing...');
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
            .then(data => {
                if (data.files && data.files.length > 0) {
                    // Restart processing status monitoring to track new files
                    processingComplete = false;
                    stopProcessingStatusMonitor();
                    startProcessingStatusMonitor();
                    
                    // Show success message
                    alert('Agent updated and files are being processed.');
                } else {
                    // Show success message
                    alert('Agent updated successfully.');
                }
                
                // If name changed, redirect to new manage URL
                if (agentName !== originalAgentName) {
                    window.location.href = `/manage/${encodeURIComponent(agentName)}`;
                }
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
                // Stop status monitoring
                stopProcessingStatusMonitor();
                
                fetch(`/api/agents/${originalAgentName}`, {
                    method: 'DELETE'
                })
                .then(response => response.json())
                .then(() => {
                    window.location.href = '/my-agents';
                })
                .catch(error => {
                    console.error('Error deleting agent:', error);
                    alert('There was an error deleting your AI Agent. Please try again.');
                });
            }
        });
    }
    
    /**
     * Clean up when leaving page
     */
    function cleanup() {
        stopProcessingStatusMonitor();
    }
    
    // Add event listener for page unload to clean up
    window.addEventListener('beforeunload', cleanup);
    
    // Initialize the manage page when DOM is loaded
    document.addEventListener('DOMContentLoaded', initManage);
})();