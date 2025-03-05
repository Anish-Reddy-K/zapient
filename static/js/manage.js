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
    const updateButton = document.querySelector('.update-btn');

    // Files array to store uploaded files
    let uploadedFiles = [];

    // Original agent data (for tracking changes)
    let originalAgentName = '';
    let originalAgentPersona = '';
    let originalFiles = [];
    
    // Flag to track if changes have been made
    let hasChanges = false;

    // Processing status monitoring
    let statusInterval = null;
    let filesCurrentlyProcessing = false; // Flag to track if any files are processing
    let processingSuccessMessage = null;
    let justFinishedProcessing = false; // Flag to track if processing just finished

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
        setupChangeTracking();

        // Initial button state - set to Save with disabled state until data is loaded
        updateButton.textContent = 'Save';
        updateButton.disabled = true;
    }

    /**
     * Setup change tracking on form inputs
     */
    function setupChangeTracking() {
        // Track changes on agent name input
        agentNameInput.addEventListener('input', checkForChanges);
        
        // Track changes on agent persona textarea
        agentPersonaInput.addEventListener('input', checkForChanges);
    }

    /**
     * Check if any changes have been made to the agent data
     */
    function checkForChanges() {
        const nameChanged = agentNameInput.value !== originalAgentName;
        const personaChanged = agentPersonaInput.value !== originalAgentPersona;
        
        // Check for new files or deleted files
        const filesChanged = uploadedFiles.some(file => !file.isExisting) || 
                            originalFiles.length !== uploadedFiles.length;
        
        hasChanges = nameChanged || personaChanged || filesChanged;
        
        // If we just finished processing, enable the button regardless of changes
        if (justFinishedProcessing) {
            updateButton.disabled = false;
        } else {
            // Otherwise, disable only if there are no changes
            updateButton.disabled = !hasChanges;
        }
    }

    /**
     * Reset update button state
     * @param {string} text - The text to set on the button
     * @param {boolean} disabled - Whether to disable the button
     */
    function resetUpdateButtonState(text, disabled = null) {
        updateButton.textContent = text;
        
        // Only update disabled state if explicitly specified, else calculate based on changes
        if (disabled !== null) {
            updateButton.disabled = disabled;
        } else {
            checkForChanges();
        }
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
        if (!originalAgentName) return;

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
                    let allFilesSuccessful = true;
                    let anyProcessing = false;

                    for (const [filename, status] of Object.entries(data.file_status)) {
                        // Update UI to show current status
                        updateFileStatus(filename, status.status, status.message);

                        // Check if any file has an error status
                        if (status.status === 'error') {
                            allFilesSuccessful = false;
                        }

                        // Check if any file is still processing
                        if (status.status === 'processing' || status.status === 'pending') {
                            anyProcessing = true;
                        }
                    }

                    // Update processing flag
                    const wasProcessing = filesCurrentlyProcessing;
                    filesCurrentlyProcessing = anyProcessing;

                    // If files were processing and now they're done
                    if (wasProcessing && !anyProcessing && data.processing_complete) {
                        // Make a direct fetch to get the latest file status
                        fetch(`/api/agents/${originalAgentName}`)
                            .then(response => response.json())
                            .then(agentData => {
                                // Update all file statuses based on latest data
                                if (agentData.files && agentData.files.length > 0) {
                                    agentData.files.forEach(file => {
                                        // Force update status to 'success' for all processed files
                                        if (file.processed) {
                                            updateFileStatus(file.name, 'success', 'Processed');
                                        }
                                    });
                                }
                                
                                // Show completion message
                                showProcessingCompleteMessage(allFilesSuccessful);
                                
                                // Set flag that we just finished processing
                                justFinishedProcessing = true;
                                
                                // Update original files to include the newly processed ones
                                originalFiles = [...uploadedFiles].map(file => {
                                    if (file instanceof File) {
                                        return {
                                            name: file.name,
                                            size: file.size,
                                            type: file.type || 'application/pdf',
                                            isExisting: true,
                                            processed: true
                                        };
                                    }
                                    return {...file, processed: true};
                                });
                                
                                // Mark all uploaded files as processed and existing
                                uploadedFiles = uploadedFiles.map(file => {
                                    if (file instanceof File) {
                                        return {
                                            name: file.name,
                                            size: file.size,
                                            type: file.type || 'application/pdf',
                                            isExisting: true,
                                            processed: true
                                        };
                                    }
                                    return {...file, processed: true};
                                });
                                
                                // Reset button state to enabled with "Save" text
                                updateButton.textContent = 'Save';
                                updateButton.disabled = false;
                                
                                // Stop monitoring as processing is complete
                                stopProcessingStatusMonitor();
                            })
                            .catch(error => {
                                console.error('Error fetching updated agent data:', error);
                            });
                    }
                }
            })
            .catch(error => {
                console.error('Error checking processing status:', error);
            });
    }

    /**
     * Remove processing complete message from UI
     */
    function removeProcessingCompleteMessage() {
        if (processingSuccessMessage && processingSuccessMessage.parentNode) {
            processingSuccessMessage.remove();
            processingSuccessMessage = null; // Reset message
        }
    }

    /**
     * Show processing complete message
     * @param {boolean} success - Whether processing was successful
     */
    function showProcessingCompleteMessage(success) {
        removeProcessingCompleteMessage(); // Ensure no old message exists

        // Create a success message above the buttons
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
        
        // Set a timeout to remove the message after 5 seconds
        setTimeout(() => {
            removeProcessingCompleteMessage();
        }, 5000);
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
                statusText = 'Processed'; // Changed from "Complete" to "Processed"
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
                // Store original values for change tracking
                originalAgentName = data.name;
                originalAgentPersona = data.persona || '';
                
                // Populate form fields
                agentNameInput.value = data.name;
                agentPersonaInput.value = data.persona || '';

                // Clear file list first
                fileList.innerHTML = '';
                uploadedFiles = [];
                originalFiles = [];

                // Load files
                if (data.files && data.files.length > 0) {
                    data.files.forEach(file => {
                        // For existing files, create a lightweight file object
                        const fileObj = {
                            name: file.name,
                            size: file.size,
                            type: file.type || 'application/pdf',
                            isExisting: true,
                            processed: file.processed || false
                        };

                        uploadedFiles.push(fileObj);
                        originalFiles.push({...fileObj}); // Clone for comparison
                        addFileToUI(fileObj, file.processing_status || 'unknown');
                    });
                }

                // Start status monitoring after loading agent data and files
                startProcessingStatusMonitor();
                
                // Initialize button state after data is loaded (initially disabled)
                checkForChanges();
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
                // Mark as unprocessed
                file.processed = false;
                
                uploadedFiles.push(file);
                addFileToUI(file, 'ready');
                removeProcessingCompleteMessage(); // New file added, remove complete message
                justFinishedProcessing = false; // Reset processing status
                
                // Check for changes after adding files
                checkForChanges();
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
                statusText = 'Processed'; // Changed from "Complete" to "Processed"
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
                    checkForChanges(); // Check for changes after removing file
                    
                    if (uploadedFiles.length === 0) { // If no files left
                        justFinishedProcessing = false;
                        removeProcessingCompleteMessage();
                    }
                })
                .catch(error => {
                    console.error('Error deleting file:', error);
                    alert('Failed to delete file. Please try again.');
                });
            } else {
                // Just remove from local array and UI
                removeFile(fileName);
                fileItem.remove();
                checkForChanges(); // Check for changes after removing file
                
                if (uploadedFiles.length === 0) { // If no files left
                    justFinishedProcessing = false;
                    removeProcessingCompleteMessage();
                }
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
     * Check if there are any unprocessed files
     * @returns {boolean} - Whether there are any unprocessed files
     */
    function hasUnprocessedFiles() {
        return uploadedFiles.some(file => 
            file instanceof File || // New files are always unprocessed
            (file.isExisting && !file.processed) // Existing files can be checked
        );
    }

    /**
     * Set up the form submission
     */
    function setupFormSubmission() {
        agentManageForm.addEventListener('submit', function(e) {
            e.preventDefault();

            // If there are files in processing state, prevent submission
            if (filesCurrentlyProcessing) {
                alert('Please wait for all files to finish processing before saving.');
                return;
            }
            
            // If no changes and just finished processing some files, go back to agents page
            if (!hasChanges && justFinishedProcessing) {
                window.location.href = '/my-agents';
                return;
            }
            
            // If no changes at all, go back to agents page
            if (!hasChanges) {
                window.location.href = '/my-agents';
                return;
            }

            // Disable button while processing
            resetUpdateButtonState('Saving...', true); // Button state during agent update

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

                // If we changed the name, update originalAgentName
                if (agentName !== originalAgentName) {
                    originalAgentName = agentName;
                }
                
                // Update original persona
                originalAgentPersona = agentPersona;

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

                    // Flag that files are processing
                    filesCurrentlyProcessing = true;

                    // Update button text
                    resetUpdateButtonState('Processing Files...', true);

                    return fetch(`/api/agents/${agentName}/upload`, {
                        method: 'POST',
                        body: formData
                    });
                }

                filesCurrentlyProcessing = true;
                updateButton.textContent = 'Processing Files...';
                updateButton.disabled = true;  

                // No new files, just update the UI
                resetUpdateButtonState('Save', true);
                
                // Check if we've just finished processing before
                if (justFinishedProcessing) {
                    // Redirect back to agents page
                    window.location.href = '/my-agents';
                    return Promise.resolve();
                } else {
                    // Show a success message
                    const message = document.createElement('div');
                    message.className = 'success-message';
                    message.style.cssText = `
                        margin-bottom: 1rem;
                        padding: 0.75rem;
                        border-radius: 0.25rem;
                        background-color: rgba(16, 185, 129, 0.1);
                        border: 1px solid #10b981;
                        color: #10b981;
                        font-size: 0.9rem;
                        text-align: center;
                    `;
                    message.innerHTML = `
                        <i class="fas fa-check-circle" style="margin-right: 0.5rem;"></i>
                        Agent updated successfully!
                    `;
                    
                    // Insert the message before the buttons row
                    const buttonsRow = document.querySelector('.buttons-row');
                    if (buttonsRow) {
                        buttonsRow.parentNode.insertBefore(message, buttonsRow);
                    }
                    
                    // Remove the message after 3 seconds
                    setTimeout(() => {
                        if (message.parentNode) {
                            message.remove();
                        }
                    }, 3000);
                    
                    // Reset button state
                    resetUpdateButtonState('Save', true);
                    
                    // Reset hasChanges since we just saved
                    hasChanges = false;
                    
                    return Promise.resolve({ message: 'Agent updated successfully' });
                }
            })
            .then(response => {
                if (response instanceof Response) {
                    return response.json();
                }
                return response;
            })
            .catch(error => {
                console.error('Error updating agent:', error);
                alert('There was an error updating your AI Agent: ' + error.message);

                // Re-enable update button
                resetUpdateButtonState('Save'); // Reset button on error
                stopProcessingStatusMonitor(); // Stop status monitor on error
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