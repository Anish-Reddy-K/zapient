/**
 * Authentication Module
 * Handles user authentication for the Document AI Assistant
 */

// Immediately invoked function expression (IIFE) to avoid polluting the global namespace
(function() {
    // Preconfigured credentials for demonstration purposes
    const validCredentials = [
        { username: "admin", password: "admin" },
        { username: "test", password: "test" },
        { username: "tester1@example.com", password: "test123" },
        { username: "tester2@example.com", password: "test456" },
        { username: "demo@example.com", password: "demo789" },
        { username: "beta@example.com", password: "beta2025" }
    ];
    
    // DOM Elements
    const loginForm = document.getElementById("loginForm");
    const errorMessage = document.getElementById("errorMessage");
    
    /**
     * Authenticates a user against the valid credentials list
     * @param {string} username - The username to check
     * @param {string} password - The password to check
     * @returns {boolean} - Whether the authentication was successful
     */
    function authenticateUser(username, password) {
        const userFound = validCredentials.find(
            user => (user.username === username || user.username === username.toLowerCase()) && 
                    user.password === password
        );
        
        return !!userFound ? userFound : false;
    }
    
    /**
     * Handle successful login
     * @param {string} username - The authenticated username
     */
    function handleSuccessfulLogin(username) {
        // Store user information in session storage
        sessionStorage.setItem('currentUser', username);
        
        // Redirect to dashboard
        window.location.href = "dashboard.html";
    }
    
    /**
     * Handle failed login
     */
    function handleFailedLogin() {
        // Show error message
        errorMessage.style.visibility = "visible";
        errorMessage.style.opacity = "1";
        
        // Clear password field
        document.getElementById("password").value = "";
        
        // Focus on password field
        document.getElementById("password").focus();
    }
    
    // Check if user is already logged in
    function checkExistingSession() {
        const currentUser = sessionStorage.getItem('currentUser');
        
        if (currentUser && window.location.pathname.includes('login.html')) {
            window.location.href = "dashboard.html";
        }
    }
    
    // Event Listeners
    if (loginForm) {
        loginForm.addEventListener("submit", function(event) {
            event.preventDefault();
            
            const username = document.getElementById("username").value;
            const password = document.getElementById("password").value;
            
            const user = authenticateUser(username, password);
            
            if (user) {
                handleSuccessfulLogin(user.username);
            } else {
                handleFailedLogin();
            }
        });
        
        // Hide error message when user starts typing again
        document.getElementById("username").addEventListener("input", function() {
            errorMessage.style.visibility = "hidden";
            errorMessage.style.opacity = "0";
        });
        
        document.getElementById("password").addEventListener("input", function() {
            errorMessage.style.visibility = "hidden";
            errorMessage.style.opacity = "0";
        });
    }
    
    // Check for existing session on page load
    document.addEventListener("DOMContentLoaded", checkExistingSession);
})();