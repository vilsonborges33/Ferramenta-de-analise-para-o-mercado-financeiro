/**
 * Monograma do ativo: arte própria gerada a partir do ticker (não usamos logotipos das empresas).
 * A cor sai de um hash do ticker, o padrão de fundo indica a classe (ações: barras; FII: telhado; EUA: estrela).
 */
const TONS = [168, 199, 38, 271, 16, 142, 330, 222, 52, 290];

function hash(s: string) {
  let h = 0;
  for (const c of s) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return h;
}

export function Monograma({ ticker, classe, tamanho = 44 }: { ticker: string; classe?: string; tamanho?: number }) {
  const h = hash(ticker);
  const tom = TONS[h % TONS.length];
  const cor = `hsl(${tom} 70% 60%)`;
  const letras = ticker.replace(/\d+$/, "").slice(0, 2);
  const id = `mono-${ticker}`;
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 44 44" aria-hidden="true" className="shrink-0">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={cor} stopOpacity="0.28" />
          <stop offset="1" stopColor={cor} stopOpacity="0.08" />
        </linearGradient>
      </defs>
      <rect x="0.75" y="0.75" width="42.5" height="42.5" rx="11" fill={`url(#${id})`} stroke={cor} strokeOpacity="0.55" />
      {classe === "FII" ? (
        <path d="M6 38V27l8-6 8 6v11M22 38V22l8-6 8 6v16" fill="none" stroke={cor} strokeOpacity="0.25" strokeWidth="1.5" />
      ) : ["STOCK", "REIT", "ETF"].includes(classe ?? "") ? (
        <path d="M34 5l1.5 3 3.3.5-2.4 2.3.6 3.3-3-1.6-3 1.6.6-3.3-2.4-2.3 3.3-.5z" fill={cor} fillOpacity="0.45" />
      ) : (
        <g fill={cor} fillOpacity="0.22">
          <rect x="6" y="31" width="4" height="7" rx="1" />
          <rect x="12" y="27" width="4" height="11" rx="1" />
          <rect x="18" y="29" width="4" height="9" rx="1" />
        </g>
      )}
      <text x="22" y="25.5" textAnchor="middle" fontSize="14" fontWeight="700" fill={cor}
        fontFamily="ui-monospace, Consolas, monospace">{letras}</text>
    </svg>
  );
}
