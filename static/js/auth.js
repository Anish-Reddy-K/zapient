/**
 * Authentication Module
 * Handles user authentication for the Document AI Assistant with Flask backend
 */

// Immediately invoked function expression (IIFE) to avoid polluting the global namespace
(function() {
    // DOM Elements
    const loginForm = document.getElementById("loginForm");
    const errorMessage = document.getElementById("errorMessage");
    
    /**
     * Initialize the authentication functionality
     */
    function initAuth() {
        if (loginForm) {
            setupLoginForm();
        }
    }
    
    /**
     * Set up the login form submission
     */
    function setupLoginForm() {
        loginForm.addEventListener("submit", function(event) {
            event.preventDefault();
            
            const username = document.getElementById("username").value;
            const password = document.getElementById("password").value;
            
            // Submit the form using fetch to the Flask backend
            fetch('/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: new URLSearchParams({
                    'username': username,
                    'password': password
                })
            })
            .then(response => {
                if (response.redirected) {
                    // If the response is a redirect, follow it
                    window.location.href = response.url;
                } else {
                    // If not redirected, there was an error
                    return response.text().then(text => {
                        // Show the error message
                        showErrorMessage();
                        return Promise.reject(new Error('Login failed'));
                    });
                }
            })
            .catch(error => {
                console.error('Error during login:', error);
                showErrorMessage();
            });
        });
        
        // Hide error message when user starts typing again
        document.getElementById("username").addEventListener("input", function() {
            hideErrorMessage();
        });
        
        document.getElementById("password").addEventListener("input", function() {
            hideErrorMessage();
        });
    }
    
    /**
     * Show the error message
     */
    function showErrorMessage() {
        errorMessage.style.visibility = "visible";
        errorMessage.style.opacity = "1";
        
        // Clear password field
        document.getElementById("password").value = "";
        
        // Focus on password field
        document.getElementById("password").focus();
    }
    
    /**
     * Hide the error message
     */
    function hideErrorMessage() {
        errorMessage.style.visibility = "hidden";
        errorMessage.style.opacity = "0";
    }
    
    // Initialize the authentication functionality when DOM is loaded
    document.addEventListener("DOMContentLoaded", initAuth);
})();