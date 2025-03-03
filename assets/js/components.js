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
                    <img src="../assets/images/logo.png" alt="Logo" class="sidebar-logo">
                </div>
                
                <nav class="sidebar-nav">
                    <ul>
                        <li class="nav-item" id="nav-ai-hub">
                            <a href="dashboard.html" class="nav-link">
                                <i class="fas fa-rocket nav-icon"></i>
                                <span class="nav-text">AI Hub</span>
                            </a>
                        </li>
                        <li class="nav-item" id="nav-my-agents">
                            <a href="my-agents.html" class="nav-link">
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
    }
    
    /**
     * Load the header component with user menu
     */
    function loadHeader() {
        const headerContainer = document.getElementById('header-container');
        if (!headerContainer) return;
        
        headerContainer.innerHTML = `
            <div class="content-header">
                <div class="user-menu">
                    <span class="username" id="currentUsername">User</span>
                    <button class="logout-btn" onclick="app.logout()">Log Out</button>
                </div>
            </div>
        `;
        
        // Set current username
        const currentUser = sessionStorage.getItem('currentUser');
        if (currentUser) {
            document.getElementById('currentUsername').textContent = currentUser;
        }
    }
    
    /**
     * Set up event listeners for component interactions
     */
    function setupComponentEvents() {
        // Sidebar collapse functionality
        const sidebar = document.getElementById('sidebar');
        const collapseBtn = document.getElementById('collapse-btn');
        
        if (sidebar && collapseBtn) {
            const sidebarLogo = sidebar.querySelector('.sidebar-logo');
            
            collapseBtn.addEventListener('click', function() {
                sidebar.classList.toggle('collapsed');
                
                // Change the logo image
                if (sidebarLogo) {
                    if (sidebar.classList.contains('collapsed')) {
                        sidebarLogo.src = '../assets/images/logo_small.png';
                    } else {
                        sidebarLogo.src = '../assets/images/logo.png';
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
        if (currentPath.includes('dashboard.html')) {
            document.getElementById('nav-ai-hub').classList.add('active');
        } else if (currentPath.includes('my-agents.html')) {
            document.getElementById('nav-my-agents').classList.add('active');
        }
        
        // Config page is also considered part of AI Hub
        if (currentPath.includes('config.html')) {
            document.getElementById('nav-ai-hub').classList.add('active');
        }
    }
    
    // Initialize components when DOM is loaded
    document.addEventListener('DOMContentLoaded', initComponents);
})();