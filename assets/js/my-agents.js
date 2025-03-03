/**
 * My AI Agents Module
 * Handles displaying and managing AI agents
 */

// Immediately invoked function expression (IIFE) to avoid polluting the global namespace
(function() {
    // DOM Elements
    const agentsContainer = document.getElementById('agentsContainer');
    
    /**
     * Initialize the my-agents page
     */
    function initMyAgents() {
        loadAgents();
    }
    
    /**
     * Load and display the agents
     */
    function loadAgents() {
        try {
            // Get the agents from localStorage
            const agentsFolder = JSON.parse(localStorage.getItem('agentsFolder'));
            
            if (!agentsFolder || !agentsFolder.agents || Object.keys(agentsFolder.agents).length === 0) {
                showNoAgents();
                return;
            }
            
            // Display the agents
            displayAgents(agentsFolder.agents);
        } catch (error) {
            console.error('Error loading agents:', error);
            showNoAgents();
        }
    }
    
    /**
     * Display the agents in the UI
     * @param {Object} agents - The agents to display
     */
    function displayAgents(agents) {
        // Create a grid to hold the agent cards
        const agentsGrid = document.createElement('div');
        agentsGrid.className = 'agents-grid';
        
        // Iterate through the agents and create cards
        Object.values(agents).forEach(agent => {
            // Parse the agent config
            const config = JSON.parse(agent.configFile.content);
            
            // Create the agent card
            const agentCard = document.createElement('div');
            agentCard.className = 'agent-card';
            agentCard.innerHTML = `
                <div class="agent-header">
                    <h2 class="agent-title">${config.name}</h2>
                    <p class="agent-subtitle">Created: ${formatDate(config.createdAt)}</p>
                </div>
                <div class="agent-body">
                    <p class="agent-description">${truncateText(config.persona, 150)}</p>
                    ${agent.files.length > 0 ? `
                    <div class="agent-files">
                        <p class="files-title">Attached Files:</p>
                        ${agent.files.map(file => `
                            <span class="file-badge"><i class="fas fa-file"></i> ${file.name}</span>
                        `).join('')}
                    </div>
                    ` : ''}
                </div>
                <div class="agent-actions">
                    <button class="agent-button manage-btn" data-agent-id="${agent.id}">Manage</button>
                </div>
            `;
            
            // Add event listener to manage button
            const manageBtn = agentCard.querySelector('.manage-btn');
            manageBtn.addEventListener('click', function() {
                // In a real app, this would navigate to a management page
                alert(`Management functionality for "${config.name}" is coming soon!`);
            });
            
            // Add the card to the grid
            agentsGrid.appendChild(agentCard);
        });
        
        // Add the grid to the container
        agentsContainer.innerHTML = '';
        agentsContainer.appendChild(agentsGrid);
    }
    
    /**
     * Show a message when there are no agents
     */
    function showNoAgents() {
        const noAgentsEl = document.createElement('div');
        noAgentsEl.className = 'no-agents';
        noAgentsEl.innerHTML = `
            <div class="no-agents-icon">
                <i class="fas fa-robot"></i>
            </div>
            <p class="no-agents-text">You haven't created any AI agents yet</p>
            <a href="config.html" class="create-new-btn">
                <i class="fas fa-plus"></i> Create Your First Agent
            </a>
        `;
        
        agentsContainer.innerHTML = '';
        agentsContainer.appendChild(noAgentsEl);
    }
    
    /**
     * Format a date string
     * @param {string} dateString - The ISO date string to format
     * @returns {string} The formatted date
     */
    function formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    }
    
    /**
     * Truncate text to a specified length and add ellipsis
     * @param {string} text - The text to truncate
     * @param {number} maxLength - The maximum length
     * @returns {string} The truncated text
     */
    function truncateText(text, maxLength) {
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }
    
    // Initialize the my-agents page when DOM is loaded
    document.addEventListener('DOMContentLoaded', initMyAgents);
})();