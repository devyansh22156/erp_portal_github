/**
 * ERP Portal Header & Authentication Utilities
 */
document.addEventListener('DOMContentLoaded', () => {
  const headerEl = document.getElementById('header');
  if (!headerEl) return;
  const isLoggedIn = !!localStorage.getItem('token');
  const user = getUser();
  let navLinks = '';

  if (isLoggedIn) {
    navLinks = `
      <a href="dashboard.html">Dashboard</a>
      ${user && user.role === 'owner' ? '<a href="manage-projects.html">Manage Projects</a>' : ''}
      <a href="#" id="logoutBtn">Logout</a>`;
  } else {
    navLinks = `<a href="index.html">Home</a>
                <a href="login.html">Login</a>
                <a href="register.html">Register</a>`;
  }

  const userInfo = isLoggedIn && user
    ? `<div class="user-info">
         <div class="user-profile">${user.name.charAt(0).toUpperCase()}</div>
         <span>${user.name}</span>
       </div>`
    : '';

  headerEl.innerHTML = `<header class="header">
                          <h1>ERP Portal</h1>
                          <nav>${navLinks}</nav>
                          ${userInfo}
                        </header>`;

  const logoutBtn = document.getElementById('logoutBtn');
  if (logoutBtn) logoutBtn.addEventListener('click', e => { e.preventDefault(); logout(); });
});

function getUser() {
  try { return JSON.parse(localStorage.getItem('user')); }
  catch { clearAuth(); return null; }
}

async function validateToken() {
  const token = localStorage.getItem('token');
  if (!token) return false;
  try {
    const res = await fetch('/api/me', { headers: { 'Authorization': `Bearer ${token}` } });
    return res.ok;
  } catch { return false; }
}

function protectRoute() {
  if (!localStorage.getItem('token')) { window.location = 'login.html'; return false; }
  return true;
}

function clearAuth() { localStorage.removeItem('token'); localStorage.removeItem('user'); }
function logout() { clearAuth(); window.location = 'login.html'; }