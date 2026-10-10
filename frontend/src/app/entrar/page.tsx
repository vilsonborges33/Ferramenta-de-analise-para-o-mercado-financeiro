"use client";

import { useState } from "react";

export default function Entrar() {
  const [modo, setModo] = useState<"entrar" | "registrar">("entrar");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [mensagem, setMensagem] = useState<string | null>(null);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setMensagem(null);
    const resposta = await fetch(`/api/auth/${modo}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, senha }),
    });
    if (resposta.ok) {
      const usuario = await resposta.json();
      setMensagem(`Conectado como ${usuario.email}.`);
    } else {
      const erro = await resposta.json().catch(() => ({}));
      const detalhe = Array.isArray(erro.detail) ? erro.detail[0]?.msg : erro.detail;
      setMensagem(detalhe ?? "Não foi possível concluir.");
    }
  }

  return (
    <form onSubmit={enviar} className="cartao mx-auto max-w-sm space-y-3 p-5">
      <h1 className="text-xl font-semibold">{modo === "entrar" ? "Entrar" : "Criar conta"}</h1>
      <label className="block text-sm">
        E-mail
        <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
               className="cartao mt-1 w-full px-3 py-2" autoComplete="email" />
      </label>
      <label className="block text-sm">
        Senha
        <input type="password" required minLength={modo === "registrar" ? 8 : 1} value={senha}
               onChange={(e) => setSenha(e.target.value)} className="cartao mt-1 w-full px-3 py-2"
               autoComplete={modo === "entrar" ? "current-password" : "new-password"} />
      </label>
      <button type="submit" className="w-full rounded-lg px-3 py-2 text-sm font-medium text-white"
              style={{ background: "var(--destaque)" }}>
        {modo === "entrar" ? "Entrar" : "Criar conta"}
      </button>
      {mensagem && <p className="text-sm" role="status">{mensagem}</p>}
      <button type="button" className="link text-sm" onClick={() => setModo(modo === "entrar" ? "registrar" : "entrar")}>
        {modo === "entrar" ? "Não tem conta? Criar conta" : "Já tem conta? Entrar"}
      </button>
    </form>
  );
}
