/**
 * Artes próprias do projeto, todas em SVG desenhado à mão (sem imagens de terceiros):
 * marca, ilustração do painel inicial, emblemas dos métodos e ícones do menu.
 * As cores vêm das variáveis do tema, então tudo acompanha o modo claro/escuro.
 */

export const NOME_PRODUTO = "Prumo";

/** Marca: três candles subindo dentro de um quadrado, com o fio de prumo à direita (margem de segurança). */
export function Marca({ tamanho = 30, id = "marca" }: { tamanho?: number; id?: string }) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 32 32" aria-hidden="true">
      <defs>
        <linearGradient id={`${id}-g`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--destaque)" />
          <stop offset="1" stopColor="var(--destaque-2)" />
        </linearGradient>
      </defs>
      <rect x="1.25" y="1.25" width="29.5" height="29.5" rx="8" fill="var(--superficie-2)" stroke={`url(#${id}-g)`}
        strokeWidth="1.5" />
      <g stroke={`url(#${id}-g)`} strokeWidth="1.4" strokeLinecap="round">
        <line x1="8.5" y1="15" x2="8.5" y2="25" />
        <line x1="14" y1="11" x2="14" y2="23" />
        <line x1="19.5" y1="7" x2="19.5" y2="19" />
      </g>
      <g fill={`url(#${id}-g)`}>
        <rect x="6.6" y="17.5" width="3.8" height="5.5" rx="1" />
        <rect x="12.1" y="13" width="3.8" height="7" rx="1" />
        <rect x="17.6" y="9" width="3.8" height="7.5" rx="1" />
      </g>
      <line x1="25" y1="6" x2="25" y2="20.5" stroke="var(--ouro)" strokeWidth="1" strokeDasharray="1.5 1.5" />
      <path d="M23.2 20.5h3.6L25 25z" fill="var(--ouro)" />
    </svg>
  );
}

/** Sequência fixa (pseudoaleatória com semente) para os candles da ilustração não mudarem a cada render. */
function candles(n: number) {
  let s = 7;
  const r = () => ((s = (s * 9301 + 49297) % 233280) / 233280);
  let preco = 150;
  return Array.from({ length: n }, (_, i) => {
    const tendencia = i < n * 0.45 ? -1.1 : 1.6;
    const abre = preco;
    const fecha = abre + tendencia + (r() - 0.5) * 9;
    const max = Math.max(abre, fecha) + r() * 5;
    const min = Math.min(abre, fecha) - r() * 5;
    preco = fecha;
    return { abre, fecha, max, min };
  });
}

/**
 * Ilustração do painel: preço em candles cruzando o "valor intrínseco" (linha tracejada dourada).
 * A área entre o preço e o valor intrínseco é a margem de segurança — a ideia central da ferramenta.
 */
export function ArteHero({ className = "" }: { className?: string }) {
  const L = 560, A = 230, n = 34, passo = (L - 40) / n;
  const dados = candles(n);
  const todos = dados.flatMap((d) => [d.max, d.min]);
  const lo = Math.min(...todos) - 6, hi = Math.max(...todos) + 6;
  const y = (v: number) => 20 + (1 - (v - lo) / (hi - lo)) * (A - 50);
  const x = (i: number) => 24 + i * passo + passo / 2;
  const justo = (i: number) => 150 - 4 + i * 0.35; // valor intrínseco subindo devagar
  const media = dados.map((_, i) => {
    const j = dados.slice(Math.max(0, i - 4), i + 1);
    return j.reduce((s, d) => s + d.fecha, 0) / j.length;
  });
  const linhaJusto = dados.map((_, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(justo(i)).toFixed(1)}`).join(" ");
  const linhaMedia = media.map((m, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(m).toFixed(1)}`).join(" ");
  // Margem de segurança: trecho em que o preço ficou abaixo do valor intrínseco.
  const abaixo = dados.map((d, i) => ({ i, p: Math.min(d.fecha, justo(i)) })).filter(({ i }) => dados[i].fecha < justo(i));
  const area = abaixo.length > 1
    ? `M${x(abaixo[0].i)} ${y(justo(abaixo[0].i))} ` +
      abaixo.map(({ i }) => `L${x(i).toFixed(1)} ${y(justo(i)).toFixed(1)}`).join(" ") + " " +
      [...abaixo].reverse().map(({ i, p }) => `L${x(i).toFixed(1)} ${y(p).toFixed(1)}`).join(" ") + "Z"
    : "";
  const meio = abaixo.length ? abaixo[Math.floor(abaixo.length / 2)].i : 8;
  return (
    <svg viewBox={`0 0 ${L} ${A}`} className={className} role="img"
      aria-label="Ilustração: preço em candles abaixo do valor intrínseco forma a margem de segurança">
      <defs>
        <linearGradient id="hero-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="var(--ouro)" stopOpacity="0.28" />
          <stop offset="1" stopColor="var(--ouro)" stopOpacity="0.02" />
        </linearGradient>
        <linearGradient id="hero-media" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="var(--destaque-2)" stopOpacity="0.2" />
          <stop offset="1" stopColor="var(--destaque-2)" />
        </linearGradient>
      </defs>
      {Array.from({ length: 6 }, (_, k) => (
        <line key={k} x1="16" x2={L - 8} y1={20 + k * ((A - 50) / 5)} y2={20 + k * ((A - 50) / 5)}
          stroke="var(--borda)" strokeDasharray="2 4" />
      ))}
      {area && <path d={area} fill="url(#hero-area)" />}
      {dados.map((d, i) => {
        const sobe = d.fecha >= d.abre;
        const cor = sobe ? "var(--positivo)" : "var(--negativo)";
        return (
          <g key={i} opacity={0.92}>
            <line x1={x(i)} x2={x(i)} y1={y(d.max)} y2={y(d.min)} stroke={cor} strokeWidth="1" />
            <rect x={x(i) - passo * 0.3} width={passo * 0.6} rx="1"
              y={y(Math.max(d.abre, d.fecha))} height={Math.max(1.5, Math.abs(y(d.abre) - y(d.fecha)))} fill={cor} />
          </g>
        );
      })}
      <path d={linhaMedia} fill="none" stroke="url(#hero-media)" strokeWidth="2" strokeLinecap="round" />
      <path d={linhaJusto} fill="none" stroke="var(--ouro)" strokeWidth="1.6" strokeDasharray="6 4" />
      <g fontSize="11" fontFamily="inherit">
        <rect x={L - 150} y={y(justo(n - 1)) - 26} width="132" height="18" rx="4" fill="var(--superficie-2)"
          stroke="var(--ouro)" strokeOpacity="0.5" />
        <text x={L - 84} y={y(justo(n - 1)) - 13.5} textAnchor="middle" fill="var(--ouro)">valor intrínseco</text>
        <text x={x(meio)} y={y(justo(meio)) + 34} textAnchor="middle" fill="var(--ouro)" opacity="0.9">
          margem de segurança
        </text>
      </g>
      <line x1="16" x2={L - 8} y1={A - 22} y2={A - 22} stroke="var(--borda-forte)" />
      {dados.map((d, i) => (
        <rect key={i} x={x(i) - passo * 0.3} width={passo * 0.6} y={A - 22 - (4 + ((i * 37) % 13))}
          height={4 + ((i * 37) % 13)} fill="var(--texto-suave)" opacity="0.25" />
      ))}
    </svg>
  );
}

type Metodo = "graham" | "bazin" | "lynch" | "greenblatt";

/** Emblemas dos métodos, cada um com a cor do método. */
export function EmblemaMetodo({ metodo, tamanho = 40 }: { metodo: Metodo; tamanho?: number }) {
  const cor = `var(--cor-${metodo})`;
  const fundo = (
    <rect x="1" y="1" width="38" height="38" rx="10" fill={cor} fillOpacity="0.12" stroke={cor} strokeOpacity="0.45" />
  );
  const traco = { fill: "none", stroke: cor, strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 40 40" aria-hidden="true">
      {fundo}
      {metodo === "graham" && (
        // Escudo com balança: margem de segurança e valor intrínseco.
        <g {...traco}>
          <path d="M20 8l9 3.5v7c0 6-4 10.5-9 12.5-5-2-9-6.5-9-12.5v-7z" />
          <path d="M20 14v11M15 17h10M15 17l-2 4h4zM25 17l-2 4h4z" />
        </g>
      )}
      {metodo === "bazin" && (
        // Moeda com gota: renda de dividendos.
        <g {...traco}>
          <circle cx="17" cy="22" r="8" />
          <path d="M17 18.5v7M14.8 20c0-1 1-1.6 2.2-1.6s2.2.6 2.2 1.5-1 1.3-2.2 1.6-2.2.7-2.2 1.6 1 1.6 2.2 1.6 2.2-.6 2.2-1.6" />
          <path d="M28 8c2 2.6 3 4.4 3 5.8a3 3 0 0 1-6 0c0-1.4 1-3.2 3-5.8z" fill={cor} fillOpacity="0.3" />
        </g>
      )}
      {metodo === "lynch" && (
        // Lupa sobre um broto: procurar crescimento a preço justo.
        <g {...traco}>
          <circle cx="18" cy="18" r="8" />
          <path d="M24 24l6 6" />
          <path d="M18 22v-5M18 18c-2.6 0-3.6-1.6-3.6-3.6 2.6 0 3.6 1.6 3.6 3.6zM18 17c0-2 1-3.4 3.6-3.4 0 2-1 3.4-3.6 3.4z" />
        </g>
      )}
      {metodo === "greenblatt" && (
        // Pódio com estrela: ranking pela soma de posições.
        <g {...traco}>
          <path d="M9 30h22M12 30v-6h6v6M18 30V20h6v10M24 30v-4h5v4" />
          <path d="M21 8.5l1.3 2.7 3 .4-2.2 2 .6 2.9-2.7-1.5-2.7 1.5.6-2.9-2.2-2 3-.4z" fill={cor} fillOpacity="0.3" />
        </g>
      )}
    </svg>
  );
}

const ICONES: Record<string, string> = {
  painel: "M4 13h6V4H4zM14 20h6v-9h-6zM4 20h6v-4H4zM14 4v4h6V4z",
  acoes: "M4 19h16M7 16V9M7 9V6M12 16v-4M12 12V7M17 16v-6M17 10V5",
  fiis: "M4 20h16M6 20V9l6-4 6 4v11M10 20v-5h4v5M9 11h.01M15 11h.01",
  eua: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3.6 9h16.8M3.6 15h16.8M12 3c2.5 2.6 3.6 5.6 3.6 9s-1.1 6.4-3.6 9c-2.5-2.6-3.6-5.6-3.6-9S9.5 5.6 12 3z",
  ranking: "M4 20h16M6 20v-6h4v6M10 20V9h4v11M14 20v-8h4v8",
  rankingFii: "M4 20h16M6 20v-5h4v5M10 20v-9h4v9M14 20v-7h4v7M12 4l1 2 2 .3-1.5 1.4.4 2.1L12 8.8l-1.9 1 .4-2.1L9 6.3l2-.3z",
  valuation: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zM12 11a1 1 0 1 0 0 2 1 1 0 0 0 0-2z",
  carteira: "M4 7h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zM4 7l11-3v3M16 13h.01",
  diario: "M6 4h11a1 1 0 0 1 1 1v15H7a2 2 0 0 1-2-2V5a1 1 0 0 1 1-1zM5 18a2 2 0 0 1 2-2h11M9 8h6M9 11h4",
  alertas: "M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15zM10 20a2 2 0 0 0 4 0",
  juros: "M4 20L20 4M7 7h.01M17 17h.01M7.5 7.5a.5.5 0 1 0-1 0 .5.5 0 0 0 1 0M17.5 17.5a.5.5 0 1 0-1 0 .5.5 0 0 0 1 0",
  conversor: "M4 8h13l-3-3M20 16H7l3 3",
  aposentadoria: "M12 3v3M5.6 6.6l2 2M18.4 6.6l-2 2M3 13h3M18 13h3M7 13a5 5 0 0 1 10 0M3 18h18M7 21h10",
  comparador: "M4 5h6v14H4zM14 5h6v14h-6zM7 9v6M17 11v4",
  longoPrazo: "M4 18c4-1 6-4 8-8s4-5 8-6M4 21h16M16 4h4v4",
  metodologia: "M4 5c3-1 5-1 8 1 3-2 5-2 8-1v14c-3-1-5-1-8 1-3-2-5-2-8-1zM12 6v14",
  status: "M3 12h4l2-5 4 10 2-5h6",
  menu: "M4 7h16M4 12h16M4 17h16",
  sol: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
  lua: "M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z",
  busca: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4-4",
  seta: "M7 17L17 7M9 7h8v8",
};

export type NomeIcone = keyof typeof ICONES;

export function Icone({ nome, tamanho = 18, className = "" }: { nome: NomeIcone | string; tamanho?: number; className?: string }) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
      strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d={ICONES[nome] ?? ""} />
    </svg>
  );
}

/** Mini gráfico de linha (sparkline) para cartões. */
export function Sparkline({ valores, largura = 96, altura = 28, cor = "var(--destaque)" }:
  { valores: number[]; largura?: number; altura?: number; cor?: string }) {
  if (valores.length < 2) return null;
  const lo = Math.min(...valores), hi = Math.max(...valores);
  const pts = valores.map((v, i) =>
    `${((i / (valores.length - 1)) * largura).toFixed(1)},${(altura - 2 - ((v - lo) / (hi - lo || 1)) * (altura - 4)).toFixed(1)}`);
  return (
    <svg width={largura} height={altura} viewBox={`0 0 ${largura} ${altura}`} aria-hidden="true">
      <polyline points={pts.join(" ")} fill="none" stroke={cor} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

/** Ilustração de estado vazio: prancheta com gráfico em branco. */
export function ArteVazio({ tamanho = 120 }: { tamanho?: number }) {
  return (
    <svg width={tamanho} height={tamanho * 0.75} viewBox="0 0 160 120" aria-hidden="true">
      <rect x="30" y="14" width="100" height="92" rx="10" fill="var(--superficie-2)" stroke="var(--borda-forte)" />
      <rect x="62" y="8" width="36" height="12" rx="4" fill="var(--borda-forte)" />
      <path d="M44 86h72M44 86V36" stroke="var(--borda-forte)" strokeWidth="1.5" />
      <path d="M48 76l16-12 14 8 18-20 16 6" fill="none" stroke="var(--destaque)" strokeWidth="2" strokeDasharray="4 4"
        strokeLinecap="round" />
      <circle cx="112" cy="58" r="3.5" fill="var(--ouro)" />
    </svg>
  );
}
