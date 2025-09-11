/**
 * editCampaignLogic.js
 * Edição de Campanha de Precificação
 *
 * Página alvo:
 *   - /editar-campanha.html?id=<campanha_id>
 *
 * Endpoints utilizados:
 *   - GET    /api/precificacao/campanha/<id>
 *   - POST   /api/precificacao/campanha         (com "id" no payload para atualizar)
 *   - DELETE /api/precificacao/campanha/<id>    (opcional, se backend suportar)
 *   - GET    /api/precificacao/categorias-precificacao
 */

(function () {
  let CATEGORIAS_CACHE = [];
  let CAMPANHA_ATUAL = null;

  // =========================
  // API
  // =========================
  const Api = {
    async getCategorias() {
      try {
        return await safeFetch("/api/precificacao/categorias-precificacao");
      } catch {
        return [];
      }
    },
    async getCampanha(id) {
      return await safeFetch(`/api/precificacao/campanha/${encodeURIComponent(id)}`);
    },
    async saveCampanha(payload) {
      // Atualização usa POST com "id" no corpo (compatibilidade com backend atual)
      return await safeFetch(`/api/precificacao/campanha`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
    async deleteCampanha(id) {
      // Só chame se o backend suportar DELETE
      return await safeFetch(`/api/precificacao/campanha/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });
    },
  };

  // =========================
  // Cálculo básico (sugestões)
  // =========================
  const Calc = {
    applyDelta(basePrice, deltaPercent) {
      const v = Number(basePrice) || 0;
      const p = Number(deltaPercent) || 0;
      return v * (1 + p / 100);
    },
    buildPrices({ venda_classico_base, venda_premium_base, delta_percent, piso_preco, teto_preco }) {
      const sugC = this.applyDelta(venda_classico_base, delta_percent);
      const sugP = this.applyDelta(venda_premium_base, delta_percent);

      const clamp = (v) => {
        let out = v;
        if (isFinite(piso_preco) && piso_preco > 0) out = Math.max(out, piso_preco);
        if (isFinite(teto_preco) && teto_preco > 0) out = Math.min(out, teto_preco);
        return out;
      };

      return {
        classico: clamp(Number(sugC.toFixed(2))),
        premium:  clamp(Number(sugP.toFixed(2))),
      };
    },
  };

  // =========================
  // Manager
  // =========================
  class EditCampaignManager {
    constructor(campanhaId) {
      this.campanhaId = campanhaId;
      this.elements = {};
      this.formContainer = document.getElementById("edit-campaign-form");
      this.currentSuggestion = { classico: 0, premium: 0 };
    }

    async init() {
      await checkAuthStatusAndUpdateNav();
      setupLogoutButton();

      this.renderSkeleton();
      this.cacheElements();
      this.attachEventListeners();

      try {
        const [categorias, campanha] = await Promise.all([
          Api.getCategorias(),
          Api.getCampanha(this.campanhaId),
        ]);
        CATEGORIAS_CACHE = Array.isArray(categorias) ? categorias : [];
        CAMPANHA_ATUAL = campanha;

        this.populateCategorias(CATEGORIAS_CACHE, campanha?.categoria_precificacao || null);
        this.fillForm(campanha);
        this.recompute(); // gera/preenche sugestões (se aplicável)
      } catch (err) {
        console.error("Falha ao carregar campanha:", err);
        showAppModal({
          title: "Erro ao carregar",
          bodyHtml: `<p>${escapeHtml(err.message || "Não foi possível carregar a campanha.")}</p>`,
          buttons: [{ text: "Voltar para Campanhas", class: "primary", onClick: () => (window.location.href = "/campanhas") }],
        });
      } finally {
        const initialLoader = document.getElementById("initial-loader");
        if (initialLoader) initialLoader.classList.add("hidden");
        this.formContainer.classList.remove("hidden");
      }
    }

    renderSkeleton() {
      const html = `
        <section class="form-section">
          <h2>Campanha</h2>
          <div class="base-summary">
            <div><b>ID:</b> <span id="cmp-id">-</span></div>
            <div><b>Base ID:</b> <span id="cmp-base-id">-</span></div>
            <div><b>Marketplace:</b> <span id="cmp-marketplace">-</span></div>
            <div><b>Loja:</b> <span id="cmp-id-loja">-</span></div>
            <div><b>SKU:</b> <span id="cmp-sku">-</span></div>
            <div><b>Título:</b> <span id="cmp-titulo">-</span></div>
          </div>

          <div class="form-row">
            <div class="form-field">
              <label>Venda Base (Clássico)</label>
              <input type="text" id="base-venda-classico" readonly>
            </div>
            <div class="form-field">
              <label>Venda Base (Premium)</label>
              <input type="text" id="base-venda-premium" readonly>
            </div>
            <div class="form-field">
              <label>Categoria Precificação (Base)</label>
              <input type="text" id="base-categoria" readonly>
            </div>
          </div>
        </section>

        <section class="form-section">
          <h2>Configuração</h2>
          <div class="form-row">
            <div class="form-field">
              <label for="categoria-precificacao">Categoria Precificação</label>
              <select id="categoria-precificacao"></select>
            </div>
            <div class="form-field">
              <label for="delta-percent">Variação de Preço (%)</label>
              <input type="number" id="delta-percent" step="0.01" value="0">
            </div>
            <div class="form-field">
              <label for="piso-preco">Piso de Preço (R$)</label>
              <input type="number" id="piso-preco" step="0.01">
            </div>
            <div class="form-field">
              <label for="teto-preco">Teto de Preço (R$)</label>
              <input type="number" id="teto-preco" step="0.01">
            </div>
          </div>

          <div class="form-row">
            <div class="form-field">
              <label for="inicio">Início</label>
              <input type="datetime-local" id="inicio">
            </div>
            <div class="form-field">
              <label for="fim">Fim</label>
              <input type="datetime-local" id="fim">
            </div>
            <div class="form-field">
              <label for="canal">Canal</label>
              <select id="canal">
                <option value="">Automático/Default</option>
                <option value="catalogo">Catálogo</option>
                <option value="buybox">BuyBox</option>
                <option value="ads">Anúncios (ADS)</option>
              </select>
            </div>
            <div class="form-field">
              <label for="estoque-reservado">Reservar Estoque</label>
              <input type="number" id="estoque-reservado" min="0" step="1" value="0">
            </div>
          </div>
        </section>

        <section class="form-section">
          <h2>Preços Sugeridos</h2>
          <div class="form-row">
            <div class="form-field">
              <label>Preço Sugerido (Clássico)</label>
              <input type="text" id="preco-sugerido-classico" readonly>
            </div>
            <div class="form-field">
              <label>Preço Sugerido (Premium)</label>
              <input type="text" id="preco-sugerido-premium" readonly>
            </div>
            <div class="form-field">
              <label for="observacoes">Observações</label>
              <textarea id="observacoes" rows="2" placeholder="Anotações da campanha"></textarea>
            </div>
          </div>
        </section>

        <div class="button-container">
          <button id="btn-salvar" class="app-button save-button">Salvar alterações</button>
          <button id="btn-excluir" class="app-button danger">Excluir campanha</button>
          <a href="/campanhas" class="app-button secondary">Voltar</a>
        </div>
      `;
      this.formContainer.innerHTML = html;
    }

    cacheElements() {
      const ids = [
        // resumo
        "cmp-id","cmp-base-id","cmp-marketplace","cmp-id-loja","cmp-sku","cmp-titulo",
        // base
        "base-venda-classico","base-venda-premium","base-categoria",
        // edição
        "categoria-precificacao","delta-percent","piso-preco","teto-preco",
        "inicio","fim","canal","estoque-reservado","observacoes",
        // sugeridos
        "preco-sugerido-classico","preco-sugerido-premium",
        // ações
        "btn-salvar","btn-excluir",
      ];
      ids.forEach((id) => (this.elements[id] = document.getElementById(id)));
    }

    attachEventListeners() {
      const recalcIds = ["categoria-precificacao","delta-percent","piso-preco","teto-preco"];
      recalcIds.forEach((id) => {
        const el = this.elements[id];
        if (!el) return;
        const evt = el.tagName === "SELECT" ? "change" : "input";
        el.addEventListener(evt, () => this.recompute());
      });

      this.elements["btn-salvar"]?.addEventListener("click", () => this.handleSave());
      this.elements["btn-excluir"]?.addEventListener("click", () => this.handleDelete());
    }

    populateCategorias(categorias, selecionadaNome) {
      const sel = this.elements["categoria-precificacao"];
      if (!sel) return;

      sel.innerHTML = `<option value="">(Manter)</option>`;
      categorias.forEach((c) => {
        const opt = document.createElement("option");
        opt.value = c.margem_padrao; // guardamos a margem como valor
        opt.textContent = `${c.nome} (${c.margem_padrao}%)`;
        opt.dataset.nome = c.nome;
        sel.appendChild(opt);
      });

      // Se houver selecionada por nome, apenas marcamos visualmente no label (não alteramos valor)
      if (selecionadaNome) {
        const info = document.createElement("small");
        info.style.opacity = "0.8";
        info.style.marginLeft = "6px";
        info.textContent = ` (Atual: ${selecionadaNome})`;
        sel.parentElement.querySelector("label")?.appendChild(info);
      }
    }

    fillForm(c) {
      if (!c) return;
      const eb = (id, v) => (this.elements[id] && (this.elements[id].textContent = v ?? "-"));
      const ev = (id, v) => (this.elements[id] && (this.elements[id].value = v ?? ""));

      // resumo
      eb("cmp-id", c.id);
      eb("cmp-base-id", c.base_id);
      eb("cmp-marketplace", c.marketplace);
      eb("cmp-id-loja", c.id_loja);
      eb("cmp-sku", c.sku);
      eb("cmp-titulo", c.titulo || c.produto?.titulo || "-");

      // base
      ev("base-venda-classico", Number(c.venda_classico_base || 0).toFixed(2));
      ev("base-venda-premium",  Number(c.venda_premium_base || 0).toFixed(2));
      ev("base-categoria",      c.categoria_precificacao || "");

      // edição
      ev("delta-percent", c.parametros?.delta_percent ?? 0);
      ev("piso-preco",    c.parametros?.piso_preco ?? (c.piso_preco ?? ""));
      ev("teto-preco",    c.parametros?.teto_preco ?? (c.teto_preco ?? ""));

      // datas ISO -> datetime-local (YYYY-MM-DDTHH:MM)
      const toLocalInput = (iso) => {
        if (!iso) return "";
        try {
          const d = new Date(iso);
          const pad = (n) => String(n).padStart(2, "0");
          return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
        } catch {
          return "";
        }
      };
      ev("inicio", toLocalInput(c.inicio));
      ev("fim",    toLocalInput(c.fim));

      ev("canal", c.canal || "");
      ev("estoque-reservado", c.estoque_reservado ?? 0);
      ev("observacoes", c.observacoes || "");
    }

    recompute() {
      // Recomputa sugestão, sem sobrescrever preços já existentes no backend.
      const vendaC = parseFloat(this.elements["base-venda-classico"]?.value || "0") || 0;
      const vendaP = parseFloat(this.elements["base-venda-premium"]?.value || "0") || 0;
      const delta  = parseFloat(this.elements["delta-percent"]?.value || "0") || 0;
      const piso   = parseFloat(this.elements["piso-preco"]?.value || "0") || 0;
      const teto   = parseFloat(this.elements["teto-preco"]?.value || "0") || 0;

      const out = Calc.buildPrices({
        venda_classico_base: vendaC,
        venda_premium_base : vendaP,
        delta_percent      : delta,
        piso_preco         : isFinite(piso) && piso > 0 ? piso : undefined,
        teto_preco         : isFinite(teto) && teto > 0 ? teto : undefined,
      });

      this.currentSuggestion = out;

      if (this.elements["preco-sugerido-classico"]) this.elements["preco-sugerido-classico"].value = out.classico.toFixed(2);
      if (this.elements["preco-sugerido-premium"])  this.elements["preco-sugerido-premium"].value  = out.premium.toFixed(2);
    }

    async handleSave() {
      if (!CAMPANHA_ATUAL?.id) {
        showToast("Campanha inválida.", "error");
        return;
      }
      const dtIni = this.elements["inicio"]?.value || "";
      const dtFim = this.elements["fim"]?.value || "";
      if (!dtIni || !dtFim) {
        showToast("Informe início e fim da campanha.", "warn");
        return;
      }
      if (new Date(dtFim) <= new Date(dtIni)) {
        showToast("A data/hora de fim deve ser posterior ao início.", "warn");
        return;
      }

      const catSel = this.elements["categoria-precificacao"];
      const categoriaNome = catSel?.selectedOptions?.[0]?.dataset?.nome || CAMPANHA_ATUAL.categoria_precificacao || null;

      const payload = {
        id: CAMPANHA_ATUAL.id,          // necessário para atualizar via POST
        base_id: CAMPANHA_ATUAL.base_id,
        marketplace: CAMPANHA_ATUAL.marketplace,
        id_loja: CAMPANHA_ATUAL.id_loja,
        sku: CAMPANHA_ATUAL.sku,

        categoria_precificacao: categoriaNome,

        inicio: dtIni,
        fim: dtFim,
        canal: this.elements["canal"]?.value || "",
        estoque_reservado: parseInt(this.elements["estoque-reservado"]?.value || "0", 10) || 0,
        observacoes: this.elements["observacoes"]?.value || "",

        // sugestões (apenas informativo/auditoria; backend pode recalcular)
        preco_sugerido_classico: this.currentSuggestion.classico,
        preco_sugerido_premium:  this.currentSuggestion.premium,

        parametros: {
          delta_percent: parseFloat(this.elements["delta-percent"]?.value || "0") || 0,
          piso_preco: parseFloat(this.elements["piso-preco"]?.value || "0") || 0,
          teto_preco: parseFloat(this.elements["teto-preco"]?.value || "0") || 0,
        },
      };

      const btn = this.elements["btn-salvar"];
      btn?.classList.add("is-loading");
      btn.disabled = true;

      try {
        await Api.saveCampanha(payload);
        showToast("Campanha atualizada com sucesso!", "success");
      } catch (err) {
        console.error("Erro ao salvar campanha:", err);
        showToast(err.message || "Erro ao salvar campanha.", "error");
      } finally {
        btn?.classList.remove("is-loading");
        btn.disabled = false;
      }
    }

    async handleDelete() {
      if (!CAMPANHA_ATUAL?.id) return;

      showAppModal({
        title: "Excluir campanha?",
        bodyHtml: `<p>Essa ação não pode ser desfeita.</p>`,
        buttons: [
          { text: "Cancelar", class: "secondary" },
          {
            text: "Excluir",
            class: "primary",
            onClick: async () => {
              try {
                await Api.deleteCampanha(CAMPANHA_ATUAL.id);
                showToast("Campanha excluída.", "success");
                setTimeout(() => (window.location.href = "/campanhas"), 600);
              } catch (err) {
                console.error("Erro ao excluir:", err);
                showToast(err.message || "Erro ao excluir campanha.", "error");
              }
            },
          },
        ],
      });
    }
  }

  // =========================
  // Bootstrap + global
  // =========================
  document.addEventListener("DOMContentLoaded", () => {
    const container = document.getElementById("edit-campaign-form");
    if (!container) return;

    const params = new URLSearchParams(window.location.search);
    const id = params.get("id") || params.get("campanha_id") || params.get("campanhaId");
    if (!id) {
      showAppModal({
        title: "Campanha não informada",
        bodyHtml: `<p>Abra a edição a partir da lista de campanhas.</p>`,
        buttons: [{ text: "Ir para Campanhas", class: "primary", onClick: () => (window.location.href = "/campanhas") }],
      });
      return;
    }

    const manager = new EditCampaignManager(id);
    manager.init();
  });

  window.initializeEditCampaign = function initializeEditCampaign(campanhaId) {
    const manager = new EditCampaignManager(campanhaId);
    manager.init();
  };
})();
