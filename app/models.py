# app/models.py
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Any, Union
from datetime import date, datetime
from enum import Enum

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
    custo_total: float = Field(..., ge=0)
    aliquota: float = Field(..., ge=0)
    tarifa_fixa_classico: float = Field(..., ge=0)
    tarifa_fixa_premium: float = Field(..., ge=0)
    parcelamento: float = Field(..., ge=0)
    outros: float = Field(..., ge=0)
    regra_comissao: str
    fulfillment: bool
    catalogo_buybox: bool
    venda_classico: float = Field(..., ge=0)
    frete_classico: float = Field(..., ge=0)
    repasse_classico: float
    lucro_classico: float
    margem_classico: float
    venda_premium: float = Field(..., ge=0)
    frete_premium: float = Field(..., ge=0)
    repasse_premium: float
    lucro_premium: float
    margem_premium: float

class PrecificacaoPayload(PrecificacaoCore):
    id: str
    data_calculo: Optional[Any] = None
    calculado_por: Optional[str] = None

class PrecificacaoListResponse(BaseModel):
    total_items: int
    items: List[dict]

class UpdateAction(str, Enum):
    set_custo_unitario = "set_custo_unitario"
    set_categoria = "set_categoria"
    ajustar_margem_classico = "ajustar_margem_classico"
    ajustar_margem_premium = "ajustar_margem_premium"

class BulkUpdatePayload(BaseModel):
    ids: List[str]
    action: UpdateAction
    value: Union[str, float]

class PrecificacaoCampanhaPayload(BaseModel):
    id: Optional[str] = None
    precificacao_base_id: str
    campanha_id: str
    desconto_classico_tipo: Optional[str] = None
    desconto_classico_valor: Optional[float] = None
    venda_final_classico: float
    margem_final_classico: float
    lucro_final_classico: float
    repasse_final_classico: float
    desconto_premium_tipo: Optional[str] = None
    desconto_premium_valor: Optional[float] = None
    venda_final_premium: float
    margem_final_premium: float
    lucro_final_premium: float
    repasse_final_premium: float

class LojaConfig(BaseModel):
    id: str
    marketplace: str
    id_loja: str

class NewLojaConfig(BaseModel):
    marketplace: str
    id_loja: str

class ComissaoRegra(BaseModel):
    chave: str
    classico: float
    premium: float

class LojaConfigDetalhes(BaseModel):
    aliquota_padrao: float = 0.0
    aliquota_fulfillment: float = 0.0
    comissoes: List[ComissaoRegra] = []

class ProdutoDados(BaseModel):
    sku: str
    titulo: Optional[str] = None
    custo_update: Optional[float] = None
    peso_kg: Optional[float] = 0.0
    altura_cm: Optional[float] = 0.0
    largura_cm: Optional[float] = 0.0
    comprimento_cm: Optional[float] = 0.0

class DadosCalculoResponse(BaseModel):
    produto: ProdutoDados
    config_loja: LojaConfigDetalhes

class EditPageData(BaseModel):
    precificacao_base: dict
    config_loja: LojaConfigDetalhes
    produto_atual: ProdutoDados
    campanhas_vinculadas: List[dict]
    campanhas_ativas: List[dict]

class UserProfile(BaseModel):
    email: str
    nome: Optional[str] = None
    foto_url: Optional[str] = None
    autorizado: bool
    funcao: Optional[str] = None
    telefone: Optional[str] = None
    departamento: Optional[str] = None
    data_cadastro: Optional[Any] = None
    ultimo_login: Optional[Any] = None
    pode_ver_historico: bool = False

class UserProfileUpdate(BaseModel):
    telefone: Optional[str] = None
    departamento: Optional[str] = None

class NewUserPayload(BaseModel):
    nome: str
    email: EmailStr
    funcao: str = 'usuario'
    autorizado: bool = True

class RegraTarifaFixa(BaseModel):
    id: Optional[str] = None
    descricao: Optional[str] = None
    min_venda: Optional[float] = None
    max_venda: Optional[float] = None
    taxa_fixa: Optional[float] = None
    taxa_percentual: Optional[float] = None

class RegraFrete(BaseModel):
    id: Optional[str] = None
    min_venda: Optional[float] = None
    max_venda: Optional[float] = None
    min_peso_g: Optional[int] = None
    max_peso_g: Optional[int] = None
    custo_frete: Optional[float] = None

class CategoriaPrecificacao(BaseModel):
    id: Optional[str] = None
    nome: Optional[str] = None
    margem_padrao: Optional[float] = None

class CampanhaML(BaseModel):
    id: Optional[str] = None
    nome: Optional[str] = None
    tipo_campanha: Optional[str] = None
    tipo_cupom: Optional[str] = None
    valor_cupom: Optional[float] = None
    tipo_cashback: Optional[str] = None
    valor_cashback: Optional[float] = None
    data_inicio: Optional[date] = None
    data_fim: Optional[date] = None

class AlertaCusto(BaseModel):
    id_precificacao: str
    sku: str
    titulo: Optional[str] = None
    custo_precificado: float
    custo_atual: float

class AlertaProdutoEstagnado(BaseModel):
    sku: str
    titulo: Optional[str] = None
    dias_sem_vender: int

class DashboardData(BaseModel):
    campanhas_expirando: List[CampanhaML]
    custos_desatualizados: List[AlertaCusto]
    produtos_estagnados: List[AlertaProdutoEstagnado]

class ChartDataItem(BaseModel):
    label: str
    value: float

class ChartData(BaseModel):
    data: List[ChartDataItem]

# NOVOS MODELOS PARA O SIMULADOR
class SimulacaoFilter(BaseModel):
    marketplace: Optional[str] = None
    id_loja: Optional[str] = None
    categoria: Optional[str] = None

class SimulacaoAction(BaseModel):
    field: str # Ex: 'custo_unitario', 'frete_classico'
    operation: str # Ex: 'percent_increase', 'fixed_value'
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