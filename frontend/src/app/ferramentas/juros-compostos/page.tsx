"use client";

import { useMemo, useState } from "react";
import { Grafico, reaisCurto } from "@/componentes/Grafico";
import { brl, Cabecalho, CampoNumero, Kpi, pctf, useApi } from "@/componentes/Ferramenta";

type Resposta = {
  valor: number | null; motivo_indisponivel: string | null; investido: number; juros: number; taxa_mensal: number;
  serie: { periodo: number; montante: number; investido: number; juros: number }[];
};

export default function JurosCompostos() {
  const [inicial, setInicial] = useState(10000);
  const [aporte, setAporte] = useState(1000);
  const [taxa, setTaxa] = useState(12);
  const [unidadeTaxa, setUnidadeTaxa] = useState("ano");
  const [prazo, setPrazo] = useState(10);
  const [unidadePrazo, setUnidadePrazo] = useState("anos");
  const meses = unidadePrazo === "anos" ? Math.round(prazo * 12) : Math.round(prazo);
  const caminho = meses >= 1 && meses <= 1200
    ? `/ferramentas/juros-compostos?inicial=${inicial}&aporte=${aporte}&taxa=${taxa / 100}&taxa_periodo=${unidadeTaxa === "ano" ? "ano" : "mes"}&periodos=${meses}`
    : null;
  const { dados, erro } = useApi<Resposta>(caminho);

  const opcao = useMemo(() => {
    if (!dados?.serie) return null;
    const pontos = dados.serie.filter((p) => meses <= 36 || p.periodo % 12 === 0 || p.periodo === meses);
    return {
      tooltip: { trigger: "axis", valueFormatter: (v: unknown) => brl(Number(v)) },
      legend: { top: 0, textStyle: { color: "#8a97ab" } },
      grid: { left: 60, right: 16, top: 36, bottom: 30 },
      xAxis: { type: "category", data: pontos.map((p) => (meses <= 36 ? `${p.periodo}m` : `${p.periodo / 12 | 0}a`)) },
      yAxis: { type: "value", axisLabel: { formatter: reaisCurto } },
      series: [
        { name: "Total investido", type: "bar", stack: "t", data: pontos.map((p) => p.investido), itemStyle: { color: "#60a5fa" } },
        { name: "Juros", type: "bar", stack: "t", data: pontos.map((p) => p.juros), itemStyle: { color: "#2dd4bf" } },
      ],
    };
  }, [dados, meses]);

  return (
    <div className="space-y-5">
      <Cabecalho trilha="Ferramentas" titulo="Calculadora de juros compostos" icone="juros"
        subtitulo="Quanto um valor inicial e aportes mensais viram com juros sobre juros." />
      <div className="grid gap-5 lg:grid-cols-[340px_1fr]">
        <div className="cartao space-y-4 p-5">
          <CampoNumero rotulo="Valor inicial" prefixo="R$" valor={inicial} aoMudar={setInicial} />
          <CampoNumero rotulo="Aporte mensal" prefixo="R$" valor={aporte} aoMudar={setAporte} dica="Feito no fim de cada mês." />
          <CampoNumero rotulo="Taxa de juros" sufixo="%" valor={taxa} aoMudar={setTaxa}
            unidade={{ valor: unidadeTaxa, aoMudar: setUnidadeTaxa, opcoes: [["ano", "ao ano"], ["mes", "ao mês"]] }}
            dica={dados?.taxa_mensal !== undefined ? `Equivale a ${pctf(dados.taxa_mensal, 4)} ao mês.` : undefined} />
          <CampoNumero rotulo="Prazo" valor={prazo} aoMudar={setPrazo}
            unidade={{ valor: unidadePrazo, aoMudar: setUnidadePrazo, opcoes: [["anos", "anos"], ["meses", "meses"]] }} />
          <p className="text-xs suave">Fórmula: M<sub>t</sub> = M<sub>t−1</sub> × (1 + i) + aporte.</p>
        </div>
        <div className="space-y-4">
          {erro && <p className="cartao p-3 text-sm negativo">{erro}</p>}
          {dados?.motivo_indisponivel && <p className="cartao p-3 text-sm negativo">{dados.motivo_indisponivel}</p>}
          <div className="grid gap-3 sm:grid-cols-3">
            <Kpi rotulo="Valor final" valor={brl(dados?.valor)} cor="var(--destaque)" />
            <Kpi rotulo="Total investido" valor={brl(dados?.investido)} />
            <Kpi rotulo="Total em juros" valor={brl(dados?.juros)}
              detalhe={dados?.valor ? `${pctf(dados.juros / dados.valor, 1)} do valor final` : undefined} />
          </div>
          <div className="cartao p-4">
            {opcao && <Grafico opcao={opcao} altura="h-80" rotulo="Evolução do patrimônio: investido e juros" />}
          </div>
        </div>
      </div>
    </div>
  );
}
