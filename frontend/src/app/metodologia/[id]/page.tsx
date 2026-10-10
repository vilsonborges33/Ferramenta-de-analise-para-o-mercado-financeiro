import { notFound } from "next/navigation";
import { buscar } from "@/lib/api";
import type { Metrica } from "@/lib/tipos";

export const dynamic = "force-dynamic";

export default async function Metodologia({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const m = await buscar<Metrica>(`/metodologias/${encodeURIComponent(id)}`);
  if (!m) notFound();
  return (
    <article className="cartao max-w-3xl space-y-4 p-5">
      <h1 className="text-xl font-semibold">{m.nome}</h1>
      <section>
        <h2 className="text-sm font-semibold suave">Fórmula</h2>
        <p className="mt-1 font-mono text-sm">{m.formula}</p>
      </section>
      <section>
        <h2 className="text-sm font-semibold suave">Referência</h2>
        <p className="mt-1 text-sm">{m.referencia}</p>
      </section>
      {m.parametros.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold suave">Parâmetros padrão</h2>
          <ul className="mt-1 list-disc pl-5 text-sm">
            {m.parametros.map((p) => (
              <li key={p.chave}>
                {p.descricao}: {p.padrao.toLocaleString("pt-BR")} (de {p.minimo.toLocaleString("pt-BR")} a{" "}
                {p.maximo.toLocaleString("pt-BR")})
              </li>
            ))}
          </ul>
        </section>
      )}
      <section>
        <h2 className="text-sm font-semibold suave">Limitações</h2>
        <ul className="mt-1 list-disc pl-5 text-sm">
          {m.limitacoes.map((l) => (
            <li key={l}>{l}</li>
          ))}
          <li>Quando algum insumo falta, o indicador aparece como &quot;dado indisponível&quot;, com o motivo.</li>
        </ul>
      </section>
    </article>
  );
}
