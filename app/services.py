import os
import uuid
import json
import traceback
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from google.cloud import bigquery, storage
from cachetools import cached
from .cache import cache
from . import models

client = bigquery.Client()
storage_client = storage.Client()
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", client.project)
BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")

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
TABLE_VENDAS = f"{PROJECT_ID}.relatorio_vendas.base_dash_relatorio_vendas"

def _bq_type(value):
    from decimal import Decimal
    if value is None: return "STRING"
    if isinstance(value, bool): return "BOOL"
    if isinstance(value, int): return "INT64"
    if isinstance(value, float): return "FLOAT64"
    if isinstance(value, Decimal): return "NUMERIC"
    if isinstance(value, datetime): return "TIMESTAMP"
    if isinstance(value, date): return "DATE"
    return "STRING"

def log_action(user_email: str, action: str, details: dict = None, detalhes_alteracao: dict = None):
    try:
        if "RULE" in action or "CAMPAIGN" in action or "STORE" in action:
            cache.clear()
        log_entry = {
            "timestamp": datetime.utcnow(),
            "user_email": user_email,
            "action": action,
            "details": json.dumps(details) if details else None,
            "detalhes_alteracao": json.dumps(detalhes_alteracao) if detalhes_alteracao else None
        }
        cols = ", ".join(f"`{k}`" for k in log_entry.keys())
        placeholders = ", ".join(f"@{k}" for k in log_entry.keys())
        query = f"INSERT INTO `{TABLE_LOGS}` ({cols}) VALUES ({placeholders})"
        params = [bigquery.ScalarQueryParameter(k, _bq_type(v), v) for k, v in log_entry.items()]
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        client.query(query, job_config=job_config).result()
    except Exception as e:
        print(f"ERRO AO LOGAR AÇÃO: {e}")

def execute_query(query: str, params: Optional[List[bigquery.ScalarQueryParameter]] = None) -> bigquery.table.RowIterator:
    job_config = bigquery.QueryJobConfig(query_parameters=params) if params else None
    return client.query(query, job_config=job_config).result()

def fetch_product_data(sku: str) -> Optional[dict]:
    query = (
        f"SELECT sku, titulo, valor_de_custo as custo_update, peso as peso_kg, "
        f"altura as altura_cm, largura as largura_cm, comprimento as comprimento_cm "
        f"FROM `{TABLE_PRODUTOS}` WHERE LOWER(sku) = LOWER(@sku)"
    )
    params = [bigquery.ScalarQueryParameter("sku", "STRING", sku)]
    results = [dict(row) for row in execute_query(query, params)]
    return results[0] if results else None

def get_precificacao_by_id(record_id: str) -> Optional[Dict[str, Any]]:
    query = f"SELECT * FROM `{TABLE_PRECIFICACOES_SALVAS}` WHERE id = @id"
    params = [bigquery.ScalarQueryParameter("id", "STRING", record_id)]
    results = [dict(row) for row in execute_query(query, params)]
    if not results:
        return None
    item = results[0]
    for key, value in item.items():
        if hasattr(value, "isoformat"):
            item[key] = value.isoformat()
    return item

def get_filtered_precificacoes(filters: Dict[str, Any], page: int = 1, page_size: int = 20) -> models.PrecificacaoListResponse:
    base_query = f"FROM `{TABLE_PRECIFICACOES_SALVAS}`"
    where_clauses, params = [], []
    filter_map = {'categoria': 'categoria_precificacao'}
    for key, value in filters.items():
        if not value: continue
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
    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    count_query = f"SELECT COUNT(*) as total {base_query}{where_sql}"
    count_result = client.query(count_query, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
    total_items = list(count_result)[0].total
    offset = (page - 1) * page_size
    select_query = f"SELECT * {base_query}{where_sql} ORDER BY data_calculo DESC LIMIT @page_size OFFSET @offset"
    pag_params = [bigquery.ScalarQueryParameter("page_size", "INT64", page_size), bigquery.ScalarQueryParameter("offset", "INT64", offset)]
    results_iterator = client.query(select_query, job_config=bigquery.QueryJobConfig(query_parameters=params + pag_params)).result()
    items = []
    for row in results_iterator:
        item_dict = dict(row)
        for k, v in item_dict.items():
            if hasattr(v, "isoformat"):
                item_dict[k] = v.isoformat()
        items.append(item_dict)
    return models.PrecificacaoListResponse(total_items=total_items, items=items)

def delete_precificacao_and_campaigns(record_id: str):
    params = [bigquery.ScalarQueryParameter("id", "STRING", record_id)]
    execute_query(f"DELETE FROM `{TABLE_PRECIFICACOES_CAMPANHA}` WHERE precificacao_base_id = @id", params)
    execute_query(f"DELETE FROM `{TABLE_PRECIFICACOES_SALVAS}` WHERE id = @id", params)

def bulk_update_prices(payload: models.BulkUpdatePayload, user_email: str):
    if not payload.ids: return 0
    if payload.action == models.UpdateAction.set_custo_unitario:
        field_to_update, ptype = "custo_unitario", "FLOAT64"
    elif payload.action == models.UpdateAction.set_categoria:
        field_to_update, ptype = "categoria_precificacao", "STRING"
    else:
        raise ValueError(f"Ação de atualização em massa '{payload.action.value}' não é suportada.")
    query = (
        f"UPDATE `{TABLE_PRECIFICACOES_SALVAS}` "
        f"SET {field_to_update} = @value, calculado_por = @user_email, data_calculo = CURRENT_TIMESTAMP() "
        f"WHERE id IN UNNEST(@ids)"
    )
    params = [
        bigquery.ScalarQueryParameter("value", ptype, payload.value),
        bigquery.ScalarQueryParameter("user_email", "STRING", user_email),
        bigquery.ArrayQueryParameter("ids", "STRING", payload.ids)
    ]
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    query_job = client.query(query, job_config=job_config); query_job.result()
    log_action(user_email, "BULK_UPDATE_PRICING", details={"action": payload.action.value, "value": payload.value, "item_count": len(payload.ids), "ids_afetados": payload.ids})
    return query_job.num_dml_affected_rows

def get_linked_campaigns(base_id: str) -> List[Dict[str, Any]]:
    query = (
        f"SELECT pc.*, c.nome as nome_campanha "
        f"FROM `{TABLE_PRECIFICACOES_CAMPANHA}` pc "
        f"JOIN `{TABLE_CAMPANHAS_ML}` c ON pc.campanha_id = c.id "
        f"WHERE pc.precificacao_base_id = @base_id"
    )
    params = [bigquery.ScalarQueryParameter("base_id", "STRING", base_id)]
    results = [dict(row) for row in execute_query(query, params)]
    for item in results:
        for k, v in item.items():
            if hasattr(v, "isoformat"):
                item[k] = v.isoformat()
    return results

def get_campaign_pricing_details(item_id: str) -> Optional[Dict[str, Any]]:
    query = (
        f"SELECT pc.*, c.nome as nome_campanha, pb.sku, pb.titulo "
        f"FROM `{TABLE_PRECIFICACOES_CAMPANHA}` pc "
        f"JOIN `{TABLE_CAMPANHAS_ML}` c ON pc.campanha_id = c.id "
        f"JOIN `{TABLE_PRECIFICACOES_SALVAS}` pb ON pc.precificacao_base_id = pb.id "
        f"WHERE pc.id = @id"
    )
    params = [bigquery.ScalarQueryParameter("id", "STRING", item_id)]
    results = [dict(row) for row in execute_query(query, params)]
    if not results: return None
    item = results[0]
    for k, v in item.items():
        if hasattr(v, "isoformat"): item[k] = v.isoformat()
    return item

def get_price_history_for_sku(sku: str) -> List[Dict[str, Any]]:
    query = (
        f"SELECT * FROM `{TABLE_LOGS}` "
        f"WHERE action = 'UPDATE_PRICING' AND JSON_EXTRACT_SCALAR(details, '$.sku') = @sku "
        f"ORDER BY timestamp DESC"
    )
    params = [bigquery.ScalarQueryParameter("sku", "STRING", sku)]
    results = [dict(row) for row in execute_query(query, params)]
    for item in results:
        for k, v in item.items():
            if hasattr(v, "isoformat"): item[k] = v.isoformat()
    return results

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    query = f"SELECT *, pode_ver_historico FROM `{TABLE_USUARIOS}` WHERE email = @email"
    params = [bigquery.ScalarQueryParameter("email", "STRING", email)]
    results = [dict(row) for row in execute_query(query, params)]
    return results[0] if results else None

def get_all_users() -> List[Dict[str, Any]]:
    query = f"SELECT *, pode_ver_historico FROM `{TABLE_USUARIOS}` ORDER BY nome ASC"
    results = [dict(row) for row in execute_query(query)]
    for user in results:
        for k, v in user.items():
            if hasattr(v, "isoformat"): user[k] = v.isoformat()
    return results

def create_user(user_data: Dict[str, Any]) -> Dict[str, Any]:
    cols = ", ".join(f"`{k}`" for k in user_data.keys())
    placeholders = ", ".join(f"@{k}" for k in user_data.keys())
    query = f"INSERT INTO `{TABLE_USUARIOS}` ({cols}) VALUES ({placeholders})"
    params = [bigquery.ScalarQueryParameter(k, _bq_type(v), v) for k, v in user_data.items()]
    execute_query(query, params)
    return user_data

def update_user_properties(email: str, updates: Dict[str, Any]):
    set_clauses = ", ".join([f"`{k}` = @{k}" for k in updates.keys()])
    query = f"UPDATE `{TABLE_USUARIOS}` SET {set_clauses} WHERE email = @email"
    params = [bigquery.ScalarQueryParameter("email", "STRING", email)]
    for k, v in updates.items():
        params.append(bigquery.ScalarQueryParameter(k, _bq_type(v), v))
    execute_query(query, params)

def delete_user_by_email(email: str):
    execute_query(f"DELETE FROM `{TABLE_USUARIOS}` WHERE email = @email", [bigquery.ScalarQueryParameter("email", "STRING", email)])

@cached(cache)
def get_all_campaigns() -> List[Dict[str, Any]]:
    return [dict(row) for row in execute_query(f"SELECT * FROM `{TABLE_CAMPANHAS_ML}` ORDER BY data_fim DESC, nome")]

@cached(cache)
def get_active_campaigns() -> List[Dict[str, Any]]:
    return [dict(row) for row in execute_query(f"SELECT * FROM `{TABLE_CAMPANHAS_ML}` WHERE data_fim >= CURRENT_DATE() OR data_fim IS NULL ORDER BY nome")]

def save_all_campaigns(campaigns_list: List[Dict[str, Any]]):
    from decimal import Decimal
    ids_na_ui = [c['id'] for c in campaigns_list if c.get('id')]
    if ids_na_ui:
        execute_query(f"DELETE FROM `{TABLE_CAMPANHAS_ML}` WHERE id NOT IN UNNEST(@ids)", [bigquery.ArrayQueryParameter("ids", "STRING", ids_na_ui)])
    else:
        execute_query(f"DELETE FROM `{TABLE_CAMPANHAS_ML}` WHERE true")
    for campaign in campaigns_list:
        if not campaign.get('id'):
            campaign['id'] = str(uuid.uuid4())
        cols = ", ".join(f"`{k}`" for k in campaign.keys())
        placeholders = ", ".join(f"@{k}" for k in campaign.keys())
        merge_query = f"""
            MERGE `{TABLE_CAMPANHAS_ML}` T
            USING (SELECT {placeholders}) S ON T.id = S.id
            WHEN MATCHED THEN UPDATE SET {", ".join([f"T.{k} = S.{k}" for k in campaign.keys() if k != 'id'])}
            WHEN NOT MATCHED THEN INSERT ({cols}) VALUES ({cols})
        """
        def _ptype(v):
            if v is None or isinstance(v, str): return "STRING"
            if isinstance(v, date): return "DATE"
            if isinstance(v, float): return "FLOAT64"
            from decimal import Decimal as D
            if isinstance(v, D): return "NUMERIC"
            if isinstance(v, bool): return "BOOL"
            if isinstance(v, int): return "INT64"
            return "STRING"
        params = [bigquery.ScalarQueryParameter(k, _ptype(v), v) for k, v in campaign.items()]
        execute_query(merge_query, params)
    cache.clear()

@cached(cache)
def get_lojas_config() -> List[Dict[str, Any]]:
    return [dict(row) for row in execute_query(f"SELECT * FROM `{TABLE_LOJAS_CONFIG}` ORDER BY marketplace, id_loja")]

async def get_loja_details(loja_id: str) -> Dict[str, Any]:
    params = [bigquery.ScalarQueryParameter("loja_id", "STRING", loja_id)]
    results = [dict(row) for row in execute_query(f"SELECT configuracoes FROM `{TABLE_LOJA_CONFIG_DETALHES}` WHERE loja_id = @loja_id", params)]
    if not results or not results[0].get('configuracoes'):
        return {}
    config_data = results[0]['configuracoes']
    if isinstance(config_data, str):
        try:
            config_data = json.loads(config_data)
        except json.JSONDecodeError:
            return {}
    return config_data if isinstance(config_data, dict) else {}

def get_loja_id_by_marketplace_and_loja(marketplace: str, id_loja: str) -> Optional[str]:
    params = [bigquery.ScalarQueryParameter("marketplace", "STRING", marketplace), bigquery.ScalarQueryParameter("id_loja", "STRING", id_loja)]
    results = [dict(row) for row in execute_query(f"SELECT id FROM `{TABLE_LOJAS_CONFIG}` WHERE marketplace = @marketplace AND id_loja = @id_loja", params)]
    return results[0]['id'] if results else None

def save_loja_details(loja_id: str, detalhes_json: str):
    query = (
        f"MERGE `{TABLE_LOJA_CONFIG_DETALHES}` T "
        f"USING (SELECT @loja_id as loja_id, @config_json as configuracoes) S ON T.loja_id = S.loja_id "
        f"WHEN MATCHED THEN UPDATE SET T.configuracoes = S.configuracoes "
        f"WHEN NOT MATCHED THEN INSERT (loja_id, configuracoes) VALUES (S.loja_id, S.configuracoes)"
    )
    params = [bigquery.ScalarQueryParameter("loja_id", "STRING", loja_id), bigquery.ScalarQueryParameter("config_json", "JSON", detalhes_json)]
    execute_query(query, params); cache.clear()

def delete_loja_and_details(loja_id: str):
    params = [bigquery.ScalarQueryParameter("loja_id", "STRING", loja_id)]
    execute_query(f"DELETE FROM `{TABLE_LOJAS_CONFIG}` WHERE id = @loja_id", params)
    execute_query(f"DELETE FROM `{TABLE_LOJA_CONFIG_DETALHES}` WHERE loja_id = @loja_id", params)
    cache.clear()

def get_dashboard_alert_data() -> Dict[str, List]:
    query_campanhas = (
        f"SELECT * FROM `{TABLE_CAMPANHAS_ML}` "
        f"WHERE data_fim BETWEEN CURRENT_DATE() AND DATE_ADD(CURRENT_DATE(), INTERVAL 7 DAY) "
        f"ORDER BY data_fim ASC"
    )
    campanhas = [dict(row) for row in execute_query(query_campanhas)]
    query_custos = (
        f"WITH LatestPricing AS ("
        f"  SELECT id, sku, titulo, custo_unitario, ROW_NUMBER() OVER(PARTITION BY sku ORDER BY data_calculo DESC) as rn "
        f"  FROM `{TABLE_PRECIFICACOES_SALVAS}`)"
        f"SELECT lp.id as id_precificacao, lp.sku, lp.titulo, lp.custo_unitario as custo_precificado, "
        f"       p.valor_de_custo as custo_atual "
        f"FROM LatestPricing lp JOIN `{TABLE_PRODUTOS}` p ON lp.sku = p.sku "
        f"WHERE lp.rn = 1 AND lp.custo_unitario != p.valor_de_custo AND p.valor_de_custo IS NOT NULL LIMIT 50"
    )
    custos = [dict(row) for row in execute_query(query_custos)]
    query_estagnados = f"""
        WITH LastSale AS (
            SELECT sku, MAX(data_do_pedido) as ultima_venda
            FROM `{TABLE_VENDAS}`
            GROUP BY sku
        )
        SELECT 
            p.sku, p.titulo,
            DATE_DIFF(CURRENT_DATE(), COALESCE(DATE(ls.ultima_venda), DATE(p.data_cadastro)), DAY) as dias_sem_vender
        FROM `{TABLE_PRODUTOS}` p
        LEFT JOIN LastSale ls ON p.sku = ls.sku
        WHERE COALESCE(DATE(ls.ultima_venda), DATE(p.data_cadastro)) <= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
          AND p.status = 'ATIVO'
        ORDER BY dias_sem_vender DESC
        LIMIT 50
    """
    try:
        estagnados = [dict(row) for row in execute_query(query_estagnados)]
    except Exception as e:
        print(f"AVISO: Não foi possível buscar produtos estagnados. Erro: {e}")
        estagnados = []
    return {"campanhas_expirando": campanhas, "custos_desatualizados": custos, "produtos_estagnados": estagnados}

def get_history_logs() -> List[Dict[str, Any]]:
    results = [dict(row) for row in execute_query(f"SELECT * FROM `{TABLE_LOGS}` ORDER BY timestamp DESC LIMIT 200")]
    for r in results:
        for k, v in list(r.items()):
            if hasattr(v, "isoformat"): r[k] = v.isoformat()
    return results

def get_profitability_by_category() -> List[Dict[str, Any]]:
    query = (
        f"SELECT categoria_precificacao as label, SUM(lucro_classico + lucro_premium) as value "
        f"FROM `{TABLE_PRECIFICACOES_SALVAS}` WHERE categoria_precificacao IS NOT NULL "
        f"GROUP BY categoria_precificacao ORDER BY value DESC"
    )
    return [dict(row) for row in execute_query(query)]

def get_profit_evolution() -> List[Dict[str, Any]]:
    query = (
        f"SELECT FORMAT_TIMESTAMP('%Y-%m', data_calculo) as label, SUM(lucro_classico + lucro_premium) as value "
        f"FROM `{TABLE_PRECIFICACOES_SALVAS}` "
        f"WHERE data_calculo >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 6 MONTH)) "
        f"GROUP BY label ORDER BY label"
    )
    return [dict(row) for row in execute_query(query)]

async def get_all_business_rules() -> Dict[str, List]:
    try:
        queries = {
            "REGRAS_TARIFA_FIXA_ML": f"SELECT * FROM `{TABLE_REGRAS_TARIFA_FIXA}` ORDER BY min_venda",
            "REGRAS_FRETE_ML": f"SELECT * FROM `{TABLE_REGRAS_FRETE}` ORDER BY min_venda, min_peso_g",
            "CATEGORIAS_PRECIFICACAO": f"SELECT * FROM `{TABLE_CATEGORIAS_PRECIFICACAO}` ORDER BY nome"
        }
        results = {}
        for key, query in queries.items():
            rows = [dict(row) for row in client.query(query).result()]
            results[key] = rows
        return results
    except Exception as e:
        traceback.print_exc()
        raise e

def get_all_precificacao_categories() -> List[Dict[str, Any]]:
    return [dict(row) for row in execute_query(f"SELECT * FROM `{TABLE_CATEGORIAS_PRECIFICACAO}` ORDER BY nome")]

async def run_simulation(payload: models.SimulacaoPayload) -> models.SimulacaoResultado:
    filters = payload.filters.model_dump(exclude_none=True)
    precificacoes_response = get_filtered_precificacoes(filters, page=1, page_size=10000)
    precificacoes = precificacoes_response.items
    if not precificacoes:
        raise ValueError("Nenhum produto encontrado para os filtros selecionados.")
    def calculate_totals(price_list):
        receita = sum((p.get('venda_classico', 0) or 0) + (p.get('venda_premium', 0) or 0) for p in price_list)
        custo = sum(p.get('custo_total', 0) or 0 for p in price_list)
        lucro = sum((p.get('lucro_classico', 0) or 0) + (p.get('lucro_premium', 0) or 0) for p in price_list)
        margem = (lucro / receita * 100) if receita > 0 else 0
        return models.TotaisSimulacao(receita_total=receita, custo_total=custo, lucro_total=lucro, margem_media=margem, total_items=len(price_list))
    antes = calculate_totals(precificacoes)
    action = payload.action
    precificacoes_depois = []
    for p in precificacoes:
        p_depois = p.copy()
        if action.field == 'custo_unitario' and action.operation == 'percent_increase':
            novo_custo = (p_depois.get('custo_unitario', 0) or 0) * (1 + action.value / 100)
            p_depois['custo_unitario'] = novo_custo
            p_depois['custo_total'] = novo_custo * (p_depois.get('quantidade', 1) or 1)
            repasse = (p_depois.get('repasse_classico', 0) or 0) + (p_depois.get('repasse_premium', 0) or 0)
            lucro_total = repasse - p_depois['custo_total']
            p_depois['lucro_classico'] = lucro_total / 2
            p_depois['lucro_premium'] = lucro_total / 2
        precificacoes_depois.append(p_depois)
    depois = calculate_totals(precificacoes_depois)
    return models.SimulacaoResultado(antes=antes, depois=depois)

def process_rules_with_merge(table_id: str, rules: List[models.BaseModel], p_keys: List[str]):
    from decimal import Decimal
    for rule in rules:
        if not getattr(rule, 'id', None):
            setattr(rule, 'id', str(uuid.uuid4()))
    ids_to_keep = [rule.id for rule in rules if getattr(rule, 'id', None)]
    if ids_to_keep:
        execute_query(f"DELETE FROM `{table_id}` WHERE id NOT IN UNNEST(@ids)", [bigquery.ArrayQueryParameter("ids", "STRING", ids_to_keep)])
    elif not rules:
        execute_query(f"DELETE FROM `{table_id}` WHERE true"); return
    if not rules: return
    model_fields = rules[0].model_fields.keys()
    source_columns = ", ".join(f"`{col}`" for col in model_fields)
    update_clause = ", ".join(f"T.`{col}` = S.`{col}`" for col in model_fields if col not in p_keys)
    source_selects, all_params, param_counter = [], [], 0
    for rule in rules:
        placeholders = []
        rule_dict = rule.model_dump()
        for key, value in rule_dict.items():
            param_name = f"p{param_counter}"
            placeholders.append(f"@{param_name} AS `{key}`")
            if isinstance(value, bool): ptype = "BOOL"
            elif isinstance(value, int): ptype = "INT64"
            elif isinstance(value, float): ptype = "FLOAT64"
            elif isinstance(value, date): ptype = "DATE"
            elif isinstance(value, Decimal): ptype = "NUMERIC"
            else: ptype = "STRING"
            all_params.append(bigquery.ScalarQueryParameter(param_name, ptype, value))
            param_counter += 1
        source_selects.append(f"SELECT {', '.join(placeholders)}")
    source_query_part = "\nUNION ALL\n".join(source_selects)
    merge_query = f"""
    MERGE `{table_id}` T
    USING ({source_query_part}) AS S ON {' AND '.join([f'T.{pk} = S.{pk}' for pk in p_keys])}
    WHEN MATCHED THEN UPDATE SET {update_clause}
    WHEN NOT MATCHED BY TARGET THEN INSERT ({source_columns}) VALUES ({source_columns})
    """
    execute_query(merge_query, all_params); cache.clear()
