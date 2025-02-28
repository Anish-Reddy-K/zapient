/**
 * Main Application Module
 * Handles core functionality for the Document AI Assistant
 */

// Immediately invoked function expression (IIFE) to avoid polluting the global namespace
(function() {
    // Application Constants
    const APP_NAME = 'Document AI Assistant';
    const APP_VERSION = '0.1.0';
    
    // DOM Elements - will be populated when specific pages load
    let currentUser = null;
    
    /**
     * Initialize the application
     */
    function initApp() {
        console.log(`${APP_NAME} v${APP_VERSION} initialized`);
        checkAuth();
    }
    
    /**
     * Check if user is authenticated
     * Redirects to login if not authenticated
     */
    function checkAuth() {
        currentUser = sessionStorage.getItem('currentUser');
        
        if (!currentUser && !window.location.pathname.includes('login.html')) {
            window.location.href = 'login.html';
            return false;
        }
        
        return true;
    }
    
    /**
     * Log out the current user
     */
    function logout() {
        sessionStorage.removeItem('currentUser');
        window.location.href = 'login.html';
    }
    
    // Expose public methods
    window.app = {
        logout: logout
    };
    
    // Initialize application when DOM is loaded
    document.addEventListener('DOMContentLoaded', initApp);
})();