# app/services.py
import os
import uuid
import json
import traceback
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from google.cloud import bigquery, storage
from cachetools import cached
from .cache import cache

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

def get_filtered_precificacoes(filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    query = f"SELECT * FROM `{TABLE_PRECIFICACOES_SALVAS}`"
    where_clauses, params, filter_map = [], [], {'categoria': 'categoria_precificacao'}
    for key, value in filters.items():
        if not value: continue
        column_name = filter_map.get(key, key)
        if key in ['sku', 'titulo']:
            where_clauses.append(f"LOWER({column_name}) LIKE LOWER(@{key})")
            params.append(bigquery.ScalarQueryParameter(key, "STRING", f"%{value}%"))
        elif key == 'plano':
            if value == 'classico': where_clauses.append("venda_classico > 0")
            elif value == 'premium': where_clauses.append("venda_premium > 0")
        else:
            where_clauses.append(f"LOWER({column_name}) = LOWER(@{key})")
            params.append(bigquery.ScalarQueryParameter(key, "STRING", value))
    if where_clauses: query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY data_calculo DESC LIMIT 100"
    results = [dict(row) for row in execute_query(query, params)]
    for r in results:
        for key, value in r.items():
            if isinstance(value, (datetime, date)): r[key] = value.isoformat()
    return results

def delete_precificacao_and_campaigns(record_id: str):
    params = [bigquery.ScalarQueryParameter("id", "STRING", record_id)]
    execute_query(f"DELETE FROM `{TABLE_PRECIFICACOES_CAMPANHA}` WHERE precificacao_base_id = @id", params)
    execute_query(f"DELETE FROM `{TABLE_PRECIFICACOES_SALVAS}` WHERE id = @id", params)

def get_linked_campaigns(base_id: str) -> List[Dict[str, Any]]:
    query = f"""
        SELECT pc.*, c.nome as nome_campanha
        FROM `{TABLE_PRECIFICACOES_CAMPANHA}` pc
        JOIN `{TABLE_CAMPANHAS_ML}` c ON pc.campanha_id = c.id
        WHERE pc.precificacao_base_id = @base_id
    """
    params = [bigquery.ScalarQueryParameter("base_id", "STRING", base_id)]
    results = [dict(row) for row in execute_query(query, params)]
    for r in results:
        for key, value in r.items():
            if isinstance(value, (datetime, date)): r[key] = value.isoformat()
    return results

def get_campaign_pricing_details(item_id: str) -> Optional[Dict[str, Any]]:
    query = f"""
        SELECT pc.*, c.nome as nome_campanha, pb.sku, pb.titulo
        FROM `{TABLE_PRECIFICACOES_CAMPANHA}` pc
        JOIN `{TABLE_CAMPANHAS_ML}` c ON pc.campanha_id = c.id
        JOIN `{TABLE_PRECIFICACOES_SALVAS}` pb ON pc.precificacao_base_id = pb.id
        WHERE pc.id = @id
    """
    params = [bigquery.ScalarQueryParameter("id", "STRING", item_id)]
    results = [dict(row) for row in execute_query(query, params)]
    if not results: return None
    item = results[0]
    for key, value in item.items():
        if isinstance(value, (datetime, date)): item[key] = value.isoformat()
    return item

# --- Usuários ---
def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    query = f"SELECT *, pode_ver_historico FROM `{TABLE_USUARIOS}` WHERE email = @email"
    params = [bigquery.ScalarQueryParameter("email", "STRING", email)]
    results = [dict(row) for row in execute_query(query, params)]
    return results[0] if results else None

def get_all_users() -> List[Dict[str, Any]]:
    query = f"SELECT *, pode_ver_historico FROM `{TABLE_USUARIOS}` ORDER BY nome ASC"
    results = [dict(row) for row in execute_query(query)]
    for user_data in results:
        for key, value in user_data.items():
            if isinstance(value, (datetime, date)): user_data[key] = value.isoformat()
    return results

def create_user(user_data: Dict[str, Any]) -> Dict[str, Any]:
    cols = ", ".join(f"`{k}`" for k in user_data.keys())
    placeholders = ", ".join(f"@{k}" for k in user_data.keys())
    query = f"INSERT INTO `{TABLE_USUARIOS}` ({cols}) VALUES ({placeholders})"
    params = [bigquery.ScalarQueryParameter(k, "BOOL" if isinstance(v, bool) else "STRING", v) for k, v in user_data.items()]
    execute_query(query, params)
    return user_data

def update_user_properties(email: str, updates: Dict[str, Any]):
    set_clauses = ", ".join([f"{key} = @{key}" for key in updates.keys()])
    query = f"UPDATE `{TABLE_USUARIOS}` SET {set_clauses} WHERE email = @email"
    params = [bigquery.ScalarQueryParameter("email", "STRING", email)]
    params.extend([bigquery.ScalarQueryParameter(k, "BOOL" if isinstance(v, bool) else "STRING", v) for k, v in updates.items()])
    execute_query(query, params)

def delete_user_by_email(email: str):
    query = f"DELETE FROM `{TABLE_USUARIOS}` WHERE email = @email"
    params = [bigquery.ScalarQueryParameter("email", "STRING", email)]
    execute_query(query, params)

# --- Campanhas ---
@cached(cache)
def get_all_campaigns() -> List[Dict[str, Any]]:
    query = f"SELECT * FROM `{TABLE_CAMPANHAS_ML}` ORDER BY data_fim DESC, nome"
    return [dict(row) for row in execute_query(query)]

@cached(cache)
def get_active_campaigns() -> List[Dict[str, Any]]:
    query = f"SELECT * FROM `{TABLE_CAMPANHAS_ML}` WHERE data_fim >= CURRENT_DATE() OR data_fim IS NULL ORDER BY nome"
    results = [dict(row) for row in execute_query(query)]
    # Pydantic model conversion will happen in the router
    return results

# --- Configurações de Loja ---
@cached(cache)
def get_lojas_config() -> List[Dict[str, Any]]:
    query = f"SELECT * FROM `{TABLE_LOJAS_CONFIG}` ORDER BY marketplace, id_loja"
    return [dict(row) for row in execute_query(query)]

@cached(cache)
def get_loja_details(loja_id: str) -> Dict[str, Any]:
    query = f"SELECT configuracoes FROM `{TABLE_LOJA_CONFIG_DETALHES}` WHERE loja_id = @loja_id"
    params = [bigquery.ScalarQueryParameter("loja_id", "STRING", loja_id)]
    results = [dict(row) for row in execute_query(query, params)]
    if not results or not results[0].get('configuracoes'):
        return {}
    config_data = results[0]['configuracoes']
    if isinstance(config_data, str):
      try:
        return json.loads(config_data)
      except json.JSONDecodeError:
        return {}
    return config_data if isinstance(config_data, dict) else {}

def get_loja_id_by_marketplace_and_loja(marketplace: str, id_loja: str) -> Optional[str]:
    query = f"SELECT id FROM `{TABLE_LOJAS_CONFIG}` WHERE marketplace = @marketplace AND id_loja = @id_loja"
    params = [
        bigquery.ScalarQueryParameter("marketplace", "STRING", marketplace),
        bigquery.ScalarQueryParameter("id_loja", "STRING", id_loja),
    ]
    results = list(execute_query(query, params))
    return results[0]['id'] if results else None

def save_loja_details(loja_id: str, detalhes_json: str):
    merge_query = f"""
        MERGE `{TABLE_LOJA_CONFIG_DETALHES}` T
        USING (SELECT @loja_id as loja_id, @config_json as configuracoes) S ON T.loja_id = S.loja_id
        WHEN MATCHED THEN UPDATE SET T.configuracoes = S.configuracoes
        WHEN NOT MATCHED THEN INSERT (loja_id, configuracoes) VALUES (S.loja_id, S.configuracoes)
    """
    params = [
        bigquery.ScalarQueryParameter("loja_id", "STRING", loja_id),
        bigquery.ScalarQueryParameter("config_json", "JSON", detalhes_json),
    ]
    execute_query(merge_query, params)

def delete_loja_and_details(loja_id: str):
    params = [bigquery.ScalarQueryParameter("loja_id", "STRING", loja_id)]
    execute_query(f"DELETE FROM `{TABLE_LOJA_CONFIG_DETALHES}` WHERE loja_id = @loja_id", params)
    execute_query(f"DELETE FROM `{TABLE_LOJAS_CONFIG}` WHERE id = @loja_id", params)

# --- Dashboard & Histórico ---
def get_dashboard_alert_data() -> Dict[str, List]:
    # ... (código mantido da resposta anterior)
    pass
def get_history_logs() -> List[Dict[str, Any]]:
    query = f"SELECT * FROM `{TABLE_LOGS}` ORDER BY timestamp DESC LIMIT 200"
    results = [dict(row) for row in execute_query(query)]
    for r in results:
        for key, value in r.items():
            if isinstance(value, (datetime, date)): r[key] = value.isoformat()
    return results

# --- Regras de Negócio ---
@cached(cache)
def get_all_business_rules() -> Dict[str, List]:
    # ... (código mantido da resposta anterior)
    pass
def get_all_precificacao_categories() -> List[Dict[str, Any]]:
    query = f"SELECT * FROM `{TABLE_CATEGORIAS_PRECIFICACAO}` ORDER BY nome"
    return [dict(row) for row in execute_query(query)]