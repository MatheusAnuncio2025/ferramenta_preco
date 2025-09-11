# app/routers/dashboard.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException

from .. import dependencies

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


# =============================================================================
# Helpers seguros (integração com services + fallbacks)
# =============================================================================
def _try_import_services():
    try:
        from app import services  # type: ignore
        return services
    except Exception:
        return None


def _log_warning(msg: str):
    services = _try_import_services()
    if services and hasattr(services, "logger"):
        try:
            services.logger.warning(msg)
            return
        except Exception:
            pass
    # fallback
    print(f"AVISO: {msg}")


def _safe_call(fn_name: str, *args, **kwargs):
    """
    Chama uma função do app.services, se existir; caso contrário, retorna None.
    Nunca propaga exceção (converte em None + warning).
    """
    services = _try_import_services()
    if not services:
        return None
    fn = getattr(services, fn_name, None)
    if not callable(fn):
        return None
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        _log_warning(f"Falha em services.{fn_name}: {e}")
        return None


# =============================================================================
# Normalizadores – evitam quebraz na UI
# =============================================================================
def _norm_alert_campanha(row: Dict[str, Any]) -> Dict[str, Any]:
    # UI usa: id, nome, data_inicio, data_fim, tipo_campanha (opcional)
    return {
        "id": row.get("id"),
        "nome": row.get("nome") or row.get("title") or row.get("descricao"),
        "data_inicio": row.get("data_inicio") or row.get("inicio"),
        "data_fim": row.get("data_fim") or row.get("fim"),
        "tipo_campanha": row.get("tipo_campanha") or row.get("tipo"),
    }


def _norm_alert_custo(row: Dict[str, Any]) -> Dict[str, Any]:
    # UI usa: id_precificacao, sku, titulo, custo_update (do cadastro), custo_unitario_atual (na base), dias_desde_atualizacao
    return {
        "id_precificacao": row.get("id_precificacao") or row.get("id") or row.get("precificacao_id"),
        "sku": row.get("sku") or row.get("codigo_sku") or row.get("id_sku"),
        "titulo": row.get("titulo") or row.get("nome_produto"),
        "custo_update": row.get("custo_update") or row.get("custo_fornecedor") or 0.0,
        "custo_unitario_atual": row.get("custo_unitario_atual") or row.get("custo_unitario") or 0.0,
        "dias_desde_atualizacao": row.get("dias_desde_atualizacao") or row.get("dias") or None,
    }


def _norm_alert_estagnado(row: Dict[str, Any]) -> Dict[str, Any]:
    # UI usa: sku, titulo, dias_sem_vender
    # BigQuery pode não ter 'data_cadastro' em algumas visões, então normalize sem depender dela.
    return {
        "sku": row.get("sku") or row.get("codigo_sku") or row.get("id_sku"),
        "titulo": row.get("titulo") or row.get("nome_produto"),
        "dias_sem_vender": row.get("dias_sem_vender") or row.get("dias") or row.get("dias_sem_movimento") or 0,
    }


def _norm_chart_point(label: Any, value: Any) -> Dict[str, Any]:
    try:
        v = float(value)
    except Exception:
        v = 0.0
    return {"label": str(label), "value": v}


# =============================================================================
# Endpoints – compatíveis com Alertas.html
# =============================================================================
@router.get("/alertas")
async def get_dashboard_alertas(user: dict = Depends(dependencies.get_current_user)):
    """
    Retorna os três blocos de alertas esperados pela UI de /alertas:
      - campanhas_expirando (7 dias)
      - custos_desatualizados
      - produtos_estagnados (+90 dias)
    Nunca retorna 500; no pior caso, devolve listas vazias.
    """
    # Campanhas expirando (7 dias)
    rows_campanhas = _safe_call("get_campaigns_expiring", 7) or []
    campanhas_expirando = [_norm_alert_campanha(r) for r in rows_campanhas if isinstance(r, dict)]

    # Custos desatualizados
    rows_custos = _safe_call("get_outdated_costs") or []
    custos_desatualizados = [_norm_alert_custo(r) for r in rows_custos if isinstance(r, dict)]

    # Produtos estagnados (+90 dias) – se a query/fonte não tiver 'data_cadastro', não quebrar
    produtos_estagnados: List[Dict[str, Any]] = []
    rows_estagnados = _safe_call("get_stagnant_products", 90)
    if isinstance(rows_estagnados, list):
        produtos_estagnados = [_norm_alert_estagnado(r) for r in rows_estagnados if isinstance(r, dict)]
    else:
        # manter compat com o seu log e não derrubar a rota
        _log_warning(
            "Não foi possível buscar produtos estagnados. "
            "Verifique se a consulta possui as colunas esperadas (ex.: data_ultima_venda)."
        )

    return {
        "campanhas_expirando": campanhas_expirando,
        "custos_desatualizados": custos_desatualizados,
        "produtos_estagnados": produtos_estagnados,
    }


@router.get("/rentabilidade-categoria")
async def get_rentabilidade_categoria(user: dict = Depends(dependencies.get_current_user)):
    """
    Dados para o gráfico de rosca (doughnut) em Alertas.html.
    Resposta:
      { "data": [ { "label": "<categoria>", "value": <lucro_total> }, ... ] }
    """
    rows = _safe_call("get_profit_by_category") or []
    # Aceita formatos comuns: [{'categoria': 'A', 'lucro': 123.4}, ...]
    data = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        label = r.get("categoria") or r.get("label") or r.get("nome") or "—"
        value = r.get("lucro") or r.get("valor") or r.get("value") or 0
        data.append(_norm_chart_point(label, value))
    return {"data": data}


@router.get("/evolucao-lucro")
async def get_evolucao_lucro(user: dict = Depends(dependencies.get_current_user)):
    """
    Dados para o gráfico de linha (evolução dos últimos meses) em Alertas.html.
    Resposta:
      { "data": [ { "label": "<MMM/AAAA>", "value": <lucro_mensal> }, ... ] }
    """
    rows = _safe_call("get_profit_evolution") or []
    # Aceita formatos: [{'mes': '2025-07', 'lucro': 1000.0}, {'label': 'Jul/2025', 'value': 1000.0}, ...]
    def pretty_label(r: Dict[str, Any]) -> str:
        if r.get("label"):
            return str(r["label"])
        if r.get("mes_formatado"):
            return str(r["mes_formatado"])
        mes = str(r.get("mes") or r.get("periodo") or "")
        if len(mes) == 7 and mes[4] == "-":  # YYYY-MM
            ano, m = mes.split("-")
            nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
            try:
                idx = int(m) - 1
                if 0 <= idx < 12:
                    return f"{nomes[idx]}/{ano}"
            except Exception:
                pass
        return mes or "—"

    data = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        label = pretty_label(r)
        value = r.get("lucro") or r.get("valor") or r.get("value") or 0
        data.append(_norm_chart_point(label, value))
    return {"data": data}
