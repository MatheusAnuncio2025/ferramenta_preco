# app/routers/precificacao.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from .. import models, services, dependencies
import traceback

router = APIRouter(
    prefix="/api",
    tags=["Precificação e Dados"]
)

# --- Rotas de Precificação Base ---

@router.post("/precificacao/salvar", status_code=201)
async def salvar_precificacao(data: models.PrecificacaoCore, user: dict = Depends(dependencies.get_current_user)):
    user_email = user.get('email')
    try:
        record_id = str(services.uuid.uuid4())
        row_data = data.model_dump()
        row_data.update({
            "id": record_id,
            "data_calculo": services.datetime.utcnow(),
            "calculado_por": user_email
        })

        cols = ", ".join(f"`{k}`" for k in row_data.keys())
        placeholders = ", ".join(f"@{k}" for k in row_data.keys())
        query = f"INSERT INTO `{services.TABLE_PRECIFICACOES_SALVAS}` ({cols}) VALUES ({placeholders})"
        
        params = []
        for key, value in row_data.items():
            param_type = "STRING"
            if isinstance(value, bool): param_type = "BOOL"
            elif isinstance(value, int): param_type = "INT64"
            elif isinstance(value, float): param_type = "NUMERIC"
            elif isinstance(value, services.datetime): param_type = "TIMESTAMP"
            params.append(services.bigquery.ScalarQueryParameter(key, param_type, value))

        services.execute_query(query, params)
        
        services.log_action(user_email, "SAVE_PRICING", {"id": record_id, "sku": data.sku})
        return {"message": "Precificação salva com sucesso!", "id": record_id}
    except Exception as e:
        traceback.print_exc()
        services.log_action(user_email, "SAVE_PRICING_FAILED", {"sku": data.sku, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"Erro ao salvar no banco de dados: {e}")

@router.get("/precificacao/listar", response_model=models.PrecificacaoListResponse)
async def listar_precificacoes(
    marketplace: Optional[str]=None, 
    id_loja: Optional[str]=None, 
    sku: Optional[str]=None, 
    titulo: Optional[str]=None,
    plano: Optional[str]=None,
    categoria: Optional[str]=None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(dependencies.get_current_user)
):
    filters = {
        "marketplace": marketplace, "id_loja": id_loja, "sku": sku,
        "titulo": titulo, "plano": plano, "categoria": categoria
    }
    return services.get_filtered_precificacoes(filters, page, page_size)

# NOVO: ENDPOINT PARA EDIÇÃO EM MASSA
@router.post("/precificacao/bulk-update", status_code=200)
async def bulk_update_precificacoes(payload: models.BulkUpdatePayload, user: dict = Depends(dependencies.get_current_user)):
    user_email = user.get('email')
    try:
        affected_rows = services.bulk_update_prices(payload, user_email)
        return {"message": f"{affected_rows} precificações foram atualizadas com sucesso!"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro inesperado durante a atualização em massa: {e}")

@router.get("/precificacao/item/{id}", response_model=dict)
async def get_precificacao_item(id: str, user: dict = Depends(dependencies.get_current_user)):
    item = services.get_precificacao_by_id(id)
    if not item:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    return item

@router.put("/precificacao/atualizar/{id}", status_code=200)
async def atualizar_precificacao(id: str, data: models.PrecificacaoCore, user: dict = Depends(dependencies.get_current_user)):
    user_email = user.get('email')
    try:
        old_record = await get_precificacao_item(id, user)

        new_data_dict = data.model_dump()
        new_data_dict['data_calculo'] = services.datetime.utcnow()
        new_data_dict['calculado_por'] = user_email

        update_sets = ", ".join([f"`{key}` = @{key}" for key in new_data_dict.keys()])
        query = f"UPDATE `{services.TABLE_PRECIFICACOES_SALVAS}` SET {update_sets} WHERE id = @id"

        params = [services.bigquery.ScalarQueryParameter("id", "STRING", id)]
        for key, value in new_data_dict.items():
            param_type = "STRING"
            if isinstance(value, bool): param_type = "BOOL"
            elif isinstance(value, int): param_type = "INT64"
            elif isinstance(value, float): param_type = "NUMERIC"
            elif isinstance(value, services.datetime): param_type = "TIMESTAMP"
            params.append(services.bigquery.ScalarQueryParameter(key, param_type, value))

        services.execute_query(query, params)
        
        detalhes_alteracao = {}
        for key, new_value in new_data_dict.items():
            old_value = old_record.get(key)
            is_different = False
            if isinstance(new_value, float) or isinstance(old_value, float):
                if abs(float(new_value or 0) - float(old_value or 0)) > 1e-6:
                    is_different = True
            elif str(old_value) != str(new_value):
                 is_different = True

            if is_different and key not in ['data_calculo', 'calculado_por']:
                 detalhes_alteracao[key] = {"old_value": old_value, "new_value": new_value}

        if detalhes_alteracao:
            services.log_action(user_email, "UPDATE_PRICING", 
                       details={"id": id, "sku": data.sku},
                       detalhes_alteracao=detalhes_alteracao)
                   
        return {"message": "Precificação atualizada!", "id": id}
    except Exception as e:
        traceback.print_exc()
        services.log_action(user_email, "UPDATE_PRICING_FAILED", {"id": id, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar no banco de dados: {e}")

@router.delete("/precificacao/excluir/{id}", status_code=204)
async def excluir_precificacao(id: str, user: dict = Depends(dependencies.get_current_user)):
    user_email = user.get('email')
    services.delete_precificacao_and_campaigns(id)
    services.log_action(user_email, "DELETE_PRICING", {"id": id})

@router.get("/precificacao/historico/{sku}", response_model=List[dict])
async def get_historico_sku(sku: str, user: dict = Depends(dependencies.get_current_user)):
    return services.get_price_history_for_sku(sku)

# --- Rotas de Dados Auxiliares ---

@router.get("/categorias-precificacao")
async def get_categorias_precificacao(user: dict = Depends(dependencies.get_current_user)):
    return services.get_all_precificacao_categories()
    
@router.get("/dados-para-calculo", response_model=models.DadosCalculoResponse)
async def get_dados_para_calculo(sku: str, loja_id: str, user: dict = Depends(dependencies.get_current_user)):
    produto_data = services.fetch_product_data(sku)
    if not produto_data:
        raise HTTPException(status_code=404, detail=f"Produto com SKU '{sku}' não encontrado no cadastro.")
    
    config_loja_data = await services.get_loja_details(loja_id)
    return models.DadosCalculoResponse(
        produto=models.ProdutoDados(**produto_data), 
        config_loja=models.LojaConfigDetalhes(**config_loja_data)
    )

# --- Rotas de Precificação de Campanha ---

@router.post("/precificacao-campanha/salvar", status_code=201)
async def salvar_precificacao_campanha(data: models.PrecificacaoCampanhaPayload, user: dict = Depends(dependencies.get_current_user)):
    user_email = user.get('email')
    try:
        is_update = bool(data.id)
        row_data = data.model_dump()
        
        if is_update:
            row_data.pop("precificacao_base_id", None)
            row_data.pop("campanha_id", None)
            set_clauses = [f'T.{k} = @{k}' for k in row_data if k != 'id']
            query = f"UPDATE `{services.TABLE_PRECIFICACOES_CAMPANHA}` T SET {', '.join(set_clauses)} WHERE T.id = @id"
        else:
            row_data["id"] = str(services.uuid.uuid4())
            row_data.update({"data_criacao": services.datetime.utcnow(), "criado_por": user_email})
            cols = ', '.join([f'`{k}`' for k in row_data.keys()])
            placeholders = ', '.join([f'@{k}' for k in row_data.keys()])
            query = f"INSERT INTO `{services.TABLE_PRECIFICACOES_CAMPANHA}` ({cols}) VALUES ({placeholders})"

        params = []
        for key, value in row_data.items():
            param_type = "STRING"
            if isinstance(value, bool): param_type = "BOOL"
            elif isinstance(value, int): param_type = "INT64"
            elif isinstance(value, float): param_type = "NUMERIC"
            elif isinstance(value, services.datetime): param_type = "TIMESTAMP"
            elif isinstance(value, services.date): param_type = "DATE"
            params.append(services.bigquery.ScalarQueryParameter(key, param_type, value))

        services.execute_query(query, params)
        
        action = "UPDATE_CAMPAIGN_PRICE" if is_update else "SAVE_CAMPAIGN_PRICE"
        services.log_action(user_email, action, {"id": row_data["id"]})
        return {"message": "Preço de campanha salvo com sucesso!", "id": row_data["id"]}
    except Exception as e:
        traceback.print_exc()
        services.log_action(user_email, "SAVE_CAMPAIGN_PRICE_FAILED", {"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Erro ao salvar preço de campanha: {e}")

@router.get("/precificacao/edit-data/{id}", response_model=models.EditPageData)
async def get_data_for_edit_page(id: str, user: dict = Depends(dependencies.get_current_user)):
    try:
        precificacao_base = await get_precificacao_item(id, user)
        
        loja_id = services.get_loja_id_by_marketplace_and_loja(
            precificacao_base['marketplace'], precificacao_base['id_loja']
        )
        if not loja_id: raise HTTPException(status_code=404, detail="Configuração da loja não encontrada.")
        
        config_loja = await services.get_loja_details(loja_id)

        produto_atual_data = services.fetch_product_data(precificacao_base['sku'])
        if not produto_atual_data: produto_atual_data = {"sku": precificacao_base['sku']}

        campanhas_vinculadas = services.get_linked_campaigns(id)
        
        campanhas_ativas_raw = services.get_active_campaigns()
        campanhas_ativas = [models.CampanhaML(**row) for row in campanhas_ativas_raw]

        return models.EditPageData(
            precificacao_base=precificacao_base,
            config_loja=models.LojaConfigDetalhes(**config_loja),
            produto_atual=models.ProdutoDados(**produto_atual_data),
            campanhas_vinculadas=campanhas_vinculadas,
            campanhas_ativas=[c.model_dump() for c in campanhas_ativas]
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao carregar dados para edição: {str(e)}")

@router.get("/precificacao-campanha/item/{id}")
async def get_campaign_pricing_item(id: str, user: dict = Depends(dependencies.get_current_user)):
    item = services.get_campaign_pricing_details(id)
    if not item: 
        raise HTTPException(status_code=404, detail="Precificação de campanha não encontrada.")
    return item

# --- Rota de Histórico ---

@router.get("/historico")
async def get_historico(user: dict = Depends(dependencies.get_historico_viewer_user)):
    try:
        return services.get_history_logs()
    except Exception as e:
        print(f"Erro ao buscar histórico: {e}")
        raise HTTPException(status_code=500, detail="Erro ao buscar os dados do histórico.")