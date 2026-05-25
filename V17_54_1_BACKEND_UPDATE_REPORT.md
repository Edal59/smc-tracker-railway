# v17.54.1 Backend Support Update — Report

**Date**: 2026-05-25  
**Commit**: `0176b06`  
**Railway**: ✅ Deployed — health check returns `v17.54.1`  

---

### Problem
The Pine Script hotfix changed version to v17.54.1, but the entire backend/frontend/templates stack still referenced v17.54. The health check, dashboard, settings page, and alert templates all showed the old version.

### Solution
Updated **94 version references** across **15 files** in the full stack:

---

### Files Modified

#### Backend (Python)
| File | Changes | Critical Fix? |
|---|---|---|
| `src/oie_processor.py` | 27 replacements + line 263 logic fix | ✅ YES — changed `version == "v17.54"` to `version.startswith("v17.5")` for backward compat |
| `src/webhook_server/routes.py` | 4 replacements (health check version, comments) | Health check now returns `v17.54.1` |
| `src/database.py` | 4 replacements (migration comments) | Comments only |
| `src/decoders.py` | 1 replacement (docstring) | Comments only |
| `src/oie_database.py` | 1 replacement (default version) | |
| `app.py` | 1 replacement (startup log message) | |

#### Templates (Jinja2/HTML)
| File | Changes |
|---|---|
| `templates/base.html` | 2 replacements (page title, nav badge) |
| `templates/dashboard.html` | 1 replacement (page title) |
| `templates/settings.html` | 16 replacements (alert examples, webhook templates) |

#### Frontend (Next.js/TypeScript)
| File | Changes |
|---|---|
| `tradex-frontend/app/layout.tsx` | 3 replacements (title, nav, footer) |
| `tradex-frontend/app/page.tsx` | 3 replacements (description, Pine version display, decode ref) |
| `tradex-frontend/app/settings/page.tsx` | 12 replacements (alert examples, version text) |
| `tradex-frontend/lib/api.ts` | 1 replacement (API client comment) |

#### Scripts & Docs
| File | Changes |
|---|---|
| `scripts/test_webhook.py` | 15 replacements (test payloads, descriptions) |
| `DEPLOYMENT.md` | 3 replacements |

---

### Critical Logic Fix

**`src/oie_processor.py` line 263** — The version check for v17.54+ payload normalization:

```python
# BEFORE (broken — rejects v17.54 payloads after update):
if version == "v17.54.1" and "alert" in payload:

# AFTER (correct — accepts both v17.54 and v17.54.1):
if version.startswith("v17.5") and "alert" in payload:
```

This ensures **backward compatibility** — any existing TradingView alerts still sending `"version":"v17.54"` will continue to work.

---

### Deployment Verification

#### Health Check
```json
{"service":"SMC Performance Tracker","status":"ok","version":"v17.54.1"}
```

#### Webhook Tests

| Test | Version | Alert | Symbol | Status | Opp ID |
|---|---|---|---|---|---|
| v17.54.1 payload | `v17.54.1` | A+ SNIPER BUY | BTCUSD | ✅ 200 | #1 |
| v17.54.1 payload | `v17.54.1` | RETRACE LONG | GBPUSD | ✅ 200 | #2 |
| **Backward compat** | `v17.54` | A+ SNIPER SELL | EURUSD | ✅ 200 | #3 |

All three tests passed — both v17.54.1 and v17.54 payloads are processed correctly.

---

### Version Support Matrix

| Payload Version | `detect_version()` Returns | Processing Path | Status |
|---|---|---|---|
| `v17.54.1` | `v17.54.1` | `normalize_v17_54_payload()` | ✅ Supported |
| `v17.54` | `v17.54.1` (via `startswith("v17.5")`) | `normalize_v17_54_payload()` | ✅ Backward compatible |
| `v17.25` | `v17.25` | Plot-based normalization | ✅ Supported |
| `v17.14` | `v17.14` | Legacy normalization | ✅ Supported |
| Compact format | `compact` | Direct processing | ✅ Supported |
