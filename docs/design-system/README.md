# Designsystem abgemiked.de — Kurzfassung für NiceBot

Dieses Tool ist an die Website **abgemiked.de** (Abgemiked Media) angebunden. Die Website folgt einem einheitlichen Designsystem; dieser Ordner enthält eine Kurzfassung und die Token-Dateien, damit künftige Arbeit an diesem Tool dem gleichen System folgt.

**Vollständige Dokumentation (maßgeblich):** Repo `Abgemiked/website-abgemiked`, Ordner `docs/design-system/` (README, components, patterns, a11y, theming, tokens). Bei Abweichung gilt dort bzw. der Code `client/src/styles/gw-tokens.css` der Website.

## Dateien hier

- `tokens.json`: alle Design-Tokens (Hell + Dunkel) mit nachgerechneten Kontrastwerten.
- `gw-tokens.css`: CSS-Variablen `--gw-*` (Kopie der Quelle in der Website).

## Kurzfassung der Prinzipien

- **Look:** Flyer-Mesh-Kopf (Violett-Magenta), Pflaumenkarten (`--gw-plum`) für Hero/Zähler, weiße Karten (28 px rund), Lavendel (orientiert) und Mint (die eine Aktion pro Ansicht), Pillen-Buttons.
- **Schriften:** Bricolage Grotesque (Überschriften) und Nunito Sans (Text), selbst gehostet über `@fontsource-variable/*` (OFL-Lizenz, kein Google-Fonts-CDN). Keine Font-Dateien in diesem Ordner.
- **Hell + Dunkel:** ohne gespeicherte Wahl gilt die Systemeinstellung; die Wahl trifft der Nutzer im Profilmenü der Website (`localStorage` `theme` = `light` | `dark` | `system`). Nur `var(--gw-…)` verwenden, keine eigenen Hex-Werte.
- **Barrierefrei:** Kontrast WCAG AA, Tippziele ≥ 44 px, Status immer Wort + Farbe + Symbol, sichtbarer Fokus.
- **Keine Emojis als UI-Symbolik** (Linien-Icons neben einem Wort).
- **Ganze Kachel = ein Link; Karten statt Text direkt auf dem Mesh.**

## So bindet dieses Tool das Designsystem ein

**Rahmen in der Website.** Die Seite `/nicebot` bettet die Verwaltung als same-origin-iframe `/nicebot/` ein; Zugriff regelt weiter die eingebettete App (verknüpftes Discord-Konto + Rolle). NiceBot selbst ist ein Python-Discord-Bot; nur seine Verwaltungsoberfläche erscheint im Rahmen.

Die Website gestaltet nur die **Hülle** (Seitenhintergrund, Hero mit Titel, Rahmenkarte `.gw-frame`, Navigation, Hell/Dunkel); der Inhalt dieses Tools bleibt unberührt. Wo die Website die Rahmenhöhe automatisch an den Inhalt anpasst (`useIframeAutoHeight`, nur same-origin), scrollt die ganze Seite statt eines Balkens im Rahmen. Dafür sollte das Tool mit seinem Inhalt wachsen und kein erzwungenes `100vh`-Layout nutzen (sonst friert die Website die Höhe ein und das Tool scrollt selbst).

**Farb-/Token-Nutzung im eigenen UI.** Das eigene UI dieses Tools ist **bisher nicht auf die `--gw-*`-Tokens umgestellt** (Stand der Prüfung: kein Verweis auf die Tokens im Tool-Code). Es behält seine eigenen Farben; Anpassungen sind nur nötig, wenn Mike eine Angleichung beauftragt. Discord-Ausgaben des Bots (Embeds, Nachrichten) sind nicht Teil des Website-Designsystems.

**Wenn dieses Tool seine Oberfläche künftig angleicht:** `gw-tokens.css` einbinden, Wurzel mit `class="gw-theme"` oder `<html data-theme="light|dark">` versehen (Wahl aus `localStorage` `theme` lesen, sonst Systemeinstellung), Schriften über die zwei npm-Pakete laden, alle Farben/Radien über `var(--gw-…)`. Details: Abschnitt „In ein anderes Tool übernehmen“ in `theming.md` der Website-Doku.

**Pflege:** Ändert sich das Designsystem der Website, aktualisiert die Website-Doku zuerst; dieser Ordner wird bei Bedarf nachgezogen.
