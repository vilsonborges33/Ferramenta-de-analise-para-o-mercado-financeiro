"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

/** Canto do menu: "Entrar" ou o e-mail da conta com "Sair". */
export function Conta() {
  const [email, setEmail] = useState<string | null | undefined>(undefined);
  const caminho = usePathname();
  useEffect(() => {
    fetch("/api/auth/eu").then((r) => (r.ok ? r.json() : null)).then((u) => setEmail(u?.email ?? null))
      .catch(() => setEmail(null));
  }, [caminho]);
  if (email === undefined) return <span className="ml-auto" />;
  if (email === null) return <Link href="/entrar" className="ml-auto">Entrar</Link>;
  return (
    <span className="ml-auto flex items-center gap-3">
      <span className="suave max-w-40 truncate" title={email}>{email}</span>
      <button type="button" className="hover:underline" onClick={async () => {
        await fetch("/api/auth/sair", { method: "POST" });
        window.location.href = "/";
      }}>Sair</button>
    </span>
  );
}
