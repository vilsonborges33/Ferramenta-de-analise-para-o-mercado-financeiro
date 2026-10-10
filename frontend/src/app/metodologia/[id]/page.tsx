import { notFound } from "next/navigation";
import { buscar } from "@/lib/api";
import type { Metrica } from "@/lib/tipos";

/** Parâmetros em fração (taxas, yields, alíquotas) aparecem em %; os demais como número. */
function formatarParametro(valor: number, chave: string): string {
  const percentual = /taxa_livre|yield|aliquota|limite/.test(chave);
  return percentual
    ? `${(valor * 100).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%`
    : valor.toLocaleString("pt-BR");
}

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
      {m.premissas.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold suave">Premissas</h2>
          <ul className="mt-1 list-disc pl-5 text-sm">
            {m.premissas.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </section>
      )}
      {m.parametros.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold suave">Parâmetros padrão</h2>
          <ul className="mt-1 list-disc pl-5 text-sm">
            {m.parametros.map((p) => (
              <li key={p.chave}>
                {p.descricao}: {formatarParametro(p.padrao, p.chave)} (de {formatarParametro(p.minimo, p.chave)} a {formatarParametro(p.maximo, p.chave)})
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
