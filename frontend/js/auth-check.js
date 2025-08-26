// auth-check.js - Authentication Protection Script
// Add this to all protected pages to enforce login

(function() {
    'use strict';
    // Check if running locally - BYPASS AUTH FOR DEVELOPMENT
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        console.log('Auth disabled for local development');
        // Set fake admin session
        sessionStorage.setItem('adminToken', 'local-dev-token');
        sessionStorage.setItem('userRole', 'admin');
        window.currentUserRole = 'admin';
        // Make page visible
        document.documentElement.style.visibility = 'visible';
        document.documentElement.style.opacity = '1';
        return; // Exit early - skip all auth checks
    }
    // Configuration
    const LOGIN_PAGE = '/login.html';
    const SHOP_FLOOR_PIN_EXPIRY = 180 * 24 * 60 * 60 * 1000; // 180 days
    
    // Get current page
    const currentPage = window.location.pathname.toLowerCase();
    
    // Define page access rules
    const pageAccessRules = {
        '/admin.html': ['admin', 'manager'],
        '/manager.html': ['admin', 'manager'],
        '/employee.html': ['admin', 'manager', 'employee'],
        '/shop-floor.html': ['admin', 'manager', 'employee', 'shopfloor'],
        '/index.html': ['admin', 'manager'],  // Dashboard selector
        '/dashboard-selector.html': ['admin', 'manager']
    };
    
    // Function to get user role from tokens
    function getUserRole() {
        // Check admin token
        const adminToken = localStorage.getItem('adminToken') || sessionStorage.getItem('adminToken');
        if (adminToken) {
            return 'admin';
        }
        
        // Check employee token
        const employeeToken = localStorage.getItem('employeeToken') || sessionStorage.getItem('employeeToken');
        if (employeeToken) {
            return 'employee';
        }
        
        // Check shop floor token
        const shopfloorToken = localStorage.getItem('shopfloorToken') || sessionStorage.getItem('shopfloorToken');
        if (shopfloorToken) {
            // Check if shop floor token is expired
            const expiry = localStorage.getItem('shopfloorExpiry');
            if (expiry && Date.now() < parseInt(expiry)) {
                return 'shopfloor';
            } else {
                // Expired - clear tokens
                localStorage.removeItem('shopfloorToken');
                localStorage.removeItem('shopfloorExpiry');
            }
        }
        
        return null;
    }
    
    // Function to check if user has access to current page
    function hasAccess(userRole, page) {
        const allowedRoles = pageAccessRules[page];
        if (!allowedRoles) {
            // Page not in rules - allow access (for non-protected pages)
            return true;
        }
        return allowedRoles.includes(userRole);
    }
    
    // Function to verify token with backend (optional - for extra security)
    async function verifyToken(role) {
        if (role === 'shopfloor') {
            // Shop floor doesn't need backend verification
            return true;
        }
        
        try {
            const endpoint = role === 'admin' ? '/api/admin/verify' : '/api/employee/verify';
            const token = role === 'admin' 
                ? (localStorage.getItem('adminToken') || sessionStorage.getItem('adminToken'))
                : (localStorage.getItem('employeeToken') || sessionStorage.getItem('employeeToken'));
            
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ token })
            });
            
            const data = await response.json();
            return data.success;
        } catch (error) {
            console.error('Token verification failed:', error);
            return false;
        }
    }
    
    // Function to redirect to login
    function redirectToLogin() {
        // Save the page they were trying to access
        sessionStorage.setItem('redirectAfterLogin', currentPage);
        window.location.href = LOGIN_PAGE;
    }
    
    // Function to show access denied message
    function showAccessDenied(userRole) {
        document.body.innerHTML = `
            <div style="display: flex; justify-content: center; align-items: center; height: 100vh; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                <div style="background: white; padding: 40px; border-radius: 10px; text-align: center; max-width: 400px;">
                    <h2 style="color: #e74c3c; margin-bottom: 20px;">Access Denied</h2>
                    <p style="color: #333; margin-bottom: 30px;">
                        You don't have permission to access this page.
                        ${userRole === 'employee' ? 'This page is for managers only.' : ''}
                        ${userRole === 'shopfloor' ? 'This page is for employees and managers only.' : ''}
                    </p>
                    <button onclick="window.location.href='${userRole === 'employee' ? '/employee.html' : '/shop-floor.html'}'" 
                            style="padding: 10px 30px; background: #667eea; color: white; border: none; border-radius: 5px; cursor: pointer;">
                        Go to Your Dashboard
                    </button>
                    <button onclick="logout()" 
                            style="padding: 10px 30px; background: #e74c3c; color: white; border: none; border-radius: 5px; cursor: pointer; margin-left: 10px;">
                        Logout
                    </button>
                </div>
            </div>
        `;
    }
    
    // Logout function
    window.logout = function() {
        // Clear all tokens
        localStorage.removeItem('adminToken');
        localStorage.removeItem('adminUser');
        localStorage.removeItem('employeeToken');
        localStorage.removeItem('employeeData');
        localStorage.removeItem('shopfloorToken');
        localStorage.removeItem('shopfloorExpiry');
        
        sessionStorage.clear();
        
        // Redirect to login
        window.location.href = LOGIN_PAGE;
    }
    
    // Add logout button to page (optional)
    function addLogoutButton(role) {
        // Don't add logout button to shop floor display
        if (role === 'shopfloor' && currentPage === '/shop-floor.html') {
            return;
        }
        
        const logoutBtn = document.createElement('button');
        logoutBtn.innerHTML = '🚪 Logout';
        logoutBtn.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            background: #e74c3c;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-weight: 500;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        `;
        logoutBtn.onclick = logout;
        
        // Add to page after DOM loads
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                document.body.appendChild(logoutBtn);
            });
        } else {
            document.body.appendChild(logoutBtn);
        }
    }
    
    // Check for redirect after login
    function checkRedirect() {
        const redirectTo = sessionStorage.getItem('redirectAfterLogin');
        if (redirectTo && currentPage === LOGIN_PAGE) {
            sessionStorage.removeItem('redirectAfterLogin');
            // This will be handled by login.html after successful login
        }
    }
    
    // Main authentication check
    function checkAuthentication() {
        // Skip check for login page
        if (currentPage === LOGIN_PAGE || currentPage === '/login.html') {
            return;
        }
        
        const userRole = getUserRole();
        
        // No token found - redirect to login
        if (!userRole) {
            redirectToLogin();
            return;
        }
        
        // Check if user has access to this page
        if (!hasAccess(userRole, currentPage)) {
            showAccessDenied(userRole);
            return;
        }
        
        // Optional: Verify token with backend (uncomment if needed)
        // verifyToken(userRole).then(isValid => {
        //     if (!isValid) {
        //         redirectToLogin();
        //     } else {
        //         addLogoutButton(userRole);
        //     }
        // });
        
        // Add logout button
        addLogoutButton(userRole);
        
        // Store current user role for page use
        window.currentUserRole = userRole;

        // Show page after successful authentication
        setTimeout(function() {
            console.log("Attempting to show page...");
            document.documentElement.style.visibility = "visible";
            document.documentElement.style.opacity = "1";
            console.log("Page visibility restored!");
        }, 50);
        
        // For employee page, store employee data
        if (currentPage === '/employee.html' && userRole === 'employee') {
            const employeeData = localStorage.getItem('employeeData') || sessionStorage.getItem('employeeData');
            if (employeeData) {
                window.currentEmployee = JSON.parse(employeeData);
            }
        }
    }
    
    // Run authentication check when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', checkAuthentication);
    } else {
        checkAuthentication();
    }
    
    // Also check on page visibility change (in case token expires while page is open)
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            const userRole = getUserRole();
            if (!userRole && currentPage !== LOGIN_PAGE) {
                redirectToLogin();
            }
        }
    });
    
})();
