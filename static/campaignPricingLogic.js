/**
 * campaignPricingLogic.js
 * Fluxo de CRIAÇÃO de campanha a partir de uma Precificação Base.
 *
 * Páginas alvo:
 *  - /precificar-campanha.html?base_id=<uuid>
 *
 * Endpoints esperados:
 *  - GET  /api/precificacao/<base_id>/edit-data
 *  - POST /api/precificacao/campanha
 *
 * Observação:
 *  - Para EDIÇÃO de campanha (quando existe id de campanha), use editCampaignLogic.js
 */

(function () {
  // caches simples
  let BASE_DATA = null; // { precificacao_base, produto_atual, config_loja }
  let CATEGORIAS_CACHE = [];

  // =========================
  // API
  // =========================
  const Api = {
    async getBaseEditData(baseId) {
      return await safeFetch(`/api/precificacao/${encodeURIComponent(baseId)}/edit-data`);
    },
    async getCategoriasPrecificacao() {
      try {
        return await safeFetch(`/api/precificacao/categorias-precificacao`);
      } catch {
        return [];
      }
    },
    async createCampaign(payload) {
      return await safeFetch(`/api/precificacao/campanha`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
  };

  // =========================
  // Cálculo da campanha
  // =========================
  const CampaignCalc = {
    /**
     * Aplica desconto/aumento em cima do valor de venda da base.
     * @param {number} basePrice
     * @param {number} deltaPercent - positivo aumenta, negativo reduz
     * @returns {number}
     */
    applyDelta(basePrice, deltaPercent) {
      const v = Number(basePrice) || 0;
      const p = Number(deltaPercent) || 0;
      return v * (1 + p / 100);
    },

    /**
     * Gera preços sugeridos a partir da base e parâmetros informados.
     */
    buildPrices(params) {
      const {
        venda_classico_base,
        venda_premium_base,
        delta_percent,
        teto_preco,      // opcional
        piso_preco,      // opcional
      } = params;

      const sugClassico = this.applyDelta(venda_classico_base, delta_percent);
      const sugPremium  = this.applyDelta(venda_premium_base,  delta_percent);

      const clamp = (v) => {
        let out = v;
        if (isFinite(piso_preco) && piso_preco > 0) out = Math.max(out, piso_preco);
        if (isFinite(teto_preco) && teto_preco > 0) out = Math.min(out, teto_preco);
        return out;
      };

      return {
        classico: clamp(Number(sugClassico.toFixed(2))),
        premium:  clamp(Number(sugPremium.toFixed(2))),
      };
    },
  };

  // =========================
  // Manager da página
  // =========================
  class CampaignFormManager {
    constructor(baseId) {
      this.baseId = baseId;
      this.elements = {};
      this.currentSuggestion = { classico: 0, premium: 0 };
      this.formContainer = document.getElementById("campaign-form");
    }

    async init() {
      // UI base
      this.renderFormHTML();
      this.cacheElements();
      this.attachEventListeners();

      // Dados necessários
      await checkAuthStatusAndUpdateNav();
      setupLogoutButton();

      try {
        const [baseData, categorias] = await Promise.all([
          Api.getBaseEditData(this.baseId),
          Api.getCategoriasPrecificacao(),
        ]);
        BASE_DATA = baseData;
        CATEGORIAS_CACHE = Array.isArray(categorias) ? categorias : [];

        this.fillBaseSummary(baseData);
        this.populateCategorias(CATEGORIAS_CACHE);
        this.recompute();

      } catch (err) {
        console.error("Falha ao carregar dados:", err);
        showAppModal({
          title: "Erro",
          bodyHtml: `<p>Não foi possível carregar os dados da base (${escapeHtml(err.message || "")}).</p>`,
          buttons: [{ text: "OK", class: "primary", onClick: () => (window.location.href = "/lista") }],
        });
      }
    }

    renderFormHTML() {
      const html = `
        <section class="form-section">
          <h2>Precificação Base</h2>
          <div class="base-summary">
            <div><b>Marketplace:</b> <span id="base-marketplace">-</span></div>
            <div><b>Loja:</b> <span id="base-id-loja">-</span></div>
            <div><b>SKU:</b> <span id="base-sku">-</span></div>
            <div><b>Título:</b> <span id="base-titulo">-</span></div>
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
          <h2>Configuração da Campanha</h2>
          <div class="form-row">
            <div class="form-field">
              <label for="categoria-precificacao">Categoria Precificação</label>
              <select id="categoria-precificacao"></select>
            </div>
            <div class="form-field">
              <label for="delta-percent">Variação de Preço (%)</label>
              <input type="number" id="delta-percent" step="0.01" value="0" placeholder="-10 para desconto de 10%">
            </div>
            <div class="form-field">
              <label for="piso-preco">Piso de Preço (R$)</label>
              <input type="number" id="piso-preco" step="0.01" placeholder="Opcional">
            </div>
            <div class="form-field">
              <label for="teto-preco">Teto de Preço (R$)</label>
              <input type="number" id="teto-preco" step="0.01" placeholder="Opcional">
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
          <h2>Preços Sugeridos pela Campanha</h2>
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
              <textarea id="observacoes" rows="2" placeholder="Anotações internas da campanha"></textarea>
            </div>
          </div>
        </section>

        <div class="button-container">
          <button id="btn-salvar-campanha" class="app-button save-button">Criar Campanha</button>
          <a href="/editar?id=${encodeURIComponent(this.baseId)}" class="app-button secondary">Voltar</a>
        </div>
      `;
      this.formContainer.innerHTML = html;
      const initialLoader = document.getElementById("initial-loader");
      if (initialLoader) initialLoader.classList.add("hidden");
      this.formContainer.classList.remove("hidden");
    }

    cacheElements() {
      const ids = [
        // base
        "base-marketplace","base-id-loja","base-sku","base-titulo",
        "base-venda-classico","base-venda-premium","base-categoria",
        // campanha
        "categoria-precificacao","delta-percent","piso-preco","teto-preco",
        "inicio","fim","canal","estoque-reservado","observacoes",
        // sugeridos
        "preco-sugerido-classico","preco-sugerido-premium",
        // ações
        "btn-salvar-campanha",
      ];
      ids.forEach((id) => (this.elements[id] = document.getElementById(id)));
    }

    attachEventListeners() {
      const recalcIds = [
        "categoria-precificacao","delta-percent","piso-preco","teto-preco","inicio","fim","canal","estoque-reservado",
      ];
      recalcIds.forEach((id) => {
        const el = this.elements[id];
        if (!el) return;
        const evt = el.tagName === "SELECT" ? "change" : "input";
        el.addEventListener(evt, () => this.recompute());
      });

      if (this.elements["btn-salvar-campanha"]) {
        this.elements["btn-salvar-campanha"].addEventListener("click", () => this.handleSave());
      }
    }

    fillBaseSummary(data) {
      const { precificacao_base, produto_atual } = data || {};
      const eb = (id, value) => (this.elements[id] && (this.elements[id].textContent = value));

      eb("base-marketplace", precificacao_base?.marketplace || "-");
      eb("base-id-loja", precificacao_base?.id_loja || "-");
      eb("base-sku", precificacao_base?.sku || "-");
      eb("base-titulo", precificacao_base?.titulo || produto_atual?.titulo || "-");

      const vendaC = Number(precificacao_base?.venda_classico || 0);
      const vendaP = Number(precificacao_base?.venda_premium || 0);
      const cat    = precificacao_base?.categoria_precificacao || "-";

      const set = (id, v) => this.elements[id] && (this.elements[id].value = typeof v === "number" ? v.toFixed(2) : v);

      set("base-venda-classico", vendaC);
      set("base-venda-premium",  vendaP);
      set("base-categoria",      cat);
    }

    populateCategorias(categorias) {
      const sel = this.elements["categoria-precificacao"];
      if (!sel) return;
      sel.innerHTML = `<option value="">(Manter da Base)</option>`;
      categorias.forEach((c) => {
        const opt = document.createElement("option");
        opt.value = c.margem_padrao; // guardamos margem como valor
        opt.textContent = `${c.nome} (${c.margem_padrao}%)`;
        opt.dataset.nome = c.nome;
        sel.appendChild(opt);
      });
    }

    recompute() {
      const vendaC = parseFloat(this.elements["base-venda-classico"]?.value || "0") || 0;
      const vendaP = parseFloat(this.elements["base-venda-premium"]?.value || "0") || 0;

      const deltaPercent = parseFloat(this.elements["delta-percent"]?.value || "0") || 0;
      const piso = parseFloat(this.elements["piso-preco"]?.value || "0") || 0;
      const teto = parseFloat(this.elements["teto-preco"]?.value || "0") || 0;

      const { classico, premium } = CampaignCalc.buildPrices({
        venda_classico_base: vendaC,
        venda_premium_base: vendaP,
        delta_percent: deltaPercent,
        piso_preco: isFinite(piso) && piso > 0 ? piso : undefined,
        teto_preco: isFinite(teto) && teto > 0 ? teto : undefined,
      });

      this.currentSuggestion = { classico, premium };
      if (this.elements["preco-sugerido-classico"]) this.elements["preco-sugerido-classico"].value = classico.toFixed(2);
      if (this.elements["preco-sugerido-premium"])  this.elements["preco-sugerido-premium"].value  = premium.toFixed(2);
    }

    async handleSave() {
      // validações mínimas
      if (!BASE_DATA?.precificacao_base?.id) {
        showToast("Base inválida ou não carregada.", "error");
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

      // construir payload
      const catSel = this.elements["categoria-precificacao"];
      const categoriaPrecificacaoNome = catSel?.selectedOptions?.[0]?.dataset?.nome || null;

      const payload = {
        base_id: BASE_DATA.precificacao_base.id,
        // metadados
        marketplace: BASE_DATA.precificacao_base.marketplace,
        id_loja: BASE_DATA.precificacao_base.id_loja,
        sku: BASE_DATA.precificacao_base.sku,
        categoria_precificacao: categoriaPrecificacaoNome || BASE_DATA.precificacao_base.categoria_precificacao || null,
        // janela
        inicio: dtIni,
        fim: dtFim,
        canal: this.elements["canal"]?.value || "",
        estoque_reservado: parseInt(this.elements["estoque-reservado"]?.value || "0", 10) || 0,
        observacoes: this.elements["observacoes"]?.value || "",
        // precos sugeridos (padrão, o backend pode recalcular também)
        preco_sugerido_classico: this.currentSuggestion.classico,
        preco_sugerido_premium:  this.currentSuggestion.premium,
        // parâmetros usados para o cálculo (auditoria/explicabilidade)
        parametros: {
          delta_percent: parseFloat(this.elements["delta-percent"]?.value || "0") || 0,
          piso_preco: parseFloat(this.elements["piso-preco"]?.value || "0") || 0,
          teto_preco: parseFloat(this.elements["teto-preco"]?.value || "0") || 0,
        },
      };

      // submit
      const btn = this.elements["btn-salvar-campanha"];
      btn?.classList.add("is-loading");
      btn.disabled = true;

      try {
        const result = await Api.createCampaign(payload);
        const campanhaId = result?.id || result?.campanha_id;

        showAppModal({
          title: "Campanha criada!",
          bodyHtml: `<p>Sua campanha foi criada com sucesso.</p>`,
          buttons: [
            { text: "Ver Campanhas", class: "secondary", onClick: () => (window.location.href = "/campanhas") },
            { text: "Editar esta Campanha", class: "primary", onClick: () => (window.location.href = `/editar-campanha.html?id=${encodeURIComponent(campanhaId)}`) },
          ],
        });
      } catch (err) {
        console.error("Erro ao criar campanha:", err);
        showToast(err.message || "Erro ao criar campanha.", "error");
      } finally {
        btn?.classList.remove("is-loading");
        btn.disabled = false;
      }
    }
  }

  // =========================
  // Bootstrap + função global
  // =========================
  document.addEventListener("DOMContentLoaded", () => {
    const container = document.getElementById("campaign-form");
    if (!container) return; // outra página
    const params = new URLSearchParams(window.location.search);
    const baseId = params.get("base_id") || params.get("baseId") || params.get("id_base");
    if (!baseId) {
      showAppModal({
        title: "Base não informada",
        bodyHtml: `<p>Use a página de edição da precificação base para abrir a criação de campanha.</p>`,
        buttons: [{ text: "Ir para Lista", class: "primary", onClick: () => (window.location.href = "/lista") }],
      });
      return;
    }
    const manager = new CampaignFormManager(baseId);
    manager.init();
  });

  // Expor função global para inicialização manual
  window.initializeCampaignForm = function initializeCampaignForm(baseId) {
    const manager = new CampaignFormManager(baseId);
    manager.init();
  };
})();
