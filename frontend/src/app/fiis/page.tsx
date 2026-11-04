import Link from "next/link";
import { BuscaAtivos } from "@/componentes/BuscaAtivos";

const COLUNAS = [
  { id: "fii.p_vp", rotulo: "P/VP" },
  { id: "basico.dy", rotulo: "DY (proventos)" },
  { id: "fii.dy_informado_12m", rotulo: "DY informado 12m" },
  { id: "fii.patrimonio_liquido", rotulo: "Patrimônio" },
  { id: "fii.numero_cotistas", rotulo: "Cotistas" },
  { id: "basico.liquidez_diaria", rotulo: "Liquidez" },
];

export default function Fiis() {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <h1 className="text-2xl font-semibold">Fundos imobiliários</h1>
        <Link href="/fiis/ranking" className="link text-sm">Ver o ranking de FIIs com filtros →</Link>
      </div>
      <BuscaAtivos base="fiis" colunas={COLUNAS} exemplo="HGLG11" />
    </div>
  );
}
