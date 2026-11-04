import Link from "next/link";
import { BuscaAtivos } from "@/componentes/BuscaAtivos";

const COLUNAS = [
  { id: "basico.p_l", rotulo: "P/L" },
  { id: "basico.p_vp", rotulo: "P/VP" },
  { id: "basico.dy", rotulo: "DY" },
  { id: "basico.roe", rotulo: "ROE" },
  { id: "basico.margem_liquida", rotulo: "Marg. líq." },
  { id: "basico.dl_ebitda", rotulo: "DL/EBITDA" },
  { id: "basico.liquidez_diaria", rotulo: "Liquidez" },
];

export default function Eua() {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <h1 className="text-2xl font-semibold">Mercado dos EUA</h1>
        <Link href="/mais-baratas?mercado=EUA" className="link text-sm">Ranking de ações e REITs dos EUA →</Link>
      </div>
      <p className="suave text-sm">
        Ações, REITs e ETFs com as mesmas metodologias, em dólares. Balanços da SEC (EDGAR); cotações e dividendos do
        Yahoo Finance. A lista acompanhada fica no arquivo .env (TICKERS_EUA e ETFS_EUA).
      </p>
      <BuscaAtivos base="eua" colunas={COLUNAS} exemplo="AAPL, O ou SPY" />
    </div>
  );
}
