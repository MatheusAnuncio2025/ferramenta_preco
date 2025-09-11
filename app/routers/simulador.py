# app/routers/simulador.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import dependencies

router = APIRouter(prefix="/api", tags=["Simulador"])


# =============================================================================
# Modelos
# =============================================================================
class SimFilters(BaseModel):
    marketplace: Optional[str] = Field(None, description="Nome do marketplace (ex.: 'Mercado Livre')")
    id_loja: Optional[str] = Field(None, description="Identificador da loja no marketplace (ex.: 'Julishop')")
    categoria: Optional[str] = Field(None, description="Categoria de precificação (opcional)")


SimOperation = Literal[
    "percent_increase",  # +X%
    "percent_decrease",  # -X%
    "value_increase",    # +X reais
    "value_decrease",    # -X reais
]

class SimAction(BaseModel):
    field: Literal["custo_unitario"] = Field("custo_unitario", description="Campo a alterar (suportado: custo_unitario)")
    operation: SimOperation = "percent_increase"
    value: float = 0.0


class SimInput(BaseModel):
    filters: SimFilters
    action: SimAction


class SimAgg(BaseModel):
    receita_total: float = 0.0
    custo_total: float = 0.0
    lucro_total: float = 0.0
    margem_media: float = 0.0
    total_items: int = 0


class SimOutput(BaseModel):
    antes: SimAgg
    depois: SimAgg


# =============================================================================
# Helpers seguros (services + fallbacks)
# =============================================================================
def _try_services():
    try:
        from app import services  # type: ignore
        return services
    except Exception:
        return None


def _log_warning(msg: str):
    services = _try_services()
    if services and hasattr(services, "logger"):
        try:
            services.logger.warning(msg)
            return
        except Exception:
            pass
    print(f"AVISO: {msg}")


def _safe_list_snapshot(filters: SimFilters) -> List[Dict[str, Any]]:
    """
    Obtém um 'snapshot' de itens para simulação a partir do services.
    Tentativas (nessa ordem), sempre com fallback para []:
      - services.get_simulation_snapshot(filters_dict)
      - services.get_precificacao_base_for_simulation(filters_dict)
      - services.get_products_for_simulation(filters_dict)
    Cada item deve idealmente conter:
      - 'venda_classico' (ou 'preco'/'preco_venda')
      - 'custo_unitario' (ou 'custo')
      - 'quantidade' (default 1)
    """
    services = _try_services()
    if not services:
        return []

    fdict = {
        "marketplace": filters.marketplace,
        "id_loja": filters.id_loja,
        "categoria": filters.categoria,
    }

    for fn_name in (
        "get_simulation_snapshot",
        "get_precificacao_base_for_simulation",
        "get_products_for_simulation",
    ):
        try:
            fn = getattr(services, fn_name, None)
            if callable(fn):
                rows = fn(fdict) or []
                if isinstance(rows, list):
                    return rows
        except Exception as e:
            _log_warning(f"Falha em services.{fn_name}: {e}")

    return []


def _safe_categories() -> List[Dict[str, Any]]:
    """
    Lista categorias de precificação:
      - services.get_pricing_categories() → [{nome, margem_padrao}]
      - fallback: []
    """
    services = _try_services()
    if services and hasattr(services, "get_pricing_categories"):
        try:
            cats = services.get_pricing_categories() or []
            if isinstance(cats, list):
                # normaliza para {"nome": str, "margem_padrao": float}
                out = []
                for c in cats:
                    if not isinstance(c, dict):
                        continue
                    out.append(
                        {
                            "nome": str(c.get("nome") or c.get("categoria") or ""),
                            "margem_padrao": float(c.get("margem_padrao") or c.get("margem") or 0),
                        }
                    )
                return out
        except Exception as e:
            _log_warning(f"Falha em services.get_pricing_categories: {e}")
    return []


# =============================================================================
# Núcleo da simulação (puro/estateless)
# =============================================================================
def _norm_price(row: Dict[str, Any]) -> float:
    # aceita diversas chaves comuns
    for k in ("venda_classico", "preco", "preco_venda", "valor_venda"):
        v = row.get(k)
        if v is not None:
            try:
                return float(v)
            except Exception:
                pass
    return 0.0


def _norm_cost(row: Dict[str, Any]) -> float:
    for k in ("custo_unitario", "custo", "cost"):
        v = row.get(k)
        if v is not None:
            try:
                return float(v)
            except Exception:
                pass
    return 0.0


def _norm_qty(row: Dict[str, Any]) -> float:
    v = row.get("quantidade") or row.get("qty") or 1
    try:
        q = float(v)
        return q if q > 0 else 1.0
    except Exception:
        return 1.0


def _apply_action_cost(cost: float, action: SimAction) -> float:
    v = float(action.value or 0)
    if action.operation == "percent_increase":
        return max(0.0, cost * (1 + v / 100.0))
    if action.operation == "percent_decrease":
        return max(0.0, cost * (1 - v / 100.0))
    if action.operation == "value_increase":
        return max(0.0, cost + v)
    if action.operation == "value_decrease":
        return max(0.0, cost - v)
    # padrão seguro
    return cost


def _aggregate(rows: List[Dict[str, Any]], mutate_cost_with: Optional[SimAction] = None) -> SimAgg:
    receita = 0.0
    custo = 0.0
    total_items = 0

    for r in rows:
        if not isinstance(r, dict):
            continue
        price = _norm_price(r)
        cost = _norm_cost(r)
        qty = _norm_qty(r)

        if mutate_cost_with is not None:
            # apenas custo é alterado na simulação
            cost = _apply_action_cost(cost, mutate_cost_with)

        receita += price * qty
        custo += cost * qty
        total_items += 1

    lucro = receita - custo
    margem = (lucro / receita * 100.0) if receita > 0 else 0.0
    return SimAgg(
        receita_total=round(receita, 2),
        custo_total=round(custo, 2),
        lucro_total=round(lucro, 2),
        margem_media=round(margem, 2),
        total_items=total_items,
    )


# =============================================================================
# Endpoints
# =============================================================================
@router.get(
    "/categorias-precificacao",
    summary="(LEGADO) Lista categorias de precificação – compatível com simulador.html",
)
async def list_categorias_legacy(user: dict = Depends(dependencies.get_current_user)):
    """
    Back-compat para páginas que ainda chamam /api/categorias-precificacao.
    Se seu front já usa /api/precificacao/categorias-precificacao, mantenha ambos.
    """
    return _safe_categories()


@router.post("/simulador/run", response_model=SimOutput, summary="Executa simulação de cenários")
async def run_simulacao(payload: SimInput, user: dict = Depends(dependencies.get_current_user)) -> SimOutput:
    """
    Roda simulação de cenários alterando *apenas* o campo `custo_unitario`
    conforme 'action'. A receita permanece constante (preço de venda base),
    afetando lucro e margem.
    """
    try:
        # 1) snapshot de itens conforme filtros
        rows = _safe_list_snapshot(payload.filters)

        # 2) agregados "antes"
        antes = _aggregate(rows)

        # 3) agregados "depois" (aplicando ação no custo)
        if payload.action.field != "custo_unitario":
            # garantindo comportamento previsível (front hoje só envia custo_unitario)
            _log_warning(f"Ação com field não suportado: {payload.action.field}. Mantendo apenas custo_unitario.")
        depois = _aggregate(rows, mutate_cost_with=payload.action)

        return SimOutput(antes=antes, depois=depois)
    except HTTPException:
        raise
    except Exception as e:
        # Nunca deixar estourar 500 — converte em 400 explicando
        raise HTTPException(status_code=400, detail=f"Falha ao executar simulação: {e}")
