/** Busca na API a partir de componentes de servidor (rede interna do Docker). */
const BASE = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function buscar<T>(caminho: string): Promise<T | null> {
  try {
    const resposta = await fetch(`${BASE}${caminho}`, { cache: "no-store" });
    if (resposta.status === 404) return null;
    if (!resposta.ok) throw new Error(`API ${resposta.status}`);
    return (await resposta.json()) as T;
  } catch (erro) {
    console.error(`falha ao buscar ${caminho}:`, erro);
    throw erro;
  }
}
