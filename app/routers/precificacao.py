# app/routers/precificacao.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .. import dependencies

router = APIRouter(prefix="/api/precificacao", tags=["Precificação"])


# =============================================================================
# Models (Pydantic)
# =============================================================================
class CategoriaPrecificacao(BaseModel):
    nome: str
    margem_padrao: float = 0.0


class ProdutoInfo(BaseModel):
    sku: Optional[str] = None
    titulo: Optional[str] = None
    custo_update: float = 0.0
    peso_kg: float = 0.0
    altura_cm: float = 0.0
    largura_cm: float = 0.0
    comprimento_cm: float = 0.0
    id_sku_marketplace: Optional[str] = None
    id_anuncio: Optional[str] = None


class LojaConfig(BaseModel):
    aliquota_padrao: float = 0.0
    aliquota_fulfillment: float = 0.0
    comissoes: List[Dict[str, Any]] = Field(default_factory=list)


class PrecificacaoBaseItem(BaseModel):
    # campos mínimos usados na UI/lista/edição
    id: Optional[str] = None
    marketplace: str
    id_loja: str
    sku: str
    titulo: Optional[str] = None
    categoria_precificacao: Optional[str] = None

    quantidade: int = 1
    custo_unitario: float = 0.0
    custo_total: float = 0.0

    aliquota: float = 0.0
    parcelamento: float = 0.0
    outros: float = 0.0
    regra_comissao: Optional[str] = None
    fulfillment: bool = False
    catalogo_buybox: bool = False

    venda_classico: float = 0.0
    frete_classico: float = 0.0
    repasse_classico: float = 0.0
    lucro_classico: float = 0.0
    margem_classico: float = 0.0
    tarifa_fixa_classico: float = 0.0

    venda_premium: float = 0.0
    frete_premium: float = 0.0
    repasse_premium: float = 0.0
    lucro_premium: float = 0.0
    margem_premium: float = 0.0
    tarifa_fixa_premium: float = 0.0

    # auxiliares
    id_sku_marketplace: Optional[str] = None
    id_anuncio: Optional[str] = None


class PrecificacaoListResponse(BaseModel):
    items: List[PrecificacaoBaseItem]
    page: int
    page_size: int
    total: int


class EditDataResponse(BaseModel):
    precificacao_base: PrecificacaoBaseItem
    config_loja: LojaConfig
    produto_atual: ProdutoInfo


# ==== Campanha (compat com editCampaignLogic.js e campaignPricingLogic.js) ====
class CampanhaPayload(BaseModel):
    # Create/Update (update quando 'id' presente)
    id: Optional[str] = None
    base_id: str

    marketplace: str
    id_loja: str
    sku: str
    titulo: Optional[str] = None

    categoria_precificacao: Optional[str] = None

    inicio: str
    fim: str
    canal: Optional[str] = ""
    estoque_reservado: int = 0
    observacoes: Optional[str] = ""

    preco_sugerido_classico: Optional[float] = None
    preco_sugerido_premium: Optional[float] = None

    parametros: Dict[str, Any] = Field(default_factory=dict)

    # base info (facilita telas)
    venda_classico_base: Optional[float] = None
    venda_premium_base: Optional[float] = None


class CampanhaResponse(BaseModel):
    id: str
    base_id: str
    marketplace: str
    id_loja: str
    sku: str
    titulo: Optional[str] = None
    categoria_precificacao: Optional[str] = None
    inicio: str
    fim: str
    canal: Optional[str] = None
    estoque_reservado: int = 0
    observacoes: Optional[str] = None
    preco_sugerido_classico: Optional[float] = None
    preco_sugerido_premium: Optional[float] = None
    parametros: Dict[str, Any] = Field(default_factory=dict)
    venda_classico_base: Optional[float] = None
    venda_premium_base: Optional[float] = None


# =============================================================================
# Safe services helper
# =============================================================================
def _services():
    try:
        from app import services  # type: ignore
        return services
    except Exception:
        return None


def _log_warn(msg: str):
    s = _services()
    if s and hasattr(s, "logger"):
        try:
            s.logger.warning(msg)
            return
        except Exception:
            pass
    print(f"AVISO: {msg}")


def _safe(fn_name: str, *args, **kwargs):
    s = _services()
    if not s:
        return None
    fn = getattr(s, fn_name, None)
    if not callable(fn):
        return None
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        _log_warn(f"Falha em services.{fn_name}: {e}")
        return None


# =============================================================================
# Normalizers
# =============================================================================
def _norm_produto(row: Dict[str, Any]) -> ProdutoInfo:
    return ProdutoInfo(
        sku=row.get("sku"),
        titulo=row.get("titulo") or row.get("nome") or row.get("descricao"),
        custo_update=float(row.get("custo_update") or row.get("custo_fornecedor") or 0.0),
        peso_kg=float(row.get("peso_kg") or row.get("peso") or 0.0),
        altura_cm=float(row.get("altura_cm") or 0.0),
        largura_cm=float(row.get("largura_cm") or 0.0),
        comprimento_cm=float(row.get("comprimento_cm") or 0.0),
        id_sku_marketplace=row.get("id_sku_marketplace"),
        id_anuncio=row.get("id_anuncio") or row.get("mlb") or row.get("asin"),
    )


def _norm_loja_config(raw: Dict[str, Any]) -> LojaConfig:
    comissoes: List[Dict[str, Any]] = []
    for c in raw.get("comissoes") or []:
        if isinstance(c, dict):
            comissoes.append(
                {
                    "chave": str(c.get("chave") or c.get("nome") or "padrao"),
                    "classico": float(c.get("classico") or c.get("taxa_classico") or 0.0),
                    "premium": float(c.get("premium") or c.get("taxa_premium") or 0.0),
                }
            )
    return LojaConfig(
        aliquota_padrao=float(raw.get("aliquota_padrao") or raw.get("aliquota") or 0.0),
        aliquota_fulfillment=float(raw.get("aliquota_fulfillment") or raw.get("aliquota_ff") or 0.0),
        comissoes=comissoes,
    )


def _norm_base_item(row: Dict[str, Any]) -> PrecificacaoBaseItem:
    # Normaliza para o shape esperado pelo front
    def fnum(v, default=0.0):
        try:
            return float(v)
        except Exception:
            return default

    return PrecificacaoBaseItem(
        id=row.get("id"),
        marketplace=str(row.get("marketplace") or ""),
        id_loja=str(row.get("id_loja") or ""),
        sku=str(row.get("sku") or ""),
        titulo=row.get("titulo"),

        categoria_precificacao=row.get("categoria_precificacao"),

        quantidade=int(row.get("quantidade") or 1),
        custo_unitario=fnum(row.get("custo_unitario")),
        custo_total=fnum(row.get("custo_total")),

        aliquota=fnum(row.get("aliquota")),
        parcelamento=fnum(row.get("parcelamento")),
        outros=fnum(row.get("outros")),
        regra_comissao=row.get("regra_comissao"),
        fulfillment=bool(row.get("fulfillment") or False),
        catalogo_buybox=bool(row.get("catalogo_buybox") or False),

        venda_classico=fnum(row.get("venda_classico")),
        frete_classico=fnum(row.get("frete_classico")),
        repasse_classico=fnum(row.get("repasse_classico")),
        lucro_classico=fnum(row.get("lucro_classico")),
        margem_classico=fnum(row.get("margem_classico")),
        tarifa_fixa_classico=fnum(row.get("tarifa_fixa_classico")),

        venda_premium=fnum(row.get("venda_premium")),
        frete_premium=fnum(row.get("frete_premium")),
        repasse_premium=fnum(row.get("repasse_premium")),
        lucro_premium=fnum(row.get("lucro_premium")),
        margem_premium=fnum(row.get("margem_premium")),
        tarifa_fixa_premium=fnum(row.get("tarifa_fixa_premium")),

        id_sku_marketplace=row.get("id_sku_marketplace"),
        id_anuncio=row.get("id_anuncio"),
    )


# =============================================================================
# Endpoints - Categorias de Precificação
# =============================================================================
@router.get("/categorias-precificacao", response_model=List[CategoriaPrecificacao])
async def list_categorias_precificacao(user: dict = Depends(dependencies.get_current_user)):
    """
    Lista categorias com sua margem padrão. Nunca retorna 500 (fallback: []).
    """
    rows = _safe("get_pricing_categories") or []
    out: List[CategoriaPrecificacao] = []
    if isinstance(rows, list):
        for r in rows:
            if not isinstance(r, dict):
                continue
            out.append(
                CategoriaPrecificacao(
                    nome=str(r.get("nome") or r.get("categoria") or ""),
                    margem_padrao=float(r.get("margem_padrao") or r.get("margem") or 0.0),
                )
            )
    return out


# =============================================================================
# Endpoints - Dados para cálculo da Calculadora
# =============================================================================
@router.get("/dados-para-calculo")
async def get_dados_para_calculo(
    sku: str = Query(...),
    loja_id: str = Query(..., alias="loja_id"),
    user: dict = Depends(dependencies.get_current_user),
):
    """
    Retorna dados necessários para a calculadora:
      - produto: info de título, custo_update, dimensões/peso
      - config_loja: alíquotas e comissões
    """
    if not sku or not loja_id:
        raise HTTPException(status_code=400, detail="Parâmetros 'sku' e 'loja_id' são obrigatórios.")

    # Produto
    prod_raw = _safe("get_product_by_sku_and_store", sku, loja_id) or {}
    if not isinstance(prod_raw, dict) or not prod_raw:
        # UX: devolve 404 amigável — front mostra "SKU não encontrado"
        raise HTTPException(status_code=404, detail="SKU não encontrado.")

    produto = _norm_produto(prod_raw)

    # Config da loja
    loja_raw = _safe("get_store_details", loja_id) or {}
    if not isinstance(loja_raw, dict):
        loja_raw = {}
    config_loja = _norm_loja_config(loja_raw)

    return {"produto": produto.model_dump(), "config_loja": config_loja.model_dump()}


# =============================================================================
# Endpoints - Lista de Precificação Base (paginada)
# =============================================================================
@router.get("", response_model=PrecificacaoListResponse)
async def list_precificacao(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    sku: str = "",
    titulo: str = "",
    plano: str = "",
    categoria: str = "",
    user: dict = Depends(dependencies.get_current_user),
):
    """
    Lista paginada de precificações base, com filtros simples.
    """
    params = {
        "page": page,
        "page_size": page_size,
        "sku": sku,
        "titulo": titulo,
        "plano": plano,
        "categoria": categoria,
    }
    result = _safe("list_precificacao_base", params) or {}
    items_raw = result.get("items") if isinstance(result, dict) else None
    total = int(result.get("total") or 0) if isinstance(result, dict) else 0

    items: List[PrecificacaoBaseItem] = []
    if isinstance(items_raw, list):
        items = [_norm_base_item(r) for r in items_raw if isinstance(r, dict)]

    return PrecificacaoListResponse(items=items, page=page, page_size=page_size, total=total)


# =============================================================================
# Endpoints - Criar/Atualizar Precificação Base
# =============================================================================
@router.post("", response_model=Dict[str, Any])
async def create_precificacao(payload: PrecificacaoBaseItem, user: dict = Depends(dependencies.get_current_user)):
    """
    Cria uma nova Precificação Base. Retorna { id: "<uuid>" }.
    """
    data = payload.model_dump()
    res = _safe("create_precificacao_base", data)
    if isinstance(res, dict) and res.get("id"):
        return {"id": res["id"]}
    # fallback: alguns services retornam só o id
    if isinstance(res, str):
        return {"id": res}
    raise HTTPException(status_code=400, detail="Não foi possível criar a precificação base.")


@router.put("/{precificacao_id}", response_model=Dict[str, Any])
async def update_precificacao(precificacao_id: str, payload: PrecificacaoBaseItem, user: dict = Depends(dependencies.get_current_user)):
    """
    Atualiza uma Precificação Base existente. Retorna { id: "<uuid>" }.
    """
    data = payload.model_dump()
    ok = _safe("update_precificacao_base", precificacao_id, data)
    if ok is False:
        raise HTTPException(status_code=400, detail="Falha ao atualizar precificação.")
    return {"id": precificacao_id}


# =============================================================================
# Endpoints - Dados para Edição
# =============================================================================
@router.get("/{precificacao_id}/edit-data", response_model=EditDataResponse)
async def get_edit_data(precificacao_id: str, user: dict = Depends(dependencies.get_current_user)):
    """
    Retorna pacote completo para tela de edição:
      - precificacao_base     (shape usado pelo front)
      - config_loja           (alíquotas e comissões)
      - produto_atual         (dimensões, custo_update etc.)
    """
    base_raw = _safe("get_precificacao_base_by_id", precificacao_id) or {}
    if not isinstance(base_raw, dict) or not base_raw:
        raise HTTPException(status_code=404, detail="Precificação não encontrada.")

    loja_id = str(base_raw.get("loja_id") or base_raw.get("id_loja") or "")
    sku = str(base_raw.get("sku") or "")
    if not (loja_id and sku):
        _log_warn("Registro de base sem loja_id/sku suficientes para montar edit-data.")

    # Produto
    prod_raw = _safe("get_product_by_sku_and_store", sku, loja_id) or {}
    produto = _norm_produto(prod_raw if isinstance(prod_raw, dict) else {})

    # Config da loja
    loja_raw = _safe("get_store_details", loja_id) or {}
    config_loja = _norm_loja_config(loja_raw if isinstance(loja_raw, dict) else {})

    # Base normalizada
    precificacao_base = _norm_base_item(base_raw)

    return EditDataResponse(
        precificacao_base=precificacao_base,
        config_loja=config_loja,
        produto_atual=produto,
    )


# =============================================================================
# Endpoints - Campanha (compat com /static/*Campaign*.js)
# =============================================================================
@router.post("/campanha", response_model=Dict[str, Any])
async def create_or_update_campanha(payload: CampanhaPayload, user: dict = Depends(dependencies.get_current_user)):
    """
    Cria ou atualiza uma campanha:
      - se payload.id existir -> update
      - se não -> create
    Retorna { id: "<uuid>" }.
    """
    data = payload.model_dump()
    if payload.id:
        ok = _safe("update_campaign", payload.id, data)
        if ok is False:
            raise HTTPException(status_code=400, detail="Falha ao atualizar campanha.")
        return {"id": payload.id}
    else:
        res = _safe("create_campaign", data)
        if isinstance(res, dict) and res.get("id"):
            return {"id": res["id"]}
        if isinstance(res, str):
            return {"id": res}
        raise HTTPException(status_code=400, detail="Não foi possível criar a campanha.")


@router.get("/campanha/{campanha_id}", response_model=CampanhaResponse)
async def get_campanha(campanha_id: str, user: dict = Depends(dependencies.get_current_user)):
    """
    Retorna dados completos da campanha, no shape usado pelo editCampaignLogic.js.
    """
    raw = _safe("get_campaign_by_id", campanha_id) or {}
    if not isinstance(raw, dict) or not raw:
        raise HTTPException(status_code=404, detail="Campanha não encontrada.")

    def fnum(v, default=None):
        try:
            return float(v)
        except Exception:
            return default

    return CampanhaResponse(
        id=str(raw.get("id") or campanha_id),
        base_id=str(raw.get("base_id") or raw.get("precificacao_id") or ""),
        marketplace=str(raw.get("marketplace") or ""),
        id_loja=str(raw.get("id_loja") or ""),
        sku=str(raw.get("sku") or ""),

        titulo=raw.get("titulo") or raw.get("nome_produto"),
        categoria_precificacao=raw.get("categoria_precificacao"),

        inicio=str(raw.get("inicio") or raw.get("data_inicio") or ""),
        fim=str(raw.get("fim") or raw.get("data_fim") or ""),
        canal=raw.get("canal"),
        estoque_reservado=int(raw.get("estoque_reservado") or 0),
        observacoes=raw.get("observacoes"),

        preco_sugerido_classico=fnum(raw.get("preco_sugerido_classico")),
        preco_sugerido_premium=fnum(raw.get("preco_sugerido_premium")),
        parametros=raw.get("parametros") or {},

        venda_classico_base=fnum(raw.get("venda_classico_base")),
        venda_premium_base=fnum(raw.get("venda_premium_base")),
    )


@router.delete("/campanha/{campanha_id}", response_model=Dict[str, Any])
async def delete_campanha(campanha_id: str, user: dict = Depends(dependencies.get_current_user)):
    """
    Exclui uma campanha. Retorna { ok: true } mesmo que a fonte não suporte exclusão.
    """
    res = _safe("delete_campaign", campanha_id)
    if res is False:
        raise HTTPException(status_code=400, detail="Falha ao excluir campanha.")
    return {"ok": True}