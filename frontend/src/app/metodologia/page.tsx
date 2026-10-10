import Link from "next/link";
import { buscar } from "@/lib/api";
import type { Metrica } from "@/lib/tipos";

export const dynamic = "force-dynamic";

export default async function Metodologias() {
  const metricas = (await buscar<Metrica[]>("/metodologias")) ?? [];
  const grupos = Map.groupBy(metricas, (m) => m.grupo);
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Como é calculado</h1>
      {[...grupos.entries()].map(([grupo, lista]) => (
        <section key={grupo}>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide suave">{grupo}</h2>
          <ul className="cartao divide-y" style={{ borderColor: "var(--borda)" }}>
            {lista.map((m) => (
              <li key={m.id} className="flex flex-wrap justify-between gap-2 px-4 py-2 text-sm">
                <Link href={`/metodologia/${m.id}`} className="link">
                  {m.nome}
                  {m.aplica_a.includes("FII") && !m.aplica_a.includes("ACAO") ? " (FII)" : ""}
                </Link>
                <span className="suave">{m.formula}</span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
