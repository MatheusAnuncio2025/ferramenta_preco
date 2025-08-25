# app/routers/dashboard.py
from fastapi import APIRouter, Depends
from .. import models, services, dependencies

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"]
)

@router.get("/alertas", response_model=models.DashboardData)
async def get_dashboard_data(user: dict = Depends(dependencies.get_current_user)):
    """Recupera os dados para o dashboard de alertas."""
    query_campanhas = f"""
        SELECT * FROM `{services.TABLE_CAMPANHAS_ML}`
        WHERE data_fim BETWEEN CURRENT_DATE() AND DATE_ADD(CURRENT_DATE(), INTERVAL 7 DAY)
        ORDER BY data_fim ASC
    """
    campanhas_expirando = [dict(row) for row in services.client.query(query_campanhas).result()]

    query_custos = f"""
        WITH LatestPricing AS (
            SELECT 
                id, sku, titulo, custo_unitario,
                ROW_NUMBER() OVER(PARTITION BY sku ORDER BY data_calculo DESC) as rn
            FROM `{services.TABLE_PRECIFICACOES_SALVAS}`
        )
        SELECT 
            lp.id as id_precificacao,
            lp.sku, 
            lp.titulo, 
            lp.custo_unitario as custo_precificado, 
            p.valor_de_custo as custo_atual
        FROM LatestPricing lp
        JOIN `{services.TABLE_PRODUTOS}` p ON lp.sku = p.sku
        WHERE lp.rn = 1 AND lp.custo_unitario != p.valor_de_custo AND p.valor_de_custo IS NOT NULL
        LIMIT 50
    """
    custos_desatualizados = [dict(row) for row in services.client.query(query_custos).result()]

    query_estagnados = f"""
        WITH LastSale AS (
            SELECT
                sku,
                MAX(data_venda) as ultima_venda
            FROM `{services.TABLE_VENDAS}`
            GROUP BY sku
        )
        SELECT 
            p.sku,
            p.titulo,
            DATE_DIFF(CURRENT_DATE(), COALESCE(ls.ultima_venda, DATE(p.data_cadastro)), DAY) as dias_sem_vender
        FROM `{services.TABLE_PRODUTOS}` p
        LEFT JOIN LastSale ls ON p.sku = ls.sku
        WHERE COALESCE(ls.ultima_venda, DATE(p.data_cadastro)) <= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
        AND p.status = 'ATIVO'
        ORDER BY dias_sem_vender DESC
        LIMIT 50
    """
    try:
        produtos_estagnados = [dict(row) for row in services.client.query(query_estagnados).result()]
    except Exception as e:
        print(f"AVISO: Não foi possível buscar produtos estagnados. Verifique se a tabela de vendas está correta. Erro: {e}")
        produtos_estagnados = []

    return models.DashboardData(
        campanhas_expirando=campanhas_expirando,
        custos_desatualizados=custos_desatualizados,
        produtos_estagnados=produtos_estagnados
    )
