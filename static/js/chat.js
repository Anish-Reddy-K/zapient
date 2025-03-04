/**
 * Chat Module
 * Handles chat functionality with AI agents
 */

// Immediately invoked function expression (IIFE) to avoid polluting the global namespace
(function() {
    // DOM Elements
    const chatMessages = document.getElementById('chatMessages');
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    const citationTooltip = document.getElementById('citationTooltip');
    const citationBody = document.getElementById('citationBody');
    const closeCitationTooltip = document.getElementById('closeCitationTooltip');
    
    // State variables
    let conversationId = null;
    let isWaitingForResponse = false;
    let citations = [];
    
    /**
     * Initialize the chat functionality
     */
    function initChat() {
        setupEventListeners();
        //loadChatHistory();
        adjustTextareaHeight();
    }
    
    /**
     * Load chat history from the server
     */
    function loadChatHistory() {
        fetch(`/api/agents/${AGENT_NAME}/chat-history`)
            .then(response => response.json())
            .then(data => {
                // Find the most recent conversation or create a new one
                const conversations = data.conversations || [];
                if (conversations.length > 0) {
                    // Sort conversations by date, newest first
                    conversations.sort((a, b) => {
                        return new Date(b.updated_at) - new Date(a.updated_at);
                    });
                    
                    // Get the most recent conversation
                    const recentConversation = conversations[0];
                    conversationId = recentConversation.id;
                    
                    // Display messages from the most recent conversation
                    recentConversation.messages.forEach(message => {
                        if (message.role === 'user') {
                            appendUserMessage(message);
                        } else if (message.role === 'assistant') {
                            appendAgentMessage(message);
                            // Store citations from the agent message
                            if (message.citations) {
                                citations = [...citations, ...message.citations];
                            }
                        }
                    });
                    
                    // Scroll to the bottom after loading messages
                    scrollToBottom();
                }
            })
            .catch(error => {
                console.error('Error loading chat history:', error);
            });
    }
    
    /**
     * Set up event listeners
     */
    function setupEventListeners() {
        // Send message on button click
        sendButton.addEventListener('click', sendMessage);
        
        // Send message on Enter key (but allow Shift+Enter for new line)
        messageInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
        
        // Auto-resize textarea as the user types
        messageInput.addEventListener('input', function() {
            adjustTextareaHeight();
            
            // Enable/disable send button based on input
            sendButton.disabled = messageInput.value.trim() === '' || isWaitingForResponse;
        });
        
        // Close citation tooltip when clicking outside
        document.addEventListener('click', function(e) {
            if (!citationTooltip.contains(e.target) && 
                !e.target.classList.contains('citation-marker')) {
                citationTooltip.style.display = 'none';
            }
        });
        
        // Close citation tooltip on close button click
        closeCitationTooltip.addEventListener('click', function() {
            citationTooltip.style.display = 'none';
        });
        
        // Set up citation click handling (delegated event)
        chatMessages.addEventListener('click', function(e) {
            if (e.target.classList.contains('citation-marker')) {
                showCitationTooltip(e.target);
            }
        });
    }
    
    /**
     * Adjust textarea height based on content
     */
    function adjustTextareaHeight() {
        messageInput.style.height = 'auto';
        messageInput.style.height = messageInput.scrollHeight + 'px';
    }
    
    /**
     * Send a message to the agent
     */
    function sendMessage() {
        const message = messageInput.value.trim();
        
        // Don't send empty messages
        if (message === '' || isWaitingForResponse) {
            return;
        }
        
        // Display user message immediately
        const userMessageObj = {
            role: 'user',
            content: message,
            timestamp: new Date().toISOString()
        };
        appendUserMessage(userMessageObj);
        
        // Clear input field and reset height
        messageInput.value = '';
        adjustTextareaHeight();
        sendButton.disabled = true;
        
        // Scroll to bottom
        scrollToBottom();
        
        // Show loading indicator
        appendLoadingIndicator();
        
        // Set waiting flag
        isWaitingForResponse = true;
        
        // Send message to the server
        fetch(`/api/agents/${AGENT_NAME}/send-message`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message,
                conversation_id: conversationId
            })
        })
        .then(response => response.json())
        .then(data => {
            // Remove loading indicator
            removeLoadingIndicator();
            
            // Update conversation ID if this is a new conversation
            if (!conversationId) {
                conversationId = data.conversation_id;
            }
            
            // Display agent message
            appendAgentMessage(data.message);
            
            // Store citations
            if (data.message.citations) {
                citations = [...citations, ...data.message.citations];
            }
            
            // Reset waiting flag
            isWaitingForResponse = false;
            
            // Re-enable send button if there's text
            sendButton.disabled = messageInput.value.trim() === '';
            
            // Scroll to bottom
            scrollToBottom();
        })
        .catch(error => {
            console.error('Error sending message:', error);
            removeLoadingIndicator();
            appendErrorMessage();
            isWaitingForResponse = false;
            sendButton.disabled = messageInput.value.trim() === '';
        
            // Remove or comment out the red border styling:
            // messageInput.parentElement.style.border = '1px solid #ef4444';
            
            // Optionally, remove any error-specific styling:
            // setTimeout(() => {
            //     messageInput.parentElement.style.border = '';
            // }, 2000);
        });
    }
    
    /**
     * Append a user message to the chat
     * @param {Object} message - The message object
     */
    function appendUserMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = 'message-wrapper user-message';
        messageElement.innerHTML = `
            <div class="message-content">
                <p>${escapeHTML(message.content)}</p>
            </div>
        `;
        chatMessages.appendChild(messageElement);
    }
    
    /**
     * Append an agent message to the chat
     * @param {Object} message - The message object
     */
    function appendAgentMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = 'message-wrapper agent-message';
        
        // Process the content (markdown, citations, etc.)
        const processedContent = processMessageContent(message.content, message.citations);
        
        messageElement.innerHTML = `
            <div class="message-content">
                <div class="markdown-content">${processedContent}</div>
            </div>
        `;
        
        chatMessages.appendChild(messageElement);
    }
    
    /**
     * Process message content to render markdown and handle citations
     * @param {string} content - The message content
     * @param {Array} messageCitations - The citations for this message
     * @returns {string} - The processed HTML content
     */
    function processMessageContent(content, messageCitations) {
        // Replace citation markers first
        let processedContent = content;
        if (messageCitations && messageCitations.length > 0) {
            messageCitations.forEach(citation => {
                const citationMarker = `[^${citation.id}]`;
                const htmlMarker = `<a href="#" class="citation-marker" data-citation-id="${citation.id}">[${citation.id}]</a>`;
                processedContent = processedContent.replace(new RegExp(escapeRegExp(citationMarker), 'g'), htmlMarker);
            });
        }
        
        // Render markdown
        const renderedMarkdown = marked.parse(processedContent);
        return DOMPurify.sanitize(renderedMarkdown);
    }
    
    /**
     * Append a loading indicator to the chat
     */
    function appendLoadingIndicator() {
        const loadingElement = document.createElement('div');
        loadingElement.className = 'loading-indicator';
        loadingElement.id = 'loadingIndicator';
        
        loadingElement.innerHTML = `
            <div class="agent-avatar">
                <i class="fas fa-robot"></i>
            </div>
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
        
        chatMessages.appendChild(loadingElement);
        scrollToBottom();
    }
    
    /**
     * Remove the loading indicator from the chat
     */
    function removeLoadingIndicator() {
        const loadingIndicator = document.getElementById('loadingIndicator');
        if (loadingIndicator) {
            loadingIndicator.remove();
        }
    }
    
    /**
     * Append an error message to the chat
     */
    function appendErrorMessage() {
        const messageElement = document.createElement('div');
        messageElement.className = 'message-wrapper agent-message';
        
        messageElement.innerHTML = `
            <div class="agent-avatar">
                <i class="fas fa-robot"></i>
            </div>
            <div class="message-content">
                <p>Sorry, I encountered an error processing your request. Please try again.</p>
            </div>
        `;
        
        chatMessages.appendChild(messageElement);
        scrollToBottom();
    }
    
    /**
     * Show the citation tooltip
     * @param {HTMLElement} target - The citation marker element
     */
    function showCitationTooltip(target) {
        const citationId = parseInt(target.getAttribute('data-citation-id'));
        const citation = citations.find(c => c.id === citationId);
        
        if (!citation) {
            return;
        }
        
        // Fill in citation details
        citationBody.innerHTML = `
            <div class="citation-file">${citation.file}</div>
            <div class="citation-page">Page ${citation.page}</div>
            <div class="citation-text">${citation.text}</div>
        `;
        
        // Position the tooltip near the citation marker
        const rect = target.getBoundingClientRect();
        citationTooltip.style.left = `${rect.left}px`;
        citationTooltip.style.top = `${rect.bottom + 10}px`;
        
        // Show the tooltip
        citationTooltip.style.display = 'block';
        
        // Reposition if off-screen
        const tooltipRect = citationTooltip.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        
        if (tooltipRect.right > viewportWidth) {
            const overflow = tooltipRect.right - viewportWidth;
            citationTooltip.style.left = `${rect.left - overflow - 20}px`;
        }
    }
    
    /**
     * Scroll to the bottom of the chat messages
     */
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    /**
     * Format a timestamp to a human-readable time
     * @param {Date} date - The date to format
     * @returns {string} - The formatted time
     */
    function formatTime(date) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    
    /**
     * Escape HTML to prevent XSS
     * @param {string} html - The string to escape
     * @returns {string} - The escaped string
     */
    function escapeHTML(html) {
        const div = document.createElement('div');
        div.textContent = html;
        return div.innerHTML;
    }
    
    /**
     * Escape a string for use in a regular expression
     * @param {string} string - The string to escape
     * @returns {string} - The escaped string
     */
    function escapeRegExp(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    document.getElementById('clearChatButton').addEventListener('click', clearChat);

    function clearChat() {
        if (confirm('Are you sure you want to clear all chat history?')) {
            fetch(`/api/agents/${AGENT_NAME}/clear-chat`, {
                method: 'POST'
            })
            .then(() => window.location.reload())
            .catch(error => console.error('Error clearing chat:', error));
        }
    }
    
    // Initialize the chat when DOM is loaded
    document.addEventListener('DOMContentLoaded', initChat);
})();