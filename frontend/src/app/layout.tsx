import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Análise de Ações e FIIs",
  description: "Indicadores fundamentalistas calculados a partir de dados oficiais (CVM, B3, Banco Central).",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="min-h-screen">
        <header className="border-b" style={{ borderColor: "var(--borda)", background: "var(--superficie)" }}>
          <nav className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-5 gap-y-2 px-4 py-3 text-sm">
            <Link href="/" className="font-semibold" style={{ color: "var(--destaque)" }}>
              Análise
            </Link>
            <Link href="/acoes">Ações</Link>
            <Link href="/fiis">FIIs</Link>
            <Link href="/mais-baratas">Mais baratas</Link>
            <Link href="/metodologia">Como é calculado</Link>
            <Link href="/status">Status</Link>
            <Link href="/entrar" className="ml-auto">
              Entrar
            </Link>
          </nav>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
        <footer className="mx-auto max-w-6xl px-4 pb-8 text-xs suave">
          Fontes: CVM — Dados Abertos (ODbL), B3, Banco Central (SGS, ODbL), Tesouro Transparente e brapi.dev.
          Ferramenta de análise: os números são cálculos a partir de dados públicos e não constituem
          recomendação de investimento.
        </footer>
      </body>
    </html>
  );
}
