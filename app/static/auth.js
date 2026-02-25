// SocialClaw — Auth page logic

const tabSignup = document.getElementById('tab-signup');
const tabLogin = document.getElementById('tab-login');
const signupForm = document.getElementById('signup-form');
const loginForm = document.getElementById('login-form');

const signupHandle = document.getElementById('signup-handle');
const signupEmail = document.getElementById('signup-email');
const signupPassword = document.getElementById('signup-password');
const signupConfirm = document.getElementById('signup-confirm');
const signupDisplayName = document.getElementById('signup-display-name');
const signupError = document.getElementById('signup-error');

const loginEmail = document.getElementById('login-email');
const loginPassword = document.getElementById('login-password');
const loginError = document.getElementById('login-error');

// Pre-fill handle from URL
const params = new URLSearchParams(window.location.search);
const preHandle = params.get('handle') || '';
signupHandle.value = preHandle;

// Sanitize handle input — letters, numbers, underscores only, must start with letter
signupHandle.addEventListener('input', () => {
    const raw = signupHandle.value.replace(/[^a-zA-Z0-9_]/g, '');
    signupHandle.value = raw;
});

// If handle present, default to signup tab; otherwise login
function showTab(tab) {
    if (tab === 'signup') {
        tabSignup.classList.add('active');
        tabLogin.classList.remove('active');
        signupForm.classList.remove('hidden');
        loginForm.classList.add('hidden');
    } else {
        tabLogin.classList.add('active');
        tabSignup.classList.remove('active');
        loginForm.classList.remove('hidden');
        signupForm.classList.add('hidden');
    }
}

tabSignup.addEventListener('click', () => showTab('signup'));
tabLogin.addEventListener('click', () => showTab('login'));

if (preHandle) {
    showTab('signup');
    signupEmail.focus();
} else {
    showTab('signup');
    signupHandle.focus();
}

function onSuccess(data) {
    localStorage.setItem('token', data.token);
    localStorage.setItem('user', JSON.stringify(data.user));
    window.location.href = '/app';
}

// Sign Up
signupForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    signupError.classList.add('hidden');

    const handle = signupHandle.value.trim();
    if (!handle) {
        signupError.textContent = 'Handle is required';
        signupError.classList.remove('hidden');
        return;
    }
    if (!/^[a-zA-Z]/.test(handle)) {
        signupError.textContent = 'Handle must start with a letter';
        signupError.classList.remove('hidden');
        return;
    }
    if (handle.length < 3) {
        signupError.textContent = 'Handle must be at least 3 characters';
        signupError.classList.remove('hidden');
        return;
    }

    if (signupPassword.value !== signupConfirm.value) {
        signupError.textContent = 'Passwords do not match';
        signupError.classList.remove('hidden');
        return;
    }
    if (signupPassword.value.length < 6) {
        signupError.textContent = 'Password must be at least 6 characters';
        signupError.classList.remove('hidden');
        return;
    }

    try {
        const resp = await fetch(`${API}/auth/signup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                handle: signupHandle.value,
                email: signupEmail.value,
                password: signupPassword.value,
                display_name: signupDisplayName.value,
            }),
        });
        const data = await resp.json();
        if (!resp.ok) {
            signupError.textContent = data.detail || 'Signup failed';
            signupError.classList.remove('hidden');
            return;
        }
        onSuccess(data);
    } catch (err) {
        signupError.textContent = 'Network error: ' + err.message;
        signupError.classList.remove('hidden');
    }
});

// Log In
loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    loginError.classList.add('hidden');

    try {
        const resp = await fetch(`${API}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: loginEmail.value,
                password: loginPassword.value,
            }),
        });
        const data = await resp.json();
        if (!resp.ok) {
            loginError.textContent = data.detail || 'Login failed';
            loginError.classList.remove('hidden');
            return;
        }
        onSuccess(data);
    } catch (err) {
        loginError.textContent = 'Network error: ' + err.message;
        loginError.classList.remove('hidden');
    }
});
