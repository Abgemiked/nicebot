import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  massRoleCancel, massRoleCurrent, massRolePreview, massRoleResume, massRoleRoles, massRoleStart,
  type MassRole, type MassRoleJob, type MassRolePreview,
} from "./api";
import { searchRoles } from "./roleSearch";
import { BTN_DANGER, BTN_PRIMARY, BTN_SECONDARY, CARD, INPUT, Icon, toast } from "./ui";

const STATUS_TEXT: Record<MassRoleJob["status"], string> = {
  running: "Läuft …",
  done: "Fertig",
  cancelled: "Abgebrochen",
  failed: "Fehlgeschlagen",
  interrupted: "Unterbrochen (Bot-Neustart)",
};

function estimateMinutes(n: number): number {
  return Math.max(1, Math.ceil((n * 0.75) / 60));
}

export default function MassRolePage() {
  const [roles, setRoles] = useState<MassRole[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<MassRole | null>(null);
  const [includeBots, setIncludeBots] = useState(false);
  const [preview, setPreview] = useState<MassRolePreview | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [job, setJob] = useState<MassRoleJob | null>(null);
  const [dialog, setDialog] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const previewSeq = useRef(0);

  const running = job?.status === "running";

  const loadRoles = useCallback(async () => {
    const res = await massRoleRoles();
    if (res.ok) { setRoles(res.data.roles); setLoadError(null); }
    else { setRoles([]); setLoadError(res.error); }
  }, []);

  useEffect(() => {
    loadRoles();
    massRoleCurrent().then((r) => { if (r.ok) setJob(r.data.job); });
  }, [loadRoles]);

  // Fortschritt pollen, solange ein Job läuft.
  useEffect(() => {
    if (!running) return;
    const t = setInterval(async () => {
      const r = await massRoleCurrent();
      if (r.ok) {
        setJob(r.data.job);
        if (r.data.job && r.data.job.status !== "running") loadRoles();
      }
    }, 2000);
    return () => clearInterval(t);
  }, [running, loadRoles]);

  const loadPreview = useCallback(async (role: MassRole, bots: boolean) => {
    const seq = ++previewSeq.current;
    setPreviewBusy(true);
    const res = await massRolePreview(role.id, bots);
    if (seq !== previewSeq.current) return; // veraltete Antwort
    setPreviewBusy(false);
    if (res.ok) setPreview(res.data);
    else { setPreview(null); toast("err", res.error); }
  }, []);

  function choose(role: MassRole) {
    setSelected(role);
    setPreview(null);
    loadPreview(role, includeBots);
  }

  function toggleBots(v: boolean) {
    setIncludeBots(v);
    if (selected) loadPreview(selected, v);
  }

  const shown = useMemo(() => searchRoles(roles ?? [], query), [roles, query]);
  const blocked = preview?.blocked ?? selected?.blocked ?? null;
  const canStart = !!selected && !!preview && !blocked && preview.will_receive > 0 && !running && !previewBusy;

  async function onStart() {
    if (!selected || !preview) return;
    setBusy(true);
    const res = await massRoleStart(selected.id, includeBots, preview.will_receive);
    setBusy(false);
    if (res.ok) {
      setDialog(false); setTyped("");
      setJob(res.data.job);
      toast("ok", "Vergabe gestartet.");
    } else {
      toast("err", res.error);
      if (res.code === "stale" || res.code === "job_running") { setDialog(false); loadPreview(selected, includeBots); }
    }
  }

  async function onCancel() {
    if (!job) return;
    const res = await massRoleCancel(job.id);
    if (res.ok) toast("ok", "Abbruch angefordert — läuft nach dem aktuellen Mitglied aus.");
    else toast("err", res.error);
  }

  async function onResume() {
    if (!job) return;
    setBusy(true);
    const res = await massRoleResume(job.id);
    setBusy(false);
    if (res.ok) { setJob(res.data.job); toast("ok", "Vergabe wird fortgesetzt."); }
    else toast("err", res.error);
  }

  const done = job ? job.ok + job.skipped + job.failed : 0;
  const pct = job && job.total ? Math.round((done / job.total) * 100) : 0;

  return (
    <div className="flex flex-col gap-[18px]">
      {job && (
        <div className={`${CARD} p-[18px]`}>
          <div className="mb-2 flex items-center justify-between gap-3">
            <div className="text-[13.5px] font-semibold text-[#f3f4f6]">
              {running ? "Vergebe Rolle" : "Letzter Vorgang"}: „{job.role_name}“ — {STATUS_TEXT[job.status]}
            </div>
            {running && <button onClick={onCancel} className={BTN_DANGER}>Vorgang abbrechen</button>}
            {job.status === "interrupted" && <button onClick={onResume} disabled={busy} className={BTN_PRIMARY}>Fortsetzen</button>}
          </div>
          <div className="h-2.5 overflow-hidden rounded-full bg-gray-800">
            <div className="h-full bg-purple-600 transition-all" style={{ width: `${pct}%` }} />
          </div>
          <div className="mt-2 text-[13px] text-gray-400">
            {running
              ? `Vergebe Rolle … ${done} von ${job.total} · ${job.ok} vergeben · ${job.skipped} übersprungen · ${job.failed} Fehler`
              : job.status === "done"
                ? `Fertig: ${job.ok} vergeben, ${job.skipped} übersprungen, ${job.failed} Fehler.`
                : job.status === "cancelled"
                  ? `Abgebrochen nach ${done} von ${job.total}: ${job.ok} vergeben, ${job.skipped} übersprungen, ${job.failed} Fehler.`
                  : job.status === "interrupted"
                    ? `Unterbrochen nach ${done} von ${job.total} — fortsetzen?`
                    : `Fehlgeschlagen nach ${done} von ${job.total}: ${job.note ?? "unbekannter Fehler"}`}
          </div>
          {job.errors.length > 0 && (
            <ul className="mt-3 max-h-40 overflow-y-auto rounded-md border border-gray-800 bg-gray-950/50 p-3 text-[12.5px] text-red-300">
              {job.errors.map((e) => (
                <li key={e.id}>{e.name ?? e.id}: {e.error ?? "Fehler"}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className={`${CARD} p-[18px]`}>
        <div className="mb-[11px] text-[13.5px] font-semibold text-[#f3f4f6]">1 · Rolle auswählen</div>
        <div className="relative">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">{Icon.search}</span>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Rolle suchen (z. B. abgemiked) …"
            className={`${INPUT} pl-10`} />
        </div>
        {roles === null && <p className="mt-3 text-sm text-gray-400">Lade Rollen …</p>}
        {loadError && <p className="mt-3 text-sm text-red-300">Rollen nicht ladbar: {loadError}</p>}
        <div className="mt-3 flex max-h-[320px] flex-col gap-1.5 overflow-y-auto">
          {shown.map((r) => {
            const isSel = selected?.id === r.id;
            return (
              <button key={r.id} onClick={() => choose(r)} disabled={running}
                className={`flex items-center gap-3 rounded-md border px-3 py-2.5 text-left transition disabled:opacity-60 ${
                  isSel ? "border-purple-500 bg-purple-600/10" : "border-gray-800 hover:border-gray-600"} ${r.blocked ? "opacity-60" : ""}`}>
                <span className="h-3.5 w-3.5 flex-none rounded-full border border-gray-700"
                  style={{ background: r.color === "#000000" ? "#6b7280" : r.color }} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-gray-100">{r.name}</span>
                  {r.blocked && <span className="block truncate text-[11.5px] text-amber-400">{r.blocked.message}</span>}
                </span>
                <span className="flex-none text-[12px] text-gray-400">{r.member_count} Mitglieder</span>
              </button>
            );
          })}
          {roles !== null && shown.length === 0 && !loadError && (
            <p className="py-4 text-center text-sm text-gray-500">Keine passende Rolle gefunden.</p>
          )}
        </div>
      </div>

      {selected && (
        <div className={`${CARD} p-[18px]`}>
          <div className="mb-[11px] text-[13.5px] font-semibold text-[#f3f4f6]">2 · Vorschau für „{selected.name}“</div>
          <label className="mb-3 flex cursor-pointer items-center gap-2.5 text-sm text-gray-300">
            <input type="checkbox" checked={includeBots} onChange={(e) => toggleBots(e.target.checked)} disabled={running}
              className="h-4 w-4 accent-purple-600" />
            Bots einschließen
          </label>
          {previewBusy && <p className="text-sm text-gray-400">Berechne …</p>}
          {!previewBusy && blocked && (
            <div className="rounded-md border border-amber-700/50 bg-amber-950/20 p-3 text-sm text-amber-300">{blocked.message}</div>
          )}
          {!previewBusy && preview && !blocked && (
            <p className="text-sm text-gray-200">
              <b>{preview.will_receive}</b> Mitglieder bekommen die Rolle „{selected.name}“, <b>{preview.already_have}</b> haben sie bereits.
            </p>
          )}
          <div className="mt-4">
            <button onClick={() => { setTyped(""); setDialog(true); }} disabled={!canStart} className={BTN_PRIMARY}>
              Rolle an alle vergeben …
            </button>
          </div>
        </div>
      )}

      {dialog && selected && preview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4" role="dialog" aria-modal="true">
          <div className={`${CARD} w-[480px] max-w-full p-6`}>
            <h2 className="mb-2 text-lg font-bold text-white">
              Rolle „{selected.name}“ an {preview.will_receive} Mitglieder vergeben?
            </h2>
            <p className="mb-4 text-sm leading-relaxed text-gray-400">
              Das ändert die Rollen von {preview.will_receive} Mitgliedern auf dem Discord-Server und dauert ca.{" "}
              {estimateMinutes(preview.will_receive)} Minuten. Bereits vergebene Rollen bleiben unverändert. Du kannst während der
              Vergabe abbrechen; bereits vergebene Rollen werden dabei nicht zurückgenommen.
            </p>
            <label className="mb-1.5 block text-[12.5px] text-gray-400">Zur Bestätigung den Rollennamen eintippen</label>
            <input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder={selected.name} className={INPUT} autoFocus />
            <div className="mt-5 flex justify-end gap-2.5">
              <button onClick={() => setDialog(false)} className={BTN_SECONDARY}>Abbrechen</button>
              <button onClick={onStart} disabled={busy || typed.trim() !== selected.name} className={BTN_PRIMARY}>Jetzt vergeben</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
