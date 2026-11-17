export interface Permissions {
  tier: "full_admin" | "dc_mod" | "none";
  view_secrets: boolean;
  edit_settings: boolean;
  edit_secrets: boolean;
}

export interface Me {
  discord_id: string;
  username: string;
  permissions: Permissions;
}

// Base-Pfad der App. Standalone = "/", eingebettet unter abgemiked.de = "/nicebot".
// Alle API-Aufrufe MÜSSEN darüber laufen, sonst treffen sie unter der Einbettung
// die Website-API statt nicebot-admin.
const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");
const apiUrl = (path: string) => `${BASE}${path}`;

/** Lädt die eigene Identität. null = nicht angemeldet (401) oder kein Zugriff (403). */
export async function fetchMe(): Promise<Me | null> {
  const res = await fetch(apiUrl("/api/me"), { credentials: "same-origin" });
  if (res.status === 401 || res.status === 403) return null;
  if (!res.ok) throw new Error(`Unerwarteter Fehler: ${res.status}`);
  return res.json();
}

export async function logout(): Promise<void> {
  await fetch(apiUrl("/api/auth/logout"), { method: "POST", credentials: "same-origin" });
}

// --- Streamer-Verwaltung (M6) ---

export interface Streamer {
  name: string;
  category_id: string;
  channels: number;
}

export async function fetchStreamers(): Promise<Streamer[]> {
  const res = await fetch(apiUrl("/api/streamers"), { credentials: "same-origin" });
  if (!res.ok) throw new Error(`Streamer nicht ladbar (${res.status})`);
  return (await res.json()).streamers ?? [];
}

export async function createStreamer(name: string): Promise<SaveResult> {
  return streamerWrite("POST", name);
}

export async function deleteStreamer(name: string): Promise<SaveResult> {
  return streamerWrite("DELETE", name);
}

async function streamerWrite(method: string, name: string): Promise<SaveResult> {
  const res = await fetch(apiUrl("/api/streamers"), {
    method,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (res.ok) return { ok: true };
  let detail: unknown = null;
  try {
    detail = (await res.json()).detail;
  } catch {
    /* kein JSON */
  }
  return { ok: false, error: typeof detail === "string" ? detail : `Fehler ${res.status}` };
}

// --- Member-Übersicht (M7) ---

export interface Member {
  id: string;
  name: string;
  display_name: string;
  roles: { id: string; name: string }[];
}

export interface MemberList {
  items: Member[];
  total: number;
  page: number;
  page_size: number;
}

export async function fetchMembers(params: {
  search?: string;
  page?: number;
  page_size?: number;
}): Promise<MemberList> {
  const q = new URLSearchParams();
  if (params.search) q.set("search", params.search);
  q.set("page", String(params.page ?? 1));
  q.set("page_size", String(params.page_size ?? 25));
  const res = await fetch(apiUrl(`/api/members?${q.toString()}`), { credentials: "same-origin" });
  if (!res.ok) throw new Error(`Mitglieder nicht ladbar (${res.status})`);
  return res.json();
}

// --- Laufzeit-Secrets (.env, nur Voll-Admin) ---

export interface SecretEntry {
  key: string;
  label: string;
  value: string;
  set: boolean;
}

export async function fetchSecrets(): Promise<SecretEntry[]> {
  const res = await fetch(apiUrl("/api/secrets"), { credentials: "same-origin" });
  if (!res.ok) throw new Error(`Secrets nicht ladbar (${res.status})`);
  return (await res.json()).secrets ?? [];
}

export async function saveSecrets(
  updates: Record<string, string>
): Promise<SaveResult & { restartRequired?: boolean }> {
  const res = await fetch(apiUrl("/api/secrets"), {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ updates }),
  });
  if (res.ok) {
    const d = await res.json();
    return { ok: true, updated: d.updated, restartRequired: d.restart_required };
  }
  let detail: unknown = null;
  try {
    detail = (await res.json()).detail;
  } catch {
    /* kein JSON */
  }
  return { ok: false, error: typeof detail === "string" ? detail : `Fehler ${res.status}` };
}

// --- Discord-Stammdaten für Dropdowns ---

export interface DiscordChannel {
  id: string;
  name: string;
  type: string; // text, voice, category, …
  category: string | null;
}

export interface DiscordRole {
  id: string;
  name: string;
}

export async function fetchChannels(): Promise<DiscordChannel[]> {
  const res = await fetch(apiUrl("/api/discord/channels"), { credentials: "same-origin" });
  if (!res.ok) return []; // Bot evtl. weg → Felder fallen auf Texteingabe zurück
  return (await res.json()).channels ?? [];
}

export async function fetchRoles(): Promise<DiscordRole[]> {
  const res = await fetch(apiUrl("/api/discord/roles"), { credentials: "same-origin" });
  if (!res.ok) return [];
  return (await res.json()).roles ?? [];
}

// --- Audit-Log & Statistiken (M5 + M4) ---

export interface AuditEvent {
  id: number;
  ts: string;
  event_type: string;
  actor_name: string | null;
  target_id: string | null;
  target_name: string | null;
  channel_id: string | null;
  content: string | null;
  meta: unknown;
}

export interface AuditList {
  event_types: string[];
  items: AuditEvent[];
  total: number;
  page: number;
  page_size: number;
}

export async function fetchAudit(params: {
  event_type?: string;
  page?: number;
  page_size?: number;
}): Promise<AuditList> {
  const q = new URLSearchParams();
  if (params.event_type) q.set("event_type", params.event_type);
  q.set("page", String(params.page ?? 1));
  q.set("page_size", String(params.page_size ?? 25));
  const res = await fetch(apiUrl(`/api/audit?${q.toString()}`), { credentials: "same-origin" });
  if (!res.ok) throw new Error(`Audit-Log konnte nicht geladen werden (${res.status})`);
  return res.json();
}

export interface Stats {
  member_count: number;
  members_without_ignored: number;
  ignored_role_members: number;
}

export async function fetchStats(): Promise<Stats | null> {
  const res = await fetch(apiUrl("/api/stats"), { credentials: "same-origin" });
  if (!res.ok) return null; // Bot evtl. nicht erreichbar — Seite bleibt nutzbar
  return res.json();
}

// --- Bot-Konfiguration (M2) ---

export interface ConfigField {
  key: string;
  group: string;
  type: "id" | "idlist" | "string" | "hostlist" | "secret";
  kind?: "channel" | "voice" | "category" | "role" | "rolelist" | "keyword" | "hostlist" | "idlist";
  label: string;
  secret: boolean;
  editable: boolean;
}

export interface ConfigResponse {
  fields: ConfigField[];
  values: Record<string, unknown>;
  can_view_secrets: boolean;
  restart_required_keys: string[];
}

export async function fetchConfig(): Promise<ConfigResponse> {
  const res = await fetch(apiUrl("/api/config"), { credentials: "same-origin" });
  if (!res.ok) throw new Error(`Konfiguration konnte nicht geladen werden (${res.status})`);
  return res.json();
}

export interface SaveResult {
  ok: boolean;
  updated?: string[];
  error?: string;
  fieldErrors?: Record<string, string>;
}

// --- Level-System (M3) ---

export interface LevelUser {
  user_id: string;
  username: string | null;
  level: number;
  exp: number;
}

export interface LevelList {
  items: LevelUser[];
  total: number;
  page: number;
  page_size: number;
}

export async function fetchLevels(params: {
  search?: string;
  sort?: string;
  direction?: string;
  page?: number;
  page_size?: number;
}): Promise<LevelList> {
  const q = new URLSearchParams();
  if (params.search) q.set("search", params.search);
  if (params.sort) q.set("sort", params.sort);
  if (params.direction) q.set("direction", params.direction);
  q.set("page", String(params.page ?? 1));
  q.set("page_size", String(params.page_size ?? 25));
  const res = await fetch(apiUrl(`/api/levels?${q.toString()}`), { credentials: "same-origin" });
  if (!res.ok) throw new Error(`Rangliste konnte nicht geladen werden (${res.status})`);
  return res.json();
}

export async function updateLevel(
  userId: string,
  level: number,
  exp: number
): Promise<SaveResult> {
  const res = await fetch(apiUrl(`/api/levels/${userId}`), {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ level, exp }),
  });
  if (res.ok) return { ok: true };
  let detail: unknown = null;
  try {
    detail = (await res.json()).detail;
  } catch {
    /* kein JSON-Body */
  }
  return { ok: false, error: typeof detail === "string" ? detail : `Fehler ${res.status}` };
}

export async function saveConfig(updates: Record<string, unknown>): Promise<SaveResult> {
  const res = await fetch(apiUrl("/api/config"), {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ updates }),
  });
  if (res.ok) return { ok: true, ...(await res.json()) };
  let detail: unknown = null;
  try {
    detail = (await res.json()).detail;
  } catch {
    /* kein JSON-Body */
  }
  if (detail && typeof detail === "object" && "validation_errors" in (detail as object)) {
    return { ok: false, fieldErrors: (detail as { validation_errors: Record<string, string> }).validation_errors };
  }
  return { ok: false, error: typeof detail === "string" ? detail : `Fehler ${res.status}` };
}

// --- Massen-Rollenvergabe (nur Voll-Admin) ---

export interface MassRoleBlock {
  code: string;
  message: string;
  permissions?: string[];
}

export interface MassRole {
  id: string;
  name: string;
  color: string;
  position: number;
  member_count: number;
  blocked: MassRoleBlock | null;
}

export interface MassRolePreview {
  blocked: MassRoleBlock | null;
  role_name?: string;
  total_targets: number;
  already_have: number;
  will_receive: number;
}

export interface MassRoleJob {
  id: number;
  role_id: string;
  role_name: string;
  include_bots: boolean;
  actor_name: string | null;
  status: "running" | "done" | "cancelled" | "failed" | "interrupted";
  total: number;
  ok: number;
  skipped: number;
  failed: number;
  pending: number;
  started_at: string;
  finished_at: string | null;
  note: string | null;
  errors: { id: string; name: string | null; error: string | null }[];
}

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: string; code?: string };

async function massRoleCall<T>(method: string, path: string, body?: unknown): Promise<ApiResult<T>> {
  try {
    const res = await fetch(apiUrl(`/api/massrole${path}`), {
      method,
      credentials: "same-origin",
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    if (res.ok) return { ok: true, data: (await res.json()) as T };
    let detail: unknown = null;
    try {
      detail = (await res.json()).detail;
    } catch {
      /* kein JSON */
    }
    if (detail && typeof detail === "object") {
      const d = detail as { message?: string; code?: string };
      return { ok: false, error: d.message ?? `Fehler ${res.status}`, code: d.code };
    }
    return { ok: false, error: typeof detail === "string" ? detail : `Fehler ${res.status}` };
  } catch {
    return { ok: false, error: "Server nicht erreichbar" };
  }
}

export const massRoleRoles = () => massRoleCall<{ roles: MassRole[] }>("GET", "/roles");
export const massRolePreview = (role_id: string, include_bots: boolean) =>
  massRoleCall<MassRolePreview>("POST", "/preview", { role_id, include_bots });
export const massRoleStart = (role_id: string, include_bots: boolean, confirm_count: number) =>
  massRoleCall<{ job: MassRoleJob }>("POST", "/start", { role_id, include_bots, confirm_count });
export const massRoleCurrent = () => massRoleCall<{ job: MassRoleJob | null }>("GET", "/jobs/current");
export const massRoleCancel = (id: number) => massRoleCall<{ job: MassRoleJob }>("POST", `/jobs/${id}/cancel`, {});
export const massRoleResume = (id: number) => massRoleCall<{ job: MassRoleJob }>("POST", `/jobs/${id}/resume`, {});
