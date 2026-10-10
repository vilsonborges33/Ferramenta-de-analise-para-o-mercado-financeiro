import { notFound } from "next/navigation";
import { PaginaAtivo } from "@/componentes/PaginaAtivo";
import { buscar } from "@/lib/api";
import type { Detalhe } from "@/lib/tipos";

export const dynamic = "force-dynamic";

export default async function Acao({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params;
  const ativo = await buscar<Detalhe>(`/acoes/${encodeURIComponent(ticker)}`);
  if (!ativo) notFound();
  return <PaginaAtivo ativo={ativo} />;
}
