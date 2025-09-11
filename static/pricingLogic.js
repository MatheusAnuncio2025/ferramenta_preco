/**
 * pricingLogic.js
 * Calculadora/Criação/Edição da Precificação Base
 *
 * Endpoints:
 *  - GET  /api/regras-negocio
 *  - GET  /api/precificacao/categorias-precificacao
 *  - GET  /api/config/lojas
 *  - GET  /api/config/lojas/{id}/detalhes
 *  - GET  /api/precificacao/dados-para-calculo?sku=...&loja_id=...
 *  - GET  /api/precificacao/{id}/edit-data
 *  - POST /api/precificacao
 *  - PUT  /api/precificacao/{id}
 */

// caches em memória
let regrasFreteCache = [];
let regrasTarifaFixaCache = [];
let categoriasPrecificacaoCache = [];
let comissoesCache = [];

/* =========================
   Validação
   ========================= */
const ValidationService = {
  rules: {
    'loja-marketplace': { required: true, message: 'A loja é obrigatória.' },
    'sku': { required: true, message: 'O SKU é obrigatório.' },
    'quantidade': { required: true, isNumeric: true, notNegative: true, message: 'Quantidade deve ser número positivo.' },
    'custo-unitario': { required: true, isNumeric: true, notNegative: true, message: 'Custo deve ser número positivo.' },
  },
  validateField(el) {
    const rule = this.rules[el.id];
    if (!rule) return true;
    const raw = (el.value || '').trim();
    const num = parseFloat(raw.toString().replace(',', '.'));
    let ok = true; let msg = '';
    if (rule.required && !raw) { ok = false; msg = rule.message; }
    else if (rule.isNumeric && Number.isNaN(num)) { ok = false; msg = rule.message; }
    else if (rule.notNegative && num < 0) { ok = false; msg = rule.message; }
    this.updateUI(el, ok, msg);
    return ok;
  },
  updateUI(el, ok, msg) {
    el.classList.toggle('is-valid', ok);
    el.classList.toggle('is-invalid', !ok);
    let err = el.parentElement.querySelector('.error-message');
    if (!err) {
      err = document.createElement('div');
      err.className = 'error-message';
      el.parentElement.appendChild(err);
    }
    err.textContent = msg;
  },
  validateForm() {
    let ok = true;
    for (const id in this.rules) {
      const el = document.getElementById(id);
      if (el && !this.validateField(el)) ok = false;
    }
    return ok;
  }
};

/* =========================
   Helpers de API
   ========================= */
const ApiService = {
  async fetchInitialData() {
    const [regrasRes, categoriasRes] = await Promise.all([
      fetch('/api/regras-negocio'),
      fetch('/api/precificacao/categorias-precificacao'),
    ]);
    if (!regrasRes.ok) throw new Error('Falha ao carregar regras.');
    if (!categoriasRes.ok) throw new Error('Falha ao carregar categorias.');
    return { regras: await regrasRes.json(), categorias: await categoriasRes.json() };
  },
  async fetchLojas() {
    const r = await fetch('/api/config/lojas');
    if (!r.ok) throw new Error('Falha ao buscar lojas.');
    return r.json();
  },
  async fetchLojaDetails(lojaId) {
    const r = await fetch(`/api/config/lojas/${lojaId}/detalhes`);
    if (!r.ok) throw new Error('Falha ao carregar detalhes de loja.');
    return r.json();
  },
  async fetchProductData(sku, lojaId) {
    const url = `/api/precificacao/dados-para-calculo?sku=${encodeURIComponent(sku)}&loja_id=${encodeURIComponent(lojaId)}`;
    const r = await fetch(url);
    if (!r.ok) {
      try { throw new Error((await r.json()).detail || 'SKU não encontrado.'); }
      catch { throw new Error('SKU não encontrado.'); }
    }
    return r.json();
  },
  async fetchEditData(recordId) {
    const r = await fetch(`/api/precificacao/${recordId}/edit-data`);
    if (!r.ok) {
      let err = '';
      try { err = (await r.json()).detail || ''; } catch {}
      throw new Error(err || `Erro ${r.status}: ${r.statusText}`);
    }
    return r.json();
  },
  async savePricing(payload, mode, recordId) {
    const url = mode === 'edit' ? `/api/precificacao/${recordId}` : '/api/precificacao';
    const method = mode === 'edit' ? 'PUT' : 'POST';
    const r = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!r.ok) {
      let err = '';
      try { err = (await r.json()).detail || ''; } catch {}
      throw new Error(err || 'Erro ao salvar.');
    }
    return r.json();
  }
};

/* =========================
   Cálculo
   ========================= */
const PricingCalculator = {
  getTarifaFixaMl(valorVenda) {
    const regra = regrasTarifaFixaCache.find(r =>
      valorVenda >= (r.min_venda ?? 0) &&
      valorVenda <= (r.max_venda ?? Infinity)
    );
    if (!regra) return 0;
    const taxaFixa = Number(regra.taxa_fixa || 0);
    const taxaPerc = Number(regra.taxa_percentual || 0);
    return taxaFixa + (valorVenda * taxaPerc / 100);
  },

  getFretePorRegra(valorVenda, pesoKg) {
    if (!pesoKg || pesoKg <= 0) return 0;
    const g = pesoKg * 1000;
    const regra = regrasFreteCache.find(r =>
      valorVenda >= (r.min_venda ?? 0) && valorVenda <= (r.max_venda ?? Infinity) &&
      g >= (r.min_peso_g ?? 0) && g <= (r.max_peso_g ?? Infinity)
    );
    return regra ? Number(regra.custo_frete || 0) : 0;
  },

  calculateAll(E, sourceId) {
    // custos base
    const qtd = parseInt(E.quantidade.value, 10) || 1;
    const custoUnit = parseFloat(E.custoUnitario.value) || 0;
    const custoTotal = qtd * custoUnit;
    E.custoTotal.value = formatCurrency(custoTotal);

    const aliquota = parseFloat(E.aliquota.value) || 0;
    const parcel = parseFloat(E.parcelamento.value) || 0;
    const outros = parseFloat(E.outros.value) || 0;

    const regraComissao = comissoesCache.find(c => c.chave === E.regraComissao.value) || null;
    const pesoRealKg = parseFloat(E.pesoReal.value) || 0;
    const pesoCubicoKg = parseFloat(E.pesoCubico.value) || 0;
    const pesoConsiderado = Math.max(pesoRealKg, pesoCubicoKg);

    const calcPlano = (plano) => {
      const P = plano.charAt(0).toUpperCase() + plano.slice(1); // Classico/Premium
      const vendaEl = E[`venda${P}`];
      const freteEl = E[`frete${P}`];
      const margemDesejadaEl = E[`margemDesejada${P}`];

      let valorVenda = parseFloat(vendaEl.value) || 0;
      const margemDesejada = parseFloat(margemDesejadaEl.value) || 0;
      const comPerc = Number(regraComissao ? regraComissao[plano] : 0);
      const custosPerc = aliquota + parcel + outros + comPerc;

      // se o usuário alterou a margem, recalcular venda (iteração simples com tarifa/grete dependentes)
      if (sourceId !== vendaEl.id && margemDesejada > 0) {
        const denom = 1 - ((custosPerc + margemDesejada) / 100);
        let vendaTeste = custoTotal > 0 ? custoTotal * 1.5 : 50;
        if (denom > 0.0001) {
          for (let i = 0; i < 10; i++) {
            const freteT = this.getFretePorRegra(vendaTeste, pesoConsiderado);
            const tarifaT = this.getTarifaFixaMl(vendaTeste);
            const novo = (custoTotal + freteT + tarifaT) / denom;
            if (Math.abs(novo - vendaTeste) < 0.01) { vendaTeste = novo; break; }
            vendaTeste = novo;
          }
          valorVenda = vendaTeste;
          vendaEl.value = valorVenda.toFixed(2);
        } else {
          vendaEl.value = '0.00';
          valorVenda = 0;
        }
      } else if (sourceId === vendaEl.id) {
        // se o usuário digitou a venda manualmente, limpamos a margem desejada
        margemDesejadaEl.value = '';
      }

      const freteAuto = this.getFretePorRegra(valorVenda, pesoConsiderado);
      let freteFinal = freteAuto;
      if (sourceId !== freteEl.id) {
        freteEl.value = freteAuto.toFixed(2);
      } else {
        freteFinal = parseFloat(freteEl.value) || 0;
      }

      const tarifaFixaFinal = this.getTarifaFixaMl(valorVenda);
      const comissaoValor = valorVenda * (comPerc / 100);
      const outrosCustos = valorVenda * ((aliquota + parcel + outros) / 100);
      const repasse = valorVenda - comissaoValor - outrosCustos - tarifaFixaFinal - freteFinal;
      const lucro = repasse - custoTotal;
      const margem = valorVenda > 0 ? (lucro / valorVenda) * 100 : 0;

      E[`tarifaFixa${P}`].value = formatCurrency(tarifaFixaFinal);
      E[`repasse${P}`].value = formatCurrency(repasse);
      E[`lucroRs${P}`].value = formatCurrency(lucro);
      E[`margem${P}`].value = formatPercent(margem);

      const lucroEl = E[`lucroRs${P}`];
      lucroEl.classList.toggle('text-success', lucro > 0);
      lucroEl.classList.toggle('text-danger', lucro < 0);
    };

    calcPlano('classico');
    calcPlano('premium');
  }
};

/* =========================
   Manager do formulário
   ========================= */
class PricingFormManager {
  constructor(mode, recordId = null) {
    this.mode = mode; // 'new' | 'edit'
    this.recordId = recordId;
    this.currentPricingId = recordId;
    this.debounceTimer = null;
    this.isCalculating = false;
    this.custoFornecedorAtual = 0;
    this.lojaConfigAtual = {};
    this.elements = {};
    this.formContainer = document.getElementById('pricing-form');
  }

  async init() {
    this.renderFormHTML();
    this.cacheElements();
    this.attachEventListeners();

    try {
      const data = await ApiService.fetchInitialData();
      regrasFreteCache = data.regras.REGRAS_FRETE_ML || [];
      regrasTarifaFixaCache = data.regras.REGRAS_TARIFA_FIXA_ML || [];
      categoriasPrecificacaoCache = data.categorias || [];
      this.populateCategorias();

      if (this.mode === 'edit') {
        await this.loadAndPopulateSavedData();
      } else {
        await this.populateLojas();
      }
    } catch (err) {
      console.error('Erro na inicialização:', err);
      const errorContainer = document.getElementById('error-message');
      if (errorContainer) {
        errorContainer.textContent = `Erro: ${err.message}`;
        errorContainer.classList.remove('hidden');
        this.formContainer.classList.add('hidden');
      } else {
        showAppModal({ title: 'Erro', bodyHtml: `<p>${err.message}</p>`, buttons: [{ text: 'OK' }] });
      }
    }
  }

  renderFormHTML() {
    const formHtml = `
      <section class="form-section">
        <h2>Dados Iniciais</h2>
        <div class="form-row" style="grid-template-columns: 1fr 1fr 2fr;">
          <div class="form-field">
            <label for="loja-marketplace">Loja / Marketplace</label>
            ${this.mode === 'edit' ? '<input type="text" id="loja-marketplace" readonly>' : '<select id="loja-marketplace"></select>'}
          </div>
          <div class="form-field">
            <label for="categoria-precificacao">Categoria Precificação</label>
            <select id="categoria-precificacao"></select>
          </div>
          <div class="form-field">
            <label for="sku">SKU (Magis)</label>
            <input type="text" id="sku" ${this.mode === 'edit' ? 'readonly' : 'placeholder="Selecione uma loja e digite o SKU..."'}>
            <small id="search-status-container">
              <span id="search-status"></span>
              <span id="loader" class="hidden"><div class="loader-spinner"></div></span>
            </small>
          </div>
        </div>
      </section>

      <section class="form-section">
        <h2>Dados do Produto</h2>
        <div class="form-row">
          <div class="form-field"><label for="titulo">Título</label><input type="text" id="titulo"></div>
          <div class="form-field"><label for="id-sku-marketplace">ID/SKU Marketplace</label><input type="text" id="id-sku-marketplace"></div>
          <div class="form-field"><label for="id-anuncio">ID Anuncio/MLB/ASIN</label><input type="text" id="id-anuncio"></div>
        </div>
        <div class="form-row">
          <div class="form-field"><label for="altura-cm">Altura (cm)</label><input type="text" id="altura-cm" readonly></div>
          <div class="form-field"><label for="largura-cm">Largura (cm)</label><input type="text" id="largura-cm" readonly></div>
          <div class="form-field"><label for="comprimento-cm">Comprimento (cm)</label><input type="text" id="comprimento-cm" readonly></div>
          <div class="form-field"><label for="peso-real">Peso Real (kg)</label><input type="text" id="peso-real" readonly></div>
          <div class="form-field"><label for="peso-cubico">Peso Cúbico (kg)</label><input type="text" id="peso-cubico" readonly></div>
        </div>
      </section>

      <section class="form-section">
        <h2>Custo, Comissão e Tarifas</h2>
        <div class="form-row">
          <div class="form-field"><label for="quantidade">Quantidade</label><input type="number" id="quantidade" value="1"></div>
          <div class="form-field"><label for="custo-unitario">Custo Unitário (R$)</label><input type="number" step="0.01" id="custo-unitario" value="0"></div>
          <div class="form-field"><label for="custo-total">Custo Total (R$)</label><input type="text" id="custo-total" readonly></div>
          <div class="form-field">
            <label for="custo-update">Custo Fornecedor (R$)</label>
            <input type="text" id="custo-update" readonly>
            <small id="custo-warning" class="warning"></small>
          </div>
        </div>
        <div class="form-row">
          <div class="form-field"><label for="aliquota">Alíquota (%)</label><input type="number" step="0.01" id="aliquota" readonly></div>
          <div class="form-field"><label for="parcelamento">Parcelamento (%)</label><input type="number" step="0.01" id="parcelamento" value="0"></div>
          <div class="form-field"><label for="outros">Outros (%)</label><input type="number" step="0.01" id="outros" value="0"></div>
          <div class="form-field">
            <label for="regra-comissao">Regra de Comissão</label>
            <select id="regra-comissao"></select>
          </div>
        </div>
        <div class="form-row" style="grid-template-columns: 1fr 1fr;">
          <div class="checkbox-field"><input type="checkbox" id="fulfillment"><label for="fulfillment">Fulfillment</label></div>
          <div class="checkbox-field"><input type="checkbox" id="catalogo-buybox"><label for="catalogo-buybox">Catálogo/Buybox</label></div>
        </div>
      </section>

      <div class="pricing-sections">
        <section class="pricing-section">
          <h3>Precificação - Clássico</h3>
          <div class="form-row">
            <div class="form-field"><label for="valor-frete-classico">Valor do Frete (R$)</label><input type="number" step="0.01" id="valor-frete-classico" value="0"></div>
            <div class="form-field"><label for="margem-desejada-classico">Margem Desejada (%)</label><input type="number" step="0.01" id="margem-desejada-classico"></div>
            <div class="form-field"><label for="valor-venda-classico">Valor Venda (R$)</label><input type="number" step="0.01" id="valor-venda-classico" value="0"></div>
          </div>
          <div class="form-row">
            <div class="form-field"><label>Tarifa Fixa (R$)</label><input type="text" id="tarifa-fixa-classico" readonly></div>
            <div class="form-field"><label>Repasse</label><input type="text" id="repasse-classico" readonly></div>
            <div class="form-field"><label>Lucro (R$)</label><input type="text" id="lucro-rs-classico" readonly></div>
            <div class="form-field"><label>Margem Lucro (%)</label><input type="text" id="margem-classico" readonly></div>
          </div>
        </section>
        <section class="pricing-section">
          <h3>Precificação - Premium</h3>
          <div class="form-row">
            <div class="form-field"><label for="valor-frete-premium">Valor do Frete (R$)</label><input type="number" step="0.01" id="valor-frete-premium" value="0"></div>
            <div class="form-field"><label for="margem-desejada-premium">Margem Desejada (%)</label><input type="number" step="0.01" id="margem-desejada-premium"></div>
            <div class="form-field"><label for="valor-venda-premium">Valor Venda (R$)</label><input type="number" step="0.01" id="valor-venda-premium" value="0"></div>
          </div>
          <div class="form-row">
            <div class="form-field"><label>Tarifa Fixa (R$)</label><input type="text" id="tarifa-fixa-premium" readonly></div>
            <div class="form-field"><label>Repasse</label><input type="text" id="repasse-premium" readonly></div>
            <div class="form-field"><label>Lucro (R$)</label><input type="text" id="lucro-rs-premium" readonly></div>
            <div class="form-field"><label>Margem Lucro (%)</label><input type="text" id="margem-premium" readonly></div>
          </div>
        </section>
      </div>

      <div class="button-container">
        <button type="button" id="save-button" class="app-button save-button">${this.mode === 'edit' ? 'Salvar Alterações' : 'Salvar Precificação'}</button>
      </div>
    `;
    this.formContainer.innerHTML = formHtml;
    const initialLoader = document.getElementById('initial-loader');
    if (initialLoader) initialLoader.classList.add('hidden');
    this.formContainer.classList.remove('hidden');
  }

  cacheElements() {
    const ids = [
      'loja-marketplace','sku','search-status','loader','titulo','id-sku-marketplace','id-anuncio',
      'altura-cm','largura-cm','comprimento-cm','peso-real','peso-cubico',
      'quantidade','custo-unitario','custo-total','custo-update','custo-warning',
      'aliquota','parcelamento','outros','regra-comissao','categoria-precificacao',
      'fulfillment','catalogo-buybox',
      'valor-venda-classico','valor-frete-classico','margem-desejada-classico','tarifa-fixa-classico','repasse-classico','lucro-rs-classico','margem-classico',
      'valor-venda-premium','valor-frete-premium','margem-desejada-premium','tarifa-fixa-premium','repasse-premium','lucro-rs-premium','margem-premium',
      'save-button'
    ];
    const map = {
      'loja-marketplace':'lojaMarketplace','id-sku-marketplace':'idSkuMarketplace','id-anuncio':'idAnuncio',
      'altura-cm':'alturaCm','largura-cm':'larguraCm','comprimento-cm':'comprimentoCm','peso-real':'pesoReal','peso-cubico':'pesoCubico',
      'custo-unitario':'custoUnitario','custo-total':'custoTotal','custo-update':'custoUpdate','custo-warning':'custoWarning',
      'regra-comissao':'regraComissao','categoria-precificacao':'categoriaPrecificacao',
      'valor-venda-classico':'vendaClassico','valor-frete-classico':'freteClassico','margem-desejada-classico':'margemDesejadaClassico',
      'tarifa-fixa-classico':'tarifaFixaClassico','repasse-classico':'repasseClassico','lucro-rs-classico':'lucroRsClassico','margem-classico':'margemClassico',
      'valor-venda-premium':'vendaPremium','valor-frete-premium':'fretePremium','margem-desejada-premium':'margemDesejadaPremium',
      'tarifa-fixa-premium':'tarifaFixaPremium','repasse-premium':'repassePremium','lucro-rs-premium':'lucroRsPremium','margem-premium':'margemPremium',
      'save-button':'saveButton'
    };
    ids.forEach(id => {
      const key = map[id] || id;
      const el = document.getElementById(id);
      if (!el) console.warn(`[cacheElements] #${id} não encontrado no DOM.`);
      this.elements[key] = el;
    });
  }

  attachEventListeners() {
    const calcFields = [
      this.elements.quantidade,this.elements.custoUnitario,this.elements.parcelamento,this.elements.outros,
      this.elements.freteClassico,this.elements.fretePremium,this.elements.vendaClassico,this.elements.vendaPremium,
      this.elements.margemDesejadaClassico,this.elements.margemDesejadaPremium,this.elements.fulfillment,
      this.elements.categoriaPrecificacao,this.elements.regraComissao
    ];
    calcFields.forEach(el => {
      if (!el) return;
      const eventType = (el.tagName === 'SELECT' || el.type === 'checkbox') ? 'change' : 'input';
      el.addEventListener(eventType, (e) => this.handleCalculation(e));
    });

    if (this.mode === 'new' && this.elements.lojaMarketplace && this.elements.sku) {
      this.elements.lojaMarketplace.addEventListener('change', () => this.handleLojaChange());
      this.elements.sku.addEventListener('keyup', (e) => {
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => this.fetchProductData(), e.key === 'Enter' ? 0 : 500);
      });
    }

    if (this.elements.saveButton) this.elements.saveButton.addEventListener('click', () => this.handleSave());
    if (this.elements.custoUnitario) this.elements.custoUnitario.addEventListener('input', () => this.checkCustoDivergence());

    Object.keys(ValidationService.rules).forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      el.addEventListener('blur', () => ValidationService.validateField(el));
      el.addEventListener('input', () => ValidationService.validateField(el));
    });
  }

  handleCalculation(e) {
    if (this.isCalculating) return;
    this.isCalculating = true;

    if (e.target.id === 'categoria-precificacao') {
      const opt = this.elements.categoriaPrecificacao.options[this.elements.categoriaPrecificacao.selectedIndex];
      const margemPadrao = opt ? opt.value : '';
      this.elements.margemDesejadaClassico.value = margemPadrao;
      this.elements.margemDesejadaPremium.value = margemPadrao;
    }

    try {
      ValidationService.validateField(this.elements.custoUnitario);
      ValidationService.validateField(this.elements.quantidade);
      PricingCalculator.calculateAll(this.elements, e.target.id);
    } finally {
      this.isCalculating = false;
    }
  }

  async populateLojas() {
    try {
      const lojas = await ApiService.fetchLojas();
      this.elements.lojaMarketplace.innerHTML = '<option value="">Selecione...</option>';
      lojas.forEach(loja => {
        const option = new Option(`${loja.marketplace} - ${loja.id_loja}`, loja.id);
        this.elements.lojaMarketplace.add(option);
      });
    } catch (err) {
      this.elements.lojaMarketplace.innerHTML = `<option value="">${err.message}</option>`;
    }
  }

  populateCategorias() {
    this.elements.categoriaPrecificacao.innerHTML = '<option value="" data-nome="">Padrão</option>';
    categoriasPrecificacaoCache.forEach(cat => {
      const option = new Option(`${cat.nome} (${cat.margem_padrao}%)`, cat.margem_padrao);
      option.dataset.nome = cat.nome;
      this.elements.categoriaPrecificacao.add(option);
    });
  }

  async handleLojaChange() {
    const lojaId = this.elements.lojaMarketplace.value;
    if (!lojaId) {
      this.lojaConfigAtual = {};
      comissoesCache = [];
      this.elements.aliquota.value = '';
      this.elements.regraComissao.innerHTML = '';
      return;
    }
    try {
      this.lojaConfigAtual = await ApiService.fetchLojaDetails(lojaId);
      comissoesCache = this.lojaConfigAtual.comissoes || [];
      this.elements.regraComissao.innerHTML = '';
      comissoesCache.forEach(c => this.elements.regraComissao.add(new Option(c.chave, c.chave)));
      if (comissoesCache.length > 0) this.elements.regraComissao.value = comissoesCache[0].chave;

      this.elements.aliquota.value = this.elements.fulfillment.checked
        ? (this.lojaConfigAtual.aliquota_fulfillment || 0)
        : (this.lojaConfigAtual.aliquota_padrao || 0);

      if (this.elements.sku.value.trim()) await this.fetchProductData();
      else this.handleCalculation({ target: { id: 'loja-marketplace' } });
    } catch (err) {
      showAppModal({ title: 'Erro', bodyHtml: `<p>${err.message}</p>`, buttons: [{ text: 'OK' }] });
    }
  }

  async fetchProductData() {
    const sku = (this.elements.sku.value || '').trim();
    const lojaId = this.elements.lojaMarketplace.value;
    if (!sku || !lojaId) return;

    if (!this.elements.loader || !this.elements.searchStatus) {
      console.error('Elementos de status não encontrados.');
      return;
    }

    this.elements.loader.classList.remove('hidden');
    this.elements.searchStatus.textContent = 'Buscando...';
    try {
      const { produto, config_loja } = await ApiService.fetchProductData(sku, lojaId);
      this.elements.titulo.value = produto.titulo || '';
      this.custoFornecedorAtual = produto.custo_update || 0;
      this.elements.custoUnitario.value = this.custoFornecedorAtual > 0 ? this.custoFornecedorAtual.toFixed(2) : '0.00';
      this.elements.custoUpdate.value = formatCurrency(this.custoFornecedorAtual);

      const { peso_kg, altura_cm, largura_cm, comprimento_cm } = produto;
      const pesoCubico = ((altura_cm || 0) * (largura_cm || 0) * (comprimento_cm || 0)) / 6000;
      this.elements.alturaCm.value = altura_cm || 0;
      this.elements.larguraCm.value = largura_cm || 0;
      this.elements.comprimentoCm.value = comprimento_cm || 0;
      this.elements.pesoReal.value = peso_kg || 0;
      this.elements.pesoCubico.value = pesoCubico.toFixed(3);

      this.elements.searchStatus.textContent = 'Dados carregados.';
      this.elements.aliquota.value = this.elements.fulfillment.checked
        ? (config_loja.aliquota_fulfillment || 0)
        : (config_loja.aliquota_padrao || 0);

      this.checkCustoDivergence();
      this.elements.categoriaPrecificacao.dispatchEvent(new Event('change'));
    } catch (err) {
      this.elements.searchStatus.textContent = `Erro: ${err.message}`;
      console.error(err);
    } finally {
      this.elements.loader.classList.add('hidden');
    }
  }

  checkCustoDivergence() {
    const custoInformado = parseFloat(this.elements.custoUnitario.value) || 0;
    if (this.custoFornecedorAtual > 0 && Math.abs(custoInformado - this.custoFornecedorAtual) > 0.001) {
      if (this.elements.custoWarning) {
        this.elements.custoWarning.textContent = `Custo diverge do cadastro (${formatCurrency(this.custoFornecedorAtual)})`;
      }
      if (this.elements.custoUnitario) this.elements.custoUnitario.classList.add('cost-mismatch');
    } else {
      if (this.elements.custoWarning) this.elements.custoWarning.textContent = '';
      if (this.elements.custoUnitario) this.elements.custoUnitario.classList.remove('cost-mismatch');
    }
  }

  async handleSave() {
    if (!ValidationService.validateForm()) {
      showToast('Por favor, corrija os campos inválidos.', 'error');
      return;
    }

    this.elements.saveButton.classList.add('is-loading');
    this.elements.saveButton.disabled = true;

    try {
      const [marketplace, id_loja] = this.mode === 'edit'
        ? (this.elements.lojaMarketplace.value || '').split(' - ')
        : (this.elements.lojaMarketplace.options[this.elements.lojaMarketplace.selectedIndex]?.text || '').split(' - ');

      const selectedCategoryOption = this.elements.categoriaPrecificacao.options[this.elements.categoriaPrecificacao.selectedIndex];
      const payload = {
        marketplace: (marketplace || '').trim(),
        id_loja: (id_loja || '').trim(),
        sku: this.elements.sku.value,
        categoria_precificacao: selectedCategoryOption ? (selectedCategoryOption.dataset.nome || null) : null,
        titulo: this.elements.titulo.value,
        id_sku_marketplace: this.elements.idSkuMarketplace.value,
        id_anuncio: this.elements.idAnuncio.value,
        quantidade: parseInt(this.elements.quantidade.value, 10),
        custo_unitario: parseFloat(this.elements.custoUnitario.value),
        custo_total: parseCurrency(this.elements.custoTotal.value),
        aliquota: parseFloat(this.elements.aliquota.value),
        tarifa_fixa_classico: parseCurrency(this.elements.tarifaFixaClassico.value),
        tarifa_fixa_premium: parseCurrency(this.elements.tarifaFixaPremium.value),
        parcelamento: parseFloat(this.elements.parcelamento.value),
        outros: parseFloat(this.elements.outros.value),
        regra_comissao: this.elements.regraComissao.value,
        fulfillment: this.elements.fulfillment.checked,
        catalogo_buybox: this.elements.catalogoBuybox.checked,
        venda_classico: parseFloat(this.elements.vendaClassico.value),
        frete_classico: parseFloat(this.elements.freteClassico.value),
        repasse_classico: parseCurrency(this.elements.repasseClassico.value),
        lucro_classico: parseCurrency(this.elements.lucroRsClassico.value),
        margem_classico: parsePercent(this.elements.margemClassico.value),
        venda_premium: parseFloat(this.elements.vendaPremium.value),
        frete_premium: parseFloat(this.elements.fretePremium.value),
        repasse_premium: parseCurrency(this.elements.repassePremium.value),
        lucro_premium: parseCurrency(this.elements.lucroRsPremium.value),
        margem_premium: parsePercent(this.elements.margemPremium.value),
      };

      const result = await ApiService.savePricing(payload, this.mode, this.currentPricingId);
      this.currentPricingId = result.id || this.currentPricingId;

      if (this.mode === 'new') {
        showAppModal({
          title: 'Sucesso!',
          bodyHtml: `<p>Precificação base salva com sucesso.</p><p>Deseja ir para a página de edição para adicionar campanhas?</p>`,
          buttons: [
            { text: 'Não, Obrigado', class: 'secondary', onClick: () => { window.location.href = '/calculadora'; } },
            { text: 'Sim, Adicionar Campanha', class: 'primary', onClick: () => { window.location.href = `/editar?id=${this.currentPricingId}`; } }
          ]
        });
      } else {
        showToast('Precificação atualizada com sucesso!');
      }
    } catch (err) {
      console.error(err);
      showToast(err.message || 'Erro ao salvar.', 'error');
    } finally {
      this.elements.saveButton.classList.remove('is-loading');
      this.elements.saveButton.disabled = false;
    }
  }

  async loadAndPopulateSavedData() {
    const data = await ApiService.fetchEditData(this.recordId);
    const { precificacao_base, config_loja, produto_atual } = data;

    this.lojaConfigAtual = config_loja;
    comissoesCache = config_loja.comissoes || [];
    this.elements.regraComissao.innerHTML = '';
    comissoesCache.forEach(c => this.elements.regraComissao.add(new Option(c.chave, c.chave)));

    // preencher campos existentes pelo id
    Object.keys(this.elements).forEach(key => {
      const element = this.elements[key];
      if (!element || !element.id) return;
      const savedValue = precificacao_base[element.id.replace(/-/g, '_')];
      if (savedValue !== undefined && savedValue !== null) {
        if (element.type === 'checkbox') element.checked = !!savedValue;
        else element.value = savedValue;
      }
    });

    // loja/marketplace em campo somente leitura
    this.elements.lojaMarketplace.value = `${precificacao_base.marketplace} - ${precificacao_base.id_loja}`;
    const savedCategory = categoriasPrecificacaoCache.find(c => c.nome === precificacao_base.categoria_precificacao);
    if (savedCategory) this.elements.categoriaPrecificacao.value = savedCategory.margem_padrao;

    // dados do produto atual
    this.custoFornecedorAtual = produto_atual.custo_update || 0;
    this.elements.custoUpdate.value = formatCurrency(this.custoFornecedorAtual);
    const { peso_kg, altura_cm, largura_cm, comprimento_cm } = produto_atual;
    const pesoCubico = ((altura_cm || 0) * (largura_cm || 0) * (comprimento_cm || 0)) / 6000;
    this.elements.alturaCm.value = altura_cm || 0;
    this.elements.larguraCm.value = largura_cm || 0;
    this.elements.comprimentoCm.value = comprimento_cm || 0;
    this.elements.pesoReal.value = peso_kg || 0;
    this.elements.pesoCubico.value = pesoCubico.toFixed(3);

    this.checkCustoDivergence();
    this.elements.categoriaPrecificacao.dispatchEvent(new Event('change'));
  }
}

/* =========================
   Bootstrap + função global
   ========================= */

// Caso a página use inicialização automática
document.addEventListener('DOMContentLoaded', async () => {
  // se existir um container de formulário, iniciamos por padrão
  if (document.getElementById('pricing-form')) {
    try {
      await checkAuthStatusAndUpdateNav();
      setupLogoutButton();
      const params = new URLSearchParams(window.location.search);
      const id = params.get('id');
      const mode = id ? 'edit' : 'new';
      const manager = new PricingFormManager(mode, id);
      manager.init();
    } catch (e) {
      console.error('Erro ao inicializar a página da calculadora:', e);
      showToast('Erro ao inicializar a calculadora.', 'error');
    }
  }
});

// Expor função global para páginas que chamam manualmente (evita ReferenceError)
window.initializePricingForm = async function initializePricingForm() {
  await checkAuthStatusAndUpdateNav();
  setupLogoutButton();
  const params = new URLSearchParams(window.location.search);
  const id = params.get('id');
  const mode = id ? 'edit' : 'new';
  const manager = new PricingFormManager(mode, id);
  manager.init();
};
