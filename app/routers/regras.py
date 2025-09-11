from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel, Field

# -----------------------------------------------------------------------------
# Modelos (Pydantic)
# -----------------------------------------------------------------------------
class TarifaFixaItem(BaseModel):
    min_venda: float = Field(0, description="Valor mínimo de venda (R$) para a faixa")
    max_venda: float = Field(float("inf"), description="Valor máximo de venda (R$) para a faixa")
    taxa_fixa: float = Field(0, description="Tarifa fixa em R$")
    taxa_percentual: float = Field(0, description="Tarifa em % aplicada sobre o valor de venda")


class FreteRegraItem(BaseModel):
    min_venda: float = Field(0, description="Valor mínimo de venda (R$)")
    max_venda: float = Field(float("inf"), description="Valor máximo de venda (R$)")
    min_peso_g: float = Field(0, description="Peso mínimo em gramas")
    max_peso_g: float = Field(float("inf"), description="Peso máximo em gramas")
    custo_frete: float = Field(0, description="Custo de frete (R$) estimado para a faixa")


class ComissaoItem(BaseModel):
    # Ex.: {"chave": "padrão_ML", "classico": 15.0, "premium": 17.0}
    chave: str
    classico: float = 0.0
    premium: float = 0.0


class RegrasNegocioPayload(BaseModel):
    REGRAS_TARIFA_FIXA_ML: List[TarifaFixaItem] = Field(default_factory=list)
    REGRAS_FRETE_ML: List[FreteRegraItem] = Field(default_factory=list)
    COMISSOES: List[ComissaoItem] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Inicialização do router
# -----------------------------------------------------------------------------
router = APIRouter(prefix="/api/regras-negocio", tags=["regras-negocio"])

# -----------------------------------------------------------------------------
# Fontes de dados com fallback seguro
# -----------------------------------------------------------------------------
def _try_import_services() -> Optional[Any]:
    """
    Tenta importar app.services de forma segura.
    Retorna o módulo se disponível, caso contrário None.
    """
    try:
        from app import services  # type: ignore
        return services
    except Exception:
        return None


def _load_from_services() -> Dict[str, Any]:
    """
    Tenta buscar dados de regras via services.py, se as funções existirem.
    Caso algo falhe, retorna dicionário com listas vazias.
    """
    out: Dict[str, Any] = {
        "REGRAS_TARIFA_FIXA_ML": [],
        "REGRAS_FRETE_ML": [],
        "COMISSOES": [],
    }
    services = _try_import_services()
    if not services:
        return out

    # Cada chamada é protegida por try/except pra nunca estourar 500
    try:
        if hasattr(services, "get_tarifa_fixa_rules"):
            out["REGRAS_TARIFA_FIXA_ML"] = services.get_tarifa_fixa_rules() or []
    except Exception:
        pass

    try:
        if hasattr(services, "get_frete_rules"):
            out["REGRAS_FRETE_ML"] = services.get_frete_rules() or []
    except Exception:
        pass

    try:
        if hasattr(services, "get_comissoes_rules"):
            out["COMISSOES"] = services.get_comissoes_rules() or []
    except Exception:
        pass

    return out


def _load_from_json() -> Dict[str, Any]:
    """
    Opcional: carrega regras de app/data/regras.json se existir.
    Estrutura esperada:
    {
      "REGRAS_TARIFA_FIXA_ML": [...],
      "REGRAS_FRETE_ML": [...],
      "COMISSOES": [...]
    }
    """
    base_dir = Path(__file__).resolve().parent.parent  # /app/app
    data_path = base_dir / "data" / "regras.json"
    out: Dict[str, Any] = {
        "REGRAS_TARIFA_FIXA_ML": [],
        "REGRAS_FRETE_ML": [],
        "COMISSOES": [],
    }
    try:
        if data_path.exists():
            import json

            with data_path.open("r", encoding="utf-8") as f:
                raw = json.load(f) or {}
            out["REGRAS_TARIFA_FIXA_ML"] = raw.get("REGRAS_TARIFA_FIXA_ML", []) or []
            out["REGRAS_FRETE_ML"] = raw.get("REGRAS_FRETE_ML", []) or []
            out["COMISSOES"] = raw.get("COMISSOES", []) or []
    except Exception:
        # Falha ao ler/parsear? Retorna vazio, sem 500.
        pass
    return out


def _merge_rules(*sources: Dict[str, Any]) -> RegrasNegocioPayload:
    """
    Mescla múltiplas fontes de regras.
    A primeira fonte que trouxer dados válidos para cada chave “vence”.
    """
    merged: Dict[str, Any] = {
        "REGRAS_TARIFA_FIXA_ML": [],
        "REGRAS_FRETE_ML": [],
        "COMISSOES": [],
    }

    for src in sources:
        for key in merged.keys():
            if not merged[key] and src.get(key):
                merged[key] = src.get(key) or []

    # Validação/normalização leve via modelos Pydantic
    return RegrasNegocioPayload(
        REGRAS_TARIFA_FIXA_ML=[TarifaFixaItem(**x) for x in merged["REGRAS_TARIFA_FIXA_ML"]],
        REGRAS_FRETE_ML=[FreteRegraItem(**x) for x in merged["REGRAS_FRETE_ML"]],
        COMISSOES=[ComissaoItem(**x) for x in merged["COMISSOES"]],
    )


def _load_rules_payload() -> RegrasNegocioPayload:
    """
    Carrega as regras tentando (services -> json -> vazio) e retorna payload mesclado.
    """
    from_services = _load_from_services()
    from_json = _load_from_json()
    payload = _merge_rules(from_services, from_json, {})
    return payload


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@router.get("", response_model=RegrasNegocioPayload)
async def get_regras_negocio() -> RegrasNegocioPayload:
    """
    Pacote completo de regras de negócio.
    Compatível com o front que chama /api/regras-negocio.
    """
    return _load_rules_payload()


@router.get("/tarifa-fixa", response_model=List[TarifaFixaItem])
async def get_tarifa_fixa() -> List[TarifaFixaItem]:
    """
    Regras de tarifa fixa (Mercado Livre) por faixa de valor.
    Compatível com telas de configuração/diagnóstico.
    """
    payload = _load_rules_payload()
    # Nunca 500: se não houver dados, devolve lista vazia
    return payload.REGRAS_TARIFA_FIXA_ML


@router.get("/frete", response_model=List[FreteRegraItem])
async def get_regras_frete() -> List[FreteRegraItem]:
    """
    Regras de estimativa de frete por faixa (valor x peso).
    """
    payload = _load_rules_payload()
    return payload.REGRAS_FRETE_ML


@router.get("/comissoes", response_model=List[ComissaoItem])
async def get_regras_comissoes() -> List[ComissaoItem]:
    """
    Regras de comissão por 'chave' (ex.: categoria ML, ou tipo de anúncio).
    Útil para debug/admin.
    """
    payload = _load_rules_payload()
    return payload.COMISSOES
