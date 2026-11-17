"use client";

import { useCallback, useSyncExternalStore } from "react";

const EVENT = "wfw-local-store";

export function writeLocal(key: string, value: string | null) {
  if (value === null) localStorage.removeItem(key);
  else localStorage.setItem(key, value);
  window.dispatchEvent(new Event(EVENT));
}

function subscribe(cb: () => void) {
  window.addEventListener(EVENT, cb);
  window.addEventListener("storage", cb);
  return () => {
    window.removeEventListener(EVENT, cb);
    window.removeEventListener("storage", cb);
  };
}

/** Hydration-safe localStorage value: null on the server and first paint, then the stored value. */
export function useLocal(key: string): [string | null, (v: string | null) => void] {
  const value = useSyncExternalStore(
    subscribe,
    () => localStorage.getItem(key),
    () => null,
  );
  const set = useCallback((v: string | null) => writeLocal(key, v), [key]);
  return [value, set];
}

/** True once running in the browser (false during SSR/hydration). */
export function useHydrated() {
  return useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
}
