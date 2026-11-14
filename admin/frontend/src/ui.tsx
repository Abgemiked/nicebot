import { useEffect, useState } from "react";

// --- Klassen-Konstanten (Design-System abgemiked.de: gray-950/900, purple-600, Inter) ---
export const GRAD = "bg-purple-600";
export const CARD = "rounded-2xl border border-gray-800 bg-gray-900 shadow-card";
export const INPUT =
  "w-full rounded-md border border-gray-700 bg-gray-800/60 px-3 py-2.5 text-sm text-gray-200 outline-none transition focus:border-purple-500 focus:shadow-[0_0_0_2px_rgba(168,85,247,.25)]";
export const BTN_PRIMARY =
  "inline-flex items-center justify-center gap-2 rounded-md bg-purple-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-purple-700 disabled:opacity-50";
export const BTN_SECONDARY =
  "inline-flex items-center justify-center gap-2 rounded-md border border-gray-600 bg-transparent px-4 py-2.5 text-sm font-medium text-gray-300 transition hover:border-purple-500 hover:text-white disabled:opacity-50";
export const BTN_DANGER =
  "inline-flex items-center justify-center gap-2 rounded-md border border-red-900/60 bg-red-950/30 px-4 py-2.5 text-sm font-medium text-red-300 transition hover:bg-red-950/50 disabled:opacity-50";
export const ICON_BTN =
  "flex h-8 w-8 items-center justify-center rounded-md border border-gray-700 bg-transparent text-gray-400 transition hover:border-gray-600 hover:text-white";
export const TABLE_WRAP =
  "overflow-hidden rounded-2xl border border-gray-800 bg-gray-900";
export const TH =
  "px-4 py-3 text-left text-[11px] font-medium uppercase tracking-wide text-gray-400";

// --- Avatar / Initialen / Rollenfarben (gedeckte Grau-/Purpletöne statt Neon) ---
const AV_PALETTE = ["#374151", "#7e22ce", "#334155", "#4b5563", "#6d28d9", "#475569"];
const ROLE_PALETTE = [
  "#c084fc", "#9ca3af", "#7dd3fc", "#86efac", "#fcd34d",
  "#f9a8d4", "#a5b4fc", "#fca5a5", "#d1d5db", "#93c5fd",
];

function hash(seed: string): number {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return h;
}

export function initialOf(s: string | null | undefined): string {
  const m = (s || "?").replace(/[^A-Za-zÄÖÜäöü0-9]/g, "");
  return (m.charAt(0) || "?").toUpperCase();
}

export function avatarGradient(seed: string): string {
  return AV_PALETTE[hash(seed || "x") % AV_PALETTE.length];
}

export function roleColor(seed: string): string {
  return ROLE_PALETTE[hash(seed || "x") % ROLE_PALETTE.length];
}

/** Avatar-Kachel mit Initiale. */
export function Avatar({ seed, label, size = 34 }: { seed: string; label: string; size?: number }) {
  return (
    <span
      className="flex flex-none items-center justify-center rounded-full font-sans font-semibold text-white"
      style={{ width: size, height: size, background: avatarGradient(seed), fontSize: size * 0.41 }}
    >
      {initialOf(label)}
    </span>
  );
}

// --- Toast-System (global) ---
export interface ToastMsg {
  kind: "ok" | "err";
  msg: string;
}
let current: ToastMsg | null = null;
const subs = new Set<(t: ToastMsg | null) => void>();
let timer: ReturnType<typeof setTimeout> | undefined;

export function toast(kind: "ok" | "err", msg: string) {
  current = { kind, msg };
  subs.forEach((f) => f(current));
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => {
    current = null;
    subs.forEach((f) => f(null));
  }, 2800);
}

export function useToast(): ToastMsg | null {
  const [t, setT] = useState<ToastMsg | null>(current);
  useEffect(() => {
    subs.add(setT);
    return () => {
      subs.delete(setT);
    };
  }, []);
  return t;
}

export function Toast() {
  const t = useToast();
  if (!t) return null;
  const ok = t.kind === "ok";
  return (
    <div
      className="fixed bottom-6 right-6 z-[80] flex min-w-[250px] animate-tIn items-center gap-3 rounded-xl border bg-gray-900 px-4 py-3 shadow-[0_22px_44px_-16px_rgba(0,0,0,.8)]"
      style={{ borderColor: ok ? "rgba(134,239,172,.4)" : "rgba(252,165,165,.4)" }}
    >
      <span
        className="flex h-[26px] w-[26px] flex-none items-center justify-center rounded-lg"
        style={{ background: ok ? "rgba(134,239,172,.16)" : "rgba(252,165,165,.16)" }}
      >
        {ok ? (
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#86efac" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12l5 5L20 7" /></svg>
        ) : (
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#fca5a5" strokeWidth="2.4" strokeLinecap="round"><line x1="6" y1="6" x2="18" y2="18" /><line x1="18" y1="6" x2="6" y2="18" /></svg>
        )}
      </span>
      <span className="text-sm font-medium text-ink">{t.msg}</span>
    </div>
  );
}

/** Kleiner SVG-Icon-Satz (stroke=currentColor). */
export const Icon = {
  search: (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7" /><line x1="21" y1="21" x2="16.5" y2="16.5" /></svg>
  ),
  chevron: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6" /></svg>
  ),
  check: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12l5 5L20 7" /></svg>
  ),
  plus: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>
  ),
  x: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round"><line x1="6" y1="6" x2="18" y2="18" /><line x1="18" y1="6" x2="6" y2="18" /></svg>
  ),
  prev: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6" /></svg>
  ),
  next: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="m9 18 6-6-6-6" /></svg>
  ),
  edit: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" /></svg>
  ),
  trash: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 7h16" /><path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" /><path d="m6 7 1 13h10l1-13" /></svg>
  ),
  restart: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 8v4l2.5 2.5" /><circle cx="12" cy="12" r="9" /></svg>
  ),
};

/** Pagination-Leiste (Zurück/Seite/Weiter). */
export function Pager({
  page,
  totalPages,
  onPrev,
  onNext,
  label,
}: {
  page: number;
  totalPages: number;
  onPrev: () => void;
  onNext: () => void;
  label: string;
}) {
  const btn =
    "flex items-center gap-1.5 rounded-md border border-gray-700 bg-transparent px-3 py-2 text-[13px] font-medium text-gray-300 transition hover:border-gray-600 hover:text-white disabled:opacity-40";
  return (
    <div className="flex items-center justify-end gap-3">
      <span className="text-xs text-gray-500">{label}</span>
      <button disabled={page <= 1} onClick={onPrev} className={btn}>
        {Icon.prev}Zurück
      </button>
      <button disabled={page >= totalPages} onClick={onNext} className={btn}>
        Weiter{Icon.next}
      </button>
    </div>
  );
}
