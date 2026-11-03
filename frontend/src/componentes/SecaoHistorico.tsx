"use client";

import { useEffect, useMemo, useState } from "react";
import { Grafico, porcento, reais, reaisCurto } from "@/componentes/Grafico";
import { formatarMoeda, formatarValor, nomeFonte } from "@/lib/formato";

type Ano = Record<string, number | null> & { ano: number; data_referencia: string; fonte: string; consolidado: boolean };
type Resposta = { anos: Ano[]; cagr_patrimonio: number | null; observacao: string };

const LINHAS: { aba: "resultado" | "balanco"; chave: string; nome: string; tipo: "R$" | "%" | "x" }[] = [
  { aba: "resultado", chave: "receita_liquida", nome: "Receita líquida", tipo: "R$" },
  { aba: "resultado", chave: "ebitda", nome: "EBITDA", tipo: "R$" },
  { aba: "resultado", chave: "ebit", nome: "EBIT", tipo: "R$" },
  { aba: "resultado", chave: "lucro_liquido", nome: "Lucro líquido", tipo: "R$" },
  { aba: "resultado", chave: "margem_bruta", nome: "Margem bruta", tipo: "%" },
  { aba: "resultado", chave: "margem_ebit", nome: "Margem EBIT", tipo: "%" },
  { aba: "resultado", chave: "margem_liquida", nome: "Margem líquida", tipo: "%" },
  { aba: "resultado", chave: "roe", nome: "ROE", tipo: "%" },
  { aba: "resultado", chave: "fco", nome: "Fluxo de caixa operacional", tipo: "R$" },
  { aba: "balanco", chave: "ativo_total", nome: "Ativo total", tipo: "R$" },
  { aba: "balanco", chave: "passivo_total", nome: "Passivo total", tipo: "R$" },
  { aba: "balanco", chave: "patrimonio_liquido", nome: "Patrimônio líquido", tipo: "R$" },
  { aba: "balanco", chave: "divida_bruta", nome: "Dívida bruta", tipo: "R$" },
  { aba: "balanco", chave: "divida_liquida", nome: "Dívida líquida", tipo: "R$" },
  { aba: "balanco", chave: "dl_ebitda", nome: "Dív. líquida/EBITDA", tipo: "x" },
];

const fmt = (v: number | null, tipo: string) => (v === null ? "—" : tipo === "R$" ? formatarMoeda(v) : formatarValor(v, tipo));

export function SecaoHistorico({ ticker }: { ticker: string }) {
  const [dados, setDados] = useState<Resposta | null>(null);
  const [aba, setAba] = useState<"resultado" | "balanco" | "lucro_cotacao">("resultado");
  const [anos, setAnos] = useState(5);

  useEffect(() => {
    fetch(`/api/acoes/${ticker}/historico?anos=10`).then((r) => (r.ok ? r.json() : null)).then(setDados)
      .catch(() => setDados(null));
  }, [ticker]);

  const serie = useMemo(() => (dados?.anos ?? []).slice(-anos), [dados, anos]);
  const opcao = useMemo(() => {
    const eixoX = { type: "category", data: serie.map((a) => String(a.ano)) };
    if (aba === "lucro_cotacao")
      return {
        grid: { left: 60, right: 52, top: 28, bottom: 28 }, legend: { top: 0 }, tooltip: { trigger: "axis" }, xAxis: eixoX,
        yAxis: [{ type: "value", axisLabel: { formatter: reaisCurto } },
          { type: "value", axisLabel: { formatter: (v: number) => `R$ ${v.toLocaleString("pt-BR")}` }, splitLine: { show: false } }],
        series: [
          { name: "Lucro líquido", type: "bar", data: serie.map((a) => a.lucro_liquido), tooltip: { valueFormatter: (v: unknown) => formatarMoeda(Number(v)) } },
          { name: "Cotação no fim do ano", type: "line", yAxisIndex: 1, data: serie.map((a) => a.cotacao_fim_ano), tooltip: { valueFormatter: reais } },
        ],
      };
    const barras = aba === "resultado" ? ["receita_liquida", "lucro_liquido"] : ["patrimonio_liquido", "divida_liquida"];
    const linha = aba === "resultado" ? "margem_liquida" : "dl_ebitda";
    const nome = (c: string) => LINHAS.find((l) => l.chave === c)!.nome;
    return {
      grid: { left: 60, right: 52, top: 28, bottom: 28 }, legend: { top: 0 }, tooltip: { trigger: "axis" }, xAxis: eixoX,
      yAxis: [{ type: "value", axisLabel: { formatter: reaisCurto } },
        { type: "value", axisLabel: { formatter: aba === "resultado" ? porcento : (v: number) => v.toLocaleString("pt-BR") }, splitLine: { show: false } }],
      series: [
        ...barras.map((c) => ({ name: nome(c), type: "bar", data: serie.map((a) => a[c]), tooltip: { valueFormatter: (v: unknown) => formatarMoeda(Number(v)) } })),
        { name: nome(linha), type: "line", yAxisIndex: 1, data: serie.map((a) => a[linha]),
          tooltip: { valueFormatter: aba === "resultado" ? porcento : (v: unknown) => Number(v).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) } },
      ],
    };
  }, [serie, aba]);

  if (!dados) return <p className="suave text-sm">Carregando demonstrações…</p>;
  if (dados.anos.length === 0) return <p className="suave text-sm">Nenhuma demonstração anual organizada para esta empresa.</p>;

  const ultimo = serie[serie.length - 1];
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {([["resultado", "Resultados (DRE)"], ["balanco", "Balanço"], ["lucro_cotacao", "Lucro × cotação"]] as const).map(([id, nome]) => (
          <button key={id} type="button" role="tab" aria-selected={aba === id} className="pilula" onClick={() => setAba(id)}>{nome}</button>
        ))}
        <span className="suave ml-2">Período:</span>
        {[5, 10].map((n) => (
          <button key={n} type="button" className="pilula" aria-pressed={anos === n} onClick={() => setAnos(n)}>{n} anos</button>
        ))}
      </div>
      <Grafico opcao={opcao} rotulo={`Histórico anual de ${ticker}`} />
      {aba !== "lucro_cotacao" && (
        <div className="cartao overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="suave">
              <tr className="text-right">
                <th className="px-3 py-2 text-left">Conta</th>
                {serie.map((a) => <th key={a.ano} className="px-3 py-2">{a.ano}</th>)}
              </tr>
            </thead>
            <tbody>
              {LINHAS.filter((l) => l.aba === aba).map((l) => (
                <tr key={l.chave} className="border-t text-right">
                  <td className="whitespace-nowrap px-3 py-1 text-left">{l.nome}</td>
                  {serie.map((a) => <td key={a.ano} className="whitespace-nowrap px-3 py-1">{fmt(a[l.chave], l.tipo)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="suave text-xs">
        {dados.observacao} Fonte: {nomeFonte(ultimo.fonte)}{ultimo.consolidado ? " (consolidado)" : " (individual)"}.
        {aba === "balanco" && dados.cagr_patrimonio !== null && ` Crescimento anual do patrimônio (CAGR): ${formatarValor(dados.cagr_patrimonio, "%")}.`}
      </p>
    </div>
  );
}
