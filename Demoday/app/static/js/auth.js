document.addEventListener('DOMContentLoaded', function() {
    const tokenDisplay = document.getElementById('token-display');
    const loginBtn = document.getElementById('loginBtn');
    const logoutBtn = document.getElementById('logoutBtn');
    const loginForm = document.getElementById('loginForm');

    function updateAuthUI(hasToken) {
        if (hasToken) {
            tokenDisplay.classList.remove('d-none');
            loginBtn.classList.add('d-none');
            logoutBtn.classList.remove('d-none');
        } else {
            tokenDisplay.classList.add('d-none');
            loginBtn.classList.remove('d-none');
            logoutBtn.classList.add('d-none');
        }
    }

    function checkToken() {
        const token = localStorage.getItem('jwt_token');
        updateAuthUI(!!token);
    }

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        try {
            const response = await fetch('/api/v1/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    email: document.getElementById('loginEmail').value,
                    password: document.getElementById('loginPassword').value
                })
            });
            
            const data = await response.json();
            if (response.ok) {
                localStorage.setItem('jwt_token', data.token);
                updateAuthUI(true);
                bootstrap.Modal.getInstance(document.getElementById('loginModal')).hide();
                alert('Login successful!');
            } else {
                throw new Error(data.message);
            }
        } catch (error) {
            alert('Login failed: ' + error.message);
        }
    });

    logoutBtn.addEventListener('click', () => {
        localStorage.removeItem('jwt_token');
        updateAuthUI(false);
        alert('Logged out successfully!');
    });

    // Check token on page load
    checkToken();
});