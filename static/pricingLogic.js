// static/pricingLogic.js

// Cache global para evitar múltiplas buscas.
let regrasFreteCache = [];
let regrasTarifaFixaCache = [];
let comissoesCache = [];
let categoriasPrecificacaoCache = [];

/**
 * Carrega todas as regras de negócio e configurações iniciais do servidor.
 */
async function loadInitialData() {
    try {
        const [regrasRes, categoriasRes] = await Promise.all([
            fetch('/api/regras-negocio'),
            fetch('/api/categorias-precificacao')
        ]);

        if (regrasRes.ok) {
            const regrasData = await regrasRes.json();
            regrasFreteCache = regrasData.REGRAS_FRETE_ML || [];
            regrasTarifaFixaCache = regrasData.REGRAS_TARIFA_FIXA_ML || [];
        } else {
            console.error("Falha ao carregar regras de negócio.");
        }

        if (categoriasRes.ok) {
            categoriasPrecificacaoCache = await categoriasRes.json();
        } else {
            console.error("Falha ao carregar categorias de precificação.");
        }
    } catch (error) {
        console.error("Erro fatal ao carregar dados iniciais:", error);
        showAppModal({ title: 'Erro Crítico', bodyHtml: '<p>Não foi possível carregar as configurações essenciais. A calculadora pode não funcionar corretamente.</p>', buttons: [{ text: 'OK' }] });
    }
}


/**
 * Inicializa o formulário de precificação, criando o HTML e anexando os listeners.
 * @param {('new'|'edit')} mode - O modo de operação do formulário.
 * @param {string|null} recordId - O ID do registro a ser editado (apenas no modo 'edit').
 */
function initializePricingForm(mode, recordId = null) {
    const formHtml = `
        <section class="form-section">
            <h2>Dados Iniciais</h2>
            <div class="form-row" style="grid-template-columns: 1fr 1fr 2fr;">
                <div class="form-field">
                    <label for="loja-marketplace">Loja / Marketplace</label>
                    ${mode === 'edit' ? '<input type="text" id="loja-marketplace" readonly>' : '<select id="loja-marketplace" required></select>'}
                </div>
                <div class="form-field">
                    <label for="categoria-precificacao">Categoria Precificação</label>
                    <select id="categoria-precificacao"></select>
                </div>
                <div class="form-field">
                    <label for="sku">SKU (Magis)</label>
                    <input type="text" id="sku" ${mode === 'edit' ? 'readonly' : 'placeholder="Selecione uma loja e digite o SKU..."'}>
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
            <button type="button" id="save-button" class="app-button save-button">${mode === 'edit' ? 'Salvar Alterações' : 'Salvar Precificação'}</button>
        </div>
    `;

    const formContainer = document.getElementById('pricing-form');
    formContainer.innerHTML = formHtml;

    const initialLoader = document.getElementById('initial-loader');
    if(initialLoader) initialLoader.classList.add('hidden');
    formContainer.classList.remove('hidden');

    attachFormListeners(mode, recordId);
}

/**
 * Anexa todos os event listeners aos campos do formulário.
 * @param {('new'|'edit')} mode - O modo de operação do formulário.
 * @param {string|null} recordId - O ID do registro a ser editado (apenas no modo 'edit').
 */
function attachFormListeners(mode, recordId) {
    let debounceTimer;
    let isCalculating = false;
    let custoFornecedorAtual = 0;
    let lojaConfigAtual = {};
    let currentPricingId = recordId;

    const elements = {
        lojaMarketplace: document.getElementById('loja-marketplace'),
        sku: document.getElementById('sku'),
        searchStatus: document.getElementById('search-status'),
        loader: document.getElementById('loader'),
        titulo: document.getElementById('titulo'),
        idSkuMarketplace: document.getElementById('id-sku-marketplace'),
        idAnuncio: document.getElementById('id-anuncio'),
        alturaCm: document.getElementById('altura-cm'),
        larguraCm: document.getElementById('largura-cm'),
        comprimentoCm: document.getElementById('comprimento-cm'),
        pesoReal: document.getElementById('peso-real'),
        pesoCubico: document.getElementById('peso-cubico'),
        quantidade: document.getElementById('quantidade'),
        custoUnitario: document.getElementById('custo-unitario'),
        custoTotal: document.getElementById('custo-total'),
        custoUpdate: document.getElementById('custo-update'),
        custoWarning: document.getElementById('custo-warning'),
        aliquota: document.getElementById('aliquota'),
        parcelamento: document.getElementById('parcelamento'),
        outros: document.getElementById('outros'),
        regraComissao: document.getElementById('regra-comissao'),
        categoriaPrecificacao: document.getElementById('categoria-precificacao'),
        fulfillment: document.getElementById('fulfillment'),
        catalogoBuybox: document.getElementById('catalogo-buybox'),
        vendaClassico: document.getElementById('valor-venda-classico'),
        freteClassico: document.getElementById('valor-frete-classico'),
        margemDesejadaClassico: document.getElementById('margem-desejada-classico'),
        tarifaFixaClassico: document.getElementById('tarifa-fixa-classico'),
        repasseClassico: document.getElementById('repasse-classico'),
        lucroRsClassico: document.getElementById('lucro-rs-classico'),
        margemClassico: document.getElementById('margem-lucro-perc-classico'),
        vendaPremium: document.getElementById('valor-venda-premium'),
        fretePremium: document.getElementById('valor-frete-premium'),
        margemDesejadaPremium: document.getElementById('margem-desejada-premium'),
        tarifaFixaPremium: document.getElementById('tarifa-fixa-premium'),
        repassePremium: document.getElementById('repasse-premium'),
        lucroRsPremium: document.getElementById('lucro-rs-premium'),
        margemPremium: document.getElementById('margem-lucro-perc-premium'),
        saveButton: document.getElementById('save-button'),
    };

    const formatCurrency = (value) => `R$ ${parseFloat(value || 0).toFixed(2).replace('.', ',')}`;
    const formatPercent = (value) => `${parseFloat(value || 0).toFixed(2).replace('.', ',')}%`;

    // --- LÓGICA DE CÁLCULO ---

    const checkCustoDivergence = () => {
        const custoInformado = parseFloat(elements.custoUnitario.value) || 0;
        if (custoFornecedorAtual > 0 && Math.abs(custoInformado - custoFornecedorAtual) > 0.001) {
            elements.custoWarning.textContent = `Custo diverge do cadastro (${formatCurrency(custoFornecedorAtual)})`;
            elements.custoUnitario.classList.add('cost-mismatch');
        } else {
            elements.custoWarning.textContent = '';
            elements.custoUnitario.classList.remove('cost-mismatch');
        }
    };

    const getTarifaFixaMl = (valorVenda) => {
        const regra = regrasTarifaFixaCache.find(r =>
            valorVenda >= (r.min_venda || 0) && valorVenda <= (r.max_venda || Infinity)
        );
        if (!regra) return 0;
        return (regra.taxa_fixa || 0) + (valorVenda * (regra.taxa_percentual || 0) / 100);
    };

    const getFretePorRegra = (valorVenda, pesoKg) => {
        if (!pesoKg || pesoKg <= 0) return 0;
        const pesoGramas = pesoKg * 1000;
        const regra = regrasFreteCache.find(r => 
            valorVenda >= (r.min_venda || 0) && valorVenda <= (r.max_venda || Infinity) &&
            pesoGramas >= (r.min_peso_g || 0) && pesoGramas <= (r.max_peso_g || Infinity)
        );
        return regra ? regra.custo_frete : 0;
    };
    
    const updateAllCalculations = (sourceId = null) => {
        if (isCalculating) return;
        isCalculating = true;

        try {
            const C = {
                custoTotal: (parseFloat(elements.custoUnitario.value) || 0) * (parseInt(elements.quantidade.value, 10) || 1),
                aliquota: parseFloat(elements.aliquota.value) || 0,
                parcelamento: parseFloat(elements.parcelamento.value) || 0,
                outros: parseFloat(elements.outros.value) || 0,
                regraComissaoChave: elements.regraComissao.value,
            };
            elements.custoTotal.value = formatCurrency(C.custoTotal);
            
            const regraComissao = comissoesCache.find(c => c.chave === C.regraComissaoChave);
            if (!regraComissao) {
                isCalculating = false;
                return;
            }

            const pesoRealKg = parseFloat(elements.pesoReal.value) || 0;
            const pesoCubicoKg = parseFloat(elements.pesoCubico.value) || 0;
            const pesoConsiderado = Math.max(pesoRealKg, pesoCubicoKg);
            
            const calcularPlano = (plano, comissaoPerc) => {
                const custosPercentuais = C.aliquota + C.parcelamento + C.outros + comissaoPerc;
                const margemDesejadaEl = elements[`margemDesejada${plano}`];
                const vendaEl = elements[`venda${plano}`];
                const freteEl = elements[`frete${plano}`];
                let valorVenda = parseFloat(vendaEl.value) || 0;
                const margemDesejada = parseFloat(margemDesejadaEl.value) || 0;

                if (sourceId !== vendaEl.id && margemDesejada > 0) {
                    const denominador = 1 - ((custosPercentuais + margemDesejada) / 100);
                    if (denominador > 0.0001) {
                        let valorTeste = C.custoTotal > 0 ? C.custoTotal * 1.5 : 50;
                        for (let i = 0; i < 10; i++) { 
                            const freteTeste = getFretePorRegra(valorTeste, pesoConsiderado);
                            const tarifaFixaTeste = getTarifaFixaMl(valorTeste);
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

                const freteAutomatico = getFretePorRegra(valorVenda, pesoConsiderado);
                let freteFinal = freteAutomatico;
                if (sourceId !== freteEl.id) {
                    freteEl.value = freteAutomatico.toFixed(2);
                } else {
                    freteFinal = parseFloat(freteEl.value) || 0;
                }

                const tarifaFixaFinal = getTarifaFixaMl(valorVenda);
                const comissaoValor = valorVenda * (comissaoPerc / 100);
                const outrosCustos = valorVenda * ((C.aliquota + C.parcelamento + C.outros) / 100);
                const repasse = valorVenda - comissaoValor - outrosCustos - tarifaFixaFinal - freteFinal;
                const lucro = repasse - C.custoTotal;
                const margemReal = valorVenda > 0 ? (lucro / valorVenda) * 100 : 0;
                
                elements[`tarifaFixa${plano}`].value = formatCurrency(tarifaFixaFinal);
                elements[`repasse${plano}`].value = formatCurrency(repasse);
                elements[`lucroRs${plano}`].value = formatCurrency(lucro);
                elements[`margem${plano}`].value = formatPercent(margemReal);
                
                const lucroEl = elements[`lucroRs${plano}`];
                lucroEl.classList.toggle('text-success', lucro > 0);
                lucroEl.classList.toggle('text-danger', lucro < 0);
            };

            calcularPlano('Classico', parseFloat(regraComissao.classico));
            calcularPlano('Premium', parseFloat(regraComissao.premium));
        } finally {
            isCalculating = false;
        }
    };
    
    // --- LÓGICA DE PREENCHIMENTO E BUSCA DE DADOS ---

    const populateLojas = async () => {
        try {
            const response = await fetch('/api/config/lojas');
            if (!response.ok) throw new Error('Falha ao buscar lojas.');
            const lojas = await response.json();
            elements.lojaMarketplace.innerHTML = '<option value="">Selecione...</option>';
            lojas.forEach(loja => {
                const option = new Option(`${loja.marketplace} - ${loja.id_loja}`, loja.id);
                elements.lojaMarketplace.add(option);
            });
        } catch (error) {
            elements.lojaMarketplace.innerHTML = `<option value="">${error.message}</option>`;
        }
    };
    
    const populateCategorias = () => {
        elements.categoriaPrecificacao.innerHTML = '<option value="" data-nome="">Padrão</option>';
        categoriasPrecificacaoCache.forEach(cat => {
            const option = new Option(`${cat.nome} (${cat.margem_padrao}%)`, cat.margem_padrao);
            option.dataset.nome = cat.nome;
            elements.categoriaPrecificacao.add(option);
        });
    };

    const handleLojaChange = async () => {
        const lojaId = elements.lojaMarketplace.value;
        if (!lojaId) {
            lojaConfigAtual = {};
            comissoesCache = [];
            elements.aliquota.value = '';
            elements.regraComissao.innerHTML = '';
            return;
        }
        try {
            const response = await fetch(`/api/config/lojas/${lojaId}/detalhes`);
            if (!response.ok) throw new Error('Falha ao carregar detalhes da loja.');
            lojaConfigAtual = await response.json();
            
            comissoesCache = lojaConfigAtual.comissoes || [];
            elements.regraComissao.innerHTML = '';
            comissoesCache.forEach(c => elements.regraComissao.add(new Option(c.chave, c.chave)));
            
            if (comissoesCache.length > 0) {
                elements.regraComissao.value = comissoesCache[0].chave;
            }
            
            elements.aliquota.value = elements.fulfillment.checked ? (lojaConfigAtual.aliquota_fulfillment || 0) : (lojaConfigAtual.aliquota_padrao || 0);
            
            if (elements.sku.value.trim()) {
                await fetchProductData();
            } else {
                updateAllCalculations('loja-marketplace');
            }
        } catch (error) {
            showAppModal({ title: 'Erro', bodyHtml: `<p>${error.message}</p>`, buttons: [{ text: 'OK' }] });
        }
    };

    const fetchProductData = async () => {
        const skuValue = elements.sku.value.trim();
        const lojaId = elements.lojaMarketplace.value;
        if (!skuValue || !lojaId) return;

        elements.loader.classList.remove('hidden');
        elements.searchStatus.textContent = 'Buscando...';
        try {
            const response = await fetch(`/api/dados-para-calculo?sku=${encodeURIComponent(skuValue)}&loja_id=${encodeURIComponent(lojaId)}`);
            if (!response.ok) throw new Error((await response.json()).detail || 'SKU não encontrado.');
            
            const { produto, config_loja } = await response.json();
            
            elements.titulo.value = produto.titulo || '';
            custoFornecedorAtual = produto.custo_update || 0;
            
            elements.custoUnitario.value = custoFornecedorAtual > 0 ? custoFornecedorAtual.toFixed(2) : '0.00';
            elements.custoUpdate.value = formatCurrency(custoFornecedorAtual);
            
            const { peso_kg, altura_cm, largura_cm, comprimento_cm } = produto;
            const pesoCubico = ((altura_cm || 0) * (largura_cm || 0) * (comprimento_cm || 0)) / 6000;
            elements.alturaCm.value = altura_cm || 0;
            elements.larguraCm.value = largura_cm || 0;
            elements.comprimentoCm.value = comprimento_cm || 0;
            elements.pesoReal.value = peso_kg || 0;
            elements.pesoCubico.value = pesoCubico.toFixed(3);
            
            elements.searchStatus.textContent = 'Dados carregados.';
            elements.aliquota.value = elements.fulfillment.checked ? (config_loja.aliquota_fulfillment || 0) : (config_loja.aliquota_padrao || 0);

            checkCustoDivergence();
            elements.categoriaPrecificacao.dispatchEvent(new Event('change'));

        } catch(error) {
            elements.searchStatus.textContent = `Erro: ${error.message}`;
            console.error(error);
        } finally {
            elements.loader.classList.add('hidden');
        }
    };
    
    const handleSave = async () => {
        elements.saveButton.classList.add('is-loading');
        elements.saveButton.disabled = true;

        try {
            const [marketplace, id_loja] = mode === 'edit'
                ? elements.lojaMarketplace.value.split(' - ')
                : elements.lojaMarketplace.options[elements.lojaMarketplace.selectedIndex].text.split(' - ');
            
            const selectedCategoryOption = elements.categoriaPrecificacao.options[elements.categoriaPrecificacao.selectedIndex];
            const payload = {
                marketplace: marketplace.trim(), id_loja: id_loja.trim(),
                sku: elements.sku.value,
                categoria_precificacao: selectedCategoryOption ? selectedCategoryOption.dataset.nome : null,
                titulo: elements.titulo.value,
                id_sku_marketplace: elements.idSkuMarketplace.value,
                id_anuncio: elements.idAnuncio.value,
                quantidade: parseInt(elements.quantidade.value, 10),
                custo_unitario: parseFloat(elements.custoUnitario.value),
                custo_total: parseFloat(elements.custoTotal.value.replace('R$', '').replace(',', '.')),
                aliquota: parseFloat(elements.aliquota.value),
                tarifa_fixa_classico: parseFloat(elements.tarifaFixaClassico.value.replace('R$', '').replace(',', '.')),
                tarifa_fixa_premium: parseFloat(elements.tarifaFixaPremium.value.replace('R$', '').replace(',', '.')),
                parcelamento: parseFloat(elements.parcelamento.value),
                outros: parseFloat(elements.outros.value),
                regra_comissao: elements.regraComissao.value,
                fulfillment: elements.fulfillment.checked,
                catalogo_buybox: elements.catalogoBuybox.checked,
                venda_classico: parseFloat(elements.vendaClassico.value),
                frete_classico: parseFloat(elements.freteClassico.value),
                repasse_classico: parseFloat(elements.repasseClassico.value.replace('R$', '').replace(',', '.')),
                lucro_classico: parseFloat(elements.lucroRsClassico.value.replace('R$', '').replace(',', '.')),
                margem_classico: parseFloat(elements.margemClassico.value.replace('%', '').replace(',', '.')),
                venda_premium: parseFloat(elements.vendaPremium.value),
                frete_premium: parseFloat(elements.fretePremium.value),
                repasse_premium: parseFloat(elements.repassePremium.value.replace('R$', '').replace(',', '.')),
                lucro_premium: parseFloat(elements.lucroRsPremium.value.replace('R$', '').replace(',', '.')),
                margem_premium: parseFloat(elements.margemPremium.value.replace('%', '').replace(',', '.')),
            };
            
            const url = mode === 'edit' ? `/api/precificacao/atualizar/${currentPricingId}` : '/api/precificacao/salvar';
            const method = mode === 'edit' ? 'PUT' : 'POST';

            const response = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            
            if (!response.ok) throw new Error((await response.json()).detail || 'Erro ao salvar.');
            
            const result = await response.json();
            currentPricingId = result.id || currentPricingId; 

            if (mode === 'new') {
                showAppModal({ 
                    title: 'Sucesso!', 
                    bodyHtml: `<p>Precificação base salva com sucesso.</p><p>Deseja ir para a página de edição para adicionar campanhas?</p>`,
                    buttons: [
                        { text: 'Não, Obrigado', class: 'secondary', onClick: () => { window.location.href = '/calculadora'; } },
                        { text: 'Sim, Adicionar Campanha', class: 'primary', onClick: () => { window.location.href = `/editar?id=${currentPricingId}`; } }
                    ]
                });
            } else {
                 showAppModal({ 
                    title: 'Sucesso!', 
                    bodyHtml: `<p>Precificação base atualizada com sucesso.</p>`,
                    buttons: [ { text: 'OK', class: 'primary', onClick: () => { window.location.reload(); }} ]
                });
            }
        } catch (error) {
            showAppModal({ title: 'Erro ao Salvar', bodyHtml: `<p>${error.message}</p>`, buttons: [{ text: 'OK' }] });
        } finally {
            elements.saveButton.classList.remove('is-loading');
            elements.saveButton.disabled = false;
        }
    };
    
    const loadAndPopulateSavedData = async (id) => {
        try {
            const response = await fetch(`/api/precificacao/edit-data/${id}`);
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || `Erro ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            const { precificacao_base, config_loja, produto_atual } = data;
            
            // Setup de dropdowns e configs
            lojaConfigAtual = config_loja;
            comissoesCache = config_loja.comissoes || [];
            elements.regraComissao.innerHTML = '';
            comissoesCache.forEach(c => elements.regraComissao.add(new Option(c.chave, c.chave)));

            // Preenchimento manual e explícito dos campos
            elements.lojaMarketplace.value = `${precificacao_base.marketplace} - ${precificacao_base.id_loja}`;
            elements.sku.value = precificacao_base.sku || '';
            elements.titulo.value = precificacao_base.titulo || '';
            elements.idSkuMarketplace.value = precificacao_base.id_sku_marketplace || '';
            elements.idAnuncio.value = precificacao_base.id_anuncio || '';
            elements.quantidade.value = precificacao_base.quantidade || 1;
            elements.custoUnitario.value = precificacao_base.custo_unitario ? precificacao_base.custo_unitario.toFixed(2) : '0.00';
            elements.parcelamento.value = precificacao_base.parcelamento || 0;
            elements.outros.value = precificacao_base.outros || 0;
            elements.fulfillment.checked = !!precificacao_base.fulfillment;
            elements.catalogoBuybox.checked = !!precificacao_base.catalogo_buybox;
            elements.regraComissao.value = precificacao_base.regra_comissao;
            
            // Define a margem desejada com base no que foi salvo, para que o cálculo parta dela.
            elements.margemDesejadaClassico.value = precificacao_base.margem_classico || '';
            elements.margemDesejadaPremium.value = precificacao_base.margem_premium || '';

            elements.freteClassico.value = precificacao_base.frete_classico ? precificacao_base.frete_classico.toFixed(2) : '0.00';
            elements.fretePremium.value = precificacao_base.frete_premium ? precificacao_base.frete_premium.toFixed(2) : '0.00';
            
            const savedCategory = categoriasPrecificacaoCache.find(c => c.nome === precificacao_base.categoria_precificacao);
            if (savedCategory) {
                elements.categoriaPrecificacao.value = savedCategory.margem_padrao;
            }
            
            // Preenche dados do produto atual (não salvos na precificação)
            custoFornecedorAtual = produto_atual.custo_update || 0;
            elements.custoUpdate.value = formatCurrency(custoFornecedorAtual);
            const { peso_kg, altura_cm, largura_cm, comprimento_cm } = produto_atual;
            const pesoCubico = ((altura_cm || 0) * (largura_cm || 0) * (comprimento_cm || 0)) / 6000;
            elements.alturaCm.value = altura_cm || 0;
            elements.larguraCm.value = largura_cm || 0;
            elements.comprimentoCm.value = comprimento_cm || 0;
            elements.pesoReal.value = peso_kg || 0;
            elements.pesoCubico.value = pesoCubico.toFixed(3);
            
            // Passos finais
            checkCustoDivergence();
            updateAllCalculations('load-edit-data');
            
        } catch (error) {
            document.getElementById('error-message').textContent = `Erro: ${error.message}`;
            document.getElementById('error-message').classList.remove('hidden');
            document.getElementById('pricing-form').classList.add('hidden');
        }
    };
    
    // --- ANEXANDO LISTENERS ---
    const calculationTriggerIds = [ 'quantidade', 'custoUnitario', 'parcelamento', 'outros', 'freteClassico', 'fretePremium', 'vendaClassico', 'vendaPremium', 'margemDesejadaClassico', 'margemDesejadaPremium' ];
    calculationTriggerIds.forEach(id => {
        const el = elements[id];
        if (el) {
            const eventType = (el.tagName === 'SELECT' || el.type === 'checkbox') ? 'change' : 'input';
            el.addEventListener(eventType, (e) => updateAllCalculations(e.target.id));
        }
    });
    
    // Listeners dedicados
    elements.fulfillment.addEventListener('change', (e) => {
        if (Object.keys(lojaConfigAtual).length > 0) {
            elements.aliquota.value = elements.fulfillment.checked
                ? (lojaConfigAtual.aliquota_fulfillment || 0)
                : (lojaConfigAtual.aliquota_padrao || 0);
        }
        updateAllCalculations(e.target.id);
    });

    elements.categoriaPrecificacao.addEventListener('change', (e) => {
        const margem = e.target.value;
        elements.margemDesejadaClassico.value = margem || '';
        elements.margemDesejadaPremium.value = margem || '';
        updateAllCalculations(e.target.id);
    });

    elements.regraComissao.addEventListener('change', (e) => {
        updateAllCalculations(e.target.id);
    });
    
    if (mode === 'new') {
        elements.lojaMarketplace.addEventListener('change', handleLojaChange);
        elements.sku.addEventListener('keyup', (e) => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => fetchProductData(), e.key === 'Enter' ? 0 : 500);
        });
    }

    elements.saveButton.addEventListener('click', handleSave);
    elements.custoUnitario.addEventListener('input', checkCustoDivergence);

    // --- INICIALIZAÇÃO ---
    loadInitialData().then(() => {
        try {
            populateCategorias();
            if (mode === 'edit') {
                loadAndPopulateSavedData(recordId);
            } else {
                populateLojas();
            }
        } catch (e) {
            console.error('[Debug] Erro CRÍTICO durante a inicialização:', e);
            document.body.innerHTML = '<h1>Ocorreu um erro grave ao carregar a página.</h1>';
        }
    });
}