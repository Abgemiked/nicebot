# Claude-Design-Prompt — nicebot-Admin an abgemiked.de angleichen

> **So nutzt du das:** Öffne Claude Design (`/design`) und füge den kompletten Block unter
> „PROMPT" ein. Er ist selbst-tragend (alle Tokens, Screens und technischen Constraints sind
> enthalten). Ergebnis = Artboards/Mockups im abgemiked.de-Stil, die team-dev anschließend
> 1:1 in Tailwind umsetzt, ohne die Einbettungs-/Auth-Mechanik zu brechen.

---

## PROMPT (ab hier alles kopieren)

Entwirf das **UI-Redesign eines bestehenden React-Admin-Dashboards („nicebot-admin", Discord-Bot-Verwaltung)**, sodass es visuell exakt zum Design-System der Website **abgemiked.de** passt. Es ist ein reines **Re-Skin** (Farben, Typografie, Abstände, Komponenten-Look) — Struktur, Datenflüsse und API bleiben unverändert. Liefere Artboards für alle unten genannten Screens plus eine Token-Tabelle.

### Ziel-Design-System (abgemiked.de) — verbindlich

- **Framework:** Tailwind CSS 3 mit **Standard-Palette** (kein Custom-Theme), Dark-Mode (media).
- **Schrift:** **Inter** (Fallback system-ui). Antialiased. Keine Sora/Jakarta/Mono mehr.
- **Farben (Tailwind-Defaults, so verwendet):**
  - Seiten-Hintergrund `gray-950` (#030712); Flächen/Nav/Karten `gray-900` (#111827); dezente Flächen `gray-900/40`.
  - Akzent Primär `purple-600` (#9333ea, Buttons), Hover `purple-700`; Links/Icons `purple-400` (#c084fc); Ränder/Ringe/Hover-Border `purple-500`/`purple-600`.
  - Text: Überschriften `white`; Fließtext/Muted `gray-400`; sekundär `gray-300`; sehr dezent `gray-500`.
  - Ränder: `gray-800` (#1f2937), feiner `gray-700`.
  - Discord-Aktion: `#5865F2` (Hover `#4752c4`). Erfolg `green-*`, Fehler `red-*`, Warnung `amber/yellow-*` (Tailwind-Defaults).
- **Komponenten-Muster (aus abgemiked.de übernehmen):**
  - **Seiten-Header/Hero:** zentriert; H1 `text-3xl md:text-4xl font-bold text-white mb-2`; Untertitel `text-gray-400 max-w-2xl mx-auto`.
  - **Karte:** `bg-gray-900 border border-gray-800 rounded-2xl p-5 hover:border-purple-600 transition`.
  - **Primär-Button:** `bg-purple-600 hover:bg-purple-700 text-white rounded-md px-4 py-1.5 text-sm font-medium`.
  - **Sekundär/Ghost-Button:** `border border-gray-600 hover:border-purple-500 text-gray-300 rounded-md px-4 py-2 text-sm`.
  - **Link:** `text-purple-400 hover:underline`.
  - **Tabellen:** Kopf `text-gray-400 font-medium border-b border-gray-700`; Zeilen `divide-y divide-gray-800 text-gray-400`; Zellen `py-2`.
  - **Eingaben:** dunkel (`bg-gray-800/60`), Rand `gray-700`, Fokus-Ring `purple-500`, Radius `rounded-md`.
  - **Container-Breite:** `max-w-5xl/6xl mx-auto px-4`. Touch-Ziele ≥ 44px.
  - Ecken generell weich (Buttons `rounded-md`, Karten/Panels `rounded-2xl`). Schlichte Schatten (`shadow-lg`), KEINE Neon-Glows/Blob-Animationen (die alten `blob`/`glow`-Effekte entfallen).

### Was neu gestaltet wird (Screens / Artboards)

Das Dashboard hat eine **feste Shell** (linke Sidebar 264px + Header + Content) und mehrere Seiten. Bitte je ein Artboard (Desktop 1280×800), plus die zwei Zustände:

1. **App-Shell** — Sidebar (Logo „nicebot" + Untertitel „abgemiked.de"; Navigation: Konfiguration, Level & Ränge, Streamer, Mitglieder, Logs & Statistiken; Abschnitt „Administration" mit „Secrets [ADMIN]" nur für Voll-Admin; unten User-Badge mit Initialen-Avatar, Rolle, Logout) + Header (Seitentitel + Untertitel) + Content-Bereich.
2. **Konfiguration** — Formular/Felder-Gruppen (Channels, Filter, Rollen) mit Dropdowns & Speichern-Leiste.
3. **Level & Ränge** — durchsuchbare, paginierte Tabelle (User, Level, EXP), Inline-Bearbeiten (nur Voll-Admin).
4. **Streamer** — Liste beobachteter Streamer + Hinzufügen/Entfernen.
5. **Mitglieder** — durchsuchbare, paginierte Tabelle (Name, Rollen-Chips).
6. **Logs & Statistiken** — Kennzahlen-Kacheln (Membercount etc.) + gefiltertes Audit-Log (Tabelle).
7. **Secrets** — Schlüssel/Wert-Liste mit maskierten Werten (••••), nur Voll-Admin, Warn-Hinweis.
8. **Kein-Zugriff-Karte (eingebettet)** — kompakte zentrierte Karte: Titel, kurzer Text „Kein Zugriff auf die Bot-Verwaltung. Voraussetzungen: auf abgemiked.de eingeloggt, Discord auf der Konto-Seite verknüpft, berechtigte Server-Rolle." + Primär-Button „Zur Konto-Seite".

**Rollen-abhängige Sicht:** Rolle `dc_mod` sieht/bearbeitet Einstellungen, aber **keine Secrets** (Secrets-Nav + -Seite ausgeblendet, Secret-Werte maskiert). Rolle `full_admin` sieht alles. Bitte beide Varianten in den betroffenen Artboards andeuten.

### HARTE technische Constraints (das Design MUSS damit umsetzbar sein)

Das ist kein Standalone-Web — es läuft **als iframe eingebettet in abgemiked.de**. Halte dich strikt daran, sonst ist der Entwurf nicht implementierbar:

1. **Stack:** React 18 + Vite 5 + TypeScript + **Tailwind 3**. Alles wird gebündelt; eine FastAPI liefert die gebaute SPA aus und stellt die API unter `/api/*` bereit.
2. **Einbettung:** Die App wird **same-origin in einem iframe** unter `https://abgemiked.de/nicebot` gerendert (nginx-Proxy). Es gibt daher **keine eigene Top-Navigation/Footer** wie eine Vollseite — die Shell ist bewusst kompakt (Sidebar+Header genügen). Wenn eingebettet, wird die eigene Marken-Kopfzeile klein gehalten.
3. **Base-Pfad:** Vite `base=/nicebot/`. Alle Asset- und API-Pfade laufen über `import.meta.env.BASE_URL`; React-Router nutzt `basename`. **Keine hart kodierten absoluten Pfade** (`/assets`, `/api`) im Design annehmen — relative/basierte Pfade.
4. **Content-Security-Policy (nicht lockerbar) — Design muss darin funktionieren:**
   - `script-src 'self'` → **kein externes/CDN-JS, keine Inline-Skripte, keine Third-Party-Widgets.**
   - `style-src 'self' 'unsafe-inline' https://fonts.googleapis.com` → Tailwind/Inline-Styles ok; **Google Fonts (Inter) erlaubt.**
   - `font-src 'self' https://fonts.gstatic.com` → nur Self + Google-Fonts-Dateien.
   - `img-src 'self' data:` → **nur same-origin-Bilder + data-URIs.** Keine externen Bild-URLs, keine Remote-Avatare. Nutzer-Avatare bleiben **aus Initialen generiert** (kein Discord-CDN).
   - `connect-src 'self'` → Browser-Fetches nur same-origin (die eigene API). Keine externen Requests.
   - `frame-ancestors 'self'` → nur same-origin-Einbettung.
5. **Auth/Rollen (Datenvertrag unverändert):** `/api/me` liefert `{ discord_id, username, permissions: { tier: "full_admin" | "dc_mod" | "none", view_secrets, edit_settings, edit_secrets } }`. Zugang läuft serverseitig über eine SSO-Bridge (zentrales `abgemiked_session`-Cookie → verknüpfte Discord-ID → Discord-Rolle). Das Frontend triggert **keinen eigenen Discord-OAuth im iframe** — im Nicht-Zugriffs-Fall zeigt es die „Kein-Zugriff"-Karte mit Link auf `https://abgemiked.de/konto` (Ziel `_top`).
6. **API-Contract bleibt:** Endpunkte & Datenformen unverändert — `/api/config` (GET/PUT), `/api/levels` (GET, PUT `/levels/{id}`), `/api/streamers` (GET/POST/DELETE), `/api/members`, `/api/audit` + `/api/stats`, `/api/secrets` (GET/PUT, nur Voll-Admin), `/api/discord/channels`+`/roles`, `/api/auth/logout`. Das Redesign ändert **nur Optik/Layout**, nicht Props oder Datenflüsse der Seiten-Komponenten (`ConfigPage`, `LevelPage`, `StreamerPage`, `MemberPage`, `AuditPage`, `SecretsPage`, gemeinsame `ui.tsx`).
7. **Ausgabe:** Reines Tailwind (Utility-Klassen), keine zusätzlichen UI-Libraries/Icon-Pakete (bestehende Inline-SVG-Icons dürfen bleiben, gern im neuen Stil). Ziel: ein Entwickler setzt die Artboards direkt in die bestehenden Komponenten um.

Bitte liefere: die Artboards oben + eine kompakte **Token-/Klassen-Tabelle** (Alt→Neu-Mapping der Farben/Schrift), damit die Umsetzung eindeutig ist.

## PROMPT (Ende)

---

## Nach dem Claude-Design-Lauf (für dich/den PM)

1. Claude Design liefert Artboards + Token-Tabelle.
2. **team-dev** setzt um (reines Re-Skin): neue `tailwind.config` (Inter, Tailwind-Default-Farben statt Custom-Tokens), `index.css` (Font, Scrollbar), `ui.tsx` + Seiten-Komponenten auf die neuen Klassen. **Nicht** anfassen: Base-Pfad-Logik, `api.ts`-Fetch-Wrapping, Router-`basename`, Embed-/Bridge-Verhalten, CSP, API-Contract.
3. Deploy wie Phase 3 (Docker-Rebuild `nicebot-admin`), Verify: `/nicebot/api/health`, Einbettung lädt, Rollen-Gating stimmt.
