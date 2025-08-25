# app/services.py
import os
import uuid
import json
import traceback
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from google.cloud import bigquery, storage
from cachetools import cached
from .cache import cache
from . import models

# --- Configurações de Conexão ---
client = bigquery.Client()
storage_client = storage.Client()
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", client.project)
BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")

# --- Nomes das Tabelas ---
TABLE_LOJAS_CONFIG = f"{PROJECT_ID}.dados_magis.lojas_config"
TABLE_LOJA_CONFIG_DETALHES = f"{PROJECT_ID}.dados_magis.loja_config_detalhes"
TABLE_PRODUTOS = f"{PROJECT_ID}.dados_magis.dados_produtos"
TABLE_PRECIFICACOES_SALVAS = f"{PROJECT_ID}.dados_magis.precificacoes_salvas"
TABLE_USUARIOS = f"{PROJECT_ID}.dados_magis.usuarios"
TABLE_LOGS = f"{PROJECT_ID}.dados_magis.logs_auditoria"
TABLE_REGRAS_TARIFA_FIXA = f"{PROJECT_ID}.dados_magis.regras_tarifa_fixa_ml"
TABLE_REGRAS_FRETE = f"{PROJECT_ID}.dados_magis.regras_frete_ml"
TABLE_CATEGORIAS_PRECIFICACAO = f"{PROJECT_ID}.dados_magis.categorias_precificacao"
TABLE_CAMPANHAS_ML = f"{PROJECT_ID}.dados_magis.campanhas_ml"
TABLE_PRECIFICACOES_CAMPANHA = f"{PROJECT_ID}.dados_magis.precificacoes_campanha"
TABLE_VENDAS = f"{PROJECT_ID}.dados_vendas.vendas" if PROJECT_ID == "skilful-firefly-434016-b2" else f"{PROJECT_ID}.dados_vendas.vendas"

# --- Funções de Lógica de Negócio ---

def log_action(user_email: str, action: str, details: dict = None, detalhes_alteracao: dict = None):
    try:
        if "RULE" in action or "CAMPAIGN" in action or "STORE" in action:
            cache.clear()
            
        def safe_json_serializer(obj):
            if isinstance(obj, (datetime, date)): return obj.isoformat()
            return str(obj)
            
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(), 
            "user_email": user_email, 
            "action": action, 
            "details": json.dumps(details, default=safe_json_serializer) if details else None,
            "detalhes_alteracao": json.dumps(detalhes_alteracao, default=safe_json_serializer) if detalhes_alteracao else None
        }
        
        cols = ", ".join(f"`{k}`" for k in log_entry.keys())
        placeholders = ", ".join(f"@{k}" for k in log_entry.keys())
        query = f"INSERT INTO `{TABLE_LOGS}` ({cols}) VALUES ({placeholders})"
        params = [bigquery.ScalarQueryParameter(k, "STRING" if v is None else "TIMESTAMP" if isinstance(v, (datetime, date)) else "BOOL" if isinstance(v, bool) else "STRING", v) for k, v in log_entry.items()]
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        client.query(query, job_config=job_config).result()
    except Exception as e: 
        print(f"ERRO AO LOGAR AÇÃO: {e}")

# --- Funções de Acesso a Dados (Repositório) ---

def execute_query(query: str, params: Optional[List[bigquery.ScalarQueryParameter]] = None) -> bigquery.table.RowIterator:
    job_config = bigquery.QueryJobConfig(query_parameters=params) if params else None
    return client.query(query, job_config=job_config).result()

def fetch_product_data(sku: str) -> Optional[dict]:
    query = f"SELECT sku, titulo, valor_de_custo as custo_update, peso as peso_kg, altura as altura_cm, largura as largura_cm, comprimento as comprimento_cm FROM `{TABLE_PRODUTOS}` WHERE LOWER(sku) = LOWER(@sku)"
    params = [bigquery.ScalarQueryParameter("sku", "STRING", sku)]
    results = [dict(row) for row in execute_query(query, params)]
    return results[0] if results else None

# --- Precificação ---
def get_precificacao_by_id(record_id: str) -> Optional[Dict[str, Any]]:
    query = f"SELECT * FROM `{TABLE_PRECIFICACOES_SALVAS}` WHERE id = @id"
    params = [bigquery.ScalarQueryParameter("id", "STRING", record_id)]
    results = [dict(row) for row in execute_query(query, params)]
    if not results: return None
    item = results[0]
    for key, value in item.items():
        if isinstance(value, (datetime, date)): item[key] = value.isoformat()
    return item

def get_filtered_precificacoes(filters: Dict[str, Any], page: int = 1, page_size: int = 20) -> models.PrecificacaoListResponse:
    base_query = f"FROM `{TABLE_PRECIFICACOES_SALVAS}`"
    where_clauses = []
    params = []
    filter_map = {'categoria': 'categoria_precificacao'}

    for key, value in filters.items():
        if not value:
            continue
        column_name = filter_map.get(key, key)
        param_name = f"param_{key}"
        if key in ['sku', 'titulo']:
            where_clauses.append(f"LOWER({column_name}) LIKE LOWER(@{param_name})")
            params.append(bigquery.ScalarQueryParameter(param_name, "STRING", f"%{value}%"))
        elif key == 'plano':
            if value == 'classico': where_clauses.append("venda_classico > 0")
            elif value == 'premium': where_clauses.append("venda_premium > 0")
        else:
            where_clauses.append(f"LOWER({column_name}) = LOWER(@{param_name})")
            params.append(bigquery.ScalarQueryParameter(param_name, "STRING", value))

    where_sql = ""
    if where_clauses:
        where_sql = " WHERE " + " AND ".join(where_clauses)

    count_query = f"SELECT COUNT(*) as total {base_query}{where_sql}"
    count_job_config = bigquery.QueryJobConfig(query_parameters=params)
    count_result = client.query(count_query, job_config=count_job_config).result()
    total_items = list(count_result)[0].total

    offset = (page - 1) * page_size
    select_query = f"SELECT * {base_query}{where_sql} ORDER BY data_calculo DESC LIMIT @page_size OFFSET @offset"
    
    pag_params = [
        bigquery.ScalarQueryParameter("page_size", "INT64", page_size),
        bigquery.ScalarQueryParameter("offset", "INT64", offset),
    ]
    all_params = params + pag_params

    select_job_config = bigquery.QueryJobConfig(query_parameters=all_params)
    results_iterator = client.query(select_query, job_config=select_job_config).result()
    
    items = []
    for row in results_iterator:
        item_dict = dict(row)
        for key, value in item_dict.items():
            if isinstance(value, (datetime, date)):
                item_dict[key] = value.isoformat()
        items.append(item_dict)

    return models.PrecificacaoListResponse(total_items=total_items, items=items)

def delete_precificacao_and_campaigns(record_id: str):
    params = [bigquery.ScalarQueryParameter("id", "STRING", record_id)]
    execute_query(f"DELETE FROM `{TABLE_PRECIFICACOES_CAMPANHA}` WHERE precificacao_base_id = @id", params)
    execute_query(f"DELETE FROM `{TABLE_PRECIFICACOES_SALVAS}` WHERE id = @id", params)

def bulk_update_prices(payload: models.BulkUpdatePayload, user_email: str):
    if not payload.ids:
        return 0

    field_to_update = ""
    param_type = "STRING"
    
    if payload.action == models.UpdateAction.set_custo_unitario:
        field_to_update = "custo_unitario"
        param_type = "FLOAT64"
    elif payload.action == models.UpdateAction.set_categoria:
        field_to_update = "categoria_precificacao"
        param_type = "STRING"
    else:
        raise ValueError(f"Ação de atualização em massa '{payload.action.value}' não é suportada.")

    query = f"""
        UPDATE `{TABLE_PRECIFICACOES_SALVAS}`
        SET {field_to_update} = @value,
            calculado_por = @user_email,
            data_calculo = CURRENT_TIMESTAMP()
        WHERE id IN UNNEST(@ids)
    """
    
    params = [
        bigquery.ScalarQueryParameter("value", param_type, payload.value),
        bigquery.ScalarQueryParameter("user_email", "STRING", user_email),
        bigquery.ArrayQueryParameter("ids", "STRING", payload.ids),
    ]

    job_config = bigquery.QueryJobConfig(query_parameters=params)
    query_job = client.query(query, job_config=job_config)
    query_job.result()

    log_action(
        user_email,
        "BULK_UPDATE_PRICING",
        details={
            "action": payload.action.value,
            "value": payload.value,
            "item_count": len(payload.ids),
            "ids_afetados": payload.ids
        }
    )

    return query_job.num_dml_affected_rows

def get_linked_campaigns(base_id: str) -> List[Dict[str, Any]]:
    # ... (código existente)
    pass

def get_campaign_pricing_details(item_id: str) -> Optional[Dict[str, Any]]:
    # ... (código existente)
    pass

def get_price_history_for_sku(sku: str) -> List[Dict[str, Any]]:
    # ... (código existente)
    pass

# --- Usuários ---
def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    # ... (código existente)
    pass

def get_all_users() -> List[Dict[str, Any]]:
    # ... (código existente)
    pass

def create_user(user_data: Dict[str, Any]) -> Dict[str, Any]:
    # ... (código existente)
    pass

def update_user_properties(email: str, updates: Dict[str, Any]):
    # ... (código existente)
    pass

def delete_user_by_email(email: str):
    # ... (código existente)
    pass

# --- Campanhas ---
@cached(cache)
def get_all_campaigns() -> List[Dict[str, Any]]:
    # ... (código existente)
    pass

@cached(cache)
def get_active_campaigns() -> List[Dict[str, Any]]:
    # ... (código existente)
    pass

def save_all_campaigns(campaigns_data: List[Dict[str, Any]]):
    # ... (código existente)
    pass

# --- Configurações de Loja ---
@cached(cache)
def get_lojas_config() -> List[Dict[str, Any]]:
    # ... (código existente)
    pass

@cached(cache)
def get_loja_details(loja_id: str) -> Dict[str, Any]:
    # ... (código existente)
    pass

def get_loja_id_by_marketplace_and_loja(marketplace: str, id_loja: str) -> Optional[str]:
    # ... (código existente)
    pass

def save_loja_details(loja_id: str, detalhes_json: str):
    # ... (código existente)
    pass

def delete_loja_and_details(loja_id: str):
    # ... (código existente)
    pass

# --- Dashboard & Histórico ---
def get_dashboard_alert_data() -> Dict[str, List]:
    # ... (código existente)
    pass

def get_history_logs() -> List[Dict[str, Any]]:
    # ... (código existente)
    pass

def get_profitability_by_category() -> List[Dict[str, Any]]:
    # ... (código existente)
    pass

def get_profit_evolution() -> List[Dict[str, Any]]:
    # ... (código existente)
    pass

# --- Regras de Negócio ---
@cached(cache)
def get_all_business_rules() -> Dict[str, List]:
    # ... (código existente)
    pass

def get_all_precificacao_categories() -> List[Dict[str, Any]]:
    # ... (código existente)
    pass

# --- Simulador ---
async def run_simulation(payload: models.SimulacaoPayload) -> models.SimulacaoResultado:
    # 1. Buscar precificações com base nos filtros
    filters = payload.filters.model_dump()
    # Usamos a função de listagem, mas com um limite alto para pegar todos os itens do filtro
    precificacoes_response = get_filtered_precificacoes(filters, page=1, page_size=10000)
    precificacoes = precificacoes_response.items

    if not precificacoes:
        raise ValueError("Nenhum produto encontrado para os filtros selecionados.")

    # 2. Calcular o cenário "Antes"
    total_receita_antes = sum((p.get('venda_classico', 0) or 0) + (p.get('venda_premium', 0) or 0) for p in precificacoes)
    total_custo_antes = sum(p.get('custo_total', 0) or 0 for p in precificacoes)
    total_lucro_antes = sum((p.get('lucro_classico', 0) or 0) + (p.get('lucro_premium', 0) or 0) for p in precificacoes)
    margem_media_antes = (total_lucro_antes / total_receita_antes * 100) if total_receita_antes > 0 else 0

    antes = models.TotaisSimulacao(
        receita_total=total_receita_antes,
        custo_total=total_custo_antes,
        lucro_total=total_lucro_antes,
        margem_media=margem_media_antes,
        total_items=len(precificacoes)
    )

    # 3. Calcular o cenário "Depois"
    action = payload.action
    precificacoes_depois = []

    for p in precificacoes:
        p_depois = p.copy()
        
        # Lógica de simulação (exemplo inicial para custo)
        if action.field == 'custo_unitario' and action.operation == 'percent_increase':
            novo_custo_unitario = (p_depois.get('custo_unitario', 0) or 0) * (1 + action.value / 100)
            p_depois['custo_unitario'] = novo_custo_unitario
            p_depois['custo_total'] = novo_custo_unitario * (p_depois.get('quantidade', 1) or 1)
            
            # ATENÇÃO: Um recálculo completo do preço de venda seria necessário aqui
            # para uma simulação 100% precisa. Por simplicidade, vamos recalcular o lucro
            # com base no preço de venda existente.
            repasse_total = (p_depois.get('repasse_classico', 0) or 0) + (p_depois.get('repasse_premium', 0) or 0)
            lucro_total_item = repasse_total - p_depois['custo_total']
            
            # Simplificando a distribuição do lucro para o modelo
            p_depois['lucro_classico'] = lucro_total_item / 2
            p_depois['lucro_premium'] = lucro_total_item / 2
        
        precificacoes_depois.append(p_depois)

    total_receita_depois = sum((p.get('venda_classico', 0) or 0) + (p.get('venda_premium', 0) or 0) for p in precificacoes_depois)
    total_custo_depois = sum(p.get('custo_total', 0) or 0 for p in precificacoes_depois)
    total_lucro_depois = sum((p.get('lucro_classico', 0) or 0) + (p.get('lucro_premium', 0) or 0) for p in precificacoes_depois)
    margem_media_depois = (total_lucro_depois / total_receita_depois * 100) if total_receita_depois > 0 else 0

    depois = models.TotaisSimulacao(
        receita_total=total_receita_depois,
        custo_total=total_custo_depois,
        lucro_total=total_lucro_depois,
        margem_media=margem_media_depois,
        total_items=len(precificacoes_depois)
    )

    return models.SimulacaoResultado(antes=antes, depois=depois)