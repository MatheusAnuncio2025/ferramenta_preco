# app/routers/simulador.py
from fastapi import APIRouter, Depends, HTTPException
from .. import models, services, dependencies
import traceback

router = APIRouter(
    prefix="/api/simulador",
    tags=["Simulador"]
)

@router.post("/run", response_model=models.SimulacaoResultado)
async def run_simulation(payload: models.SimulacaoPayload, user: dict = Depends(dependencies.get_current_user)):
    """
    Executa uma simulação de cenário com base nos filtros e na ação fornecida.
    """
    try:
        resultado = await services.run_simulation(payload)
        return resultado
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao executar a simulação: {e}")