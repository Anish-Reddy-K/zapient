/**
 * My AI Agents Module
 * Handles displaying and managing AI agents
 */

// Immediately invoked function expression (IIFE) to avoid polluting the global namespace
(function() {
    // DOM Elements
    const agentsGrid = document.getElementById('agentsGrid');
    const noAgentsText = document.getElementById('noAgentsText');
    
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
        // Clear the existing grid
        agentsGrid.innerHTML = '';
        
        // Fetch agents from the server
        fetch('/api/agents')
            .then(response => response.json())
            .then(data => {
                if (!data.agents || data.agents.length === 0) {
                    // Show the no agents message
                    noAgentsText.style.display = 'block';
                    
                    // Add the "Create New Agent" tile at the end
                    const createNewTile = createNewAgentTile();
                    agentsGrid.appendChild(createNewTile);
                    return;
                }
                
                // Hide the no agents message
                noAgentsText.style.display = 'none';
                
                // Sort agents chronologically - newest first
                const sortedAgents = data.agents.sort((a, b) => {
                    const dateA = new Date(a.createdAt);
                    const dateB = new Date(b.createdAt);
                    return dateB - dateA; // Newest first
                });
                
                // Display the agents
                displayAgents(sortedAgents);
                
                // Add the "Create New Agent" tile at the end
                const createNewTile = createNewAgentTile();
                agentsGrid.appendChild(createNewTile);
            })
            .catch(error => {
                console.error('Error loading agents:', error);
                // Show the no agents message
                noAgentsText.style.display = 'block';
                
                // Add the "Create New Agent" tile at the end
                const createNewTile = createNewAgentTile();
                agentsGrid.appendChild(createNewTile);
            });
    }
    
    /**
     * Display the agents in the UI
     * @param {Array} agents - The agents to display
     */
    function displayAgents(agents) {
        // Iterate through the agents and create tiles
        agents.forEach(agent => {
            // Create the agent tile
            const agentTile = document.createElement('div');
            agentTile.className = 'agent-tile';
            agentTile.innerHTML = `
                <div class="agent-content">
                    <h2 class="agent-title">${agent.name}</h2>
                    <p class="agent-date">Created: ${formatDate(agent.createdAt)}</p>
                </div>
                <div class="agent-actions">
                    <button class="agent-button interact-btn" data-agent-name="${agent.name}">
                        <i class="fa-solid fa-message"></i> Interact
                    </button>
                    <button class="agent-button manage-btn" data-agent-name="${agent.name}">
                        <i class="fas fa-cog"></i> Manage
                    </button>
                </div>
            `;
            
            // Add event listeners to buttons
            const interactBtn = agentTile.querySelector('.interact-btn');
            interactBtn.addEventListener('click', function() {
                // In a real app, this would navigate to an interaction page
                alert(`Interaction functionality for "${agent.name}" is coming soon!`);
            });
            
            const manageBtn = agentTile.querySelector('.manage-btn');
            manageBtn.addEventListener('click', function() {
                // Redirect to manage page with agent name as parameter
                window.location.href = `/manage/${encodeURIComponent(agent.name)}`;
            });
            
            // Add the tile to the grid
            agentsGrid.appendChild(agentTile);
        });
    }
    
    /**
     * Create the "Create New Agent" tile
     * @returns {HTMLElement} The create new agent tile
     */
    function createNewAgentTile() {
        const createTile = document.createElement('a');
        createTile.href = '/config';
        createTile.className = 'create-tile';
        createTile.innerHTML = `
            <div class="create-content">
                <div class="create-icon">
                    <i class="fas fa-plus"></i>
                </div>
                <h3 class="create-title">Add New AI Agent</h3>
                <p class="create-subtitle">Create a custom AI agent for your needs</p>
            </div>
        `;
        
        return createTile;
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
    
    // Initialize the my-agents page when DOM is loaded
    document.addEventListener('DOMContentLoaded', initMyAgents);
})();