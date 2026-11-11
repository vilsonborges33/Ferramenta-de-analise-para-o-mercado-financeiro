"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Icone, Marca, NOME_PRODUTO } from "@/componentes/Arte";

const GRUPOS: { titulo: string; itens: [string, string, string][] }[] = [
  { titulo: "Mercado", itens: [["/", "Painel", "painel"], ["/acoes", "Ações", "acoes"], ["/fiis", "Fundos imobiliários", "fiis"],
    ["/eua", "EUA", "eua"]] },
  { titulo: "Análise", itens: [["/mais-baratas", "Ranking de ações", "ranking"], ["/fiis/ranking", "Ranking de FIIs", "rankingFii"],
    ["/valuations", "Valuation", "valuation"], ["/comparar", "Comparador", "comparador"]] },
  { titulo: "Minha conta", itens: [["/carteira", "Carteira", "carteira"], ["/diario", "Diário de decisões", "diario"],
    ["/alertas", "Alertas", "alertas"]] },
  { titulo: "Ferramentas", itens: [["/ferramentas/juros-compostos", "Juros compostos", "juros"],
    ["/ferramentas/conversor-taxas", "Conversor de taxas", "conversor"],
    ["/ferramentas/aposentadoria", "Plano de aposentadoria", "aposentadoria"],
    ["/longo-prazo", "Longo prazo (Siegel)", "longoPrazo"]] },
  { titulo: "Referência", itens: [["/metodologia", "Como é calculado", "metodologia"], ["/status", "Status dos dados", "status"]] },
];

function ativo(caminho: string, href: string) {
  if (href === "/") return caminho === "/";
  if (href === "/fiis") return caminho === "/fiis" || (caminho.startsWith("/fiis/") && !caminho.startsWith("/fiis/ranking"));
  return caminho === href || caminho.startsWith(`${href}/`);
}

/** Menu lateral fixo no desktop; no celular vira gaveta aberta pelo botão ☰ da barra do topo. */
export function MenuLateral() {
  const caminho = usePathname();
  const [aberto, setAberto] = useState(false);
  useEffect(() => setAberto(false), [caminho]);
  useEffect(() => {
    const abrir = () => setAberto((a) => !a);
    window.addEventListener("alternar-menu", abrir);
    return () => window.removeEventListener("alternar-menu", abrir);
  }, []);
  return (
    <>
      {aberto && <div className="fixed inset-0 z-30 bg-black/50 lg:hidden" onClick={() => setAberto(false)} />}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r transition-transform lg:translate-x-0 ${aberto ? "translate-x-0" : "-translate-x-full"}`}
        style={{ background: "var(--fundo-2)" }}
        aria-label="Menu principal"
      >
        <Link href="/" className="flex items-center gap-2.5 px-4 py-4">
          <Marca tamanho={32} id="marca-menu" />
          <span className="leading-tight">
            <span className="block text-base font-bold tracking-tight">{NOME_PRODUTO}</span>
            <span className="block text-[0.68rem] suave">Ações · FIIs · EUA</span>
          </span>
        </Link>
        <nav className="flex-1 space-y-4 overflow-y-auto px-3 pb-6">
          {GRUPOS.map((g) => (
            <div key={g.titulo}>
              <div className="rotulo px-2 pb-1.5">{g.titulo}</div>
              <ul className="space-y-0.5">
                {g.itens.map(([href, rotulo, icone]) => (
                  <li key={href}>
                    <Link href={href} className="menu-item" aria-current={ativo(caminho, href) ? "page" : undefined}>
                      <Icone nome={icone} />
                      {rotulo}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
        <div className="border-t px-4 py-3 text-[0.68rem] leading-snug suave">
          Cálculos sobre dados públicos. Não constitui recomendação de investimento.
        </div>
      </aside>
    </>
  );
}

export function BotaoMenu() {
  return (
    <button type="button" className="rounded-md p-1.5 hover:bg-[var(--superficie-2)] lg:hidden" aria-label="Abrir menu"
      onClick={() => window.dispatchEvent(new Event("alternar-menu"))}>
      <Icone nome="menu" tamanho={20} />
    </button>
  );
}

/** Alterna claro/escuro; a escolha fica no navegador. Os gráficos ouvem o evento "tema". */
export function BotaoTema() {
  const [tema, setTema] = useState<string | null>(null);
  useEffect(() => setTema(document.documentElement.dataset.tema ?? "escuro"), []);
  const trocar = () => {
    const novo = tema === "claro" ? "escuro" : "claro";
    document.documentElement.dataset.tema = novo;
    localStorage.setItem("tema", novo);
    setTema(novo);
    window.dispatchEvent(new Event("tema"));
  };
  return (
    <button type="button" onClick={trocar} className="rounded-md p-1.5 suave hover:bg-[var(--superficie-2)]"
      aria-label={tema === "claro" ? "Usar tema escuro" : "Usar tema claro"} title="Alternar tema">
      <Icone nome={tema === "claro" ? "lua" : "sol"} tamanho={18} />
    </button>
  );
}

type Achado = { ticker: string; nome: string | null; classe: string };

/** Busca rápida de qualquer ativo (ações, FIIs e EUA) na barra do topo. Atalho: tecla "/". */
export function BuscaRapida() {
  const [termo, setTermo] = useState("");
  const [achados, setAchados] = useState<Achado[]>([]);
  const [indice, setIndice] = useState(0);
  const ref = useRef<HTMLInputElement>(null);
  const router = useRouter();

  useEffect(() => {
    const atalho = (e: KeyboardEvent) => {
      const alvo = e.target as HTMLElement;
      if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(alvo.tagName)) {
        e.preventDefault();
        ref.current?.focus();
      }
    };
    window.addEventListener("keydown", atalho);
    return () => window.removeEventListener("keydown", atalho);
  }, []);

  useEffect(() => {
    const t = termo.trim();
    if (t.length < 2) { setAchados([]); return; }
    const c = new AbortController();
    const id = setTimeout(async () => {
      try {
        const listas = await Promise.all(["acoes", "fiis", "eua"].map((b) =>
          fetch(`/api/${b}?busca=${encodeURIComponent(t)}`, { signal: c.signal }).then((r) => (r.ok ? r.json() : []))));
        const todos: Achado[] = listas.flat();
        todos.sort((a, b) => Number(!a.ticker.startsWith(t.toUpperCase())) - Number(!b.ticker.startsWith(t.toUpperCase())));
        setAchados(todos.slice(0, 8));
        setIndice(0);
      } catch { /* busca cancelada */ }
    }, 180);
    return () => { clearTimeout(id); c.abort(); };
  }, [termo]);

  const abrir = (a: Achado) => {
    const base = a.classe === "FII" ? "fiis" : ["STOCK", "REIT", "ETF"].includes(a.classe) ? "eua" : "acoes";
    setTermo(""); setAchados([]);
    router.push(`/${base}/${a.ticker}`);
  };

  return (
    <div className="relative w-full max-w-md">
      <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 suave"><Icone nome="busca" tamanho={16} /></span>
      <input ref={ref} value={termo} onChange={(e) => setTermo(e.target.value)} placeholder="Buscar ativo (PETR4, HGLG11, AAPL…)"
        aria-label="Buscar ativo" className="campo w-full py-1.5 pl-8 pr-8 text-sm"
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setIndice((i) => Math.min(i + 1, achados.length - 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setIndice((i) => Math.max(i - 1, 0)); }
          if (e.key === "Enter" && achados[indice]) abrir(achados[indice]);
          if (e.key === "Escape") { setTermo(""); setAchados([]); }
        }} />
      <kbd className="pointer-events-none absolute right-2 top-1/2 hidden -translate-y-1/2 rounded border px-1 text-[0.65rem] suave sm:block">/</kbd>
      {achados.length > 0 && (
        <ul className="cartao absolute left-0 right-0 top-full z-50 mt-1 overflow-hidden py-1" role="listbox">
          {achados.map((a, i) => (
            <li key={a.ticker} role="option" aria-selected={i === indice}>
              <button type="button" onMouseDown={() => abrir(a)} onMouseEnter={() => setIndice(i)}
                className="flex w-full items-center gap-3 px-3 py-1.5 text-left text-sm"
                style={{ background: i === indice ? "var(--superficie-2)" : undefined }}>
                <span className="ticker w-16 font-semibold">{a.ticker}</span>
                <span className="flex-1 truncate suave">{a.nome}</span>
                <span className="rotulo">{a.classe === "ACAO" ? "Ação" : a.classe === "UNIT" ? "Unit" : a.classe}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
