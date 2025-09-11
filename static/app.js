/**
 * app.js
 * Utilitários globais de autenticação, navegação e helpers de UI/fetch.
 *
 * Este arquivo NÃO duplica as funções de formatação/modais/toasts.
 * Use as utilidades de UI já definidas em `utils.js`:
 *   - showToast(message, type?)
 *   - showAppModal({ title, bodyHtml, buttons })
 *   - formatCurrency/parseCurrency/formatPercent/parsePercent
 */

(function () {
  // =========================
  // Estado global / usuário
  // =========================
  let AUTH_CACHE = null;

  // Compat: aceita tanto `authorized` quanto `autorizado`
  function isAuthorized(user) {
    if (!user) return false;
    if (typeof user.autorizado === "boolean") return user.autorizado;
    if (typeof user.authorized === "boolean") return user.authorized;
    // fallback para strings "true"/"false"
    if (typeof user.autorizado === "string") return user.autorizado === "true";
    if (typeof user.authorized === "string") return user.authorized === "true";
    return false;
  }

  // Wrapper de fetch com tratamento padrão
  async function safeFetch(url, options = {}) {
    const res = await fetch(url, options);
    if (!res.ok) {
      let detail = "";
      try {
        const data = await res.json();
        detail = data?.detail || data?.message || "";
      } catch {
        // ignore
      }
      const msg = detail || `${res.status} ${res.statusText}`;
      const err = new Error(msg);
      err.status = res.status;
      err.url = url;
      throw err;
    }
    // tenta json, se falhar, devolve texto
    try {
      return await res.json();
    } catch {
      return await res.text();
    }
  }

  // =========================
  // Autenticação / Navbar
  // =========================
  async function getAuthStatus(force = false) {
    if (!force && AUTH_CACHE) return AUTH_CACHE;
    const data = await safeFetch("/api/auth/status");
    AUTH_CACHE = data;
    return data;
  }

  function updateNavbarUI(user) {
    const elName = document.getElementById("user-name");
    const elAvatar = document.getElementById("user-avatar");
    const elBadge = document.getElementById("auth-badge");

    if (elName) elName.textContent = user?.name ? `Olá, ${user.name}!` : "Olá!";
    if (elAvatar && user?.picture) {
      elAvatar.src = user.picture;
      elAvatar.alt = user.name || "avatar";
    }
    if (elBadge) {
      const ok = isAuthorized(user);
      elBadge.textContent = ok ? "Autorizado" : "Pendente";
      elBadge.classList.toggle("badge-ok", ok);
      elBadge.classList.toggle("badge-pending", !ok);
    }
  }

  /**
   * Verifica login/autorizações e atualiza elementos da navbar.
   * Não faz redirecionamentos agressivos (o backend já protege as rotas).
   * Porém, se a página exigir autorização explícita e o usuário não tiver,
   * redirecionamos para /pendente.
   */
  async function checkAuthStatusAndUpdateNav(options = {}) {
    const { requireAuthorized = false } = options;
    const data = await getAuthStatus(true);

    if (!data?.authenticated) {
      // Backend normalmente redireciona, mas garantimos UX no front:
      if (window.location.pathname !== "/") {
        window.location.href = "/";
      }
      return data;
    }

    updateNavbarUI(data.user);

    if (requireAuthorized && !isAuthorized(data.user)) {
      if (window.location.pathname !== "/pendente") {
        window.location.href = "/pendente";
      }
    }

    return data;
  }

  // Logout
  function setupLogoutButton() {
    const btn = document.getElementById("logout-button");
    if (!btn) return;

    btn.addEventListener("click", async () => {
      try {
        await safeFetch("/api/auth/logout", { method: "POST" });
      } catch (err) {
        // Mesmo que erro, limpamos sessão client-side e seguimos para login
        console.warn("Falha ao deslogar no backend:", err);
      } finally {
        // limpa cache e volta para login
        AUTH_CACHE = null;
        window.location.href = "/";
      }
    });
  }

  // =========================
  // Helpers de página
  // =========================

  // Inicialização genérica por pathname (somente o necessário)
  async function bootByPath() {
    const path = window.location.pathname;

    // Páginas comuns autenticadas (navbar, avatar, etc.)
    if (
      path !== "/" &&            // login
      path !== "/pendente"       // página de pendência
    ) {
      try {
        await checkAuthStatusAndUpdateNav(); // sem exigir "authorized"
      } catch (e) {
        console.error("Falha ao checar auth status:", e);
      }
      setupLogoutButton();
    }

    // Páginas específicas podem ter seus próprios scripts
    // Ex.: calculadora usa pricingLogic.js (initializePricingForm)
    //     campanhas usa campaignPricingLogic.js, etc.
  }

  // =========================
  // Exports globais
  // =========================
  window.safeFetch = safeFetch;
  window.getAuthStatus = getAuthStatus;
  window.checkAuthStatusAndUpdateNav = checkAuthStatusAndUpdateNav;
  window.setupLogoutButton = setupLogoutButton;
  window.isAuthorized = isAuthorized;

  // =========================
  // Boot
  // =========================
  document.addEventListener("DOMContentLoaded", bootByPath);
})();
