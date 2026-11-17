"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

import { useHydrated, useLocal } from "./local-store";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
const DEV_KEY = "wfw.dev-email";

export type AuthMode = "supabase" | "dev";

interface AuthState {
  mode: AuthMode;
  ready: boolean;
  email: string | null;
  getToken: () => Promise<string | null>;
  signInWithPassword: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, name?: string) => Promise<{ needsConfirmation: boolean }>;
  signInDev: (email: string) => void;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

let supabase: SupabaseClient | null = null;
function getSupabase(): SupabaseClient | null {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) return null;
  supabase ??= createBrowserClient(SUPABASE_URL, SUPABASE_ANON_KEY);
  return supabase;
}

/** Reads the current access token outside React, so API calls never race provider effects. */
export async function getAuthToken(): Promise<string | null> {
  const client = getSupabase();
  if (!client) {
    const e = typeof window === "undefined" ? null : localStorage.getItem(DEV_KEY);
    return e ? `dev:${e}` : null;
  }
  const { data } = await client.auth.getSession();
  return data.session?.access_token ?? null;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const client = getSupabase();
  const mode: AuthMode = client ? "supabase" : "dev";
  const [devEmail, setDevEmail] = useLocal(DEV_KEY);
  const hydrated = useHydrated();
  const [sbEmail, setSbEmail] = useState<string | null>(null);
  const [sbReady, setSbReady] = useState(false);

  useEffect(() => {
    if (!client) return;
    client.auth.getSession().then(({ data }) => {
      setSbEmail(data.session?.user.email ?? null);
      setSbReady(true);
    });
    const { data: sub } = client.auth.onAuthStateChange((_e, session) => setSbEmail(session?.user.email ?? null));
    return () => sub.subscription.unsubscribe();
  }, [client]);

  const email = client ? sbEmail : devEmail;
  const ready = client ? sbReady : hydrated;
  const getToken = getAuthToken;

  const value = useMemo<AuthState>(
    () => ({
      mode,
      ready,
      email,
      getToken,
      async signInWithPassword(e, password) {
        if (!client) throw new Error("Supabase is not configured");
        const { error } = await client.auth.signInWithPassword({ email: e, password });
        if (error) throw error;
      },
      async signUp(e, password, name) {
        if (!client) throw new Error("Supabase is not configured");
        const { data, error } = await client.auth.signUp({
          email: e,
          password,
          options: { data: { full_name: name }, emailRedirectTo: `${window.location.origin}/app` },
        });
        if (error) throw error;
        return { needsConfirmation: !data.session };
      },
      signInDev(e) {
        setDevEmail(e.trim().toLowerCase());
      },
      async signOut() {
        if (client) await client.auth.signOut();
        setDevEmail(null);
      },
    }),
    [mode, ready, email, getToken, client, setDevEmail],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
