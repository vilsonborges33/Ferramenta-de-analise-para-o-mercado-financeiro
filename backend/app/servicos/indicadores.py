"""Calcula e materializa os indicadores de cada ativo (DECISOES.md D-005).

Busca os insumos no banco, chama as funções puras de `app.metodologias` e grava em
`indicador_calculado` o valor (ou o motivo da indisponibilidade) com a procedência de cada insumo.
"""

import logging
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
    FiiImovel,
    FiiInformeMensal,
    Fonte,
    IndicadorCalculado,
    LoteIngestao,
    Provento,
)
from app.metodologias import bazin, graham, lynch
from app.metodologias import fii as mfii
from app.metodologias import greenblatt as gb
from app.metodologias import indicadores_basicos as ib
from app.metodologias import reit as mreit
from app.metodologias.registro import POR_ID
from app.metodologias.tipos import Resultado, indisponivel

log = logging.getLogger(__name__)

PREGOES_LIQUIDEZ = 42  # ~2 meses de pregões

# Ações que formam cada unit (ON, PN), pelo estatuto de cada empresa. Conferido em 10/11/2026 pelas cotações:
# preço da unit ≈ ON × a + PN × b (ENGI11, SANB11, SAPR11, TAEE11). A CVM não publica essa composição.
COMPOSICAO_UNITS: dict[str, tuple[int, int]] = {
    "ALUP11": (1, 2), "BPAC11": (1, 2), "BRBI11": (1, 2), "ENGI11": (1, 4), "IGTI11": (1, 2),
    "KLBN11": (1, 4), "RNEW11": (1, 2), "SANB11": (1, 1), "SAPR11": (1, 4), "TAEE11": (1, 2),
}

# Empresas que passaram a informar no ITR o capital integralizado já sem as ações em tesouraria (CNPJ → a partir
# de). Vale: em 31/03/2026 o capital cai de 4.539 mi para 4.263 mi com 175 mi em tesouraria; a B3 mostra 4.439 mi
# emitidas (= 4.256 + 183 em 30/09/2026). Subtrair a tesouraria de novo contaria 4.072 mi ações (D-043).
CAPITAL_SEM_TESOURARIA: dict[str, date] = {"33.592.510/0001-54": date(2026, 3, 31)}
MOTIVO_SEM_PROVENTOS = "proventos não ingeridos: a carga de dividendos ainda não rodou com sucesso"


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
        self._fontes_proventos: dict[str, bool] = {}

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

    def _fonte_de_proventos_carregada(self, classe: str) -> bool:
        """Verdadeiro se a fonte de proventos da classe já rodou com sucesso ao menos uma vez.

        Com a fonte carregada, ausência de provento na janela significa DY = 0 (e não dado indisponível).
        """
        if classe not in self._fontes_proventos:
            codigo = self._codigos_fonte_proventos(classe)[0]
            ok = self.sessao.scalar(select(func.count()).select_from(LoteIngestao).join(Fonte).where(
                Fonte.codigo == codigo, LoteIngestao.status == "concluido", LoteIngestao.linhas_gravadas > 0))
            self._fontes_proventos[classe] = bool(ok) or obter_configuracao().brapi_proventos_habilitado
        return self._fontes_proventos[classe]

    @staticmethod
    def _codigos_fonte_proventos(classe: str) -> list[str]:
        if obter_configuracao().fonte_mercado == "yahoo":
            return ["YAHOO_FINANCE"]
        return ["FNET_RENDIMENTOS" if classe == "FII" else "B3_PROVENTOS", "BRAPI"]

    def proventos_12m(self, ativo_id: int, referencia: date, classe: str = "ACAO"
                      ) -> tuple[float | None, list[Provento], str | None]:
        # Só a fonte configurada entra na conta, para não somar o mesmo provento vindo de duas fontes.
        ids_fonte = [i for i, c in self.fontes.items() if c in self._codigos_fonte_proventos(classe)]
        existe = self.sessao.scalar(select(func.count()).select_from(Provento).where(
            Provento.ativo_id == ativo_id, Provento.fonte_id.in_(ids_fonte)))
        if not existe and not self._fonte_de_proventos_carregada(classe):
            return None, [], MOTIVO_SEM_PROVENTOS
        # Janela pela data de pagamento (D-020); quando a fonte não informa o pagamento (Yahoo), pela data-ex (D-027).
        data_janela = func.coalesce(Provento.data_pagamento, Provento.data_ex)
        lista = list(self.sessao.scalars(select(Provento).where(
            Provento.ativo_id == ativo_id, Provento.fonte_id.in_(ids_fonte),
            data_janela > referencia - timedelta(days=365), data_janela <= referencia)))
        aliquota_jcp = POR_ID["basico.dy"].parametros[0].padrao
        soma = sum(ib.provento_liquido(float(p.valor_por_cota), p.tipo, aliquota_jcp).valor for p in lista)
        return soma, lista, None

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
        # Unit: LPA, VPA e múltiplos por unit (ações da empresa ÷ ações por unit); demais tickers, por ação.
        composicao = COMPOSICAO_UNITS.get(ativo.ticker) if ativo.classe == "UNIT" else (1, 0)
        por_ticker = sum(composicao) if composicao else None

        # Ações em circulação (todas as classes) e valor de mercado
        acoes = indisponivel("dado indisponível: composição do capital")
        i_acoes = None
        classes: list[tuple[float | None, float | None]] = []
        aviso_classes = None
        if capital:
            desde = CAPITAL_SEM_TESOURARIA.get(empresa.cnpj)
            descontar = 0.0 if desde and capital.data_referencia >= desde else 1.0
            on = float(capital.acoes_ordinarias or 0) - descontar * float(capital.acoes_tesouraria_on or 0)
            pn = float(capital.acoes_preferenciais or 0) - descontar * float(capital.acoes_tesouraria_pn or 0)
            fator, aviso_escala = ib.fator_escala_acoes(on + pn, preco, c.get("patrimonio_liquido_controladores"),
                                                        c.get("receita_liquida"))
            on, pn = on * fator, pn * fator
            acoes = ib.acoes_em_circulacao(on + pn, 0)
            if aviso_escala and acoes.disponivel:
                acoes = Resultado(acoes.valor, None, {"aviso": aviso_escala})
            i_acoes = self._insumo("acoes_em_circulacao", acoes.valor, capital, ordinarias=on, preferenciais=pn,
                                   **({"aviso_escala": aviso_escala} if aviso_escala else {}))
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
        # Para a unit, a quantidade vira "units equivalentes" (ações ÷ ações por unit).
        if por_ticker is None:
            acoes_ticker = indisponivel("composição da unit (ações por unit) desconhecida")
        elif acoes.disponivel:
            acoes_ticker = Resultado(acoes.valor / por_ticker)
        else:
            acoes_ticker = acoes
        vm_ticker = (preco * acoes_ticker.valor) if (preco is not None and acoes_ticker.disponivel) else None
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
        lpa_r = ib.lpa(lucro, acoes_ticker.valor) if acoes_ticker.disponivel else acoes_ticker
        add("basico.lpa", lpa_r, [i_lucro, i_acoes])
        vpa_r = ib.vpa(pl, acoes_ticker.valor) if acoes_ticker.disponivel else acoes_ticker
        add("basico.vpa", vpa_r, [i_pl, i_acoes])
        p_l_r = ib.p_l(vm_ticker, lucro)
        add("basico.p_l", p_l_r, base + [i_lucro])
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
        i_prov = [self._insumo("provento", p.valor_por_cota, p, tipo=p.tipo, data_com=p.data_com.isoformat(),
                                 data_pagamento=p.data_pagamento.isoformat() if p.data_pagamento else None)
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

        cagrs = self._cagr(empresa)
        calculos.extend(cagrs)
        calculos.append(self._liquidez(ativo))

        # Métodos dos livros com os parâmetros padrão (o ranking recalcula com os do usuário).
        caixa = c.get("caixa_equivalentes")
        caixa_total = None if caixa is None else caixa + (c.get("aplicacoes_financeiras") or 0)
        cg = gb.capital_giro_liquido(c.get("ativo_circulante"), caixa_total, c.get("passivo_circulante"),
                                     c.get("emprestimos_cp"))
        add("greenblatt.earnings_yield", nao_aplica(gb.earnings_yield(ebit_, ev.valor)),
            base + i_div + i_caixa + [i_ebit])
        add("greenblatt.retorno_capital", nao_aplica(gb.retorno_sobre_capital(ebit_, cg.valor, c.get("imobilizado"))),
            [i_ebit, i_ac, i_pc, contabil("imobilizado")] + i_caixa + i_div)
        vi = graham.valor_intrinseco(lpa_r.valor, vpa_r.valor)
        add("graham.valor_intrinseco", vi, [i_lucro, i_pl, i_acoes])
        add("graham.margem_seguranca", graham.margem_seguranca(vi.valor, preco), [i_preco, i_lucro, i_pl, i_acoes])
        cagr_lucro = next(x for x in cagrs if x.metrica == "basico.cagr_lucro_5a")
        g = cagr_lucro.resultado.valor
        extremos = [i.valor for i in cagr_lucro.insumos] or [None, None]
        add("lynch.peg", lynch.peg(p_l_r.valor, g) if g is not None else cagr_lucro.resultado,
            base + [i_lucro] + cagr_lucro.insumos)
        add("lynch.preco_justo", lynch.preco_justo(lpa_r.valor, g, extremos[0], extremos[-1])
            if g is not None else cagr_lucro.resultado, [i_lucro, i_acoes] + cagr_lucro.insumos)
        add("bazin.preco_teto", indisponivel(motivo) if motivo else bazin.preco_teto(soma), i_prov, referencia)
        return calculos

    def _precos_por_especie(self, empresa: Empresa) -> dict[str, float]:
        """Cotação mais recente por espécie; havendo vários tickers da mesma espécie, o mais líquido."""
        melhores: dict[str, tuple[float, float]] = {}
        unit = None
        for a in empresa.ativos:
            if a.especie == "UNIT" and a.ticker in COMPOSICAO_UNITS:
                unit = a
            if a.especie not in ("ON", "PN"):
                continue
            cot = self.ultima_cotacao(a.id)
            if cot is None:
                continue
            volume = float(cot.volume_financeiro or 0)
            if a.especie not in melhores or volume > melhores[a.especie][1]:
                melhores[a.especie] = (float(cot.fechamento), volume)
        precos = {k: v[0] for k, v in melhores.items()}
        # Empresa negociada quase só pela unit (KLBN, ALUP, BRBI): a classe sem cotação vale unit ÷ ações por unit.
        cot_unit = self.ultima_cotacao(unit.id) if unit else None
        if cot_unit is not None:
            for especie in ("ON", "PN"):
                precos.setdefault(especie, float(cot_unit.fechamento) / sum(COMPOSICAO_UNITS[unit.ticker]))
        return precos

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
        soma, proventos, motivo = self.proventos_12m(ativo.id, referencia, "FII")
        if motivo:
            calculos.append(Calculo("basico.dy", indisponivel(motivo), [i_preco] if i_preco else [], referencia))
        else:
            i_prov = [self._insumo("provento", p.valor_por_cota, p, data_com=p.data_com.isoformat(),
                                   data_pagamento=p.data_pagamento.isoformat() if p.data_pagamento else None)
                      for p in proventos]
            calculos.append(Calculo("basico.dy", ib.dividend_yield(soma, preco),
                                    ([i_preco] if i_preco else []) + i_prov, referencia))

        if fii is None:
            sem = indisponivel("dado indisponível: fundo sem informe mensal ligado ao ticker (ISIN)")
            for m in ("fii.p_vp", "fii.vp_cota", "fii.patrimonio_liquido", "fii.numero_cotistas",
                      "fii.rentab_patrimonial_12m", "fii.dy_informado_12m", "fii.vacancia", "fii.alavancagem"):
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
        ativo_total = float(ultimo.ativo_total) if ultimo and ultimo.ativo_total is not None else None
        passivo = float(ultimo.total_passivo) if ultimo and ultimo.total_passivo is not None else None
        nao_oneroso = mfii.passivo_nao_oneroso(ultimo.extras if ultimo else None)
        calculos.append(Calculo("fii.alavancagem", mfii.alavancagem(passivo, ativo_total, nao_oneroso),
                                [i_inf("total_passivo"), i_inf("ativo_total")], data_inf))
        imoveis = self.imoveis(fii.id)
        vac = mfii.vacancia_ponderada([(None if i.area_m2 is None else float(i.area_m2),
                                        None if i.percentual_vacancia is None else float(i.percentual_vacancia))
                                       for i in imoveis])
        i_vac = [self._insumo(f"vacancia {i.nome}", None if i.percentual_vacancia is None else
                              float(i.percentual_vacancia), i, area_m2=None if i.area_m2 is None else float(i.area_m2),
                              competencia=i.competencia.isoformat()) for i in imoveis[:30]]
        calculos.append(Calculo("fii.vacancia", vac, i_vac, imoveis[0].competencia if imoveis else None))
        for calc in calculos:
            calc.insumos = [i for i in calc.insumos if i]
        return calculos

    def imoveis(self, fii_id: int) -> list[FiiImovel]:
        """Imóveis do informe trimestral mais recente do fundo."""
        ultima = self.sessao.scalar(select(func.max(FiiImovel.competencia)).where(FiiImovel.fii_id == fii_id))
        if ultima is None:
            return []
        return list(self.sessao.scalars(select(FiiImovel).where(FiiImovel.fii_id == fii_id,
                                                               FiiImovel.competencia == ultima)))

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
        if ativo.classe == "ETF":
            return self.calcular_etf(ativo)
        if ativo.empresa is not None:
            calculos = self.calcular_acao(ativo)
            if ativo.classe == "REIT":
                calculos += self.calcular_reit(ativo, calculos)
            return calculos
        return []

    def calcular_etf(self, ativo: Ativo) -> list[Calculo]:
        """ETFs (EUA): só cotação, dividend yield e liquidez — não há balanço próprio na SEC."""
        cotacao = self.ultima_cotacao(ativo.id)
        preco = float(cotacao.fechamento) if cotacao else None
        referencia = cotacao.data if cotacao else date.today()
        soma, proventos, motivo = self.proventos_12m(ativo.id, referencia, ativo.classe)
        i_preco = [self._insumo("preco", preco, cotacao, data_pregao=cotacao.data.isoformat())] if cotacao else []
        i_prov = [self._insumo("provento", p.valor_por_cota, p, data_com=p.data_com.isoformat()) for p in proventos]
        dy = indisponivel(motivo) if motivo else ib.dividend_yield(soma, preco)
        return [self._liquidez(ativo), Calculo("basico.dy", dy, i_preco + i_prov, referencia)]

    def calcular_reit(self, ativo: Ativo, calculos: list[Calculo]) -> list[Calculo]:
        """FFO, AFFO, P/FFO e cobertura dos dividendos (NAREIT; Damodaran)."""
        demo = self.padronizada(ativo.empresa_id, "ttm") or self.padronizada(ativo.empresa_id, "ano")
        c = demo.campos if demo else {}
        por_id = {x.metrica: x for x in calculos}

        def insumo(campo: str):
            return self._insumo(campo, c.get(campo), demo, periodo=demo.periodo, tipo_periodo=demo.tipo_periodo,
                                contas=demo.insumos.get(campo, [])) if demo else None

        base = [i for i in (insumo("lucro_liquido_controladores"), insumo("depreciacao_amortizacao"),
                            insumo("ganho_venda_imoveis")) if i]
        f = mreit.ffo(c.get("lucro_liquido_controladores"), c.get("depreciacao_amortizacao"),
                      c.get("ganho_venda_imoveis"))
        vm = por_id.get("basico.valor_mercado")
        lpa = por_id.get("basico.lpa")
        acoes = next((i.valor for i in (lpa.insumos if lpa else []) if i.insumo == "acoes_em_circulacao"), None)
        data_ref = demo.data_fim if demo else None
        i_acoes = [i for i in (lpa.insumos if lpa else []) if i.insumo == "acoes_em_circulacao"]
        return [
            Calculo("reit.ffo", f, base, data_ref),
            Calculo("reit.ffo_acao", mreit.por_acao(f.valor, acoes), base + i_acoes, data_ref),
            Calculo("reit.p_ffo", mreit.p_ffo(vm.resultado.valor if vm else None, f.valor),
                    base + (vm.insumos if vm else []), data_ref),
            Calculo("reit.affo", mreit.affo(f.valor, c.get("capex_manutencao")),
                    base + [i for i in (insumo("capex_manutencao"),) if i], data_ref),
            Calculo("reit.payout_ffo", mreit.payout_ffo(c.get("dividendos_pagos"), f.valor),
                    base + [i for i in (insumo("dividendos_pagos"),) if i], data_ref),
        ]

    def materializar(self, ativo: Ativo) -> int:
        calculos = self.calcular(ativo)
        agora = datetime.now(UTC)
        for calc in calculos:
            metrica = POR_ID[calc.metrica]
            valores = {
                "ativo_id": ativo.id, "metrica": calc.metrica, "data_referencia": calc.data_referencia,
                "valor": calc.resultado.valor, "motivo_indisponivel": calc.resultado.motivo_indisponivel,
                "parametros": {p.chave: p.padrao for p in metrica.parametros},
                "insumos": [i.como_dict() for i in calc.insumos if i is not None] + (
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
    consulta = select(Ativo).where(Ativo.ativo.is_(True),
                                   Ativo.classe.in_(("ACAO", "UNIT", "FII", "STOCK", "REIT", "ETF")))
    if tickers:
        consulta = consulta.where(Ativo.ticker.in_(tickers))
    total, falhas = 0, []
    for ativo in sessao.scalars(consulta).all():
        try:  # um ativo com dado estranho não pode deixar todos os outros com números velhos
            total += calc.materializar(ativo)
            sessao.commit()
        except Exception:
            sessao.rollback()
            log.exception("indicadores de %s falharam", ativo.ticker)
            falhas.append(ativo.ticker)
    if falhas:
        log.error("recálculo concluído com falha em %d ativo(s): %s", len(falhas), ", ".join(falhas[:20]))
    return total
