# app/services.py
import os
import uuid
import json
import traceback
from datetime import datetime, date
from typing import Optional, List
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
TABLE_VENDAS = f"{PROJECT_ID}.dados_vendas.vendas" if PROJECT_ID == "skilful-firefly-434016-b2" else f"{PROJECT_ID}.dados_vendas.vendas" # Ajuste para diferentes projetos

# --- Funções de Lógica de Negócio ---

def log_action(user_email: str, action: str, details: dict = None, detalhes_alteracao: dict = None):
    try:
        if action in ["UPDATE_BUSINESS_RULES", "UPDATE_CAMPAIGNS", "SAVE_STORE_DETAILS", "STORE_CONFIG_ADDED", "STORE_CONFIG_DELETED"]:
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
        
        params = [bigquery.ScalarQueryParameter(k, "TIMESTAMP" if isinstance(v, (datetime, date)) else "BOOL" if isinstance(v, bool) else "STRING", v) for k, v in log_entry.items()]

        job_config = bigquery.QueryJobConfig(query_parameters=params)
        client.query(query, job_config=job_config).result()
    except Exception as e: 
        print(f"ERRO AO LOGAR AÇÃO: {e}")

def fetch_product_data(sku: str) -> Optional[dict]:
    query = f"""
        SELECT sku, titulo, valor_de_custo as custo_update, peso as peso_kg,
               altura as altura_cm, largura as largura_cm, comprimento as comprimento_cm
        FROM `{TABLE_PRODUTOS}` WHERE LOWER(sku) = LOWER(@sku)
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("sku", "STRING", sku)])
    results = [dict(row) for row in client.query(query, job_config=job_config)]
    return results[0] if results else None

def process_rules(table_id: str, rules: List[BaseModel], p_keys: List[str]):
    for rule in rules:
        if not hasattr(rule, 'id') or not rule.id:
            rule.id = str(uuid.uuid4())

    if not rules:
        client.query(f"DELETE FROM `{table_id}` WHERE true").result()
        return

    ids_to_keep = [rule.id for rule in rules if hasattr(rule, 'id') and rule.id]
    if ids_to_keep:
        client.query(f"DELETE FROM `{table_id}` WHERE id NOT IN UNNEST(@ids)",
                     job_config=bigquery.QueryJobConfig(query_parameters=[
                         bigquery.ArrayQueryParameter("ids", "STRING", ids_to_keep)
                     ])).result()

    if rules:
        model_fields = rules[0].model_fields
        source_columns = ", ".join(f"`{col}`" for col in model_fields.keys())
        target_columns = ", ".join(f"T.`{col}`" for col in model_fields.keys())
        source_values = ", ".join(f"S.`{col}`" for col in model_fields.keys())
        
        update_clause = ", ".join([f"T.`{col}` = S.`{col}`" for col in model_fields.keys() if col not in p_keys])
        
        source_selects, params, param_counter = [], [], 0
        
        for rule in rules:
            placeholders = []
            for key, value in rule.model_dump().items():
                param_name = f"p{param_counter}"
                placeholders.append(f"@{param_name} AS `{key}`")
                
                param_type = "STRING" 
                if value is None:
                    numeric_hints = ['valor', 'margem', 'taxa', 'custo', 'peso', 'altura', 'largura', 'comprimento', 'venda']
                    if any(hint in key for hint in numeric_hints): param_type = "NUMERIC"
                    elif 'data' in key: param_type = "DATE"
                
                if isinstance(value, bool): param_type = "BOOL"
                elif isinstance(value, int): param_type = "INT64"
                elif isinstance(value, float): param_type = "NUMERIC"
                elif isinstance(value, date): param_type = "DATE"

                params.append(bigquery.ScalarQueryParameter(param_name, param_type, value))
                param_counter += 1
            source_selects.append(f"SELECT {', '.join(placeholders)}")

        source_query_part = "\nUNION ALL\n".join(source_selects)
        
        pk_join_condition = ' AND '.join([f'T.`{pk}` = S.`{pk}`' for pk in p_keys])

        merge_query = f"""
        MERGE `{table_id}` T
        USING ({source_query_part}) AS S ON {pk_join_condition}
        WHEN MATCHED THEN UPDATE SET {update_clause}
        WHEN NOT MATCHED BY TARGET THEN INSERT ({source_columns}) VALUES ({source_values})
        """
        client.query(merge_query, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
