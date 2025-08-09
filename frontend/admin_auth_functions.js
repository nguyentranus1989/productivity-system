<script>
// Admin Authentication Functions - Global Scope
function doAdminLogin() {
    const username = document.getElementById('adminUsername').value;
    const password = document.getElementById('adminPassword').value;
    
    fetch('/api/admin/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username: username, password: password})
    })
    .then(r => r.json())
    .then(data => {
        if(data.success) {
            localStorage.setItem('adminToken', data.token);
            document.getElementById('adminLoginOverlay').style.display = 'none';
            const logoutBtn = document.getElementById('adminLogoutBtn2') || document.getElementById('adminLogoutBtn');
            if(logoutBtn) logoutBtn.style.display = 'inline-block';
        } else {
            alert('Login failed: ' + (data.message || 'Invalid credentials'));
        }
    })
    .catch(err => {
        alert('Connection error');
        console.error(err);
    });
}

function doAdminLogout() {
    if(confirm('Are you sure you want to logout?')) {
        localStorage.removeItem('adminToken');
        location.reload();
    }
}

function checkAdminAuth() {
    const token = localStorage.getItem('adminToken');
    if(token) {
        document.getElementById('adminLoginOverlay').style.display = 'none';
        const logoutBtn = document.getElementById('adminLogoutBtn2') || document.getElementById('adminLogoutBtn');
        if(logoutBtn) logoutBtn.style.display = 'inline-block';
    } else {
        document.getElementById('adminLoginOverlay').style.display = 'flex';
        const logoutBtn = document.getElementById('adminLogoutBtn2') || document.getElementById('adminLogoutBtn');
        if(logoutBtn) logoutBtn.style.display = 'none';
    }
}

// Check auth on page load
document.addEventListener('DOMContentLoaded', function() {
    checkAdminAuth();
});
</script>
