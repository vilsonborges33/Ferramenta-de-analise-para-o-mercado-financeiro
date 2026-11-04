"use client";

import { useMemo, useState } from "react";
import { Grafico, reaisCurto } from "@/componentes/Grafico";
import { Aviso, brl, Cabecalho, CampoNumero, Kpi, pctf, useApi } from "@/componentes/Ferramenta";

type Resposta = {
  valor: number | null; motivo_indisponivel: string | null; investido: number; renda_mensal: number;
  patrimonio_necessario: number; aporte_necessario: number; meses_ate_meta: number | null; atinge_meta: boolean;
  taxa_mensal: number; serie: { ano: number; patrimonio: number; investido: number; renda_mensal: number }[];
};

function prazo(meses: number | null) {
  if (meses === null) return "não atinge em 100 anos";
  const a = Math.floor(meses / 12), m = meses % 12;
  return [a && `${a} ano${a > 1 ? "s" : ""}`, m && `${m} ${m > 1 ? "meses" : "mês"}`].filter(Boolean).join(" e ") || "já atingida";
}

export default function Aposentadoria() {
  const [inicial, setInicial] = useState(20000);
  const [aporte, setAporte] = useState(1500);
  const [retorno, setRetorno] = useState(10);
  const [anos, setAnos] = useState(20);
  const [dy, setDy] = useState(7);
  const [meta, setMeta] = useState(5000);
  const { dados, erro } = useApi<Resposta>(
    `/ferramentas/aposentadoria?inicial=${inicial}&aporte_mensal=${aporte}&retorno_anual=${retorno / 100}&anos=${Math.round(anos)}&dividend_yield=${dy / 100}&meta_renda_mensal=${meta}`);

  const opcao = useMemo(() => dados?.serie && {
    tooltip: { trigger: "axis", valueFormatter: (v: unknown) => brl(Number(v)) },
    legend: { top: 0, textStyle: { color: "#8a97ab" } },
    grid: { left: 64, right: 64, top: 36, bottom: 30 },
    xAxis: { type: "category", data: dados.serie.map((p) => `${p.ano}a`) },
    yAxis: [{ type: "value", axisLabel: { formatter: reaisCurto } }, { type: "value", axisLabel: { formatter: reaisCurto } }],
    series: [
      { name: "Patrimônio", type: "line", smooth: true, areaStyle: { opacity: 0.15 }, data: dados.serie.map((p) => p.patrimonio) },
      { name: "Total investido", type: "line", lineStyle: { type: "dashed" }, symbol: "none", data: dados.serie.map((p) => p.investido) },
      { name: "Renda mensal", type: "bar", yAxisIndex: 1, barWidth: "40%", itemStyle: { opacity: 0.6, color: "#f5b544" },
        data: dados.serie.map((p) => p.renda_mensal),
        markLine: { symbol: "none", label: { formatter: "meta", color: "#f5b544" }, lineStyle: { color: "#f5b544", type: "dashed" },
          data: [{ yAxis: meta }] } },
    ],
  }, [dados, meta]);

  return (
    <div className="space-y-5">
      <Cabecalho trilha="Ferramentas" titulo="Plano de aposentadoria" icone="aposentadoria"
        subtitulo="Quanto juntar para viver da renda dos dividendos, sem consumir o patrimônio." />
      <div className="grid gap-5 lg:grid-cols-[340px_1fr]">
        <div className="cartao space-y-4 p-5">
          <CampoNumero rotulo="Patrimônio hoje" prefixo="R$" valor={inicial} aoMudar={setInicial} />
          <CampoNumero rotulo="Aporte mensal" prefixo="R$" valor={aporte} aoMudar={setAporte} />
          <CampoNumero rotulo="Retorno esperado" sufixo="% ao ano" valor={retorno} aoMudar={setRetorno}
            dica={dados ? `Equivale a ${pctf(dados.taxa_mensal, 3)} ao mês. Use retorno real para valores em reais de hoje.` : undefined} />
          <CampoNumero rotulo="Horizonte" sufixo="anos" valor={anos} aoMudar={setAnos} />
          <CampoNumero rotulo="Dividend yield na aposentadoria" sufixo="% ao ano" valor={dy} aoMudar={setDy} />
          <CampoNumero rotulo="Renda mensal desejada" prefixo="R$" valor={meta} aoMudar={setMeta} />
        </div>
        <div className="space-y-4">
          {(erro || dados?.motivo_indisponivel) && <p className="cartao p-3 text-sm negativo">{erro ?? dados?.motivo_indisponivel}</p>}
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Kpi rotulo={`Patrimônio em ${Math.round(anos)} anos`} valor={brl(dados?.valor, 0)} cor="var(--destaque)"
              detalhe={dados ? `investidos ${brl(dados.investido, 0)}` : undefined} />
            <Kpi rotulo="Renda mensal projetada" valor={brl(dados?.renda_mensal, 0)}
              cor={dados ? (dados.atinge_meta ? "var(--positivo)" : "var(--alerta)") : undefined}
              detalhe={dados ? (dados.atinge_meta ? "atinge a meta" : `meta: ${brl(meta, 0)}`) : undefined} />
            <Kpi rotulo="Patrimônio necessário" valor={brl(dados?.patrimonio_necessario, 0)} detalhe={`meta × 12 ÷ DY de ${dy}%`} />
            <Kpi rotulo="Aporte para a meta" valor={brl(dados?.aporte_necessario, 0)}
              detalhe={dados ? `com o aporte atual: ${prazo(dados.meses_ate_meta)}` : undefined} />
          </div>
          <div className="cartao p-4">
            {opcao && <Grafico opcao={opcao} altura="h-80" rotulo="Patrimônio e renda mensal projetados por ano" />}
          </div>
          <Aviso>Simulação com retorno e dividend yield constantes escolhidos por você; resultados reais variam.
            Não constitui recomendação de investimento.</Aviso>
        </div>
      </div>
    </div>
  );
}
