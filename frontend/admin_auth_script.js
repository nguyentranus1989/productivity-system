<script>
// Admin Authentication System
(function() {
    const API_BASE = '/api';
    let adminToken = localStorage.getItem('adminToken');
    
    // Check if user is logged in on page load
    window.addEventListener('DOMContentLoaded', function() {
        checkAdminAuth();
    });
    
    async function checkAdminAuth() {
        if (!adminToken) {
            showLoginOverlay();
            return;
        }
        
        try {
            const response = await fetch(`${API_BASE}/admin/verify`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ token: adminToken })
            });
            
            const data = await response.json();
            
            if (data.success) {
                hideLoginOverlay();
                document.getElementById('adminLogoutBtn').style.display = 'block';
            } else {
                localStorage.removeItem('adminToken');
                showLoginOverlay();
            }
        } catch (error) {
            console.error('Auth check failed:', error);
            showLoginOverlay();
        }
    }
    
    function showLoginOverlay() {
        document.getElementById('adminLoginOverlay').style.display = 'flex';
    }
    
    function hideLoginOverlay() {
        document.getElementById('adminLoginOverlay').style.display = 'none';
    }
    
    // Handle login form submission
    document.getElementById('adminLoginForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const username = document.getElementById('adminUsername').value;
        const password = document.getElementById('adminPassword').value;
        const remember = document.getElementById('rememberAdmin').checked;
        
        // Show loading state
        document.getElementById('loginText').style.display = 'none';
        document.getElementById('loginSpinner').style.display = 'inline';
        document.getElementById('adminLoginBtn').disabled = true;
        document.getElementById('loginError').style.display = 'none';
        
        try {
            const response = await fetch(`${API_BASE}/admin/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });
            
            const data = await response.json();
            
            if (data.success) {
                adminToken = data.token;
                if (remember) {
                    localStorage.setItem('adminToken', adminToken);
                } else {
                    sessionStorage.setItem('adminToken', adminToken);
                }
                
                hideLoginOverlay();
                document.getElementById('adminLogoutBtn').style.display = 'block';
                
                // Optionally reload page to refresh data
                location.reload();
            } else {
                document.getElementById('loginError').textContent = data.message || 'Login failed';
                document.getElementById('loginError').style.display = 'block';
            }
        } catch (error) {
            document.getElementById('loginError').textContent = 'Connection error. Please try again.';
            document.getElementById('loginError').style.display = 'block';
        } finally {
            document.getElementById('loginText').style.display = 'inline';
            document.getElementById('loginSpinner').style.display = 'none';
            document.getElementById('adminLoginBtn').disabled = false;
        }
    });
    
    // Logout function
    window.logoutAdmin = async function() {
        if (!confirm('Are you sure you want to logout?')) return;
        
        try {
            await fetch(`${API_BASE}/admin/logout`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ token: adminToken })
            });
        } catch (error) {
            console.error('Logout error:', error);
        }
        
        localStorage.removeItem('adminToken');
        sessionStorage.removeItem('adminToken');
        adminToken = null;
        location.reload();
    };
    
    // Make token available for API calls
    window.getAdminToken = function() {
        return adminToken || localStorage.getItem('adminToken') || sessionStorage.getItem('adminToken');
    };
})();
</script>
