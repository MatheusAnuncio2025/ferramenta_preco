// static/campaignPricingLogic.js

document.addEventListener('DOMContentLoaded', () => {
    // Cache de dados globais para esta página
    let precificacaoBase = {};
    let configLoja = {};
    let campanhasAtivas = [];
    let regrasFreteCache = [];
    let regrasTarifaFixaCache = [];

    const elements = {
        loader: document.getElementById('loader'),
        mainContent: document.getElementById('main-content'),
        productHeaderContainer: document.getElementById('product-header-container'),
        productItemTemplate: document.getElementById('product-item-template'),
        campaignSelect: document.getElementById('campaign-select'),
        campaignDetailsCard: document.getElementById('campaign-details-card'),
        pricingFormContainer: document.getElementById('pricing-form-container'),
        saveButton: document.getElementById('save-campaign-price-btn')
    };

    /**
     * Busca todos os dados necessários do backend
     */
    async function fetchData(baseId) {
        try {
            // Este endpoint agora retorna tudo o que precisamos, incluindo as regras
            const dataRes = await fetch(`/api/precificacao/edit-data/${baseId}`);

            if (!dataRes.ok) throw new Error('Falha ao carregar dados da precificação.');
            
            const data = await dataRes.json();
            precificacaoBase = data.precificacao_base;
            configLoja = data.config_loja;
            campanhasAtivas = data.campanhas_ativas;

            // Carrega regras de negócio separadamente se necessário, ou assume que vêm de outro lugar
            // Para simplificar, vamos assumir que as regras não são necessárias diretamente aqui
            // ou que poderiam ser adicionadas ao endpoint `edit-data`.

            renderPage();
            elements.loader.classList.add('hidden');
            elements.mainContent.classList.remove('hidden');

        } catch (error) {
            elements.loader.innerHTML = `<p class="text-danger">Erro: ${error.message}</p>`;
        }
    }


    /**
     * Renderiza o conteúdo da página após os dados serem carregados
     */
    function renderPage() {
        renderProductHeader();
        populateCampaignSelect();
        elements.campaignSelect.addEventListener('change', handleCampaignSelection);
        elements.saveButton.addEventListener('click', handleSave);
    }

    /**
     * Renderiza o card de cabeçalho com os dados da precificação base
     */
    function renderProductHeader() {
        const templateClone = elements.productItemTemplate.content.cloneNode(true);
        const fields = {
            titulo: precificacaoBase.titulo || 'N/A',
            sku: precificacaoBase.sku || 'N/A',
            marketplace_loja: `${precificacaoBase.marketplace || ''} - ${precificacaoBase.id_loja || ''}`,
            custo_total: formatCurrency(precificacaoBase.custo_total),
            venda_classico: formatCurrency(precificacaoBase.venda_classico),
            margem_classico: formatPercent(precificacaoBase.margem_classico),
            venda_premium: formatCurrency(precificacaoBase.venda_premium),
            margem_premium: formatPercent(precificacaoBase.margem_premium),
        };
        templateClone.querySelectorAll('[data-field]').forEach(input => {
            input.value = fields[input.dataset.field];
        });
        elements.productHeaderContainer.innerHTML = '';
        elements.productHeaderContainer.appendChild(templateClone);
    }

    /**
     * Popula o dropdown com as campanhas ativas
     */
    function populateCampaignSelect() {
        elements.campaignSelect.innerHTML = '<option value="">Selecione uma campanha...</option>';
        campanhasAtivas.forEach(c => {
            const option = new Option(c.nome, c.id);
            elements.campaignSelect.add(option);
        });
    }

    /**
     * Lida com a seleção de uma campanha, exibindo seus detalhes e o formulário de precificação
     */
    function handleCampaignSelection() {
        const selectedId = elements.campaignSelect.value;
        if (!selectedId) {
            elements.campaignDetailsCard.classList.add('hidden');
            elements.pricingFormContainer.innerHTML = '';
            elements.saveButton.disabled = true;
            return;
        }

        const campanha = campanhasAtivas.find(c => c.id === selectedId);
        renderCampaignDetails(campanha);
        renderPricingForm();
        attachPricingListeners();
        updateAllCalculations();
        elements.saveButton.disabled = false;
    }

    /**
     * Renderiza o card com os detalhes da campanha selecionada
     */
    function renderCampaignDetails(campanha) {
        const formatDate = (dateStr) => dateStr ? new Date(dateStr + 'T00:00:00').toLocaleDateString('pt-BR') : 'Indefinida';
        let detailsHtml = `<div class="campaign-details-grid">`;
        if (campanha.tipo_cupom && campanha.valor_cupom) {
            const cupomValor = campanha.tipo_cupom === 'PERCENTUAL' ? `${campanha.valor_cupom}%` : formatCurrency(campanha.valor_cupom);
            detailsHtml += `<span><strong>Cupom:</strong> ${cupomValor}</span>`;
        }
        if (campanha.tipo_cashback && campanha.valor_cashback) {
            const cashbackValor = campanha.tipo_cashback === 'PERCENTUAL' ? `${campanha.valor_cashback}%` : formatCurrency(campanha.valor_cashback);
            detailsHtml += `<span><strong>Cashback:</strong> ${cashbackValor}</span>`;
        }
        detailsHtml += `<span><strong>Início:</strong> ${formatDate(campanha.data_inicio)}</span>`;
        detailsHtml += `<span><strong>Fim:</strong> ${formatDate(campanha.data_fim)}</span>`;
        detailsHtml += `</div>`;
        elements.campaignDetailsCard.innerHTML = detailsHtml;
        elements.campaignDetailsCard.classList.remove('hidden');
    }

    /**
     * Renderiza o formulário de precificação para a campanha
     */
    function renderPricingForm() {
        const formHtml = `
            <div class="pricing-sections">
                <section class="pricing-section">
                    <h3>Precificação Campanha - Clássico</h3>
                    <div class="form-row">
                        <div class="form-field">
                            <label>Desconto</label>
                            <div class="input-group">
                                <select id="desconto-tipo-classico"><option value="PERCENTUAL">%</option><option value="FIXO">R$</option></select>
                                <input type="number" step="0.01" id="desconto-valor-classico" placeholder="Valor">
                            </div>
                        </div>
                        <div class="form-field"><label>Valor Venda Final (R$)</label><input type="text" id="valor-venda-classico" readonly></div>
                    </div>
                    <div class="form-row">
                        <div class="form-field"><label>Repasse Final</label><input type="text" id="repasse-classico" readonly></div>
                        <div class="form-field"><label>Lucro Final (R$)</label><input type="text" id="lucro-rs-classico" readonly></div>
                        <div class="form-field"><label>Margem Final (%)</label><input type="text" id="margem-lucro-perc-classico" readonly></div>
                    </div>
                </section>
                <section class="pricing-section">
                    <h3>Precificação Campanha - Premium</h3>
                    <div class="form-row">
                        <div class="form-field">
                            <label>Desconto</label>
                            <div class="input-group">
                                <select id="desconto-tipo-premium"><option value="PERCENTUAL">%</option><option value="FIXO">R$</option></select>
                                <input type="number" step="0.01" id="desconto-valor-premium" placeholder="Valor">
                            </div>
                        </div>
                        <div class="form-field"><label>Valor Venda Final (R$)</label><input type="text" id="valor-venda-premium" readonly></div>
                    </div>
                    <div class="form-row">
                        <div class="form-field"><label>Repasse Final</label><input type="text" id="repasse-premium" readonly></div>
                        <div class="form-field"><label>Lucro Final (R$)</label><input type="text" id="lucro-rs-premium" readonly></div>
                        <div class="form-field"><label>Margem Final (%)</label><input type="text" id="margem-lucro-perc-premium" readonly></div>
                    </div>
                </section>
            </div>
        `;
        elements.pricingFormContainer.innerHTML = formHtml;
    }

    /**
     * Anexa os listeners aos inputs do formulário de precificação
     */
    function attachPricingListeners() {
        const inputs = ['desconto-tipo-classico', 'desconto-valor-classico', 'desconto-tipo-premium', 'desconto-valor-premium'];
        inputs.forEach(id => {
            document.getElementById(id).addEventListener('input', updateAllCalculations);
        });
    }

    /**
     * Função principal que recalcula todos os valores
     */
    function updateAllCalculations() {
        const campanha = campanhasAtivas.find(c => c.id === elements.campaignSelect.value);
        if (!campanha) return;

        const calcular = (plano) => {
            const vendaBase = precificacaoBase[`venda_${plano}`];
            const comissaoBase = configLoja.comissoes.find(c => c.chave === precificacaoBase.regra_comissao)[plano];
            
            const tipoDescontoEl = document.getElementById(`desconto-tipo-${plano}`);
            const valorDescontoEl = document.getElementById(`desconto-valor-${plano}`);
            const vendaFinalEl = document.getElementById(`valor-venda-${plano}`);
            const repasseEl = document.getElementById(`repasse-${plano}`);
            const lucroEl = document.getElementById(`lucro-rs-${plano}`);
            const margemEl = document.getElementById(`margem-lucro-perc-${plano}`);

            const tipoDesconto = tipoDescontoEl.value;
            const valorDesconto = parseFloat(valorDescontoEl.value) || 0;

            let vendaFinal = 0;
            if (tipoDesconto === 'PERCENTUAL') {
                vendaFinal = vendaBase * (1 - valorDesconto / 100);
            } else { // FIXO
                vendaFinal = vendaBase - valorDesconto;
            }
            vendaFinalEl.value = formatCurrency(vendaFinal);

            if (vendaFinal > 0) {
                const custosPercentuais = precificacaoBase.aliquota + precificacaoBase.parcelamento + precificacaoBase.outros + comissaoBase;
                const comissaoMarketplace = vendaFinal * (custosPercentuais / 100);
                
                const custoCupom = (campanha.tipo_cupom === 'FIXO' ? (campanha.valor_cupom || 0) : vendaFinal * (campanha.valor_cupom || 0) / 100);
                const creditoCashback = (campanha.tipo_cashback === 'FIXO' ? (campanha.valor_cashback || 0) : vendaFinal * (campanha.valor_cashback || 0) / 100);

                const tarifaFixa = precificacaoBase[`tarifa_fixa_${plano}`];
                const frete = precificacaoBase[`frete_${plano}`];

                const descontosTotais = comissaoMarketplace + tarifaFixa + frete + custoCupom;
                const repasse = vendaFinal - descontosTotais;
                const lucro = repasse - precificacaoBase.custo_total + creditoCashback;
                const margem = (lucro / vendaFinal) * 100;

                repasseEl.value = formatCurrency(repasse);
                lucroEl.value = formatCurrency(lucro);
                margemEl.value = formatPercent(margem);
                margemEl.classList.toggle('text-success', lucro > 0);
                margemEl.classList.toggle('text-danger', lucro < 0);
                lucroEl.classList.toggle('text-success', lucro > 0);
                lucroEl.classList.toggle('text-danger', lucro < 0);
            } else {
                repasseEl.value = formatCurrency(0);
                lucroEl.value = formatCurrency(-precificacaoBase.custo_total);
                margemEl.value = 'N/A';
            }
        };

        calcular('classico');
        calcular('premium');
    }

    /**
     * Lida com o salvamento do preço da campanha
     */
    async function handleSave() {
        elements.saveButton.classList.add('is-loading');
        elements.saveButton.disabled = true;

        try {
            const payload = {
                precificacao_base_id: new URLSearchParams(window.location.search).get('base_id'),
                campanha_id: elements.campaignSelect.value,
                desconto_classico_tipo: document.getElementById('desconto-tipo-classico').value,
                desconto_classico_valor: parseFloat(document.getElementById('desconto-valor-classico').value) || null,
                venda_final_classico: parseCurrency(document.getElementById('valor-venda-classico').value),
                margem_final_classico: parsePercent(document.getElementById('margem-lucro-perc-classico').value),
                lucro_final_classico: parseCurrency(document.getElementById('lucro-rs-classico').value),
                repasse_final_classico: parseCurrency(document.getElementById('repasse-classico').value),
                desconto_premium_tipo: document.getElementById('desconto-tipo-premium').value,
                desconto_premium_valor: parseFloat(document.getElementById('desconto-valor-premium').value) || null,
                venda_final_premium: parseCurrency(document.getElementById('valor-venda-premium').value),
                margem_final_premium: parsePercent(document.getElementById('margem-lucro-perc-premium').value),
                lucro_final_premium: parseCurrency(document.getElementById('lucro-rs-premium').value),
                repasse_final_premium: parseCurrency(document.getElementById('repasse-premium').value),
            };

            const response = await fetch('/api/precificacao-campanha/salvar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error((await response.json()).detail || 'Erro ao salvar.');

            showAppModal({
                title: "Sucesso!",
                bodyHtml: "<p>Preço de campanha salvo com sucesso. Você pode adicionar outro preço para este produto ou voltar para a lista.</p>",
                buttons: [
                    { 
                        text: 'Adicionar Outra', 
                        class: 'secondary', 
                        onClick: () => {
                            elements.campaignSelect.value = "";
                            elements.campaignDetailsCard.classList.add('hidden');
                            elements.pricingFormContainer.innerHTML = '';
                            elements.saveButton.disabled = true;
                        } 
                    },
                    { text: 'Voltar para a Lista', class: 'primary', onClick: () => window.location.href = '/lista' }
                ]
            });

        } catch (error) {
            showAppModal({ title: "Erro", bodyHtml: `<p>${error.message}</p>`, buttons: [{ text: 'OK', class: 'primary' }] });
        } finally {
            elements.saveButton.classList.remove('is-loading');
            elements.saveButton.disabled = false;
        }
    }

    // Inicialização da página
    const baseId = new URLSearchParams(window.location.search).get('base_id');
    if (!baseId) {
        elements.loader.innerHTML = '<p class="text-danger">Erro: ID da precificação base não fornecido.</p>';
        return;
    }
    checkAuthStatusAndUpdateNav().then(user => {
        if (user) {
            setupLogoutButton();
            fetchData(baseId);
        }
    });
});