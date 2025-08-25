document.addEventListener('DOMContentLoaded', () => {
    // Cache de dados da página
    let precificacaoCampanha = {};
    let precificacaoBase = {};
    let configLoja = {};

    const elements = {
        loader: document.getElementById('loader'),
        mainContent: document.getElementById('main-content'),
        productHeaderContainer: document.getElementById('product-header-container'),
        productItemTemplate: document.getElementById('product-item-template'),
        campaignNameTitle: document.getElementById('campaign-name-title'),
        campaignDetailsCard: document.getElementById('campaign-details-card'),
        pricingFormContainer: document.getElementById('pricing-form-container'),
        saveButton: document.getElementById('save-campaign-price-btn')
    };

    /**
     * Busca todos os dados necessários do backend para a edição.
     */
    async function fetchData(campaignPricingId) {
        try {
            // Este endpoint busca tanto os dados da campanha quanto os dados da precificação base associada.
            const dataRes = await fetch(`/api/precificacao-campanha/item/${campaignPricingId}`);
            if (!dataRes.ok) throw new Error('Falha ao carregar dados da precificação de campanha.');
            
            const data = await dataRes.json();
            precificacaoCampanha = data;

            // O endpoint /edit-data é perfeito para buscar o restante das informações
            const baseDataRes = await fetch(`/api/precificacao/edit-data/${data.precificacao_base_id}`);
            if (!baseDataRes.ok) throw new Error('Falha ao carregar dados da precificação base.');
            
            const baseData = await baseDataRes.json();
            precificacaoBase = baseData.precificacao_base;
            configLoja = baseData.config_loja;

            renderPage();
            elements.loader.classList.add('hidden');
            elements.mainContent.classList.remove('hidden');

        } catch (error) {
            elements.loader.innerHTML = `<p class="text-danger">Erro: ${error.message}</p>`;
        }
    }

    /**
     * Renderiza o conteúdo da página após os dados serem carregados.
     */
    function renderPage() {
        renderProductHeader();
        renderCampaignDetails();
        renderPricingForm();
        populateFormWithData();
        attachPricingListeners();
        updateAllCalculations();
        elements.saveButton.addEventListener('click', handleSave);
    }

    /**
     * Renderiza o cabeçalho do produto base.
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
     * Renderiza os detalhes da campanha que está sendo editada.
     */
    function renderCampaignDetails() {
        elements.campaignNameTitle.textContent = `Editando Campanha: ${precificacaoCampanha.nome_campanha}`;
        // Aqui podemos adicionar mais detalhes da campanha se necessário
        elements.campaignDetailsCard.innerHTML = `Editando os descontos para a campanha selecionada.`;
    }

    /**
     * Renderiza o formulário de precificação para a campanha.
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
     * Preenche o formulário com os dados da campanha buscados do banco.
     */
    function populateFormWithData() {
        document.getElementById('desconto-tipo-classico').value = precificacaoCampanha.desconto_classico_tipo || 'PERCENTUAL';
        document.getElementById('desconto-valor-classico').value = precificacaoCampanha.desconto_classico_valor || '';
        document.getElementById('desconto-tipo-premium').value = precificacaoCampanha.desconto_premium_tipo || 'PERCENTUAL';
        document.getElementById('desconto-valor-premium').value = precificacaoCampanha.desconto_premium_valor || '';
    }

    function attachPricingListeners() {
        const inputs = ['desconto-tipo-classico', 'desconto-valor-classico', 'desconto-tipo-premium', 'desconto-valor-premium'];
        inputs.forEach(id => {
            document.getElementById(id).addEventListener('input', updateAllCalculations);
        });
    }

    /**
     * Função principal que recalcula todos os valores.
     */
    function updateAllCalculations() {
        const calcular = (plano) => {
            const vendaBase = precificacaoBase[`venda_${plano}`];
            const tipoDesconto = document.getElementById(`desconto-tipo-${plano}`).value;
            const valorDesconto = parseFloat(document.getElementById(`desconto-valor-${plano}`).value) || 0;

            let vendaFinal = 0;
            if (tipoDesconto === 'PERCENTUAL') {
                vendaFinal = vendaBase * (1 - valorDesconto / 100);
            } else { // FIXO
                vendaFinal = vendaBase - valorDesconto;
            }
            document.getElementById(`valor-venda-${plano}`).value = formatCurrency(vendaFinal);

            if (vendaFinal > 0) {
                const comissaoBase = configLoja.comissoes.find(c => c.chave === precificacaoBase.regra_comissao)[plano];
                const custosPercentuais = precificacaoBase.aliquota + precificacaoBase.parcelamento + precificacaoBase.outros + comissaoBase;
                const comissaoMarketplace = vendaFinal * (custosPercentuais / 100);
                
                // Em edição, não aplicamos novamente o custo/crédito da campanha, pois ele é só um "contexto"
                const tarifaFixa = precificacaoBase[`tarifa_fixa_${plano}`];
                const frete = precificacaoBase[`frete_${plano}`];

                const descontosTotais = comissaoMarketplace + tarifaFixa + frete;
                const repasse = vendaFinal - descontosTotais;
                const lucro = repasse - precificacaoBase.custo_total;
                const margem = (lucro / vendaFinal) * 100;

                document.getElementById(`repasse-${plano}`).value = formatCurrency(repasse);
                document.getElementById(`lucro-rs-${plano}`).value = formatCurrency(lucro);
                document.getElementById(`margem-lucro-perc-${plano}`).value = formatPercent(margem);
            } else {
                document.getElementById(`repasse-${plano}`).value = formatCurrency(0);
                document.getElementById(`lucro-rs-${plano}`).value = formatCurrency(-precificacaoBase.custo_total);
                document.getElementById(`margem-lucro-perc-${plano}`).value = 'N/A';
            }
        };

        calcular('classico');
        calcular('premium');
    }

    async function handleSave() {
        elements.saveButton.classList.add('is-loading');
        elements.saveButton.disabled = true;

        try {
            const payload = {
                id: precificacaoCampanha.id, // ID da precificação de campanha a ser atualizada
                precificacao_base_id: precificacaoCampanha.precificacao_base_id,
                campanha_id: precificacaoCampanha.campanha_id,
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
                method: 'POST', // O endpoint lida com a lógica de update se o ID for enviado
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error((await response.json()).detail || 'Erro ao salvar.');

            showAppModal({
                title: "Sucesso!",
                bodyHtml: "<p>Preço de campanha atualizado com sucesso!</p>",
                buttons: [
                    { 
                        text: 'Voltar', 
                        class: 'primary', 
                        onClick: () => {
                            window.location.href = `/editar?id=${precificacaoBase.id}`;
                        } 
                    }
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
    const campaignPricingId = new URLSearchParams(window.location.search).get('id');
    if (!campaignPricingId) {
        elements.loader.innerHTML = '<p class="text-danger">Erro: ID da precificação de campanha não fornecido.</p>';
        return;
    }
    fetchData(campaignPricingId);
});