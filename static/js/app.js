/**
 * Main Application Module
 * Handles core functionality for the Document AI Assistant with Flask backend
 */

// Immediately invoked function expression (IIFE) to avoid polluting the global namespace
(function() {
    // Application Constants
    const APP_NAME = 'Document AI Assistant';
    const APP_VERSION = '0.2.0';
    
    /**
     * Initialize the application
     */
    function initApp() {
        console.log(`${APP_NAME} v${APP_VERSION} initialized`);
    }
    
    /**
     * Log out the current user
     */
    function logout() {
        // Redirect to the Flask logout route
        window.location.href = '/logout';
    }
    
    // Expose public methods
    window.app = {
        logout: logout
    };
    
    // Initialize application when DOM is loaded
    document.addEventListener('DOMContentLoaded', initApp);
})();