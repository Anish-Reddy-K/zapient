/**
 * Components Module
 * Handles shared UI components across the application
 */

// Immediately invoked function expression (IIFE) to avoid polluting the global namespace
(function() {
    /**
     * Initialize components when DOM is loaded
     */
    function initComponents() {
        loadSidebar();
        loadHeader();
        setupComponentEvents();
    }
    
    /**
     * Load the sidebar navigation component
     */
    function loadSidebar() {
        const sidebarContainer = document.getElementById('sidebar-container');
        if (!sidebarContainer) return;
        
        sidebarContainer.innerHTML = `
            <aside class="sidebar" id="sidebar">
                <div class="sidebar-header">
                    <img src="/static/images/logo.png" alt="Logo" class="sidebar-logo">
                </div>
                
                <nav class="sidebar-nav">
                    <ul>
                        <li class="nav-item" id="nav-ai-hub">
                            <a href="/dashboard" class="nav-link">
                                <i class="fas fa-rocket nav-icon"></i>
                                <span class="nav-text">AI Hub</span>
                            </a>
                        </li>
                        <li class="nav-item" id="nav-my-agents">
                            <a href="/my-agents" class="nav-link">
                                <i class="fas fa-robot nav-icon"></i>
                                <span class="nav-text">My AI Agents</span>
                            </a>
                        </li>
                    </ul>
                </nav>
                
                <button id="collapse-btn" class="collapse-btn">
                    <i class="fas fa-chevron-left"></i>
                </button>
            </aside>
        `;
        
        // Set active nav item based on current page
        setActiveNavItem();
        
        // Apply saved sidebar collapse state
        applySavedSidebarState();
    }
    
    /**
     * Apply saved sidebar collapse state from localStorage
     */
    function applySavedSidebarState() {
        const sidebar = document.getElementById('sidebar');
        const collapseBtn = document.getElementById('collapse-btn');
        const sidebarLogo = sidebar.querySelector('.sidebar-logo');
        
        // Get saved state from localStorage
        const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
        
        if (isCollapsed && sidebar) {
            // Apply collapsed class
            sidebar.classList.add('collapsed');
            
            // Update logo
            if (sidebarLogo) {
                sidebarLogo.src = '/static/images/logo_small.png';
            }
            
            // Update button icon
            if (collapseBtn) {
                const icon = collapseBtn.querySelector('i');
                if (icon) {
                    icon.classList.remove('fa-chevron-left');
                    icon.classList.add('fa-chevron-right');
                }
            }
        }
    }
    
    /**
     * Load the header component with user menu
     */
    function loadHeader() {
        const headerContainer = document.getElementById('header-container');
        if (!headerContainer) return;
        
        // Fetch the current username
        fetch('/api/current-user')
            .then(response => response.json())
            .then(data => {
                headerContainer.innerHTML = `
                    <div class="content-header">
                        <div class="user-menu">
                            <span class="username" id="currentUsername">${data.username || 'User'}</span>
                            <button class="logout-btn" onclick="app.logout()">Log Out</button>
                        </div>
                    </div>
                `;
            })
            .catch(error => {
                console.error('Error fetching current user:', error);
                headerContainer.innerHTML = `
                    <div class="content-header">
                        <div class="user-menu">
                            <span class="username" id="currentUsername">User</span>
                            <button class="logout-btn" onclick="app.logout()">Log Out</button>
                        </div>
                    </div>
                `;
            });
    }
    
    /**
     * Set up event listeners for component interactions
     */
    function setupComponentEvents() {
        // Wait for sidebar to be loaded
        setTimeout(() => {
            // Sidebar collapse functionality
            const sidebar = document.getElementById('sidebar');
            const collapseBtn = document.getElementById('collapse-btn');
            
            if (sidebar && collapseBtn) {
                const sidebarLogo = sidebar.querySelector('.sidebar-logo');
                
                collapseBtn.addEventListener('click', function() {
                    const isCollapsed = sidebar.classList.toggle('collapsed');
                    
                    // Save state to localStorage
                    localStorage.setItem('sidebarCollapsed', isCollapsed);
                    
                    // Change the logo image
                    if (sidebarLogo) {
                        if (sidebar.classList.contains('collapsed')) {
                            sidebarLogo.src = '/static/images/logo_small.png';
                        } else {
                            sidebarLogo.src = '/static/images/logo.png';
                        }
                    }
                    
                    // Update the button icon
                    const icon = collapseBtn.querySelector('i');
                    if (icon) {
                        if (sidebar.classList.contains('collapsed')) {
                            icon.classList.remove('fa-chevron-left');
                            icon.classList.add('fa-chevron-right');
                        } else {
                            icon.classList.remove('fa-chevron-right');
                            icon.classList.add('fa-chevron-left');
                        }
                    }
                });
            }
        }, 100); // Small delay to ensure sidebar has loaded
    }
    
    /**
     * Set the active navigation item based on current page
     */
    function setActiveNavItem() {
        const currentPath = window.location.pathname;
        
        // Remove active class from all nav items
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });
        
        // Set active class based on current path
        if (currentPath.includes('/dashboard')) {
            document.getElementById('nav-ai-hub').classList.add('active');
        } else if (currentPath.includes('/my-agents')) {
            document.getElementById('nav-my-agents').classList.add('active');
        }
        
        // Config and manage pages are also considered part of AI Hub
        if (currentPath.includes('/config') || currentPath.includes('/manage')) {
            document.getElementById('nav-ai-hub').classList.add('active');
        }
    }
    
    // Add an API endpoint to get current user
    fetch('/api/current-user', { method: 'HEAD' })
        .catch(() => {
            console.log('API endpoint for current user not available');
        });
    
    // Initialize components when DOM is loaded
    document.addEventListener('DOMContentLoaded', initComponents);
})();