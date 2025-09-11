// static/pricingLogic.js

// Cache global para evitar múltiplas buscas.
let regrasFreteCache = [];
let regrasTarifaFixaCache = [];
let comissoesCache = [];
let categoriasPrecificacaoCache = [];

/**
 * Módulo de Validação: Centraliza as regras e a lógica de validação dos campos.
 */
const ValidationService = {
    rules: {
        'loja-marketplace': { required: true, message: 'A loja é obrigatória.' },
        'sku': { required: true, message: 'O SKU é obrigatório.' },
        'titulo': { required: true, message: 'O título é obrigatório.' },
        'custo-unitario': { required: true, isNumeric: true, notNegative: true, message: 'Custo deve ser um número positivo.' },
        'quantidade': { required: true, isNumeric: true, notNegative: true, message: 'Qtd. deve ser um número positivo.' }
    },

    validateField(element) {
        const rule = this.rules[element.id];
        if (!rule) return true;

        const value = element.value.trim();
        let isValid = true;
        let errorMessage = '';

        if (rule.required && !value) {
            isValid = false;
            errorMessage = rule.message;
        } else if (value && rule.isNumeric && isNaN(parseFloat(value))) {
            isValid = false;
            errorMessage = rule.message;
        } else if (value && rule.notNegative && parseFloat(value) < 0) {
            isValid = false;
            errorMessage = rule.message;
        }

        this.updateFieldUI(element, isValid, errorMessage);
        return isValid;
    },

    updateFieldUI(element, isValid, message) {
        element.classList.toggle('is-valid', isValid);
        element.classList.toggle('is-invalid', !isValid);
        
        let errorContainer = element.parentElement.querySelector('.error-message');
        if (!errorContainer) {
            errorContainer = document.createElement('div');
            errorContainer.className = 'error-message';
            element.parentElement.appendChild(errorContainer);
        }

        errorContainer.textContent = message;
    },
    
    validateForm(formElements) {
        let isFormValid = true;
        for (const key in this.rules) {
            const element = document.getElementById(key);
            if (element) {
                if (!this.validateField(element)) {
                    isFormValid = false;
                }
            }
        }
        return isFormValid;
    }
};


/**
 * Módulo de API: Centraliza todas as chamadas fetch para o backend.
 */
const ApiService = {
    async fetchInitialData() {
        const [regrasRes, categoriasRes] = await Promise.all([
            fetch('/api/regras-negocio'),
            fetch('/api/precificacao/categorias-precificacao')
        ]);
        if (!regrasRes.ok) throw new Error("Falha ao carregar regras de negócio.");
        if (!categoriasRes.ok) throw new Error("Falha ao carregar categorias de precificação.");
        
        const regrasData = await regrasRes.json();
        const categoriasData = await categoriasRes.json();
        return { regras: regrasData, categorias: categoriasData };
    },
    async fetchLojas() {
        const response = await fetch('/api/config/lojas');
        if (!response.ok) throw new Error('Falha ao buscar lojas.');
        return response.json();
    },
    async fetchLojaDetails(lojaId) {
        const response = await fetch(`/api/config/lojas/${lojaId}/detalhes`);
        if (!response.ok) throw new Error('Falha ao carregar detalhes da loja.');
        return response.json();
    },
    async fetchProductData(sku, lojaId) {
        const response = await fetch(`/api/precificacao/dados-para-calculo?sku=${encodeURIComponent(sku)}&loja_id=${encodeURIComponent(lojaId)}`);
        if (!response.ok) throw new Error((await response.json()).detail || 'SKU não encontrado.');
        return response.json();
    },
    async fetchEditData(recordId) {
        const response = await fetch(`/api/precificacao/${recordId}/edit-data`);
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || `Erro ${response.status}: ${response.statusText}`);
        }
        return response.json();
    },
    async savePricing(payload, mode, recordId) {
        const url = mode === 'edit' ? `/api/precificacao/${recordId}` : '/api/precificacao';
        const method = mode === 'edit' ? 'PUT' : 'POST';
        const response = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        if (!response.ok) throw new Error((await response.json()).detail || 'Erro ao salvar.');
        return response.json();
    }
};

/**
 * Módulo de Lógica de Precificação: Contém todos os cálculos.
 */
const PricingCalculator = {
    getTarifaFixaMl(valorVenda) {
        const regra = regrasTarifaFixaCache.find(r =>
            valorVenda >= (r.min_venda || 0) && valorVenda <= (r.max_venda || Infinity)
        );
        if (!regra) return 0;
        return (regra.taxa_fixa || 0) + (valorVenda * (regra.taxa_percentual || 0) / 100);
    },
    getFretePorRegra(valorVenda, pesoKg) {
        if (!pesoKg || pesoKg <= 0) return 0;
        const pesoGramas = pesoKg * 1000;
        const regra = regrasFreteCache.find(r => 
            valorVenda >= (r.min_venda || 0) && valorVenda <= (r.max_venda || Infinity) &&
            pesoGramas >= (r.min_peso_g || 0) && pesoGramas <= (r.max_peso_g || Infinity)
        );
        return regra ? regra.custo_frete : 0;
    },
    calculateAll(elements, sourceId) {
        const C = {
            custoTotal: (parseFloat(elements.custoUnitario.value) || 0) * (parseInt(elements.quantidade.value, 10) || 1),
            aliquota: parseFloat(elements.aliquota.value) || 0,
            parcelamento: parseFloat(elements.parcelamento.value) || 0,
            outros: parseFloat(elements.outros.value) || 0,
            regraComissaoChave: elements.regraComissao.value,
        };
        elements.custoTotal.value = formatCurrency(C.custoTotal);
        
        const regraComissao = comissoesCache.find(c => c.chave === C.regraComissaoChave);
        if (!regraComissao) return;

        const pesoRealKg = parseFloat(elements.pesoReal.value) || 0;
        const pesoCubicoKg = parseFloat(elements.pesoCubico.value) || 0;
        const pesoConsiderado = Math.max(pesoRealKg, pesoCubicoKg);
        
        const calcularPlano = (plano) => {
            const planoUpper = plano.charAt(0).toUpperCase() + plano.slice(1);
            const margemDesejadaEl = elements[`margemDesejada${planoUpper}`];
            const vendaEl = elements[`venda${planoUpper}`];
            const freteEl = elements[`frete${planoUpper}`];
            
            let valorVenda = parseFloat(vendaEl.value) || 0;
            const margemDesejada = parseFloat(margemDesejadaEl.value) || 0;

            if (sourceId !== vendaEl.id && margemDesejada > 0) {
                const custosPercentuais = C.aliquota + C.parcelamento + C.outros + parseFloat(regraComissao[plano]);
                const denominador = 1 - ((custosPercentuais + margemDesejada) / 100);
                if (denominador > 0.0001) {
                    let valorTeste = C.custoTotal > 0 ? C.custoTotal * 1.5 : 50;
                    for (let i = 0; i < 10; i++) { 
                        const freteTeste = this.getFretePorRegra(valorTeste, pesoConsiderado);
                        const tarifaFixaTeste = this.getTarifaFixaMl(valorTeste);
                        const novoValor = (C.custoTotal + freteTeste + tarifaFixaTeste) / denominador;
                        if (Math.abs(novoValor - valorTeste) < 0.01) {
                            valorTeste = novoValor;
                            break;
                        }
                        valorTeste = novoValor;
                    }
                    valorVenda = valorTeste;
                } else {
                    valorVenda = 0;
                }
                vendaEl.value = valorVenda > 0 ? valorVenda.toFixed(2) : '0.00';
            } else if (sourceId === vendaEl.id) {
                margemDesejadaEl.value = '';
            }

            const freteAutomatico = this.getFretePorRegra(valorVenda, pesoConsiderado);
            let freteFinal = freteAutomatico;
            if (sourceId !== freteEl.id) {
                freteEl.value = freteAutomatico.toFixed(2);
            } else {
                freteFinal = parseFloat(freteEl.value) || 0;
            }

            const tarifaFixaFinal = this.getTarifaFixaMl(valorVenda);
            const comissaoValor = valorVenda * (parseFloat(regraComissao[plano]) / 100);
            const outrosCustos = valorVenda * ((C.aliquota + C.parcelamento + C.outros) / 100);
            const repasse = valorVenda - comissaoValor - outrosCustos - tarifaFixaFinal - freteFinal;
            const lucro = repasse - C.custoTotal;
            const margemReal = valorVenda > 0 ? (lucro / valorVenda) * 100 : 0;
            
            elements[`tarifaFixa${planoUpper}`].value = formatCurrency(tarifaFixaFinal);
            elements[`repasse${planoUpper}`].value = formatCurrency(repasse);
            elements[`lucroRs${planoUpper}`].value = formatCurrency(lucro);
            elements[`margem${planoUpper}`].value = formatPercent(margemReal);
            
            const lucroEl = elements[`lucroRs${planoUpper}`];
            lucroEl.classList.toggle('text-success', lucro > 0);
            lucroEl.classList.toggle('text-danger', lucro < 0);
        };

        calcularPlano('classico');
        calcularPlano('premium');
    }
};


/**
 * Gerencia o estado e a interface do formulário de precificação.
 */
class PricingFormManager {
    constructor(mode, recordId = null) {
        this.mode = mode;
        this.recordId = recordId;
        this.currentPricingId = recordId; // Para manter o ID após salvar
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
        } catch (error) {
            console.error("Erro fatal ao inicializar:", error);
            const errorContainer = document.getElementById('error-message');
            if (errorContainer) {
                errorContainer.textContent = `Erro: ${error.message}`;
                errorContainer.classList.remove('hidden');
                this.formContainer.classList.add('hidden');
            } else {
                 showAppModal({ title: 'Erro Crítico', bodyHtml: `<p>${error.message}</p>`, buttons: [{ text: 'OK' }] });
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
                <h2>Custo, Comissão e Tarifas (Preço Base)</h2>
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
                        <div class="form-field"><label>Margem Lucro (%)</label><input type="text" id="margem-lucro-perc-classico" readonly></div>
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
                        <div class="form-field"><label>Margem Lucro (%)</label><input type="text" id="margem-lucro-perc-premium" readonly></div>                         
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
            'loja-marketplace', 'sku', 'search-status', 'loader', 'titulo', 'id-sku-marketplace', 'id-anuncio',
            'altura-cm', 'largura-cm', 'comprimento-cm', 'peso-real', 'peso-cubico', 'quantidade', 'custo-unitario',
            'custo-total', 'custo-update', 'custo-warning', 'aliquota', 'parcelamento', 'outros', 'regra-comissao',
            'categoria-precificacao', 'fulfillment', 'catalogo-buybox', 
            'valor-venda-classico', 'valor-frete-classico', 'margem-desejada-classico', 'tarifa-fixa-classico', 'repasse-classico', 'lucro-rs-classico', 'margem-lucro-perc-classico', 
            'valor-venda-premium', 'valor-frete-premium', 'margem-desejada-premium', 'tarifa-fixa-premium', 'repasse-premium', 'lucro-rs-premium', 'margem-lucro-perc-premium', 
            'save-button'
        ];
        const camelCaseMap = {
            'loja-marketplace': 'lojaMarketplace', 'id-sku-marketplace': 'idSkuMarketplace', 'id-anuncio': 'idAnuncio',
            'altura-cm': 'alturaCm', 'largura-cm': 'larguraCm', 'comprimento-cm': 'comprimentoCm', 'peso-real': 'pesoReal',
            'peso-cubico': 'pesoCubico', 'custo-unitario': 'custoUnitario', 'custo-total': 'custoTotal',
            'custo-update': 'custoUpdate', 'custo-warning': 'custoWarning', 'regra-comissao': 'regraComissao',
            'categoria-precificacao': 'categoriaPrecificacao', 'catalogo-buybox': 'catalogoBuybox',
            'valor-venda-classico': 'vendaClassico', 'valor-frete-classico': 'freteClassico', 'margem-desejada-classico': 'margemDesejadaClassico',
            'tarifa-fixa-classico': 'tarifaFixaClassico', 'repasse-classico': 'repasseClassico', 'lucro-rs-classico': 'lucroRsClassico', 'margem-lucro-perc-classico': 'margemClassico',
            'valor-venda-premium': 'vendaPremium', 'valor-frete-premium': 'fretePremium', 'margem-desejada-premium': 'margemDesejadaPremium',
            'tarifa-fixa-premium': 'tarifaFixaPremium', 'repasse-premium': 'repassePremium', 'lucro-rs-premium': 'lucroRsPremium', 'margem-lucro-perc-premium': 'margemPremium',
            'save-button': 'saveButton'
        };
        ids.forEach(id => {
            const key = camelCaseMap[id] || id;
            const element = document.getElementById(id);
            if (!element) {
                console.warn(`[cacheElements] Elemento com ID '${id}' não foi encontrado no DOM.`);
            }
            this.elements[key] = element;
        });
    }

    attachEventListeners() {
        // Event listeners for fields that trigger recalculation
        const calculationFields = [
            this.elements.quantidade, this.elements.custoUnitario, this.elements.parcelamento, this.elements.outros,
            this.elements.freteClassico, this.elements.fretePremium, this.elements.vendaClassico, this.elements.vendaPremium,
            this.elements.margemDesejadaClassico, this.elements.margemDesejadaPremium, this.elements.fulfillment,
            this.elements.categoriaPrecificacao, this.elements.regraComissao
        ];
        calculationFields.forEach(el => {
            if (el) {
                const eventType = (el.tagName === 'SELECT' || el.type === 'checkbox') ? 'change' : 'input';
                el.addEventListener(eventType, (e) => this.handleCalculation(e));
            }
        });
        
        // Event listeners for specific UI interactions
        if (this.mode === 'new' && this.elements.lojaMarketplace && this.elements.sku) {
            this.elements.lojaMarketplace.addEventListener('change', () => this.handleLojaChange());
            this.elements.sku.addEventListener('keyup', (e) => {
                clearTimeout(this.debounceTimer);
                this.debounceTimer = setTimeout(() => this.fetchProductData(), e.key === 'Enter' ? 0 : 500);
            });
        }

        if(this.elements.saveButton) this.elements.saveButton.addEventListener('click', () => this.handleSave());
        if(this.elements.custoUnitario) this.elements.custoUnitario.addEventListener('input', () => this.checkCustoDivergence());
        
        // Add validation listeners
        Object.keys(ValidationService.rules).forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('blur', () => ValidationService.validateField(el));
                el.addEventListener('input', () => ValidationService.validateField(el));
            }
        });
    }

    handleCalculation(e) {
        if (this.isCalculating) return;
        this.isCalculating = true;
    
        // Se o evento foi disparado pela seleção de categoria, atualiza as margens desejadas
        if (e.target.id === 'categoria-precificacao') {
            const selectedOption = this.elements.categoriaPrecificacao.options[this.elements.categoriaPrecificacao.selectedIndex];
            const margemPadrao = selectedOption.value; // O value do option é a margem
            if (margemPadrao) {
                this.elements.margemDesejadaClassico.value = margemPadrao;
                this.elements.margemDesejadaPremium.value = margemPadrao;
            } else {
                // Limpa se a opção "Padrão" for selecionada
                this.elements.margemDesejadaClassico.value = '';
                this.elements.margemDesejadaPremium.value = '';
            }
        }
    
        try {
            // Trigger validation on related fields before calculating
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
        } catch (error) {
            this.elements.lojaMarketplace.innerHTML = `<option value="">${error.message}</option>`;
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
            
            this.elements.aliquota.value = this.elements.fulfillment.checked ? (this.lojaConfigAtual.aliquota_fulfillment || 0) : (this.lojaConfigAtual.aliquota_padrao || 0);
            
            if (this.elements.sku.value.trim()) {
                await this.fetchProductData();
            } else {
                this.handleCalculation({ target: { id: 'loja-marketplace' } });
            }
        } catch (error) {
            showAppModal({ title: 'Erro', bodyHtml: `<p>${error.message}</p>`, buttons: [{ text: 'OK' }] });
        }
    }

    async fetchProductData() {
        const skuValue = this.elements.sku.value.trim();
        const lojaId = this.elements.lojaMarketplace.value;
        
        if (!skuValue || !lojaId) return;

        if (!this.elements.loader || !this.elements.searchStatus) {
            console.error("Elementos da UI para status da busca não encontrados. O cache pode ter falhado.");
            return;
        }

        this.elements.loader.classList.remove('hidden');
        this.elements.searchStatus.textContent = 'Buscando...';
        try {
            const { produto, config_loja } = await ApiService.fetchProductData(skuValue, lojaId);
            
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
            this.elements.aliquota.value = this.elements.fulfillment.checked ? (config_loja.aliquota_fulfillment || 0) : (config_loja.aliquota_padrao || 0);

            this.checkCustoDivergence();
            this.elements.categoriaPrecificacao.dispatchEvent(new Event('change'));
        } catch(error) {
            this.elements.searchStatus.textContent = `Erro: ${error.message}`;
            console.error(error);
        } finally {
            this.elements.loader.classList.add('hidden');
        }
    }
    
    checkCustoDivergence() {
        const custoInformado = parseFloat(this.elements.custoUnitario.value) || 0;
        if (this.custoFornecedorAtual > 0 && Math.abs(custoInformado - this.custoFornecedorAtual) > 0.001) {
            if(this.elements.custoWarning) this.elements.custoWarning.textContent = `Custo diverge do cadastro (${formatCurrency(this.custoFornecedorAtual)})`;
            if(this.elements.custoUnitario) this.elements.custoUnitario.classList.add('cost-mismatch');
        } else {
            if(this.elements.custoWarning) this.elements.custoWarning.textContent = '';
            if(this.elements.custoUnitario) this.elements.custoUnitario.classList.remove('cost-mismatch');
        }
    }

    async handleSave() {
        if (!ValidationService.validateForm(this.elements)) {
            showToast('Por favor, corrija os campos inválidos.', 'error');
            return;
        }

        this.elements.saveButton.classList.add('is-loading');
        this.elements.saveButton.disabled = true;

        try {
            const [marketplace, id_loja] = this.mode === 'edit'
                ? this.elements.lojaMarketplace.value.split(' - ')
                : this.elements.lojaMarketplace.options[this.elements.lojaMarketplace.selectedIndex].text.split(' - ');
            
            const selectedCategoryOption = this.elements.categoriaPrecificacao.options[this.elements.categoriaPrecificacao.selectedIndex];
            const payload = {
                marketplace: marketplace.trim(), id_loja: id_loja.trim(), sku: this.elements.sku.value,
                categoria_precificacao: selectedCategoryOption ? selectedCategoryOption.dataset.nome : null,
                titulo: this.elements.titulo.value, id_sku_marketplace: this.elements.idSkuMarketplace.value,
                id_anuncio: this.elements.idAnuncio.value, quantidade: parseInt(this.elements.quantidade.value, 10),
                custo_unitario: parseFloat(this.elements.custoUnitario.value), custo_total: parseCurrency(this.elements.custoTotal.value),
                aliquota: parseFloat(this.elements.aliquota.value), tarifa_fixa_classico: parseCurrency(this.elements.tarifaFixaClassico.value),
                tarifa_fixa_premium: parseCurrency(this.elements.tarifaFixaPremium.value), parcelamento: parseFloat(this.elements.parcelamento.value),
                outros: parseFloat(this.elements.outros.value), regra_comissao: this.elements.regraComissao.value,
                fulfillment: this.elements.fulfillment.checked, catalogo_buybox: this.elements.catalogoBuybox.checked,
                venda_classico: parseFloat(this.elements.vendaClassico.value), frete_classico: parseFloat(this.elements.freteClassico.value),
                repasse_classico: parseCurrency(this.elements.repasseClassico.value), lucro_classico: parseCurrency(this.elements.lucroRsClassico.value),
                margem_classico: parsePercent(this.elements.margemClassico.value), venda_premium: parseFloat(this.elements.vendaPremium.value),
                frete_premium: parseFloat(this.elements.fretePremium.value), repasse_premium: parseCurrency(this.elements.repassePremium.value),
                lucro_premium: parseCurrency(this.elements.lucroRsPremium.value), margem_premium: parsePercent(this.elements.margemPremium.value),
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
        } catch (error) {
            showToast(error.message, 'error');
        } finally {
            this.elements.saveButton.classList.remove('is-loading');
            this.elements.saveButton.disabled = false;
        }
    }
    
    async loadAndPopulateSavedData() {
        try {
            const data = await ApiService.fetchEditData(this.recordId);
            const { precificacao_base, config_loja, produto_atual } = data;
            
            this.lojaConfigAtual = config_loja;
            comissoesCache = config_loja.comissoes || [];
            this.elements.regraComissao.innerHTML = '';
            comissoesCache.forEach(c => this.elements.regraComissao.add(new Option(c.chave, c.chave)));

            Object.keys(this.elements).forEach(key => {
                const element = this.elements[key];
                const savedValue = precificacao_base[element.id.replace(/-/g, '_')];
                if (savedValue !== undefined && savedValue !== null) {
                    if (element.type === 'checkbox') {
                        element.checked = !!savedValue;
                    } else {
                        element.value = savedValue;
                    }
                }
            });
            
            this.elements.lojaMarketplace.value = `${precificacao_base.marketplace} - ${precificacao_base.id_loja}`;
            const savedCategory = categoriasPrecificacaoCache.find(c => c.nome === precificacao_base.categoria_precificacao);
            if (savedCategory) this.elements.categoriaPrecificacao.value = savedCategory.margem_padrao;
            
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
            this.handleCalculation({ target: { id: 'load-edit-data' } });
            
            // Dispara um evento para notificar que os dados foram carregados
            document.dispatchEvent(new CustomEvent('pricingDataLoaded', { detail: { sku: precificacao_base.sku } }));
            
        } catch (error) {
            document.getElementById('error-message').textContent = `Erro: ${error.message}`;
            document.getElementById('error-message').classList.remove('hidden');
            this.formContainer.classList.add('hidden');
        }
    }
}


/**
 * Ponto de entrada para inicializar o formulário.
 */
function initializePricingForm(mode, recordId = null) {
    const manager = new PricingFormManager(mode, recordId);
    manager.init()};