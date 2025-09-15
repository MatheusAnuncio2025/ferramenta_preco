/* ===== app.js – utilitários globais, navbar, auth ===== */

/* ---------- Toasts ---------- */
function ensureToastContainer() {
  if (!document.getElementById("toast-container")) {
    const c = document.createElement("div");
    c.id = "toast-container";
    c.className = "toast-container";
    document.body.appendChild(c);
  }
}
function showToast(message, type = "success", ms = 3000) {
  ensureToastContainer();
  const c = document.getElementById("toast-container");
  const t = document.createElement("div");
  t.className = `toast ${type}`;
  t.textContent = message;
  c.appendChild(t);
  setTimeout(() => t.classList.add("show"), 10);
  setTimeout(() => {
    t.classList.remove("show");
    setTimeout(() => t.remove(), 300);
  }, ms);
}

/* ---------- Modal simples ---------- */
function showAppModal({ title, bodyHtml, buttons = [] }) {
  let overlay = document.getElementById("app-modal");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "app-modal";
    overlay.className = "modal-overlay";
    document.body.appendChild(overlay);
  }
  overlay.innerHTML = `
    <div class="modal">
      <div class="modal-header"><h3>${title || ""}</h3></div>
      <div class="modal-body">${bodyHtml || ""}</div>
      <div class="modal-footer" id="app-modal-actions"></div>
    </div>`;
  const actions = overlay.querySelector("#app-modal-actions");
  (buttons || []).forEach((b) => {
    const btn = document.createElement("button");
    btn.className = `app-button ${b.class || ""}`;
    btn.textContent = b.text || "OK";
    btn.addEventListener("click", () => {
      if (typeof b.onClick === "function") b.onClick();
      overlay.classList.remove("show");
      setTimeout(() => (overlay.innerHTML = ""), 200);
    });
    actions.appendChild(btn);
  });
  overlay.classList.add("show");
}

/* ---------- Miscelânea ---------- */
function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
function formatCurrency(n) {
  const v = Number(n) || 0;
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

/* ---------- Fetch com tratamento padrão ---------- */
async function safeFetch(url, opts = {}) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || JSON.stringify(data);
    } catch {}
    throw new Error(`${res.status} ${detail}`);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json();
  return res.text();
}

/* ---------- Auth/Navbar ---------- */
function setupLogoutButton() {
  const btn = document.getElementById("logout-btn");
  if (btn) {
    btn.onclick = async () => {
      try {
        await safeFetch("/api/auth/logout", { method: "POST" });
      } catch {}
      window.location.href = "/";
    };
  }
}

function renderNavbar(auth) {
  // Containers esperados no header
  const nav = document.querySelector(".navbar-links") || document.getElementById("navbar-links");
  const authBox = document.getElementById("auth-container");
  const userInfo = document.getElementById("user-info");
  const pic = document.getElementById("profile-pic");

  if (authBox) authBox.classList.toggle("hidden", !auth?.authenticated);

  if (auth?.authenticated && auth?.user) {
    const u = auth.user;
    if (userInfo) userInfo.textContent = `Olá, ${u.name || u.email || "Usuário"}!`;
    if (pic && u.picture) pic.src = u.picture;

    // monta menu básico; adiciona itens admin se for admin
    const links = [
      { href: "/calculadora", text: "Calcular Preço" },
      { href: "/lista", text: "Consultar Precificações" },
      { href: "/configuracoes", text: "Configurações" },
      { href: "/perfil", text: "Meu Perfil" },
    ];
    if (u.is_admin) {
      links.splice(3, 0, { href: "/campanhas", text: "Campanhas" });
      links.splice(4, 0, { href: "/alertas", text: "Alertas" });
      links.push({ href: "/admin", text: "Admin" });
    }

    if (nav) {
      nav.innerHTML = "";
      links.forEach((l) => {
        const a = document.createElement("a");
        a.href = l.href;
        a.textContent = l.text;
        nav.appendChild(a);
      });
    }
  } else {
    if (nav) {
      nav.innerHTML = "";
      ["Login"].forEach((t) => {
        const a = document.createElement("a");
        a.href = "/login?action=login";
        a.textContent = t;
        nav.appendChild(a);
      });
    }
  }
}

async function checkAuthStatusAndUpdateNav() {
  try {
    const auth = await safeFetch("/api/auth/status");
    renderNavbar(auth);
    setupLogoutButton();
    return auth;
  } catch (e) {
    console.warn("Falha em /api/auth/status:", e.message);
    renderNavbar(null);
    return { authenticated: false };
  }
}

/* ---------- Bootstrap global ---------- */
document.addEventListener("DOMContentLoaded", () => {
  // Navbar status em todas as páginas
  checkAuthStatusAndUpdateNav();
});
