import { TabelaAtivos } from "@/componentes/TabelaAtivos";
import { buscar } from "@/lib/api";
import type { ItemLista } from "@/lib/tipos";

export const dynamic = "force-dynamic";

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

export default async function Acoes() {
  const itens = (await buscar<ItemLista[]>("/acoes")) ?? [];
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Ações</h1>
      <TabelaAtivos itens={itens} colunas={COLUNAS} base="acoes" />
    </div>
  );
}
