# app/models.py
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Any, Dict, Union
from datetime import date, datetime
from enum import Enum

# ---------------------------
# Usuários
# ---------------------------
class NewUserPayload(BaseModel):
    email: EmailStr
    nome: str
    autorizado: bool = False
    funcao: str = "usuario"

class UserProfile(BaseModel):
    email: EmailStr
    nome: Optional[str] = None
    foto_url: Optional[str] = None
    autorizado: bool = False
    funcao: str = "usuario"
    telefone: Optional[str] = None
    departamento: Optional[str] = None
    data_cadastro: Optional[datetime] = None
    ultimo_login: Optional[datetime] = None
    pode_ver_historico: bool = False

class UserProfileUpdate(BaseModel):
    telefone: Optional[str] = None
    departamento: Optional[str] = None

# ---------------------------
# Lojas / Configurações
# ---------------------------
class LojaConfigCreate(BaseModel):
    marketplace: str
    id_loja: str
    nome_loja: Optional[str] = None

class LojaConfig(BaseModel):
    id: Optional[str] = None
    marketplace: str
    id_loja: str
    nome_loja: Optional[str] = None

class ComissaoRegra(BaseModel):
    categoria: Optional[str] = None
    aliquota: float = 0.0

class LojaConfigDetalhes(BaseModel):
    aliquota_padrao: float = 0.0
    aliquota_fulfillment: float = 0.0
    comissoes: List[ComissaoRegra] = Field(default_factory=list)

# ---------------------------
# Categorias / Regras
# ---------------------------
class CategoriaPrecificacao(BaseModel):
    id: Optional[str] = None
    nome: str
    descricao: Optional[str] = None

class RegraTarifaFixa(BaseModel):
    id: Optional[str] = None
    min_venda: float
    max_venda: Optional[float] = None
    tarifa: float

class RegraFrete(BaseModel):
    id: Optional[str] = None
    min_venda: float
    min_peso_g: float
    max_peso_g: Optional[float] = None
    custo_frete: float

class AllBusinessRules(BaseModel):
    REGRAS_TARIFA_FIXA_ML: List[Dict[str, Any]] = Field(default_factory=list)
    REGRAS_FRETE_ML: List[Dict[str, Any]] = Field(default_factory=list)
    CATEGORIAS_PRECIFICACAO: List[Dict[str, Any]] = Field(default_factory=list)

# ---------------------------
# Produto / Calculadora
# ---------------------------
class ProdutoDados(BaseModel):
    sku: str
    titulo: Optional[str] = None
    custo_update: Optional[float] = None
    peso_kg: Optional[float] = None
    altura_cm: Optional[float] = None
    largura_cm: Optional[float] = None
    comprimento_cm: Optional[float] = None

class DadosCalculoResponse(BaseModel):
    produto: ProdutoDados
    config_loja: LojaConfigDetalhes

# ---------------------------
# Precificação Base
# ---------------------------
class PrecificacaoCore(BaseModel):
    marketplace: str
    id_loja: str
    sku: str
    categoria_precificacao: Optional[str] = None
    titulo: Optional[str] = None
    id_sku_marketplace: Optional[str] = None
    id_anuncio: Optional[str] = None
    quantidade: int = Field(..., gt=0)
    custo_unitario: float = Field(..., ge=0)

    # campos operacionais usados em filtros/telas
    venda_classico: Optional[float] = None
    venda_premium: Optional[float] = None
    repasse_classico: Optional[float] = None
    repasse_premium: Optional[float] = None
    custo_total: Optional[float] = None
    lucro_classico: Optional[float] = None
    lucro_premium: Optional[float] = None

class PrecificacaoListResponse(BaseModel):
    total_items: int
    items: List[Dict[str, Any]]

# ---------------------------
# Campanhas
# ---------------------------
class CampanhaML(BaseModel):
    id: Optional[str] = None
    nome: str
    data_inicio: Optional[date] = None
    data_fim: Optional[date] = None
    desconto_percentual: Optional[float] = None
    observacoes: Optional[str] = None

class PrecificacaoCampanhaPayload(BaseModel):
    id: Optional[str] = None
    precificacao_base_id: str
    campanha_id: str
    preco_promocional: Optional[float] = None
    data_criacao: Optional[datetime] = None
    criado_por: Optional[str] = None

class EditPageData(BaseModel):
    precificacao_base: Dict[str, Any]
    config_loja: LojaConfigDetalhes
    produto_atual: ProdutoDados
    campanhas_vinculadas: List[Dict[str, Any]]
    campanhas_ativas: List[Dict[str, Any]]

# ---------------------------
# Dashboard / Gráficos
# ---------------------------
class ChartDataItem(BaseModel):
    label: str
    value: float

class ChartData(BaseModel):
    data: List[ChartDataItem]

class DashboardData(BaseModel):
    campanhas_expirando: List[Dict[str, Any]]
    custos_desatualizados: List[Dict[str, Any]]
    produtos_estagnados: List[Dict[str, Any]]

# ---------------------------
# Bulk Update
# ---------------------------
class UpdateAction(str, Enum):
    set_custo_unitario = "set_custo_unitario"
    set_categoria = "set_categoria"

class BulkUpdatePayload(BaseModel):
    ids: List[str]
    action: UpdateAction
    value: Union[str, float]

# ---------------------------
# Simulador
# ---------------------------
class SimulacaoFilter(BaseModel):
    marketplace: Optional[str] = None
    id_loja: Optional[str] = None
    sku: Optional[str] = None
    titulo: Optional[str] = None
    plano: Optional[str] = None
    categoria: Optional[str] = None

class SimulacaoAction(BaseModel):
    field: str  # ex.: 'custo_unitario'
    operation: str  # ex.: 'percent_increase'
    value: float

class SimulacaoPayload(BaseModel):
    filters: SimulacaoFilter
    action: SimulacaoAction

class TotaisSimulacao(BaseModel):
    receita_total: float
    custo_total: float
    lucro_total: float
    margem_media: float
    total_items: int

class SimulacaoResultado(BaseModel):
    antes: TotaisSimulacao
    depois: TotaisSimulacao
