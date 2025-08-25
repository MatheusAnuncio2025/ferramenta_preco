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
        campanhas_expirando=alert_data["campanhas_expirando"],
        custos_desatualizados=alert_data["custos_desatualizados"],
        produtos_estagnados=alert_data["produtos_estagnados"]
    )