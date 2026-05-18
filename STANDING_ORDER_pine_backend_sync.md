# STANDING ORDER: Pine Script ↔ Backend Version Sync Protocol

> Effective immediately. **Mandatory** on every Pine Script version increment.
> Reason: On `2026-05-17` the production Railway dashboard was caught serving **v17.15** while the Pine Script was at **v17.25**, and the on-page alert templates contained wrong `{{plot_X}}` mappings (`h4_bias=plot_3` instead of `plot_10`, etc.) which would have produced wrong opportunity records for every alert pasted from the dashboard.

---

## The Rule
**You may not ship a Pine Script version bump as "complete" unless the backend, templates, frontend, schema, and alert template documentation are updated in the same PR (or an immediately-following sibling PR merged together).**

A Pine Script bump on its own is a regression. The dashboard becomes a lie. Alert templates drift silently.

---

## Mandatory Checklist on Every `vX.Y → vX.Z` Increment

Run this checklist **every single time** the Pine Script's `indicator(...)` title changes. No exceptions.

### 1. Backup
- [ ] `cp smc_premium_discount_indicator_v<OLD>.pine smc_premium_discount_indicator_v<OLD>_backup.pine`
- [ ] Snapshot the backend: `cp -r app.py templates src schemas tradex-frontend/app backups/v<OLD>_backend_backup/`

### 2. Pine Script
- [ ] Update `indicator(...)` title to new version.
- [ ] Update changelog header.
- [ ] Update HUD header cell text.
- [ ] Update **all four** `alertcondition()` JSON payloads: `sniper_long`, `sniper_short`, `retrace_long`, `retrace_short` — both the `"version":"..."` field and any inline comments.
- [ ] Confirm plot budget ≤ 64 (`grep -c "^plot\|plotshape\|alertcondition\|bgcolor"`).

### 3. Backend Version Strings
Update **every** occurrence in:
- [ ] `app.py` (logger banner)
- [ ] `src/webhook_server/routes.py` (sample payloads + format-detection comments)
- [ ] `src/database.py` (migration log messages)
- [ ] `src/decoders.py` (module header)
- [ ] `src/oie_database.py` (default version on insert)
- [ ] `src/oie_processor.py` (header + the **current-version branch only** — keep legacy version branches intact for backward compatibility)
- [ ] `schemas/migrate_v17_*.sql` (header comment + `DEFAULT 'vX.Z'`)

### 4. HTML Templates
- [ ] `templates/base.html` — `<title>` + footer badge
- [ ] `templates/settings.html` — title, section headers, server-info badge, decode-reference label, API-endpoints heading
- [ ] `templates/dashboard.html` — `<title>`
- [ ] `templates/trades.html` — `<title>`
- [ ] `templates/opportunities.html` — `<title>` + page badge

### 5. Next.js Frontend
- [ ] `tradex-frontend/app/layout.tsx` — title metadata, header & footer badges
- [ ] `tradex-frontend/app/page.tsx` — hero subtitle, version badge, decode-reference header
- [ ] `tradex-frontend/app/opportunities/page.tsx` — subtitle + empty-state copy
- [ ] `tradex-frontend/app/settings/page.tsx` — section header + all alert JSON blocks
- [ ] `tradex-frontend/lib/api.ts` — module banner

### 6. Alert Template Audit (CRITICAL)
Open the Pine Script and read lines containing `alertcondition(...)`. For each of the 4 alerts, write down the **exact** `{{plot_N}}` placement for every JSON field. Then open:
- [ ] `templates/settings.html` — the four `<pre>` blocks under "Alert Templates"
- [ ] `tradex-frontend/app/settings/page.tsx` — the four `<pre>` blocks under "Alert Templates"

For **each** of the 4 alerts (`sniper_long`, `sniper_short`, `retrace_long`, `retrace_short`), confirm field-by-field that every `{{plot_N}}` in the docs matches the Pine Script. **Never copy from the previous version's template** — always re-derive from the Pine Script's `alertcondition()` line for the new version.

Currently (v17.25) the canonical map is:
```
plot_0  → entryLong          plot_7  → poiScore
plot_1  → slLong             plot_8  → confluenceScore
plot_2  → tpLong             plot_9  → dtStage
plot_3  → entryShort         plot_10 → h4Bias
plot_4  → slShort            plot_11 → pdZone
plot_5  → tpShort            plot_12 → kzCode (kill_zone)
plot_6  → qualityScore       plot_13 → guardianCode
```

If the Pine Script renumbers plots in a future version, this map **must** be re-derived and the templates **must** be regenerated.

### 7. Validation
- [ ] `python3 -m py_compile app.py src/**/*.py` → exit 0
- [ ] Jinja2 parse: `for t in templates/*.html; do python3 -c "from jinja2 import Environment, FileSystemLoader; Environment(loader=FileSystemLoader('templates')).get_template('$(basename $t)')"; done`
- [ ] Flask test client renders every page with the new version visible and no stale version strings.
- [ ] `cd tradex-frontend && npx tsc --noEmit` → exit 0.
- [ ] `grep -rEn "v<OLD>" --include="*.py" --include="*.html" --include="*.tsx" --include="*.ts" --include="*.sql" | grep -v "backups/\|test_oie_integration\|smc_premium_discount_indicator"` → empty.

### 8. Deploy Verification
- [ ] After merging to `main`, wait for Railway redeploy.
- [ ] `curl -s https://web-production-b63af.up.railway.app/settings | grep -c "v<NEW>"` → ≥ 5.
- [ ] After merging, wait for Vercel redeploy.
- [ ] `curl -s https://smc-tracker-railway-2027.vercel.app/settings | grep -c "v<NEW>"` → ≥ 5.

### 9. Reporting
- [ ] Write `v<NEW>_completion_report.md` covering Pine Script changes.
- [ ] Write `v<NEW>_backend_sync_report.md` covering backend + frontend + template audit.

---

## Anti-patterns (Do Not Do These)
- ❌ Shipping a Pine Script bump on TradingView before the backend is updated.
- ❌ Updating only the `<title>` and `<badge>` and skipping the alert template audit.
- ❌ Copying the previous version's settings.html alert blocks forward without re-checking the Pine Script's `alertcondition()` plot indices.
- ❌ Touching `oie_processor.py`'s `v17.14` / `v17.12.3` compatibility branches when sweeping version strings — those are intentional legacy handlers.
- ❌ Modifying `test_oie_integration.py`'s legacy payloads — they're there to prove the backend still accepts old alerts.
- ❌ Force-pushing or skipping the per-version backup directory.

---

## When You're Done
You should be able to answer **YES** to every one of these:
1. Does `https://web-production-b63af.up.railway.app/settings` display the new version?
2. Does `https://smc-tracker-railway-2027.vercel.app/settings` display the new version?
3. If a user copies a Sniper Long template from `/settings` into TradingView **right now**, will the decoded opportunity row show correct `h4_bias`, `p_d_zone`, `guardian`, `quality`, and `poi` values?
4. Is there a backup of the previous backend state under `backups/v<OLD>_backend_backup/`?
5. Are the completion report **and** the backend-sync report both present in the repo root?

If any answer is "no", **the release is not complete**.

---

_Last enforced: v17.25 (2026-05-17) — see `v17.25_backend_sync_report.md`._
