import Link from "next/link";
import { ArteHero, EmblemaMetodo, Icone } from "@/componentes/Arte";
import { Monograma } from "@/componentes/Monograma";
import { buscar } from "@/lib/api";
import { formatarData } from "@/lib/formato";
import { buscarPainel, formatarMacro, pct, type GrupoVariacoes } from "@/lib/painel";

type ItemRanking = { ticker: string; nome: string | null; preco: number | null; valor_justo: number | null;
  desconto: number | null; posicao: number };
type Ranking = { itens: ItemRanking[]; total_no_ranking: number };

const METODOS = [
  { id: "greenblatt", nome: "Fórmula Mágica", autor: "Joel Greenblatt", texto: "Earnings yield + retorno sobre capital" },
  { id: "graham", nome: "Valor intrínseco", autor: "Benjamin Graham", texto: "√(22,5 × LPA × VPA)" },
  { id: "bazin", nome: "Preço teto", autor: "Décio Bazin", texto: "Dividendos ÷ yield mínimo de 6%" },
  { id: "lynch", nome: "Preço justo", autor: "Peter Lynch", texto: "P/L justo = crescimento (PEG 1)" },
] as const;

const FERRAMENTAS = [
  ["/ferramentas/juros-compostos", "Juros compostos", "Quanto um aporte vira com o tempo.", "juros"],
  ["/ferramentas/conversor-taxas", "Conversor de taxas", "Diária, mensal e anual equivalentes.", "conversor"],
  ["/ferramentas/aposentadoria", "Plano de aposentadoria", "Aporte para viver de dividendos.", "aposentadoria"],
  ["/comparar", "Comparador", "Até 4 ativos lado a lado.", "comparador"],
  ["/longo-prazo", "Longo prazo", "Retorno real e CAPE (Siegel).", "longoPrazo"],
  ["/carteira", "Carteira", "Rentabilidade, proventos e Markowitz.", "carteira"],
] as const;

async function ranking(metodo: string): Promise<Ranking | null> {
  try {
    return await buscar<Ranking>(`/ranking/acoes?metodo=${metodo}&limite=5`);
  } catch {
    return null;
  }
}

function Variacoes({ titulo, grupo, base }: { titulo: string; grupo: GrupoVariacoes; base: string }) {
  const largura = grupo.total ? (grupo.positivas / grupo.total) * 100 : 50;
  return (
    <div className="cartao p-4">
      <div className="flex items-baseline justify-between">
        <h2 className="font-semibold">{titulo}</h2>
        <span className="text-xs suave">{grupo.positivas} sobem · {grupo.negativas} caem</span>
      </div>
      <div className="mt-2 flex h-1.5 overflow-hidden rounded-full" title="Amplitude: ativos em alta × em queda">
        <div style={{ width: `${largura}%`, background: "var(--positivo)" }} />
        <div className="flex-1" style={{ background: "var(--negativo)" }} />
      </div>
      <div className="mt-3 grid gap-4 sm:grid-cols-2">
        {(["altas", "baixas"] as const).map((lado) => (
          <div key={lado}>
            <div className="rotulo mb-1">{lado === "altas" ? "Maiores altas" : "Maiores baixas"}</div>
            <ul className="divide-y">
              {grupo[lado].map((x) => (
                <li key={x.ticker}>
                  <Link href={`/${base}/${x.ticker}`} className="flex items-center gap-2 py-1.5 text-sm hover:underline">
                    <Monograma ticker={x.ticker} classe={x.classe} tamanho={22} />
                    <span className="ticker flex-1 font-semibold">{x.ticker}</span>
                    <span className="mono suave">{x.fechamento.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                    <span className={`variacao mono ${x.variacao >= 0 ? "positivo" : "negativo"}`}>{pct(x.variacao)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

export default async function Inicio() {
  const [painel, ...rankings] = await Promise.all([buscarPainel(), ...METODOS.map((m) => ranking(m.id))]);
  return (
    <div className="space-y-6">
      <section className="cartao fundo-grade relative overflow-hidden">
        <div className="grid items-center gap-4 p-6 lg:grid-cols-[1.05fr_1fr] lg:p-8">
          <div className="space-y-4">
            <div className="rotulo" style={{ color: "var(--destaque)" }}>Análise fundamentalista · B3 e EUA</div>
            <h1 className="text-3xl font-bold leading-tight sm:text-4xl">
              Preço é o que você paga.<br />
              <span style={{ color: "var(--ouro)" }}>Valor</span> é o que você calcula.
            </h1>
            <p className="max-w-xl suave">
              Indicadores, rankings e valuation pelos métodos de Graham, Bazin, Lynch, Greenblatt, Damodaran e outros —
              cada número com a fórmula, o livro que a fundamenta e a fonte oficial do dado (CVM, B3, Banco Central, SEC).
            </p>
            <div className="flex flex-wrap gap-2">
              <Link href="/mais-baratas" className="botao">Ranking de ações <Icone nome="seta" tamanho={16} /></Link>
              <Link href="/fiis/ranking" className="pilula px-4 py-2 font-medium">Ranking de FIIs</Link>
              <Link href="/metodologia" className="pilula px-4 py-2 font-medium">Como é calculado</Link>
            </div>
          </div>
          <ArteHero className="w-full" />
        </div>
      </section>

      {painel && painel.macro.length > 0 && (
        <section aria-label="Indicadores de mercado" className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          {painel.macro.map((m) => (
            <div key={m.id} className="cartao cartao-kpi p-3" title={`${m.fonte} — referência ${formatarData(m.data)}`}>
              <div className="rotulo">{m.rotulo}</div>
              <div className="mono mt-1.5 text-xl font-semibold">{formatarMacro(m)}</div>
              <div className="mt-0.5 flex items-center justify-between text-[0.7rem] suave">
                <span>{formatarData(m.data)}</span>
                {m.variacao !== null && m.variacao !== 0 && (
                  <span className={m.variacao > 0 ? "positivo" : "negativo"}>{pct(m.variacao)}</span>
                )}
              </div>
            </div>
          ))}
        </section>
      )}

      {painel?.variacoes.data && (
        <section className="space-y-2">
          <div className="flex items-baseline justify-between">
            <h2 className="text-lg font-semibold">Último pregão</h2>
            <span className="text-xs suave">
              {formatarData(painel.variacoes.data)} · {painel.variacoes.fonte} · só ativos com liquidez relevante
            </span>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Variacoes titulo="Ações" grupo={painel.variacoes.acoes} base="acoes" />
            <Variacoes titulo="Fundos imobiliários" grupo={painel.variacoes.fiis} base="fiis" />
          </div>
        </section>
      )}

      <section className="space-y-2">
        <div className="flex items-baseline justify-between">
          <h2 className="text-lg font-semibold">Os 5 primeiros de cada método</h2>
          <Link href="/mais-baratas" className="link text-sm">Ver ranking completo →</Link>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {METODOS.map((m, i) => {
            const r = rankings[i];
            return (
              <div key={m.id} className={`cartao metodo-${m.id} p-4`}>
                <div className="flex items-center gap-3">
                  <EmblemaMetodo metodo={m.id} />
                  <div>
                    <div className="font-semibold texto-metodo">{m.nome}</div>
                    <div className="text-xs suave">{m.autor} · {m.texto}</div>
                  </div>
                </div>
                <ol className="mt-3 divide-y text-sm">
                  {(r?.itens ?? []).map((x) => (
                    <li key={x.ticker}>
                      <Link href={`/acoes/${x.ticker}`} className="flex items-center gap-2 py-1.5 hover:underline">
                        <span className="mono w-4 text-xs suave">{x.posicao}</span>
                        <span className="ticker flex-1 font-semibold">{x.ticker}</span>
                        {x.desconto !== null ? (
                          <span className={`mono text-xs ${x.desconto >= 0 ? "positivo" : "negativo"}`}
                            title="Margem de segurança: (valor justo − preço) ÷ valor justo">
                            margem {pct(x.desconto, false)}
                          </span>
                        ) : (
                          <span className="mono text-xs suave">{x.preco?.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</span>
                        )}
                      </Link>
                    </li>
                  ))}
                  {!r && <li className="py-2 suave">Ranking indisponível.</li>}
                </ol>
              </div>
            );
          })}
        </div>
        <p className="text-xs" style={{ color: "var(--alerta)" }}>
          Rankings com os parâmetros padrão de cada livro (liquidez mínima R$ 1 mi/dia, sem financeiras e utilities).
          São cálculos sobre dados públicos e não constituem recomendação de investimento.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Ferramentas</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {FERRAMENTAS.map(([href, titulo, texto, icone]) => (
            <Link key={href} href={href} className="cartao group flex items-center gap-3 p-4 transition-colors hover:border-[var(--destaque)]">
              <span className="grid h-10 w-10 place-items-center rounded-lg"
                style={{ background: "color-mix(in srgb, var(--destaque) 12%, transparent)", color: "var(--destaque)" }}>
                <Icone nome={icone} tamanho={20} />
              </span>
              <span className="flex-1">
                <span className="block font-medium">{titulo}</span>
                <span className="block text-sm suave">{texto}</span>
              </span>
              <span className="suave transition-transform group-hover:translate-x-0.5"><Icone nome="seta" tamanho={16} /></span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
