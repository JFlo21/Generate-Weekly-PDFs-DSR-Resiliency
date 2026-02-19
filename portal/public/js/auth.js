(function () {
  'use strict';

  const form = document.getElementById('loginForm');
  const errorMsg = document.getElementById('errorMsg');
  const loginBtn = document.getElementById('loginBtn');

  // Check if already authenticated
  fetch('/auth/session')
    .then(r => r.json())
    .then(data => { if (data.authenticated) window.location.href = '/dashboard'; })
    .catch(() => {});

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorMsg.textContent = '';
    loginBtn.disabled = true;
    loginBtn.textContent = 'Signing in…';

    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;

    try {
      const res = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();

      if (res.ok && data.success) {
        window.location.href = '/dashboard';
      } else {
        errorMsg.textContent = data.error || 'Login failed';
      }
    } catch {
      errorMsg.textContent = 'Network error. Please try again.';
    } finally {
      loginBtn.disabled = false;
      loginBtn.textContent = 'Sign In';
    }
  });
})();
