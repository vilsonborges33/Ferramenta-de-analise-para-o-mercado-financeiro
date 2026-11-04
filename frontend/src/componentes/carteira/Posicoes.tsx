"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Grafico } from "@/componentes/Grafico";
import { formatarMoeda, formatarValor } from "@/lib/formato";

type Posicao = { ticker: string; classe: string; nome: string | null; setor: string | null; quantidade: number;
  preco_medio: number | null; preco_medio_ajustado: boolean; preco: number | null; valor: number | null;
  resultado_aberto: number | null; rentabilidade_aberta: number | null; resultado_realizado: number;
  proventos_recebidos: number; yield_on_cost: number | null; peso: number | null };
type Resumo = { posicoes: Posicao[]; encerradas: Posicao[]; total_valor: number; total_custo: number;
  resultado_aberto: number; resultado_realizado: number; proventos_recebidos: number;
  alocacao: Record<"ativo" | "classe" | "setor", Record<string, number>>; criterios: string };

const CORES = ["#2463b8", "#a86400", "#7a3fc4", "#c2410c", "#0f6b5c", "#6b7280", "#b42318", "#4fc3a9", "#9a5b00", "#3b82f6"];
const cor = (v: number | null) => (v === null ? undefined : v >= 0 ? "var(--destaque)" : "var(--negativo)");

export function Posicoes({ carteira, versao }: { carteira: number; versao: number }) {
  const [dados, setDados] = useState<Resumo | null>(null);
  const [por, setPor] = useState<"ativo" | "classe" | "setor">("ativo");
  const [recarregar, setRecarregar] = useState(0);

  useEffect(() => {
    fetch(`/api/carteiras/${carteira}/resumo`).then((r) => (r.ok ? r.json() : null)).then(setDados);
  }, [carteira, versao, recarregar]);

  const pizza = useMemo(() => ({
    tooltip: { trigger: "item", valueFormatter: (v: unknown) => formatarValor(Number(v), "%") },
    legend: { bottom: 0, type: "scroll" },
    series: [{ type: "pie", radius: ["45%", "70%"], top: -20, label: { show: false },
      data: Object.entries(dados?.alocacao[por] ?? {}).sort((a, b) => b[1] - a[1])
        .map(([nome, v], i) => ({ name: nome, value: v, itemStyle: { color: CORES[i % CORES.length] } })) }],
  }), [dados, por]);

  const ajustar = async (ticker: string, atual: number | null) => {
    const texto = window.prompt(`Preço médio de ${ticker} (deixe vazio para voltar ao calculado):`,
      atual?.toLocaleString("pt-BR") ?? "");
    if (texto === null) return;
    const n = texto.trim() ? Number(texto.replace(/\./g, "").replace(",", ".")) : null;
    await fetch(`/api/carteiras/${carteira}/preco-medio/${ticker}`, { method: "PUT",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ preco_medio: n, motivo: "ajuste manual" }) });
    setRecarregar((x) => x + 1);
  };

  if (!dados) return <p className="suave text-sm">Carregando…</p>;
  if (dados.posicoes.length === 0 && dados.encerradas.length === 0)
    return <p className="suave text-sm">Carteira vazia. Registre compras na aba Lançamentos ou importe o extrato da B3.</p>;
  const resultadoPct = dados.total_custo ? dados.total_valor / dados.total_custo - 1 : null;
  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 gap-3 text-sm lg:grid-cols-5">
        {[["Patrimônio", formatarMoeda(dados.total_valor)], ["Custo das posições", formatarMoeda(dados.total_custo)],
          ["Resultado em aberto", `${formatarMoeda(dados.resultado_aberto)} (${formatarValor(resultadoPct, "%")})`],
          ["Resultado realizado", formatarMoeda(dados.resultado_realizado)],
          ["Proventos recebidos", formatarMoeda(dados.proventos_recebidos)]].map(([r, v]) => (
          <div key={r} className="cartao p-3"><dt className="suave text-xs">{r}</dt><dd className="font-semibold">{v}</dd></div>
        ))}
      </dl>
      <div className="grid gap-4 lg:grid-cols-[1fr_20rem] [&>*]:min-w-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="suave"><tr className="text-right">
              <th className="px-2 py-1 text-left">Ativo</th><th className="px-2">Qtd.</th><th className="px-2">Preço médio</th>
              <th className="px-2">Cotação</th><th className="px-2">Valor</th><th className="px-2">Resultado</th>
              <th className="px-2">Peso</th><th className="px-2">Proventos</th><th className="px-2">Yield on cost</th>
            </tr></thead>
            <tbody>
              {dados.posicoes.map((p) => (
                <tr key={p.ticker} className="border-t text-right">
                  <td className="px-2 py-1 text-left"><Link href={`/${p.classe === "FII" ? "fiis" : "acoes"}/${p.ticker}`} className="link font-medium">{p.ticker}</Link>
                    <span className="suave block max-w-40 truncate text-xs">{p.setor}</span></td>
                  <td className="px-2">{p.quantidade.toLocaleString("pt-BR")}</td>
                  <td className="whitespace-nowrap px-2">
                    <button type="button" className="hover:underline" title="Ajustar o preço médio à mão" onClick={() => ajustar(p.ticker, p.preco_medio)}>
                      {formatarValor(p.preco_medio, "R$/ação")}{p.preco_medio_ajustado ? " ✎" : ""}
                    </button>
                  </td>
                  <td className="whitespace-nowrap px-2">{formatarValor(p.preco, "R$/ação")}</td>
                  <td className="whitespace-nowrap px-2">{p.valor === null ? "—" : formatarMoeda(p.valor)}</td>
                  <td className="whitespace-nowrap px-2" style={{ color: cor(p.rentabilidade_aberta) }}>{formatarValor(p.rentabilidade_aberta, "%")}</td>
                  <td className="px-2">{formatarValor(p.peso, "%")}</td>
                  <td className="whitespace-nowrap px-2">{formatarMoeda(p.proventos_recebidos)}</td>
                  <td className="px-2">{formatarValor(p.yield_on_cost, "%")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {dados.encerradas.length > 0 && (
            <p className="suave mt-2 text-xs">Posições encerradas: {dados.encerradas.map((e) => `${e.ticker} (${formatarMoeda(e.resultado_realizado)})`).join(", ")}.</p>
          )}
        </div>
        <div>
          <div className="flex gap-2 text-sm" role="tablist">
            {(["ativo", "classe", "setor"] as const).map((k) => (
              <button key={k} type="button" role="tab" aria-selected={por === k} className="pilula" onClick={() => setPor(k)}>Por {k}</button>
            ))}
          </div>
          <Grafico opcao={pizza} altura="h-64" rotulo="Alocação da carteira" />
        </div>
      </div>
      <p className="suave text-xs">{dados.criterios} Clique no preço médio para ajustá-lo à mão.</p>
    </div>
  );
}
