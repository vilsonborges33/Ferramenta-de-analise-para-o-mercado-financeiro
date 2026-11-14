import type { Metadata } from "next";
import Link from "next/link";
import { NOME_PRODUTO } from "@/componentes/Arte";
import { Conta } from "@/componentes/Conta";
import { BotaoMenu, BotaoTema, BuscaRapida, MenuLateral } from "@/componentes/Navegacao";
import { buscarPainel, formatarMacro, pct, type Painel } from "@/lib/painel";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: `${NOME_PRODUTO} — Análise de Ações e FIIs`, template: `%s · ${NOME_PRODUTO}` },
  description: "Indicadores fundamentalistas calculados a partir de dados oficiais (CVM, B3, Banco Central).",
};

// Aplica o tema salvo antes da primeira pintura (evita piscar claro→escuro).
const SCRIPT_TEMA = `try{var t=localStorage.getItem("tema");if(t)document.documentElement.dataset.tema=t}catch(e){}`;

/** Ações e FIIs da faixa: os mais negociados do pregão e depois as maiores altas e baixas, sem repetir ticker. */
function cotacoesDaFaixa(painel: Painel) {
  const v = painel.variacoes;
  const vistos = new Set<string>();
  return [...(v.mais_negociadas ?? []), ...v.acoes.altas.slice(0, 4), ...v.acoes.baixas.slice(0, 4), ...v.fiis.altas.slice(0, 2)]
    .filter((x) => !vistos.has(x.ticker) && vistos.add(x.ticker));
}

/** Faixa de indicadores de mercado que rola no topo de todas as páginas. */
function FaixaMercado({ painel }: { painel: Painel | null }) {
  if (!painel) return null;
  const v = painel.variacoes;
  const itens = [
    ...painel.macro.map((m) => ({ chave: m.id, rotulo: m.rotulo.replace(" (mais longo)", ""), valor: formatarMacro(m), variacao: m.variacao,
      titulo: `${m.fonte} — ${m.data}`, href: undefined as string | undefined })),
    ...cotacoesDaFaixa(painel).map((x) => ({
      chave: x.ticker, rotulo: x.ticker, valor: x.fechamento.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
      variacao: x.variacao, titulo: `${v.fonte} — ${v.data}`, href: `/${x.classe === "FII" ? "fiis" : "acoes"}/${x.ticker}`,
    })),
  ];
  const bloco = (copia: number) => itens.map((i) => {
    const conteudo = (
      <>
        <span className="font-semibold">{i.rotulo}</span>
        <span>{i.valor}</span>
        {i.variacao !== null && i.variacao !== 0 && (
          <span className={i.variacao > 0 ? "positivo" : "negativo"}>{i.variacao > 0 ? "▲" : "▼"} {pct(i.variacao)}</span>
        )}
      </>
    );
    return i.href ? (
      <Link key={`${copia}-${i.chave}`} href={i.href} title={i.titulo} className="mono flex shrink-0 items-center gap-2 hover:underline"
        aria-hidden={copia === 1 ? true : undefined} tabIndex={copia === 1 ? -1 : undefined}>{conteudo}</Link>
    ) : (
      <span key={`${copia}-${i.chave}`} title={i.titulo} className="mono flex shrink-0 items-center gap-2"
        aria-hidden={copia === 1 ? true : undefined}>{conteudo}</span>
    );
  });
  return (
    <div className="overflow-hidden border-b text-[0.75rem]" style={{ background: "var(--fundo-2)" }} aria-label="Indicadores de mercado">
      <div className="faixa-rolante flex w-max gap-8 px-4 py-1.5" style={{ animationDuration: `${Math.max(40, itens.length * 3)}s` }}>
        {bloco(0)}
        {bloco(1)}
      </div>
    </div>
  );
}

export default async function Layout({ children }: { children: React.ReactNode }) {
  const painel = await buscarPainel();
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: SCRIPT_TEMA }} />
      </head>
      <body className="min-h-screen">
        <MenuLateral />
        <div className="lg:pl-60">
          <header className="sticky top-0 z-20 border-b backdrop-blur"
            style={{ background: "color-mix(in srgb, var(--fundo) 85%, transparent)" }}>
            <div className="flex items-center gap-3 px-4 py-2.5">
              <BotaoMenu />
              <BuscaRapida />
              <div className="ml-auto flex items-center gap-2 text-sm">
                <BotaoTema />
                <Conta />
              </div>
            </div>
            <FaixaMercado painel={painel} />
          </header>
          <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
          <footer className="mx-auto max-w-7xl px-4 pb-8 text-xs suave">
            Fontes: CVM — Dados Abertos (ODbL) para balanços e informes de FII; Yahoo Finance para cotações e
            dividendos; Banco Central (SGS, ODbL) e Tesouro Transparente; EUA: SEC EDGAR e Tesouro dos EUA.
            Ferramenta de análise: os números são cálculos a partir de dados públicos e não constituem
            recomendação de investimento.
          </footer>
        </div>
      </body>
    </html>
  );
}
