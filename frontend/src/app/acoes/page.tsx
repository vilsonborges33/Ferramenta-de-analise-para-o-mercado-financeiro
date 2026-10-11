import Link from "next/link";
import { BuscaAtivos } from "@/componentes/BuscaAtivos";

const COLUNAS = [
  { id: "basico.p_l", rotulo: "P/L" },
  { id: "basico.p_vp", rotulo: "P/VP" },
  { id: "basico.dy", rotulo: "DY" },
  { id: "basico.roe", rotulo: "ROE" },
  { id: "basico.margem_liquida", rotulo: "Marg. líq." },
  { id: "basico.ev_ebitda", rotulo: "EV/EBITDA" },
  { id: "basico.dl_ebitda", rotulo: "DL/EBITDA" },
  { id: "basico.liquidez_diaria", rotulo: "Liquidez" },
];

export default function Acoes() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Ações</h1>
      <BuscaAtivos base="acoes" colunas={COLUNAS} exemplo="PETR4 ou Petrobras" />
      <p className="text-sm suave">
        Para ver a lista de ações ordenada por desconto, use{" "}
        <Link href="/mais-baratas" className="link">
          Mais baratas
        </Link>
        .
      </p>
    </div>
  );
}
