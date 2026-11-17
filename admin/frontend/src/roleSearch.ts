// Tolerante Rollensuche (rein clientseitig, ohne externe Dienste).
// Groß/Klein, Umlaute (ä/ae/a), Sonderzeichen/Leerzeichen und Tippfehler
// (Levenshtein) werden toleriert. Treffer-Rang: exakt > Präfix > Teilstring > Fuzzy.

/** Normalisiert: klein, ä→ae/ö→oe/ü→ue/ß→ss, Akzente weg, nur [a-z0-9]. */
export function normalize(s: string): string {
  return s
    .toLowerCase()
    .replace(/ä/g, "ae")
    .replace(/ö/g, "oe")
    .replace(/ü/g, "ue")
    .replace(/ß/g, "ss")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^\p{L}\p{N}]/gu, "");
}

/** Variante mit Umlaut→Grundbuchstabe (für Eingaben ohne „e“: „kueche“ vs. „kuche“). */
function normalizeBase(s: string): string {
  return s
    .toLowerCase()
    .replace(/ß/g, "ss")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^\p{L}\p{N}]/gu, "");
}

export function levenshtein(a: string, b: string): number {
  if (a === b) return 0;
  if (!a.length) return b.length;
  if (!b.length) return a.length;
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    for (let j = 1; j <= b.length; j++) {
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
    prev = cur;
  }
  return prev[b.length];
}

function maxDistance(len: number): number {
  if (len <= 3) return 0;
  if (len <= 5) return 1;
  return 2;
}

/** Kleinster Abstand von q zu irgendeinem Fenster (Länge len(q)±1) in name. */
function windowDistance(q: string, name: string): number {
  let best = levenshtein(q, name);
  for (let len = Math.max(1, q.length - 1); len <= q.length + 1; len++) {
    for (let i = 0; i + len <= name.length; i++) {
      best = Math.min(best, levenshtein(q, name.slice(i, i + len)));
    }
  }
  return best;
}

function scoreOne(q: string, n: string): number {
  if (!q || !n) return 0;
  if (n === q) return 100;
  if (n.startsWith(q)) return 80;
  if (n.includes(q)) return 60;
  const max = maxDistance(q.length);
  if (max === 0) return 0;
  const d = windowDistance(q, n);
  return d <= max ? 40 - d * 10 : 0;
}

/** Score 0 = kein Treffer; höher = besser. */
export function scoreRole(query: string, name: string): number {
  return Math.max(
    scoreOne(normalize(query), normalize(name)),
    scoreOne(normalizeBase(query), normalizeBase(name)),
  );
}

/** Filtert + sortiert Rollen nach Trefferqualität (leere Suche: Reihenfolge unverändert). */
export function searchRoles<T extends { name: string }>(roles: T[], query: string): T[] {
  if (!normalize(query)) return roles;
  return roles
    .map((r, i) => ({ r, i, s: scoreRole(query, r.name) }))
    .filter((x) => x.s > 0)
    .sort((a, b) => b.s - a.s || a.i - b.i)
    .map((x) => x.r);
}
