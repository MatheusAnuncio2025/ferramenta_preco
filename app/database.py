# app/database.py
from typing import List, Dict, Any, Optional
from . import services
from google.cloud import bigquery

def run_query(query: str, params: Optional[List[bigquery.ScalarQueryParameter]] = None) -> List[Dict[str, Any]]:
    """
    Executa uma query no BigQuery e retorna os resultados como uma lista de dicionários.
    """
    job_config = bigquery.QueryJobConfig(query_parameters=params) if params else None
    try:
        results = services.client.query(query, job_config=job_config).result()
        # Converte o resultado para uma lista de dicionários, tratando tipos de dados como data/hora
        rows = []
        for row in results:
            row_dict = dict(row)
            for key, value in row_dict.items():
                if isinstance(value, (services.datetime, services.date)):
                    row_dict[key] = value.isoformat()
            rows.append(row_dict)
        return rows
    except Exception as e:
        print(f"Erro ao executar a query no BigQuery: {e}")
        # Em um ambiente de produção, seria ideal logar este erro de forma mais robusta.
        raise

# --- Funções de Precificação ---

def get_precificacao_by_id(record_id: str) -> Optional[Dict[str, Any]]:
    """Busca um registro de precificação pelo seu ID."""
    query = f"SELECT * FROM `{services.TABLE_PRECIFICACOES_SALVAS}` WHERE id = @id"
    params = [bigquery.ScalarQueryParameter("id", "STRING", record_id)]
    results = run_query(query, params)
    return results[0] if results else None

def get_filtered_precificacoes(filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Busca precificações com base em um dicionário de filtros."""
    query = f"SELECT * FROM `{services.TABLE_PRECIFICACOES_SALVAS}`"
    where_clauses = []
    params = []

    for key, value in filters.items():
        if not value:
            continue
        if key in ['sku', 'titulo']:
            where_clauses.append(f"LOWER({key}) LIKE LOWER(@{key})")
            params.append(bigquery.ScalarQueryParameter(key, "STRING", f"%{value}%"))
        elif key == 'plano':
            if value == 'classico': where_clauses.append("venda_classico > 0")
            elif value == 'premium': where_clauses.append("venda_premium > 0")
        else:
            where_clauses.append(f"LOWER({key}) = LOWER(@{key})")
            params.append(bigquery.ScalarQueryParameter(key, "STRING", value))

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    
    query += " ORDER BY data_calculo DESC LIMIT 100"
    
    return run_query(query, params)

def delete_precificacao_by_id(record_id: str):
    """Deleta uma precificação base e suas campanhas associadas."""
    query_campanhas = f"DELETE FROM `{services.TABLE_PRECIFICACOES_CAMPANHA}` WHERE precificacao_base_id = @id"
    query_base = f"DELETE FROM `{services.TABLE_PRECIFICACOES_SALVAS}` WHERE id = @id"
    params = [bigquery.ScalarQueryParameter("id", "STRING", record_id)]
    
    run_query(query_campanhas, params)
    run_query(query_base, params)

# Adicione aqui outras funções de acesso a dados conforme necessário (para usuários, regras, etc.)
# Exemplo para buscar um usuário:
def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    query = f"SELECT *, pode_ver_historico FROM `{services.TABLE_USUARIOS}` WHERE email = @email"
    params = [bigquery.ScalarQueryParameter("email", "STRING", email)]
    results = run_query(query, params)
    return results[0] if results else None