/**
 * utils.js
 * Utilidades de UI (toast, modal), formatação (moeda/percentual) e helpers.
 *
 * Este arquivo é deliberadamente independente (sem libs) para funcionar em
 * todas as páginas. É usado por app.js, pricingLogic.js e outros.
 */

(function () {
  // =========================
  // Helpers DOM
  // =========================
  function ensureContainer(id, htmlFactory) {
    let el = document.getElementById(id);
    if (!el) {
      el = document.createElement("div");
      el.id = id;
      el.innerHTML = htmlFactory ? htmlFactory() : "";
      document.body.appendChild(el);
    }
    return el;
  }

  function qs(sel, root = document) {
    return root.querySelector(sel);
  }
  function qsa(sel, root = document) {
    return Array.from(root.querySelectorAll(sel));
  }

  // =========================
  // Toasts
  // =========================
  function getToastRoot() {
    return ensureContainer("toast-root", () => `
      <style>
        #toast-root { position: fixed; top: 16px; right: 16px; z-index: 9999; display: flex; flex-direction: column; gap: 8px; }
        .toast {
          min-width: 240px; max-width: 420px; padding: 12px 14px; border-radius: 10px;
          box-shadow: 0 6px 18px rgba(0,0,0,.12); font: 14px/1.4 system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
          display: flex; gap: 10px; align-items: flex-start; color: #1b1b1b; background: #fff;
          border-left: 5px solid #4CAF50; opacity: 0; transform: translateY(-8px); animation: toast-in .25s ease-out forwards;
        }
        .toast.error { border-left-color: #E53935; }
        .toast.warn  { border-left-color: #FB8C00; }
        .toast.info  { border-left-color: #1976D2; }
        .toast .title { font-weight: 600; margin-bottom: 2px; }
        .toast .msg { opacity: .9; }
        .toast .close { margin-left: auto; background: transparent; border: 0; font-size: 18px; cursor: pointer; opacity: .6; }
        .toast .close:hover { opacity: 1; }
        @keyframes toast-in { to { opacity: 1; transform: translateY(0); } }
        @keyframes toast-out { to { opacity: 0; transform: translateY(-8px); } }
      </style>
    `);
  }

  function showToast(message, type = "info", title = "") {
    const root = getToastRoot();
    const wrap = document.createElement("div");
    wrap.className = `toast ${type}`;
    wrap.innerHTML = `
      <div class="content">
        ${title ? `<div class="title">${title}</div>` : ""}
        <div class="msg">${escapeHtml(message)}</div>
      </div>
      <button class="close" aria-label="Fechar">&times;</button>
    `;
    root.appendChild(wrap);

    const remove = () => {
      wrap.style.animation = "toast-out .2s ease-in forwards";
      setTimeout(() => wrap.remove(), 180);
    };
    qs(".close", wrap).addEventListener("click", remove);

    // Autoclose (5s info/warn, 7s success, 8s error)
    const ttl = type === "error" ? 8000 : type === "success" ? 7000 : 5000;
    const tm = setTimeout(remove, ttl);

    // Pausar ao passar o mouse
    wrap.addEventListener("mouseenter", () => clearTimeout(tm), { once: true });

    return remove;
  }

  // =========================
  // Modal
  // =========================
  function getModalRoot() {
    return ensureContainer("modal-root", () => `
      <style>
        #modal-root { position: fixed; inset: 0; z-index: 9998; display: none; }
        #modal-root.active { display: block; }
        #modal-root .backdrop { position: absolute; inset: 0; background: rgba(0,0,0,.35); }
        #modal-root .panel {
          position: absolute; inset: 0; display: grid; place-items: center; padding: 16px;
        }
        #modal-root .card {
          width: min(640px, 92vw); background: #fff; border-radius: 14px; box-shadow: 0 16px 48px rgba(0,0,0,.22);
          overflow: hidden; font: 14px/1.5 system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
          transform: translateY(10px); opacity: 0; animation: modal-in .2s ease-out forwards;
        }
        #modal-root .head { padding: 16px 18px; border-bottom: 1px solid #eee; font-weight: 700; font-size: 16px; }
        #modal-root .body { padding: 16px 18px; max-height: 70vh; overflow: auto; }
        #modal-root .foot { padding: 12px 18px; border-top: 1px solid #eee; display: flex; gap: 8px; justify-content: flex-end; }
        #modal-root button { border: 0; border-radius: 10px; padding: 10px 14px; cursor: pointer; font-weight: 600; }
        #modal-root button.primary { background: #1976D2; color: #fff; }
        #modal-root button.secondary { background: #ECEFF1; color: #263238; }
        @keyframes modal-in { to { transform: translateY(0); opacity: 1; } }
      </style>
      <div class="backdrop"></div>
      <div class="panel" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <div class="card">
          <div id="modal-title" class="head"></div>
          <div class="body"></div>
          <div class="foot"></div>
        </div>
      </div>
    `);
  }

  /**
   * showAppModal({ title, bodyHtml, buttons })
   * buttons: [{ text, class, onClick }]
   */
  function showAppModal({ title = "Mensagem", bodyHtml = "", buttons = [{ text: "OK", class: "primary" }] } = {}) {
    const root = getModalRoot();
    root.classList.add("active");
    qs(".head", root).textContent = title;
    qs(".body", root).innerHTML = bodyHtml;
    const foot = qs(".foot", root);
    foot.innerHTML = "";

    const close = () => root.classList.remove("active");
    qs(".backdrop", root).onclick = close;

    buttons.forEach((b) => {
      const btn = document.createElement("button");
      btn.className = b.class || "primary";
      btn.textContent = b.text || "OK";
      btn.addEventListener("click", async () => {
        try {
          if (typeof b.onClick === "function") {
            const ret = b.onClick();
            if (ret && typeof ret.then === "function") await ret;
          }
        } finally {
          close();
        }
      });
      foot.appendChild(btn);
    });

    return { close };
  }

  // =========================
  // Formatadores
  // =========================
  const BRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: 2 });

  function formatCurrency(value) {
    const n = Number(value);
    if (!isFinite(n)) return "R$ 0,00";
    return BRL.format(n);
  }

  function parseCurrency(str) {
    if (typeof str === "number") return str;
    if (!str) return 0;
    // remove tudo que não número, vírgula ou ponto
    const s = String(str).replace(/[^\d,.-]/g, "").replace(/\./g, "").replace(",", ".");
    const n = parseFloat(s);
    return isFinite(n) ? n : 0;
  }

  function formatPercent(value, options = { decimals: 2 }) {
    const n = Number(value);
    if (!isFinite(n)) return "0%";
    const d = options.decimals ?? 2;
    return `${n.toFixed(d)}%`;
  }

  function parsePercent(str) {
    if (typeof str === "number") return str;
    if (!str) return 0;
    const s = String(str).replace("%", "").replace(",", ".");
    const n = parseFloat(s);
    return isFinite(n) ? n : 0;
  }

  // =========================
  // Strings / Segurança básica
  // =========================
  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // =========================
  // Exports globais
  // =========================
  window.qs = qs;
  window.qsa = qsa;
  window.showToast = showToast;
  window.showAppModal = showAppModal;
  window.formatCurrency = formatCurrency;
  window.parseCurrency = parseCurrency;
  window.formatPercent = formatPercent;
  window.parsePercent = parsePercent;
  window.escapeHtml = escapeHtml;
})();
