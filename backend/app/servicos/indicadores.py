"""Calcula e materializa os indicadores de cada ativo (DECISOES.md D-005).

Busca os insumos no banco, chama as funções puras de `app.metodologias` e grava em
`indicador_calculado` o valor (ou o motivo da indisponibilidade) com a procedência de cada insumo.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import obter_configuracao
from app.db.modelos import (
    Ativo,
    ComposicaoCapital,
    CotacaoDiaria,
    DemonstracaoPadronizada,
    Empresa,
    Fii,
    FiiInformeMensal,
    Fonte,
    IndicadorCalculado,
    Provento,
)
from app.metodologias import fii as mfii
from app.metodologias import indicadores_basicos as ib
from app.metodologias.registro import POR_ID
from app.metodologias.tipos import Resultado, indisponivel

PREGOES_LIQUIDEZ = 42  # ~2 meses de pregões
MOTIVO_SEM_PROVENTOS = ("proventos não ingeridos: o plano gratuito da brapi não inclui proventos "
                        "(habilitar com plano pago)")


@dataclass
class Insumo:
    insumo: str
    valor: float | None
    fonte: str
    data_referencia: str
    coletado_em: str
    detalhe: dict = field(default_factory=dict)

    def como_dict(self) -> dict:
        return {"insumo": self.insumo, "valor": self.valor, "fonte": self.fonte,
                "data_referencia": self.data_referencia, "coletado_em": self.coletado_em, **self.detalhe}


@dataclass
class Calculo:
    metrica: str
    resultado: Resultado
    insumos: list[Insumo]
    data_referencia: date | None


class Calculadora:
    def __init__(self, sessao: Session):
        self.sessao = sessao
        self.fontes = {f.id: f.codigo for f in sessao.scalars(select(Fonte))}

    # ------------------------------------------------------------- consultas

    def _insumo(self, nome: str, valor, registro, **detalhe) -> Insumo:
        return Insumo(nome, None if valor is None else float(valor), self.fontes.get(registro.fonte_id, "?"),
                      registro.data_referencia.isoformat(), registro.coletado_em.isoformat(), detalhe)

    def ultima_cotacao(self, ativo_id: int) -> CotacaoDiaria | None:
        return self.sessao.scalar(select(CotacaoDiaria).where(CotacaoDiaria.ativo_id == ativo_id)
                                  .order_by(desc(CotacaoDiaria.data)).limit(1))

    def volumes_recentes(self, ativo_id: int) -> list[CotacaoDiaria]:
        return list(self.sessao.scalars(select(CotacaoDiaria).where(CotacaoDiaria.ativo_id == ativo_id)
                                        .order_by(desc(CotacaoDiaria.data)).limit(PREGOES_LIQUIDEZ)))

    def proventos_12m(self, ativo_id: int, referencia: date) -> tuple[float | None, list[Provento], str | None]:
        existe = self.sessao.scalar(select(func.count()).select_from(Provento).where(Provento.ativo_id == ativo_id))
        if not existe and not obter_configuracao().brapi_proventos_habilitado:
            return None, [], MOTIVO_SEM_PROVENTOS
        lista = list(self.sessao.scalars(select(Provento).where(
            Provento.ativo_id == ativo_id, Provento.data_com > referencia - timedelta(days=365),
            Provento.data_com <= referencia)))
        return sum(float(p.valor_por_cota) for p in lista), lista, None

    def padronizada(self, empresa_id: int, tipo: str) -> DemonstracaoPadronizada | None:
        return self.sessao.scalar(select(DemonstracaoPadronizada).where(
            DemonstracaoPadronizada.empresa_id == empresa_id, DemonstracaoPadronizada.tipo_periodo == tipo)
            .order_by(desc(DemonstracaoPadronizada.data_fim)).limit(1))

    def anual(self, empresa_id: int, ano: int) -> DemonstracaoPadronizada | None:
        return self.sessao.scalar(select(DemonstracaoPadronizada).where(
            DemonstracaoPadronizada.empresa_id == empresa_id, DemonstracaoPadronizada.periodo == f"{ano}-A"))

    # ---------------------------------------------------------------- ações

    def calcular_acao(self, ativo: Ativo) -> list[Calculo]:
        empresa: Empresa = ativo.empresa
        cotacao = self.ultima_cotacao(ativo.id)
        demo = self.padronizada(empresa.id, "ttm") or self.padronizada(empresa.id, "ano")
        capital = self.sessao.scalar(select(ComposicaoCapital).where(ComposicaoCapital.empresa_id == empresa.id)
                                     .order_by(desc(ComposicaoCapital.data_referencia)).limit(1))
        c = demo.campos if demo else {}
        calculos: list[Calculo] = []

        def contabil(campo: str) -> Insumo | None:
            if demo is None:
                return None
            return self._insumo(campo, c.get(campo), demo, periodo=demo.periodo, tipo_periodo=demo.tipo_periodo,
                                contas=demo.insumos.get(campo, []))

        def add(metrica: str, resultado: Resultado, insumos: list[Insumo | None], data_ref: date | None = None):
            calculos.append(Calculo(metrica, resultado, [i for i in insumos if i], data_ref or
                                    (demo.data_fim if demo else None)))

        preco = float(cotacao.fechamento) if cotacao else None
        i_preco = self._insumo("preco", preco, cotacao, data_pregao=cotacao.data.isoformat()) if cotacao else None

        # Ações em circulação (todas as classes) e valor de mercado
        acoes = indisponivel("dado indisponível: composição do capital")
        i_acoes = None
        classes: list[tuple[float | None, float | None]] = []
        aviso_classes = None
        if capital:
            on = float(capital.acoes_ordinarias or 0) - float(capital.acoes_tesouraria_on or 0)
            pn = float(capital.acoes_preferenciais or 0) - float(capital.acoes_tesouraria_pn or 0)
            acoes = ib.acoes_em_circulacao(on + pn, 0)
            i_acoes = self._insumo("acoes_em_circulacao", acoes.valor, capital, ordinarias=on, preferenciais=pn)
            precos = self._precos_por_especie(empresa)
            for qtd, especie in ((on, "ON"), (pn, "PN")):
                if qtd <= 0:
                    continue
                p = precos.get(especie) or precos.get("ON") or precos.get("PN")
                if especie not in precos:
                    aviso_classes = "classe sem negociação valorada pela cotação da outra classe"
                classes.append((qtd, p))
        vm = ib.valor_de_mercado(classes) if classes else indisponivel("dado indisponível: composição do capital")
        if aviso_classes and vm.disponivel:
            vm = Resultado(vm.valor, None, {**vm.detalhes, "aviso": aviso_classes})
        add("basico.valor_mercado", vm, [i_preco, i_acoes], cotacao.data if cotacao else None)

        # "Valor de mercado do ticker": cotação deste ticker × total de ações (P/L = preço ÷ LPA).
        vm_ticker = (preco * acoes.valor) if (preco is not None and acoes.disponivel) else None
        base = [i_preco, i_acoes]

        lucro = c.get("lucro_liquido_controladores")
        pl = c.get("patrimonio_liquido_controladores")
        receita = c.get("receita_liquida")
        ebit_ = c.get("ebit")
        ebitda_r = ib.ebitda(ebit_, c.get("depreciacao_amortizacao"))
        ebitda_ = ebitda_r.valor
        db = ib.divida_bruta(c.get("emprestimos_cp"), c.get("emprestimos_lp"))
        dl = ib.divida_liquida(db.valor, c.get("caixa_equivalentes"), c.get("aplicacoes_financeiras"))
        ev = ib.valor_da_firma(vm.valor, dl.valor)
        financeira = empresa.tipo_plano_contas != "geral"

        def nao_aplica(r: Resultado) -> Resultado:
            return indisponivel("não se aplica a bancos e seguradoras") if financeira else r

        i_lucro, i_pl, i_rec = contabil("lucro_liquido_controladores"), contabil("patrimonio_liquido_controladores"), \
            contabil("receita_liquida")
        i_ebit, i_da = contabil("ebit"), contabil("depreciacao_amortizacao")
        i_div = [contabil("emprestimos_cp"), contabil("emprestimos_lp")]
        i_caixa = [contabil("caixa_equivalentes"), contabil("aplicacoes_financeiras")]

        add("basico.divida_bruta", nao_aplica(db), i_div)
        add("basico.divida_liquida", nao_aplica(dl), i_div + i_caixa)
        add("basico.ev", nao_aplica(ev), base + i_div + i_caixa)
        lpa_r = ib.lpa(lucro, acoes.valor)
        add("basico.lpa", lpa_r, [i_lucro, i_acoes])
        add("basico.vpa", ib.vpa(pl, acoes.valor), [i_pl, i_acoes])
        add("basico.p_l", ib.p_l(vm_ticker, lucro), base + [i_lucro])
        add("basico.p_vp", ib.p_vp(vm_ticker, pl), base + [i_pl])
        add("basico.p_receita", ib.p_receita(vm_ticker, receita), base + [i_rec])
        add("basico.p_ebit", nao_aplica(ib.p_ebit(vm_ticker, ebit_)), base + [i_ebit])
        add("basico.p_ebitda", nao_aplica(ib.p_ebitda(vm_ticker, ebitda_)), base + [i_ebit, i_da])
        add("basico.ev_ebit", nao_aplica(ib.ev_ebit(ev.valor, ebit_)), base + i_div + i_caixa + [i_ebit])
        add("basico.ev_ebitda", nao_aplica(ib.ev_ebitda(ev.valor, ebitda_)), base + i_div + i_caixa + [i_ebit, i_da])
        add("basico.p_ativo", ib.p_ativo(vm_ticker, c.get("ativo_total")), base + [contabil("ativo_total")])
        i_ac, i_pc, i_pt = contabil("ativo_circulante"), contabil("passivo_circulante"), contabil("passivo_total")
        add("basico.p_capital_giro", nao_aplica(ib.p_capital_giro(vm_ticker, c.get("ativo_circulante"),
                                                                  c.get("passivo_circulante"))), base + [i_ac, i_pc])
        add("basico.p_ativo_circ_liq", nao_aplica(ib.p_ativo_circulante_liquido(
            vm_ticker, c.get("ativo_circulante"), c.get("passivo_total"))), base + [i_ac, i_pt])

        referencia = cotacao.data if cotacao else date.today()
        soma, proventos, motivo = self.proventos_12m(ativo.id, referencia)
        i_prov = [self._insumo("provento", p.valor_por_cota, p, tipo=p.tipo, data_com=p.data_com.isoformat())
                  for p in proventos]
        if motivo:
            add("basico.dy", indisponivel(motivo), [i_preco], referencia)
            add("basico.payout", indisponivel(motivo), [i_lucro], referencia)
        else:
            add("basico.dy", ib.dividend_yield(soma, preco), [i_preco] + i_prov, referencia)
            add("basico.payout", ib.payout(soma, lpa_r.valor), [i_lucro, i_acoes] + i_prov, referencia)

        aliquota = POR_ID["basico.roic"].parametros[0].padrao
        add("basico.roe", ib.roe(lucro, pl), [i_lucro, i_pl])
        add("basico.roa", ib.roa(lucro, c.get("ativo_total")), [i_lucro, contabil("ativo_total")])
        add("basico.roic", nao_aplica(ib.roic(ebit_, pl, dl.valor, aliquota)), [i_ebit, i_pl] + i_div + i_caixa)
        add("basico.margem_bruta", nao_aplica(ib.margem(c.get("lucro_bruto"), receita, "lucro_bruto")),
            [contabil("lucro_bruto"), i_rec])
        add("basico.margem_ebit", nao_aplica(ib.margem(ebit_, receita, "ebit")), [i_ebit, i_rec])
        add("basico.margem_ebitda", nao_aplica(ib.margem(ebitda_, receita, "ebitda")), [i_ebit, i_da, i_rec])
        add("basico.margem_liquida", ib.margem(lucro, receita, "lucro_liquido"), [i_lucro, i_rec])
        add("basico.giro_ativos", ib.giro_ativos(receita, c.get("ativo_total")), [i_rec, contabil("ativo_total")])
        add("basico.dl_pl", nao_aplica(ib.divida_liquida_sobre(dl.valor, pl, "patrimonio_liquido")),
            i_div + i_caixa + [i_pl])
        add("basico.dl_ebitda", nao_aplica(ib.divida_liquida_sobre(dl.valor, ebitda_, "ebitda")),
            i_div + i_caixa + [i_ebit, i_da])
        add("basico.dl_ebit", nao_aplica(ib.divida_liquida_sobre(dl.valor, ebit_, "ebit")), i_div + i_caixa + [i_ebit])
        add("basico.pl_ativos", ib.pl_sobre_ativos(c.get("patrimonio_liquido"), c.get("ativo_total")),
            [contabil("patrimonio_liquido"), contabil("ativo_total")])
        add("basico.passivos_ativos", ib.passivos_sobre_ativos(c.get("passivo_total"), c.get("ativo_total")),
            [i_pt, contabil("ativo_total")])
        add("basico.liquidez_corrente", nao_aplica(ib.liquidez_corrente(c.get("ativo_circulante"),
                                                                        c.get("passivo_circulante"))), [i_ac, i_pc])

        calculos.extend(self._cagr(empresa))
        calculos.append(self._liquidez(ativo))
        return calculos

    def _precos_por_especie(self, empresa: Empresa) -> dict[str, float]:
        """Cotação mais recente por espécie; havendo vários tickers da mesma espécie, o mais líquido."""
        melhores: dict[str, tuple[float, float]] = {}
        for a in empresa.ativos:
            if a.especie not in ("ON", "PN"):
                continue
            cot = self.ultima_cotacao(a.id)
            if cot is None:
                continue
            volume = float(cot.volume_financeiro or 0)
            if a.especie not in melhores or volume > melhores[a.especie][1]:
                melhores[a.especie] = (float(cot.fechamento), volume)
        return {k: v[0] for k, v in melhores.items()}

    def _cagr(self, empresa: Empresa) -> list[Calculo]:
        ultimo = self.padronizada(empresa.id, "ano")
        saida = []
        for metrica, campo in (("basico.cagr_receita_5a", "receita_liquida"),
                               ("basico.cagr_lucro_5a", "lucro_liquido_controladores")):
            if ultimo is None:
                saida.append(Calculo(metrica, indisponivel("dado indisponível: demonstrações anuais"), [], None))
                continue
            inicial = self.anual(empresa.id, ultimo.data_fim.year - 5)
            if inicial is None:
                saida.append(Calculo(metrica, indisponivel("dado indisponível: menos de 6 anos de DFP"), [],
                                     ultimo.data_fim))
                continue
            r = ib.cagr(inicial.campos.get(campo), ultimo.campos.get(campo), 5)
            saida.append(Calculo(metrica, r, [
                self._insumo(f"{campo}_inicial", inicial.campos.get(campo), inicial, periodo=inicial.periodo),
                self._insumo(f"{campo}_final", ultimo.campos.get(campo), ultimo, periodo=ultimo.periodo)],
                ultimo.data_fim))
        return saida

    def _liquidez(self, ativo: Ativo) -> Calculo:
        cotacoes = self.volumes_recentes(ativo.id)
        r = ib.liquidez_media_diaria([float(c.volume_financeiro) if c.volume_financeiro is not None else None
                                      for c in cotacoes])
        insumos = []
        if cotacoes:
            insumos.append(self._insumo("volume_financeiro", None, cotacoes[0], pregoes=len(cotacoes),
                                        de=cotacoes[-1].data.isoformat(), ate=cotacoes[0].data.isoformat()))
        return Calculo("basico.liquidez_diaria", r, insumos, cotacoes[0].data if cotacoes else None)

    # ------------------------------------------------------------------ FIIs

    def calcular_fii(self, ativo: Ativo) -> list[Calculo]:
        fii = self.sessao.scalar(select(Fii).where(Fii.ativo_id == ativo.id))
        cotacao = self.ultima_cotacao(ativo.id)
        preco = float(cotacao.fechamento) if cotacao else None
        i_preco = self._insumo("preco", preco, cotacao, data_pregao=cotacao.data.isoformat()) if cotacao else None
        calculos = [self._liquidez(ativo)]
        referencia = cotacao.data if cotacao else date.today()
        soma, proventos, motivo = self.proventos_12m(ativo.id, referencia)
        if motivo:
            calculos.append(Calculo("basico.dy", indisponivel(motivo), [i_preco] if i_preco else [], referencia))
        else:
            i_prov = [self._insumo("provento", p.valor_por_cota, p, data_com=p.data_com.isoformat()) for p in proventos]
            calculos.append(Calculo("basico.dy", ib.dividend_yield(soma, preco), [i_preco] + i_prov, referencia))

        if fii is None:
            sem = indisponivel("dado indisponível: fundo sem informe mensal ligado ao ticker (ISIN)")
            for m in ("fii.p_vp", "fii.vp_cota", "fii.patrimonio_liquido", "fii.numero_cotistas",
                      "fii.rentab_patrimonial_12m", "fii.dy_informado_12m"):
                calculos.append(Calculo(m, sem, [], None))
            return calculos

        informes = self._informes(fii.id)
        ultimo = informes[-1] if informes else None

        def campo(nome: str) -> Resultado:
            v = getattr(ultimo, nome) if ultimo else None
            return indisponivel(f"dado indisponível: {nome}") if v is None else Resultado(float(v))

        def i_inf(nome: str, inf=None) -> Insumo | None:
            inf = inf or ultimo
            return self._insumo(nome, getattr(inf, nome), inf, competencia=inf.competencia.isoformat()) if inf else None

        vp = float(ultimo.valor_patrimonial_cota) if ultimo and ultimo.valor_patrimonial_cota is not None else None
        data_inf = ultimo.competencia if ultimo else None
        calculos += [
            Calculo("fii.p_vp", mfii.p_vp_cota(preco, vp), [i_preco, i_inf("valor_patrimonial_cota")], data_inf),
            Calculo("fii.vp_cota", campo("valor_patrimonial_cota"), [i_inf("valor_patrimonial_cota")], data_inf),
            Calculo("fii.patrimonio_liquido", campo("patrimonio_liquido"), [i_inf("patrimonio_liquido")], data_inf),
            Calculo("fii.numero_cotistas", campo("numero_cotistas"), [i_inf("numero_cotistas")], data_inf),
        ]
        ultimos12 = informes[-12:]
        rentab = [None if i.rentabilidade_patrimonial_mes is None else float(i.rentabilidade_patrimonial_mes)
                  for i in ultimos12]
        dy = [None if i.dividend_yield_mes is None else float(i.dividend_yield_mes) for i in ultimos12]
        calculos += [
            Calculo("fii.rentab_patrimonial_12m", mfii.composicao_percentuais(rentab),
                    [i_inf("rentabilidade_patrimonial_mes", i) for i in ultimos12], data_inf),
            Calculo("fii.dy_informado_12m", mfii.soma_percentuais(dy),
                    [i_inf("dividend_yield_mes", i) for i in ultimos12], data_inf),
        ]
        for calc in calculos:
            calc.insumos = [i for i in calc.insumos if i]
        return calculos

    def _informes(self, fii_id: int) -> list[FiiInformeMensal]:
        """Informes mensais em ordem cronológica, versão mais recente de cada competência."""
        todos = self.sessao.scalars(select(FiiInformeMensal).where(FiiInformeMensal.fii_id == fii_id)
                                    .order_by(FiiInformeMensal.competencia, FiiInformeMensal.versao))
        por_mes = {}
        for inf in todos:
            por_mes[inf.competencia] = inf
        return list(por_mes.values())

    # --------------------------------------------------------------- gravação

    def calcular(self, ativo: Ativo) -> list[Calculo]:
        if ativo.classe == "FII":
            return self.calcular_fii(ativo)
        if ativo.empresa is not None:
            return self.calcular_acao(ativo)
        return []

    def materializar(self, ativo: Ativo) -> int:
        calculos = self.calcular(ativo)
        agora = datetime.now(UTC)
        for calc in calculos:
            metrica = POR_ID[calc.metrica]
            valores = {
                "ativo_id": ativo.id, "metrica": calc.metrica, "data_referencia": calc.data_referencia,
                "valor": calc.resultado.valor, "motivo_indisponivel": calc.resultado.motivo_indisponivel,
                "parametros": {p.chave: p.padrao for p in metrica.parametros},
                "insumos": [i.como_dict() for i in calc.insumos] + (
                    [{"aviso": calc.resultado.detalhes["aviso"]}] if "aviso" in calc.resultado.detalhes else []),
                "versao_metodologia": metrica.versao, "calculado_em": agora,
            }
            stmt = insert(IndicadorCalculado).values(**valores)
            stmt = stmt.on_conflict_do_update(index_elements=["ativo_id", "metrica"],
                                              set_={k: stmt.excluded[k] for k in valores
                                                    if k not in ("ativo_id", "metrica")})
            self.sessao.execute(stmt)
        return len(calculos)


def recalcular(sessao: Session, tickers: list[str] | None = None) -> int:
    calc = Calculadora(sessao)
    consulta = select(Ativo).where(Ativo.ativo.is_(True), Ativo.classe.in_(("ACAO", "FII")))
    if tickers:
        consulta = consulta.where(Ativo.ticker.in_(tickers))
    total = 0
    for ativo in sessao.scalars(consulta).all():
        total += calc.materializar(ativo)
        sessao.commit()
    return total
