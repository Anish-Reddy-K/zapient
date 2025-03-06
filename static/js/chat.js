/**
 * Chat Module
 * Handles chat functionality with AI agents
 */
(function() {
    // DOM Elements
    const chatMessages = document.getElementById('chatMessages');
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    const clearChatButton = document.getElementById('clearChatButton');

    // State variables
    let conversationId = null;
    let isWaitingForResponse = false;
    
    /**
     * Initialize the chat functionality
     */
    function initChat() {
        setupEventListeners();
        loadChatHistory();
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
            sendButton.disabled = messageInput.value.trim() === '' || isWaitingForResponse;
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
                
                isWaitingForResponse = false;
                sendButton.disabled = messageInput.value.trim() === '';
                scrollToBottom();
            }, 500);  // optional small delay
        })
        .catch(error => {
            console.error('Error sending message:', error);
            removeLoadingIndicator();
            appendErrorMessage();
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
        
        // Process the content (markdown and add sources at the bottom)
        let processedContent = processMessageContent(message.content);
        
        // Add sources section if available
        let sourcesHtml = '';
        if (message.sources && message.sources.length > 0) {
            sourcesHtml = createSourcesSection(message.sources);
        }
        
        messageElement.innerHTML = `
            <div class="message-content">
                <div class="markdown-content">${processedContent}</div>
                ${sourcesHtml}
            </div>
        `;
        chatMessages.appendChild(messageElement);
    }
    
    /**
     * Process message content to render markdown
     */
    function processMessageContent(content) {
        // Configure marked for better compatibility
        marked.setOptions({
            breaks: true,          // Add line breaks on single line breaks
            gfm: true,             // Use GitHub Flavored Markdown
            headerIds: false,      // Don't add ids to headings
            smartLists: true       // Use smarter list behavior
        });
        
        // Preprocess content to handle any whitespace issues
        let preprocessed = content.trim();
        
        // Ensure bullet points and numbered lists have proper spacing
        preprocessed = preprocessed.replace(/^(\s*[*-])\s*/gm, '* ');  // Fix bullet points
        preprocessed = preprocessed.replace(/^(\s*\d+\.)\s*/gm, '$1 '); // Fix numbered lists
        
        // Render markdown
        const renderedMarkdown = marked.parse(preprocessed);
        return DOMPurify.sanitize(renderedMarkdown);
    }
    
    /**
     * Create the sources section HTML
     */
    function createSourcesSection(sources) {
        if (!sources || sources.length === 0) {
            return '';
        }
        
        // Sort sources by file and page
        sources.sort((a, b) => {
            if (a.file === b.file) {
                return a.page - b.page;
            }
            return a.file.localeCompare(b.file);
        });
        
        // Create a unique list of sources (no duplicates)
        const uniqueSources = [];
        const seen = new Set();
        
        sources.forEach(source => {
            const key = `${source.file}_${source.page}`;
            if (!seen.has(key)) {
                seen.add(key);
                uniqueSources.push(source);
            }
        });
        
        // Format filenames to be shorter
        function formatFileName(fileName) {
            // Remove file extension
            const baseName = fileName.replace(/\.[^/.]+$/, "");
            // Truncate if too long
            return baseName.length > 15 ? baseName.substring(0, 12) + '...' : baseName;
        }
        
        // Create HTML for sources with requested format
        const sourceItems = uniqueSources.map(source => 
            `<li title="${escapeHTML(source.file)}">${formatFileName(escapeHTML(source.file))}, Page ${source.page}</li>`
        ).join('');
        
        return `
            <div class="sources-section">
                <h4>Sources:</h4>
                <ul class="sources-list">
                    ${sourceItems}
                </ul>
            </div>
        `;
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
        
        const errorMessage = {
            content: "## Error\n\nCould not process your request.",
            sources: [{ file: "Error.log", page: 1 }]
        };
        
        const processedContent = processMessageContent(errorMessage.content);
        const sourcesHtml = createSourcesSection(errorMessage.sources);
        
        messageElement.innerHTML = `
            <div class="message-content">
                <div class="markdown-content">${processedContent}</div>
                ${sourcesHtml}
            </div>
        `;
        
        chatMessages.appendChild(messageElement);
        scrollToBottom();
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