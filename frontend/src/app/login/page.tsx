"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const auth = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"in" | "up">("in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (auth.ready && auth.email) router.replace("/app");
  }, [auth.ready, auth.email, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (auth.mode === "dev") {
        auth.signInDev(email);
      } else if (mode === "in") {
        await auth.signInWithPassword(email, password);
      } else {
        const { needsConfirmation } = await auth.signUp(email, password, name);
        if (needsConfirmation) setNotice("Check your inbox to confirm your email, then sign in.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen grid-cols-1 lg:grid-cols-2">
      <div className="grid-bg hidden flex-col justify-between border-r-2 border-ink p-10 lg:flex">
        <Link href="/" className="display text-xl">WorkflowWise</Link>
        <div>
          <p className="display text-7xl">
            Nothing
            <br />
            your team
            <br />
            learned
            <br />
            <span className="bg-acid px-2">gets lost.</span>
          </p>
        </div>
        <p className="label text-muted">Documents · Meetings · Decisions · Actions · Gaps</p>
      </div>

      <div className="flex items-center justify-center p-8">
        <form onSubmit={submit} className="w-full max-w-sm border-2 border-ink bg-white shadow-[var(--shadow-hard-lg)]">
          <div className="flex border-b-2 border-ink">
            {(["in", "up"] as const).map((m) => (
              <button
                key={m}
                type="button"
                disabled={auth.mode === "dev"}
                onClick={() => setMode(m)}
                className={`label flex-1 cursor-pointer py-3 font-bold ${mode === m ? "bg-ink text-paper" : "bg-paper hover:bg-paper-2"} ${m === "up" ? "border-l-2 border-ink" : ""}`}
              >
                {m === "in" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>
          <div className="space-y-4 p-6">
            {auth.mode === "dev" && (
              <p className="border-2 border-ink bg-acid p-3 font-mono text-[11px] leading-relaxed">
                LOCAL DEV MODE — Supabase isn&apos;t configured, so any email signs you in. Set
                NEXT_PUBLIC_SUPABASE_URL to enable real accounts.
              </p>
            )}
            {mode === "up" && auth.mode === "supabase" && (
              <Field label="Name">
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ada Lovelace" />
              </Field>
            )}
            <Field label="Work email">
              <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
            </Field>
            {auth.mode === "supabase" && (
              <Field label="Password">
                <Input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
              </Field>
            )}
            {error && <p className="border-2 border-ink bg-signal p-2 font-mono text-xs">{error}</p>}
            {notice && <p className="border-2 border-ink bg-acid p-2 font-mono text-xs">{notice}</p>}
            <Button type="submit" variant="accent" size="lg" className="w-full" disabled={busy}>
              {busy ? "Working…" : mode === "in" || auth.mode === "dev" ? "Enter workspace →" : "Create account →"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
