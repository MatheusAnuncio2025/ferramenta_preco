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
    alert_data = services.get_dashboard_alert_data()
    return models.DashboardData(
        campanhas_expirando=alert_data.get("campanhas_expirando", []),
        custos_desatualizados=alert_data.get("custos_desatualizados", []),
        produtos_estagnados=alert_data.get("produtos_estagnados", []),
    )

# Gráfico de rentabilidade por categoria
@router.get("/rentabilidade-categoria", response_model=models.ChartData)
async def get_rentabilidade_por_categoria(user: dict = Depends(dependencies.get_current_user)):
    """Recupera dados de rentabilidade agrupados por categoria."""
    data = services.get_profitability_by_category()
    return models.ChartData(data=[models.ChartDataItem(**item) for item in data])

# Gráfico de evolução do lucro (últimos 6 meses)
@router.get("/evolucao-lucro", response_model=models.ChartData)
async def get_evolucao_lucro(user: dict = Depends(dependencies.get_current_user)):
    """Recupera dados da evolução do lucro nos últimos 6 meses."""
    data = services.get_profit_evolution()
    return models.ChartData(data=[models.ChartDataItem(**item) for item in data])
