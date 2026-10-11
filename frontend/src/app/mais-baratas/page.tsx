"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { formatarData, formatarMoeda, formatarValor } from "@/lib/formato";

type Metodo = "greenblatt" | "graham" | "bazin" | "lynch";

type Item = {
  posicao: number;
  ticker: string;
  nome: string | null;
  preco: number | null;
  data_preco: string | null;
  liquidez_diaria: number | null;
  valor_justo: number | null;
  desconto: number | null;
  earnings_yield?: number | null;
  retorno_capital?: number | null;
  soma_posicoes?: number;
  dividend_yield?: number | null;
  crescimento_lucro?: number | null;
  peg?: number | null;
  aviso?: string | null;
};

type Resposta = {
  aviso: string;
  total_avaliados: number;
  total_no_ranking: number;
  excluidos: Record<string, number>;
  itens: Item[];
};

const METODOS: { id: Metodo; nome: string; livro: string; criterio: string; metodologia: string }[] = [
  {
    id: "greenblatt", nome: "Fórmula Mágica", livro: "Joel Greenblatt",
    criterio: "Menor soma das posições em earnings yield (EBIT/EV) e retorno sobre capital.",
    metodologia: "greenblatt.ranking",
  },
  {
    id: "graham", nome: "Graham", livro: "Benjamin Graham",
    criterio: "Maior desconto da cotação em relação a √(fator × LPA × VPA).",
    metodologia: "graham.valor_intrinseco",
  },
  {
    id: "bazin", nome: "Bazin", livro: "Décio Bazin",
    criterio: "Maior desconto em relação ao preço teto = dividendos de 12 meses ÷ yield mínimo.",
    metodologia: "bazin.preco_teto",
  },
  {
    id: "lynch", nome: "Peter Lynch", livro: "Peter Lynch",
    criterio: "Maior desconto em relação ao preço justo = LPA × crescimento do lucro (PEG = 1).",
    metodologia: "lynch.preco_justo",
  },
];

const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : formatarValor(v, "%"));

export default function MaisBaratas() {
  const [metodo, setMetodo] = useState<Metodo>("greenblatt");
  const [liquidez, setLiquidez] = useState(1);
  const [yieldBazin, setYieldBazin] = useState(6);
  const [fatorGraham, setFatorGraham] = useState(22.5);
  const [fatorLynch, setFatorLynch] = useState(1);
  const [incluirUtilities, setIncluirUtilities] = useState(false);
  const [dados, setDados] = useState<Resposta | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    const parametros = new URLSearchParams({
      metodo,
      liquidez_minima: String(liquidez * 1_000_000),
      yield_bazin: String(yieldBazin / 100),
      fator_graham: String(fatorGraham),
      fator_lynch: String(fatorLynch),
      excluir_utilities: String(!incluirUtilities),
    });
    const controle = new AbortController();
    const espera = setTimeout(async () => {
      try {
        const r = await fetch(`/api/ranking/acoes?${parametros}`, { signal: controle.signal });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        setDados(await r.json());
        setErro(null);
      } catch (e) {
        if ((e as Error).name !== "AbortError") setErro("Não foi possível calcular o ranking.");
      }
    }, 300);
    return () => {
      clearTimeout(espera);
      controle.abort();
    };
  }, [metodo, liquidez, yieldBazin, fatorGraham, fatorLynch, incluirUtilities]);

  const info = METODOS.find((m) => m.id === metodo)!;
  const campo = "cartao w-24 px-2 py-1 text-right";

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Ações mais baratas</h1>
        <p className="suave text-sm">Ranking pelo método de cada livro, com os parâmetros que você escolher.</p>
      </div>

      <p className="cartao p-3 text-sm" style={{ color: "var(--alerta)" }} role="note">
        {dados?.aviso ??
          "Resultados calculados a partir de dados públicos e dos parâmetros escolhidos. Não constituem recomendação de investimento."}
      </p>

      <div className="flex flex-wrap gap-2" role="tablist">
        {METODOS.map((m) => (
          <button
            key={m.id}
            role="tab"
            aria-selected={metodo === m.id}
            onClick={() => setMetodo(m.id)}
            className="rounded-full border px-3 py-1 text-sm"
            style={metodo === m.id ? { background: "var(--destaque)", color: "white", borderColor: "var(--destaque)" } : {}}
          >
            {m.nome}
          </button>
        ))}
      </div>

      <div className="cartao space-y-3 p-4 text-sm">
        <p>
          <span className="font-medium">{info.livro}:</span> {info.criterio}{" "}
          <Link href={`/metodologia/${info.metodologia}`} className="link">
            Como é calculado
          </Link>
        </p>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <label className="flex items-center gap-2">
            Liquidez mínima (R$ mi/dia)
            <input type="number" min={0} step={0.5} value={liquidez} onChange={(e) => setLiquidez(Number(e.target.value))} className={campo} />
          </label>
          {metodo === "bazin" && (
            <label className="flex items-center gap-2">
              Yield mínimo (%)
              <input type="number" min={1} max={30} step={0.5} value={yieldBazin} onChange={(e) => setYieldBazin(Number(e.target.value))} className={campo} />
            </label>
          )}
          {metodo === "graham" && (
            <label className="flex items-center gap-2">
              Fator de Graham
              <input type="number" min={1} max={100} step={0.5} value={fatorGraham} onChange={(e) => setFatorGraham(Number(e.target.value))} className={campo} />
            </label>
          )}
          {metodo === "lynch" && (
            <label className="flex items-center gap-2">
              Multiplicador do P/L justo
              <input type="number" min={0.1} max={5} step={0.1} value={fatorLynch} onChange={(e) => setFatorLynch(Number(e.target.value))} className={campo} />
            </label>
          )}
          {metodo === "greenblatt" && (
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={incluirUtilities} onChange={(e) => setIncluirUtilities(e.target.checked)} />
              Incluir energia elétrica e saneamento
            </label>
          )}
        </div>
      </div>

      {erro && <p style={{ color: "var(--alerta)" }}>{erro}</p>}

      {dados && (
        <>
          <p className="text-xs suave">
            {dados.total_no_ranking} de {dados.total_avaliados} ações no ranking.
            {Object.keys(dados.excluidos).length > 0 &&
              " Fora do ranking: " +
                Object.entries(dados.excluidos)
                  .map(([motivo, n]) => `${n} por ${motivo}`)
                  .join("; ") +
                "."}
          </p>
          <div className="cartao overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="suave">
                <tr className="text-right">
                  <th className="px-3 py-2 text-left">#</th>
                  <th className="px-3 py-2 text-left">Ação</th>
                  <th className="px-3 py-2">Cotação</th>
                  {metodo === "greenblatt" ? (
                    <>
                      <th className="px-3 py-2">Earnings yield</th>
                      <th className="px-3 py-2">Retorno s/ capital</th>
                      <th className="px-3 py-2">Soma posições</th>
                    </>
                  ) : (
                    <>
                      <th className="px-3 py-2">{metodo === "bazin" ? "Preço teto" : metodo === "lynch" ? "Preço justo" : "Valor intrínseco"}</th>
                      <th className="px-3 py-2">Desconto</th>
                      {metodo === "bazin" && <th className="px-3 py-2">DY</th>}
                      {metodo === "lynch" && (
                        <>
                          <th className="px-3 py-2">Cresc. lucro</th>
                          <th className="px-3 py-2">PEG</th>
                        </>
                      )}
                    </>
                  )}
                  <th className="px-3 py-2">Liquidez</th>
                </tr>
              </thead>
              <tbody>
                {dados.itens.map((i) => (
                  <tr key={i.ticker} className="border-t text-right">
                    <td className="px-3 py-2 text-left suave">{i.posicao}</td>
                    <td className="px-3 py-2 text-left">
                      <Link href={`/acoes/${i.ticker}`} className="link font-medium">
                        {i.ticker}
                      </Link>
                      {i.aviso && (
                        <span title={i.aviso} style={{ color: "var(--alerta)" }} className="ml-1">
                          !
                        </span>
                      )}
                      <div className="suave max-w-48 truncate text-xs">{i.nome}</div>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2" title={i.data_preco ? `fechamento de ${formatarData(i.data_preco)}` : ""}>
                      {formatarValor(i.preco, "R$/ação")}
                    </td>
                    {metodo === "greenblatt" ? (
                      <>
                        <td className="px-3 py-2">{pct(i.earnings_yield)}</td>
                        <td className="px-3 py-2">{pct(i.retorno_capital)}</td>
                        <td className="px-3 py-2">{i.soma_posicoes}</td>
                      </>
                    ) : (
                      <>
                        <td className="whitespace-nowrap px-3 py-2">{formatarValor(i.valor_justo, "R$/ação")}</td>
                        <td className="px-3 py-2" style={{ color: (i.desconto ?? 0) >= 0 ? "var(--destaque)" : "var(--alerta)" }}>
                          {pct(i.desconto)}
                        </td>
                        {metodo === "bazin" && <td className="px-3 py-2">{pct(i.dividend_yield)}</td>}
                        {metodo === "lynch" && (
                          <>
                            <td className="px-3 py-2">{pct(i.crescimento_lucro)}</td>
                            <td className="px-3 py-2">{formatarValor(i.peg ?? null, "x")}</td>
                          </>
                        )}
                      </>
                    )}
                    <td className="whitespace-nowrap px-3 py-2">{i.liquidez_diaria ? formatarMoeda(i.liquidez_diaria) : "—"}</td>
                  </tr>
                ))}
                {dados.itens.length === 0 && (
                  <tr>
                    <td colSpan={9} className="suave px-3 py-6 text-center">
                      Nenhuma ação com dados suficientes para este método. Veja os motivos acima ou a página{" "}
                      <Link href="/status" className="link">
                        Status dos dados
                      </Link>
                      .
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
