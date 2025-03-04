/**
 * Chat Module
 * Handles chat functionality with AI agents
 */
(function() {
    // DOM Elements
    const chatMessages = document.getElementById('chatMessages');
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    const citationTooltip = document.getElementById('citationTooltip');
    const citationBody = document.getElementById('citationBody');
    const closeCitationTooltip = document.getElementById('closeCitationTooltip');
    const clearChatButton = document.getElementById('clearChatButton');

    // State variables
    let conversationId = null;
    let isWaitingForResponse = false;
    let citations = [];
    
    /**
     * Initialize the chat functionality
     */
    function initChat() {
        setupEventListeners();
        loadChatHistory();    // UNCOMMENTED to load existing conversation
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
                    conversationId = recentConversation.conversation_id;
                    
                    // Display messages
                    recentConversation.messages.forEach(message => {
                        if (message.role === 'user') {
                            appendUserMessage(message);
                        } else if (message.role === 'assistant') {
                            appendAgentMessage(message);
                            // Store citations from the agent message if present
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
        
        // Citation click handling (delegated event)
        chatMessages.addEventListener('click', function(e) {
            if (e.target.classList.contains('citation-marker')) {
                showCitationTooltip(e.target);
            }
        });

        // Clear chat
        clearChatButton.addEventListener('click', clearChat);
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
        if (message === '' || isWaitingForResponse) {
            return;
        }
        
        // Append the user message immediately
        const userMessageObj = {
            role: 'user',
            content: message,
            timestamp: new Date().toISOString()
        };
        appendUserMessage(userMessageObj);
        
        // Clear input and disable send button
        messageInput.value = '';
        adjustTextareaHeight();
        sendButton.disabled = true;
        
        scrollToBottom();
        appendLoadingIndicator();
        isWaitingForResponse = true;
        
        fetch(`/api/agents/${AGENT_NAME}/send-message`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                conversation_id: conversationId
            })
        })
        .then(response => response.json())
        .then(data => {
            setTimeout(() => {
                removeLoadingIndicator();
                
                if (!conversationId) {
                    conversationId = data.conversation_id;
                }
                
                // The assistant's message
                appendAgentMessage(data.message);
                
                // Add any citations
                if (data.message.citations) {
                    citations = [...citations, ...data.message.citations];
                }
                
                isWaitingForResponse = false;
                sendButton.disabled = messageInput.value.trim() === '';
                scrollToBottom();
            }, 500);  // Smaller artificial delay
        })
        .catch(error => {
            console.error('Error sending message:', error);
            removeLoadingIndicator();
            appendErrorMessage();  // Provide fallback
            isWaitingForResponse = false;
            sendButton.disabled = messageInput.value.trim() === '';
        });
    }
    
    /**
     * Append a user message to the chat
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
     */
    function processMessageContent(content, messageCitations) {
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
     * Append a loading indicator
     */
    function appendLoadingIndicator() {
        const loadingElement = document.createElement('div');
        loadingElement.className = 'loading-indicator';
        loadingElement.id = 'loadingIndicator';
        
        loadingElement.innerHTML = `
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
     * Remove the loading indicator
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
        
        const fakeMessage = {
             content: "## Error\n\nCould not process your request. [^1]",
             citations: [{
                 id: 1,
                 file: "Error.log",
                 page: 999,
                 text: "No additional info"
             }]
        };
        
        const processedContent = processMessageContent(fakeMessage.content, fakeMessage.citations);
        
        messageElement.innerHTML = `
            <div class="message-content">
                <div class="markdown-content">${processedContent}</div>
            </div>
        `;
        
        chatMessages.appendChild(messageElement);
        scrollToBottom();
    }
    
    /**
     * Show the citation tooltip
     */
    function showCitationTooltip(target) {
        const citationId = parseInt(target.getAttribute('data-citation-id'));
        const citation = citations.find(c => c.id === citationId);
        
        if (!citation) {
            return;
        }
        
        citationBody.innerHTML = `
            <div class="citation-file">${citation.file}</div>
            <div class="citation-page">Page ${citation.page}</div>
        `;
        
        const rect = target.getBoundingClientRect();
        citationTooltip.style.left = `${rect.left}px`;
        citationTooltip.style.top = `${rect.bottom + 10}px`;
        
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
     * Utility: escape HTML
     */
    function escapeHTML(html) {
        const div = document.createElement('div');
        div.textContent = html;
        return div.innerHTML;
    }
    
    /**
     * Utility: escape string for RegExp
     */
    function escapeRegExp(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    /**
     * Clear chat
     */
    function clearChat() {
        if (confirm('Are you sure you want to clear all chat history?')) {
            fetch(`/api/agents/${AGENT_NAME}/clear-chat`, {
                method: 'POST'
            })
            .then(() => window.location.reload())
            .catch(error => console.error('Error clearing chat:', error));
        }
    }

    // Initialize on DOM load
    document.addEventListener('DOMContentLoaded', initChat);
})();