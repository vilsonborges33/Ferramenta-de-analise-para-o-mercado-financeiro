"""Modelo de dados (ver docs/ARQUITETURA.md, seção 4).

Toda tabela de dado de origem herda `Procedencia`: fonte, lote de ingestão, data de referência e
data de coleta são obrigatórias.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from app.db.sessao import Base

Valor = Numeric(30, 10)


class Procedencia:
    @declared_attr
    def fonte_id(cls) -> Mapped[int]:
        return mapped_column(ForeignKey("fonte.id"), nullable=False, index=True)

    @declared_attr
    def lote_ingestao_id(cls) -> Mapped[int]:
        return mapped_column(ForeignKey("lote_ingestao.id"), nullable=False, index=True)

    data_referencia: Mapped[date] = mapped_column(Date, nullable=False)
    coletado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ---------------------------------------------------------------- procedência


class Fonte(Base):
    __tablename__ = "fonte"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    nome: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(500))
    licenca: Mapped[str] = mapped_column(String(200))
    termos_verificados_em: Mapped[date | None] = mapped_column(Date)


class LoteIngestao(Base):
    __tablename__ = "lote_ingestao"
    id: Mapped[int] = mapped_column(primary_key=True)
    fonte_id: Mapped[int] = mapped_column(ForeignKey("fonte.id"), index=True)
    iniciado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="em_andamento")
    arquivo_origem: Mapped[str | None] = mapped_column(String(500))
    hash_arquivo: Mapped[str | None] = mapped_column(String(64))
    etag: Mapped[str | None] = mapped_column(String(200))
    linhas_gravadas: Mapped[int] = mapped_column(Integer, default=0)
    erro: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------- emissores e ativos


class Empresa(Procedencia, Base):
    __tablename__ = "empresa"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(300))
    cnpj: Mapped[str | None] = mapped_column(String(18), unique=True)
    cik: Mapped[str | None] = mapped_column(String(10), unique=True)
    codigo_cvm: Mapped[str | None] = mapped_column(String(10), unique=True)
    pais: Mapped[str] = mapped_column(String(2), default="BR")
    setor: Mapped[str | None] = mapped_column(String(200))
    subsetor: Mapped[str | None] = mapped_column(String(200))
    segmento: Mapped[str | None] = mapped_column(String(200))
    segmento_listagem: Mapped[str | None] = mapped_column(String(100))
    tipo_plano_contas: Mapped[str] = mapped_column(String(20), default="geral")
    situacao: Mapped[str | None] = mapped_column(String(100))

    ativos: Mapped[list["Ativo"]] = relationship(back_populates="empresa")


class Ativo(Base):
    __tablename__ = "ativo"
    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), unique=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresa.id"), index=True)
    classe: Mapped[str] = mapped_column(String(10))  # ACAO, UNIT, FII, ETF, REIT, BDR, INDICE
    especie: Mapped[str | None] = mapped_column(String(10))  # ON, PN, UNIT
    isin: Mapped[str | None] = mapped_column(String(12))
    mercado: Mapped[str] = mapped_column(String(10), default="B3")
    moeda: Mapped[str] = mapped_column(String(3), default="BRL")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    empresa: Mapped[Empresa | None] = relationship(back_populates="ativos")


class ComposicaoCapital(Procedencia, Base):
    __tablename__ = "composicao_capital"
    __table_args__ = (UniqueConstraint("empresa_id", "data_referencia"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)
    acoes_ordinarias: Mapped[Decimal | None] = mapped_column(Valor)
    acoes_preferenciais: Mapped[Decimal | None] = mapped_column(Valor)
    acoes_tesouraria_on: Mapped[Decimal | None] = mapped_column(Valor)
    acoes_tesouraria_pn: Mapped[Decimal | None] = mapped_column(Valor)


class UnitComposicao(Base):
    __tablename__ = "unit_composicao"
    id: Mapped[int] = mapped_column(primary_key=True)
    ativo_unit_id: Mapped[int] = mapped_column(ForeignKey("ativo.id"))
    ativo_componente_id: Mapped[int] = mapped_column(ForeignKey("ativo.id"))
    quantidade: Mapped[Decimal] = mapped_column(Valor)


# ------------------------------------------------- cotações, séries e mercado


class CotacaoDiaria(Procedencia, Base):
    __tablename__ = "cotacao_diaria"
    ativo_id: Mapped[int] = mapped_column(ForeignKey("ativo.id"), primary_key=True)
    data: Mapped[date] = mapped_column(Date, primary_key=True)
    abertura: Mapped[Decimal | None] = mapped_column(Valor)
    maxima: Mapped[Decimal | None] = mapped_column(Valor)
    minima: Mapped[Decimal | None] = mapped_column(Valor)
    fechamento: Mapped[Decimal] = mapped_column(Valor)
    volume_financeiro: Mapped[Decimal | None] = mapped_column(Valor)
    negocios: Mapped[int | None] = mapped_column(Integer)
    fator_ajuste: Mapped[Decimal | None] = mapped_column(Valor)


class EventoSocietario(Procedencia, Base):
    __tablename__ = "evento_societario"
    id: Mapped[int] = mapped_column(primary_key=True)
    ativo_id: Mapped[int] = mapped_column(ForeignKey("ativo.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(20))
    data_ex: Mapped[date] = mapped_column(Date)
    fator: Mapped[Decimal] = mapped_column(Valor)


class SerieEconomica(Procedencia, Base):
    __tablename__ = "serie_economica"
    codigo: Mapped[str] = mapped_column(String(30), primary_key=True)
    data: Mapped[date] = mapped_column(Date, primary_key=True)
    valor: Mapped[Decimal] = mapped_column(Valor)


class TituloTesouroTaxa(Procedencia, Base):
    __tablename__ = "titulo_tesouro_taxa"
    __table_args__ = (UniqueConstraint("titulo", "vencimento", "data_base"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(80))
    vencimento: Mapped[date] = mapped_column(Date)
    data_base: Mapped[date] = mapped_column(Date, index=True)
    taxa_compra: Mapped[Decimal | None] = mapped_column(Valor)
    taxa_venda: Mapped[Decimal | None] = mapped_column(Valor)
    pu_compra: Mapped[Decimal | None] = mapped_column(Valor)
    pu_venda: Mapped[Decimal | None] = mapped_column(Valor)


class ParametroMercado(Procedencia, Base):
    __tablename__ = "parametro_mercado"
    __table_args__ = (UniqueConstraint("chave", "data_referencia"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    chave: Mapped[str] = mapped_column(String(60))
    valor: Mapped[Decimal] = mapped_column(Valor)


class BetaSetorial(Procedencia, Base):
    __tablename__ = "beta_setorial"
    id: Mapped[int] = mapped_column(primary_key=True)
    setor_damodaran: Mapped[str] = mapped_column(String(200))
    regiao: Mapped[str] = mapped_column(String(20))
    beta_alavancado: Mapped[Decimal | None] = mapped_column(Valor)
    beta_desalavancado: Mapped[Decimal | None] = mapped_column(Valor)
    de_ratio: Mapped[Decimal | None] = mapped_column(Valor)
    aliquota_efetiva: Mapped[Decimal | None] = mapped_column(Valor)
    numero_empresas: Mapped[int | None] = mapped_column(Integer)


class MapaSetorDamodaran(Base):
    __tablename__ = "mapa_setor_damodaran"
    id: Mapped[int] = mapped_column(primary_key=True)
    setor_b3: Mapped[str] = mapped_column(String(200))
    subsetor_b3: Mapped[str | None] = mapped_column(String(200))
    setor_damodaran: Mapped[str] = mapped_column(String(200))


# ------------------------------------------------------ demonstrações financeiras


class DemonstracaoLinha(Procedencia, Base):
    __tablename__ = "demonstracao_linha"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id", "documento", "tipo", "consolidado", "data_inicio", "data_fim", "versao",
            "conta_codigo", "ordem_exercicio",
            postgresql_nulls_not_distinct=True,  # data_inicio é nula nas linhas de balanço
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)
    documento: Mapped[str] = mapped_column(String(10))  # DFP, ITR, 10-K, 10-Q
    tipo: Mapped[str] = mapped_column(String(10))  # BPA, BPP, DRE, DFC_MD, DFC_MI, DVA
    consolidado: Mapped[bool] = mapped_column(Boolean)
    ordem_exercicio: Mapped[str] = mapped_column(String(10))  # ÚLTIMO / PENÚLTIMO
    data_inicio: Mapped[date | None] = mapped_column(Date)
    data_fim: Mapped[date] = mapped_column(Date)
    versao: Mapped[int] = mapped_column(Integer)
    conta_codigo: Mapped[str] = mapped_column(String(120))
    conta_descricao: Mapped[str] = mapped_column(String(500))
    conta_fixa: Mapped[bool | None] = mapped_column(Boolean)
    valor: Mapped[Decimal] = mapped_column(Valor)
    moeda: Mapped[str] = mapped_column(String(3), default="BRL")


class MapaConta(Base):
    __tablename__ = "mapa_conta"
    id: Mapped[int] = mapped_column(primary_key=True)
    tipo_plano_contas: Mapped[str] = mapped_column(String(20))
    tipo_demonstracao: Mapped[str] = mapped_column(String(10))
    conta_codigo: Mapped[str | None] = mapped_column(String(120))
    padrao_descricao: Mapped[str | None] = mapped_column(String(300))  # regex para contas não fixas
    campo_padronizado: Mapped[str] = mapped_column(String(60))
    sinal: Mapped[int] = mapped_column(Integer, default=1)
    prioridade: Mapped[int] = mapped_column(Integer, default=1)


class DemonstracaoPadronizada(Procedencia, Base):
    __tablename__ = "demonstracao_padronizada"
    __table_args__ = (UniqueConstraint("empresa_id", "periodo", "tipo_periodo"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)
    periodo: Mapped[str] = mapped_column(String(10))  # 2025-T3, 2025-A, 2025-T3-TTM
    tipo_periodo: Mapped[str] = mapped_column(String(10))  # trimestre, ano, ttm
    data_inicio: Mapped[date | None] = mapped_column(Date)
    data_fim: Mapped[date] = mapped_column(Date)
    consolidado: Mapped[bool] = mapped_column(Boolean)
    versao_usada: Mapped[int] = mapped_column(Integer)
    campos: Mapped[dict] = mapped_column(JSONB)  # campo_padronizado -> valor (unidades)
    insumos: Mapped[dict] = mapped_column(JSONB)  # campo_padronizado -> [contas de origem]


# ---------------------------------------------------------------- proventos


class Provento(Procedencia, Base):
    __tablename__ = "provento"
    __table_args__ = (UniqueConstraint("ativo_id", "tipo", "data_com", "valor_por_cota"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    ativo_id: Mapped[int] = mapped_column(ForeignKey("ativo.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(25))
    valor_por_cota: Mapped[Decimal] = mapped_column(Valor)  # bruto
    data_aprovacao: Mapped[date | None] = mapped_column(Date)
    data_com: Mapped[date] = mapped_column(Date)
    data_ex: Mapped[date | None] = mapped_column(Date)
    data_pagamento: Mapped[date | None] = mapped_column(Date)


# ------------------------------------------------------- fundos imobiliários


class Fii(Procedencia, Base):
    __tablename__ = "fii"
    id: Mapped[int] = mapped_column(primary_key=True)
    ativo_id: Mapped[int | None] = mapped_column(ForeignKey("ativo.id"), unique=True)
    cnpj: Mapped[str] = mapped_column(String(18), unique=True)
    isin: Mapped[str | None] = mapped_column(String(12))
    nome: Mapped[str] = mapped_column(String(300))
    segmento: Mapped[str | None] = mapped_column(String(200))
    subsegmento: Mapped[str | None] = mapped_column(String(200))
    mandato: Mapped[str | None] = mapped_column(String(200))
    tipo_gestao: Mapped[str | None] = mapped_column(String(50))
    gestora: Mapped[str | None] = mapped_column(String(300))
    administrador: Mapped[str | None] = mapped_column(String(300))
    publico_alvo: Mapped[str | None] = mapped_column(String(100))
    taxa_administracao: Mapped[str | None] = mapped_column(String(500))
    taxa_performance: Mapped[str | None] = mapped_column(String(500))
    politica_distribuicao: Mapped[str | None] = mapped_column(Text)
    data_inicio: Mapped[date | None] = mapped_column(Date)


class FiiInformeMensal(Procedencia, Base):
    __tablename__ = "fii_informe_mensal"
    __table_args__ = (UniqueConstraint("fii_id", "competencia", "versao"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    fii_id: Mapped[int] = mapped_column(ForeignKey("fii.id"), index=True)
    competencia: Mapped[date] = mapped_column(Date)
    versao: Mapped[int] = mapped_column(Integer, default=1)
    patrimonio_liquido: Mapped[Decimal | None] = mapped_column(Valor)
    cotas_emitidas: Mapped[Decimal | None] = mapped_column(Valor)
    valor_patrimonial_cota: Mapped[Decimal | None] = mapped_column(Valor)
    numero_cotistas: Mapped[int | None] = mapped_column(Integer)
    cotistas_pf: Mapped[int | None] = mapped_column(Integer)
    cotistas_pj: Mapped[int | None] = mapped_column(Integer)
    cotistas_bancos: Mapped[int | None] = mapped_column(Integer)
    cotistas_outros: Mapped[int | None] = mapped_column(Integer)
    rentabilidade_efetiva_mes: Mapped[Decimal | None] = mapped_column(Valor)
    rentabilidade_patrimonial_mes: Mapped[Decimal | None] = mapped_column(Valor)
    dividend_yield_mes: Mapped[Decimal | None] = mapped_column(Valor)
    taxa_administracao_mes: Mapped[Decimal | None] = mapped_column(Valor)
    ativo_total: Mapped[Decimal | None] = mapped_column(Valor)
    imoveis_renda_acabados: Mapped[Decimal | None] = mapped_column(Valor)
    imoveis_renda_construcao: Mapped[Decimal | None] = mapped_column(Valor)
    imoveis_venda: Mapped[Decimal | None] = mapped_column(Valor)
    direitos_reais: Mapped[Decimal | None] = mapped_column(Valor)
    instrumentos_financeiros: Mapped[Decimal | None] = mapped_column(Valor)
    caixa: Mapped[Decimal | None] = mapped_column(Valor)
    total_passivo: Mapped[Decimal | None] = mapped_column(Valor)
    rendimentos_a_distribuir: Mapped[Decimal | None] = mapped_column(Valor)
    obrigacoes_aquisicao_imoveis: Mapped[Decimal | None] = mapped_column(Valor)
    extras: Mapped[dict | None] = mapped_column(JSONB)


class FiiInformeTrimestral(Procedencia, Base):
    __tablename__ = "fii_informe_trimestral"
    id: Mapped[int] = mapped_column(primary_key=True)
    fii_id: Mapped[int] = mapped_column(ForeignKey("fii.id"), index=True)
    competencia: Mapped[date] = mapped_column(Date)
    campos: Mapped[dict] = mapped_column(JSONB)


class FiiImovel(Procedencia, Base):
    __tablename__ = "fii_imovel"
    id: Mapped[int] = mapped_column(primary_key=True)
    fii_id: Mapped[int] = mapped_column(ForeignKey("fii.id"), index=True)
    competencia: Mapped[date] = mapped_column(Date)
    nome: Mapped[str] = mapped_column(String(300))
    endereco: Mapped[str | None] = mapped_column(String(500))
    classe: Mapped[str | None] = mapped_column(String(50))
    area_m2: Mapped[Decimal | None] = mapped_column(Valor)
    numero_unidades: Mapped[int | None] = mapped_column(Integer)
    percentual_vacancia: Mapped[Decimal | None] = mapped_column(Valor)
    percentual_inadimplencia: Mapped[Decimal | None] = mapped_column(Valor)
    percentual_receitas_fii: Mapped[Decimal | None] = mapped_column(Valor)


class FiiDocumento(Procedencia, Base):
    __tablename__ = "fii_documento"
    id: Mapped[int] = mapped_column(primary_key=True)
    fii_id: Mapped[int] = mapped_column(ForeignKey("fii.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(60))
    data_entrega: Mapped[date | None] = mapped_column(Date)
    url_fnet: Mapped[str] = mapped_column(String(500))
    id_fnet: Mapped[str] = mapped_column(String(30), unique=True)
    status: Mapped[str | None] = mapped_column(String(30))


class IndiceComposicao(Procedencia, Base):
    __tablename__ = "indice_composicao"
    id: Mapped[int] = mapped_column(primary_key=True)
    indice: Mapped[str] = mapped_column(String(10))
    ativo_id: Mapped[int] = mapped_column(ForeignKey("ativo.id"), index=True)
    peso: Mapped[Decimal] = mapped_column(Valor)


# ---------------------------------------------------------- indicadores calculados


class IndicadorCalculado(Base):
    __tablename__ = "indicador_calculado"
    __table_args__ = (UniqueConstraint("ativo_id", "metrica"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    ativo_id: Mapped[int] = mapped_column(ForeignKey("ativo.id"), index=True)
    metrica: Mapped[str] = mapped_column(String(80))
    data_referencia: Mapped[date | None] = mapped_column(Date)
    valor: Mapped[Decimal | None] = mapped_column(Valor)
    motivo_indisponivel: Mapped[str | None] = mapped_column(String(500))
    parametros: Mapped[dict] = mapped_column(JSONB, default=dict)
    insumos: Mapped[list] = mapped_column(JSONB, default=list)
    versao_metodologia: Mapped[str] = mapped_column(String(20))
    calculado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ------------------------------------------------------------------- usuário


class Usuario(Base):
    __tablename__ = "usuario"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    hash_senha: Mapped[str] = mapped_column(String(200))
    nome: Mapped[str | None] = mapped_column(String(200))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    ultimo_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ParametroUsuario(Base):
    __tablename__ = "parametro_usuario"
    __table_args__ = (UniqueConstraint("usuario_id", "chave"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"))
    chave: Mapped[str] = mapped_column(String(60))
    valor: Mapped[Decimal] = mapped_column(Valor)


class Favorito(Base):
    __tablename__ = "favorito"
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"), primary_key=True)
    ativo_id: Mapped[int] = mapped_column(ForeignKey("ativo.id"), primary_key=True)


class ValuationSalvo(Base):
    __tablename__ = "valuation_salvo"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"), index=True)
    ativo_id: Mapped[int] = mapped_column(ForeignKey("ativo.id"))
    metodo: Mapped[str] = mapped_column(String(40))
    nome: Mapped[str] = mapped_column(String(200))
    parametros: Mapped[dict] = mapped_column(JSONB)
    narrativa: Mapped[str | None] = mapped_column(Text)
    resultado: Mapped[dict] = mapped_column(JSONB)
    insumos_snapshot: Mapped[dict] = mapped_column(JSONB)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Carteira(Base):
    __tablename__ = "carteira"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"), index=True)
    nome: Mapped[str] = mapped_column(String(200))
    moeda_base: Mapped[str] = mapped_column(String(3), default="BRL")
    token_compartilhamento: Mapped[str | None] = mapped_column(String(64), unique=True)


class ArquivoImportacao(Base):
    __tablename__ = "arquivo_importacao"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"))
    tipo: Mapped[str] = mapped_column(String(30))
    nome_arquivo: Mapped[str] = mapped_column(String(300))
    hash: Mapped[str] = mapped_column(String(64))
    processado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    linhas_ok: Mapped[int] = mapped_column(Integer, default=0)
    linhas_erro: Mapped[int] = mapped_column(Integer, default=0)


class Lancamento(Base):
    __tablename__ = "lancamento"
    id: Mapped[int] = mapped_column(primary_key=True)
    carteira_id: Mapped[int] = mapped_column(ForeignKey("carteira.id", ondelete="CASCADE"), index=True)
    ativo_id: Mapped[int] = mapped_column(ForeignKey("ativo.id"))
    tipo: Mapped[str] = mapped_column(String(20))
    data: Mapped[date] = mapped_column(Date)
    quantidade: Mapped[Decimal] = mapped_column(Valor)
    preco: Mapped[Decimal | None] = mapped_column(Valor)
    taxas: Mapped[Decimal | None] = mapped_column(Valor)
    origem: Mapped[str] = mapped_column(String(20), default="manual")
    arquivo_importacao_id: Mapped[int | None] = mapped_column(ForeignKey("arquivo_importacao.id"))


class PrecoMedioAjuste(Base):
    __tablename__ = "preco_medio_ajuste"
    __table_args__ = (UniqueConstraint("carteira_id", "ativo_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    carteira_id: Mapped[int] = mapped_column(ForeignKey("carteira.id", ondelete="CASCADE"))
    ativo_id: Mapped[int] = mapped_column(ForeignKey("ativo.id"))
    preco_medio_manual: Mapped[Decimal] = mapped_column(Valor)
    motivo: Mapped[str | None] = mapped_column(String(500))


class DiarioDecisao(Base):
    __tablename__ = "diario_decisao"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"), index=True)
    ativo_id: Mapped[int | None] = mapped_column(ForeignKey("ativo.id"))
    data: Mapped[date] = mapped_column(Date)
    decisao: Mapped[str] = mapped_column(String(200))
    tese: Mapped[str] = mapped_column(Text)
    premissas: Mapped[dict] = mapped_column(JSONB, default=dict)
    data_revisao_prevista: Mapped[date | None] = mapped_column(Date)
    revisao: Mapped[str | None] = mapped_column(Text)
    resultado_observado: Mapped[str | None] = mapped_column(Text)


class Alerta(Base):
    __tablename__ = "alerta"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"), index=True)
    ativo_id: Mapped[int] = mapped_column(ForeignKey("ativo.id"))
    condicao: Mapped[dict] = mapped_column(JSONB)
    canal: Mapped[str] = mapped_column(String(20), default="email")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    ultimo_disparo: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
