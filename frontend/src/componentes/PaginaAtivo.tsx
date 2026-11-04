import Link from "next/link";
import { BotaoFavorito } from "@/componentes/BotaoFavorito";
import { CartoesRisco } from "@/componentes/CartoesRisco";
import { PainelValuation } from "@/componentes/PainelValuation";
import { SecaoDividendos } from "@/componentes/SecaoDividendos";
import { SecaoHistorico } from "@/componentes/SecaoHistorico";
import { PainelGordonFii, SecoesFundo } from "@/componentes/SecoesFundo";
import { CustosEtf } from "@/componentes/CustosEtf";
import { GraficoCotacao } from "@/componentes/GraficoCotacao";
import { MoedaProvider } from "@/lib/moeda";
import { Numero } from "@/componentes/Numero";
import { formatarData, formatarValor, nomeFonte } from "@/lib/formato";
import type { Detalhe } from "@/lib/tipos";

const METODOS_DE_PRECO = ["Graham", "Bazin", "Lynch", "Greenblatt"];
const DESTAQUES = ["basico.roe", "basico.p_l", "basico.dy", "basico.liquidez_diaria"];
const DESTAQUES_REIT = ["reit.p_ffo", "basico.dy", "reit.payout_ffo", "basico.liquidez_diaria"];
const DESTAQUES_ETF = ["basico.dy", "basico.liquidez_diaria"];
const SECOES_ETF = [["cotacao", "Cotação"], ["custos", "Custos"], ["dividendos", "Dividendos"],
  ["indicadores", "Indicadores"]] as const;
const DESTAQUES_FII = ["fii.p_vp", "basico.dy", "fii.vacancia", "fii.alavancagem"];
const SECOES_FII = [
  ["cotacao", "Cotação"], ["valuation", "Valuation"], ["dividendos", "Rendimentos"], ["indicadores", "Indicadores"],
  ["composicao", "Composição"], ["endividamento", "Endividamento"], ["imoveis", "Imóveis"], ["historico", "Histórico"],
  ["documentos", "Documentos"], ["empresa", "Fundo"],
] as const;
const SECOES_ACAO = [
  ["cotacao", "Cotação"], ["valuation", "Valuation"], ["dividendos", "Dividendos"], ["indicadores", "Indicadores"],
  ["historico", "Histórico"], ["empresa", "Empresa"],
] as const;
const ORDEM_GRUPOS = ["Valuation", "REIT", "Graham", "Bazin", "Lynch", "Greenblatt", "Rentabilidade", "Endividamento",
  "Crescimento", "Mercado", "Base"];

function Secao({ id, titulo, children }: { id: string; titulo: string; children: React.ReactNode }) {
  return (
    <section id={id} className="cartao scroll-mt-16 space-y-3 p-4">
      <h2 className="font-semibold">{titulo}</h2>
      {children}
    </section>
  );
}

export function PaginaAtivo({ ativo }: { ativo: Detalhe }) {
  const fii = ativo.classe === "FII";
  const etf = ativo.classe === "ETF";
  const eua = ativo.mercado === "US";
  const acao = !fii && !etf; // ações da B3, ações e REITs dos EUA
  const moeda = ativo.moeda ?? "BRL";
  const grupos = Object.entries(ativo.grupos)
    .filter(([grupo]) => !(acao && METODOS_DE_PRECO.includes(grupo))) // nas ações, os métodos ficam no painel de valuation
    .sort(([a], [b]) => ORDEM_GRUPOS.indexOf(a) - ORDEM_GRUPOS.indexOf(b));
  const todos = Object.values(ativo.grupos).flat();
  const destaques = (fii ? DESTAQUES_FII : etf ? DESTAQUES_ETF : ativo.classe === "REIT" ? DESTAQUES_REIT : DESTAQUES)
    .map((id) => todos.find((n) => n.metrica === id))
    .filter((n) => n !== undefined);
  const secoes = acao ? SECOES_ACAO : fii ? SECOES_FII : SECOES_ETF;
  const fichas: [string, string | undefined][] = [
    ["CNPJ", ativo.cnpj],
    [eua ? "Setor (SEC)" : "Setor (CVM)", ativo.setor],
    ["Mercado", eua ? "EUA (valores em US$)" : undefined],
    ["Segmento de listagem", ativo.segmento_listagem],
    ["Segmento", ativo.segmento],
    ["Mandato", ativo.mandato],
    ["Gestão", ativo.tipo_gestao],
    ["Administrador", ativo.administrador],
    ["Código ISIN", ativo.isin],
  ];
  return (
    <MoedaProvider moeda={moeda}>
    <div className="space-y-5">
      <div>
        <div className="suave text-xs">
          <Link href={eua ? "/eua" : fii ? "/fiis" : "/acoes"} className="hover:underline">
            {eua ? "EUA" : fii ? "FIIs" : "Ações"}</Link> › {ativo.ticker}
        </div>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold">{ativo.ticker}</h1>
              <BotaoFavorito ticker={ativo.ticker} />
            </div>
            <div className="suave">{ativo.nome}</div>
            <div className="mt-1 flex flex-wrap gap-2 text-xs">
              {ativo.setor && <span className="pilula">{ativo.setor}</span>}
              {ativo.segmento_listagem && <span className="pilula">{ativo.segmento_listagem}</span>}
              {ativo.outros_tickers && ativo.outros_tickers.length > 0 && (
                <span className="suave self-center">
                  Outras classes:{" "}
                  {ativo.outros_tickers.map((t) => (
                    <Link key={t} href={`/acoes/${t}`} className="link mr-2">{t}</Link>
                  ))}
                </span>
              )}
            </div>
          </div>
          {ativo.cotacao && (
            <div className="text-right">
              <div className="text-2xl font-semibold">{formatarValor(ativo.cotacao.valor, "R$/ação", moeda)}</div>
              <div className="text-xs suave">
                fechamento de {formatarData(ativo.cotacao.data)} · {nomeFonte(ativo.cotacao.fonte)}
              </div>
            </div>
          )}
        </div>
      </div>

      <nav aria-label="Seções" className="sticky top-0 z-10 -mx-4 flex gap-2 overflow-x-auto px-4 py-2 text-sm"
        style={{ background: "var(--fundo)" }}>
        {secoes.map(([id, nome]) => (
          <a key={id} href={`#${id}`} className="pilula whitespace-nowrap">{nome}</a>
        ))}
      </nav>

      {ativo.tipo_plano_contas && ativo.tipo_plano_contas !== "geral" && (
        <p className="cartao p-3 text-sm" style={{ color: "var(--alerta)" }}>
          Instituição financeira/seguradora: indicadores baseados em EBIT, dívida e capital de giro não se aplicam.
        </p>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {destaques.map((n) => (
          <div key={n.metrica} className="cartao p-3">
            <div className="text-xs suave">{n.nome}</div>
            <div className="mt-1 text-lg font-semibold"><Numero compacto numero={n} /></div>
          </div>
        ))}
        <CartoesRisco ticker={ativo.ticker} />
      </div>

      <Secao id="cotacao" titulo="Cotação">
        <GraficoCotacao ticker={ativo.ticker} />
      </Secao>

      {fii && (
        <Secao id="valuation" titulo="Valuation — preço teto pelo Gordon ajustado">
          <PainelGordonFii ticker={ativo.ticker} />
        </Secao>
      )}

      {acao && (
        <Secao id="valuation" titulo="Valuation pelos livros">
          <PainelValuation ticker={ativo.ticker} />
          <Link href={`/valuation/${ativo.ticker}`} className="link inline-block text-sm">
            Valuation completo: DCF, Gordon, múltiplos do setor e cenários salvos →
          </Link>
        </Secao>
      )}

      {etf && (
        <Secao id="custos" titulo="Custos do ETF (Bogle)">
          <CustosEtf ticker={ativo.ticker} />
        </Secao>
      )}

      <Secao id="dividendos" titulo={fii ? "Rendimentos" : "Dividendos"}>
        <SecaoDividendos ticker={ativo.ticker} />
      </Secao>

      <Secao id="indicadores" titulo="Indicadores">
        <div className="space-y-2">
          {grupos.map(([grupo, numeros], i) => (
            <details key={grupo} open={i < 3} className="rounded-lg border">
              <summary className="cursor-pointer px-3 py-2 font-medium">{grupo}</summary>
              {METODOS_DE_PRECO.includes(grupo) && (
                <p className="px-3 text-xs" style={{ color: "var(--alerta)" }}>
                  Valor calculado com os parâmetros padrão do método; não constitui recomendação de investimento.
                </p>
              )}
              <div className="grid grid-cols-2 gap-3 p-3 sm:grid-cols-3 lg:grid-cols-5">
                {numeros.map((n) => (
                  <div key={n.metrica} className="rounded-lg p-2" style={{ background: "var(--fundo)" }}>
                    <div className="text-xs suave">{n.nome}</div>
                    <div className="mt-1 text-base font-medium"><Numero numero={n} /></div>
                  </div>
                ))}
              </div>
            </details>
          ))}
        </div>
      </Secao>

      {fii && <SecoesFundo ticker={ativo.ticker} />}

      {acao && (
        <Secao id="historico" titulo="Histórico anual">
          <SecaoHistorico ticker={ativo.ticker} />
        </Secao>
      )}

      <Secao id="empresa" titulo={acao ? "Sobre a empresa" : "Sobre o fundo"}>
        <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
          {fichas
            .filter(([, v]) => v)
            .map(([rotulo, valor]) => (
              <div key={rotulo} className="flex justify-between gap-3 border-b py-1">
                <dt className="suave">{rotulo}</dt>
                <dd className="text-right">{valor}</dd>
              </div>
            ))}
        </dl>
      </Secao>
    </div>
    </MoedaProvider>
  );
}
