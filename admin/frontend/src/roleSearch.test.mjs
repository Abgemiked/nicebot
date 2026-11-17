// Ausführen: node --experimental-strip-types src/roleSearch.test.mjs   (Node >= 22.6)
import assert from "node:assert/strict";
import { normalize, searchRoles, scoreRole, levenshtein } from "./roleSearch.ts";

const roles = ["abgemiked", "Moderator", "Küchenhilfe", "Streamer", "NiceCom Mitglied", "DJ", "Turnierteilnehmer-Cup"]
  .map((name) => ({ name }));
const names = (q) => searchRoles(roles, q).map((r) => r.name);

assert.equal(normalize("  Ab-Gemiked! "), "abgemiked");
assert.equal(normalize("Küche"), "kueche");
assert.equal(levenshtein("kitten", "sitting"), 3);

// exakt / Groß-Klein / Teilstring
assert.deepEqual(names("abgemiked"), ["abgemiked"]);
assert.deepEqual(names("ABGEMIKED "), ["abgemiked"]);
assert.deepEqual(names("gemik"), ["abgemiked"]);
// Tippfehler
assert.deepEqual(names("abgemicked"), ["abgemiked"]);
assert.deepEqual(names("abgemikt"), ["abgemiked"]);
assert.deepEqual(names("moderater"), ["Moderator"]);
// Umlaute
assert.deepEqual(names("kuechenhilfe"), ["Küchenhilfe"]);
assert.deepEqual(names("kuchenhilfe"), ["Küchenhilfe"]);
assert.deepEqual(names("küche"), ["Küchenhilfe"]);
// Leerzeichen/Sonderzeichen
assert.deepEqual(names("nicecom mitglied"), ["NiceCom Mitglied"]);
assert.deepEqual(names("turnierteilnehmercup"), ["Turnierteilnehmer-Cup"]);
// Rang: Präfix vor Teilstring
const r2 = searchRoles([{ name: "xxStream" }, { name: "Streamer" }], "stream").map((r) => r.name);
assert.deepEqual(r2, ["Streamer", "xxStream"]);
// kein Treffer / kurze Eingaben nicht fuzzy
assert.deepEqual(names("zzzzzz"), []);
assert.deepEqual(names("dk"), []);
assert.equal(searchRoles(roles, "").length, roles.length);
assert.ok(scoreRole("abgemiked", "abgemiked") > scoreRole("abgemik", "abgemiked"));
console.log("roleSearch: alle Tests OK");
