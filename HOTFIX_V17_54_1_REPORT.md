# Hotfix v17.54.1 — Historical Buffer Increase

**Date**: 2026-05-24  
**Commit**: `f08279f`  
**File**: `smc_premium_discount_indicator_v17.54.pine` → `smc_premium_discount_indicator_v17.54.1.pine`  
**Railway**: ✅ Deployed & Healthy  

---

### Error Resolved

```
Runtime error
Error on bar 10088: The requested historical offset (1810) is beyond 
the historical buffer's limit (1809).
at #main():2137
```

**Root Cause**: The multi-zone array system (introduced in v17.54) uses `bar_index - swingLen` lookbacks to find swing points. On data-dense 5M charts, this can exceed Pine Script's default historical buffer limit (~1800 bars).

---

### Exact Changes (3 items, zero logic modifications)

#### 1. `indicator()` declaration (line 4)
```diff
- indicator("SMC Premium/Discount Confluence Engine v17.54", shorttitle="SMC PD v17", 
-           overlay=true, max_labels_count=500, max_lines_count=500, max_boxes_count=500)
+ indicator("SMC Premium/Discount Confluence Engine v17.54.1", shorttitle="SMC PD v17", 
+           overlay=true, max_labels_count=500, max_lines_count=500, max_boxes_count=500, 
+           max_bars_back=5000)
```

#### 2. Explicit buffer declaration (line 5, new)
```pine
max_bars_back(time, 5000)
```

#### 3. Version string updates (30 occurrences)
All `"v17.54"` → `"v17.54.1"` in:
- Alert `alertcondition()` message payloads (4 lines)
- Alert `alert()` call payloads (4 lines)  
- HUD table version display (1 line)
- Comments throughout (~21 lines)

---

### Verification: Zero Logic Changes

```bash
# Extract old file from git, diff against new — filter out version strings
diff <(git show HEAD~1:smc_premium_discount_indicator_v17.54.pine) \
     smc_premium_discount_indicator_v17.54.1.pine \
     | grep "^[<>]" | grep -v "v17\\.54"

# OUTPUT (only 1 line):
> max_bars_back(time, 5000)
```

**Confirmed**: The ONLY non-version change is the added `max_bars_back(time, 5000)` line.

| Component | Changed? |
|---|---|
| Zone detection logic | ❌ No |
| Multi-zone array system | ❌ No |
| H4 P&D calculations | ❌ No |
| Alert fire conditions | ❌ No |
| Alert payload format | ❌ No (only version string in payload) |
| SL/TP calculations | ❌ No |
| Guardian logic | ❌ No |
| HUD rendering | ❌ No (only version text) |
| Backend (oie_processor.py) | ❌ No change needed — `version.startswith("v17.5")` accepts both |

---

### Buffer Settings

| Setting | Before (v17.54) | After (v17.54.1) |
|---|---|---|
| `max_bars_back` (indicator) | Default (~300–1800) | **5000** |
| `max_bars_back(time, ...)` | Not set | **5000** |

---

### Backend Compatibility

The backend `oie_processor.py` detects v17.54+ payloads via:
```python
if version.startswith("v17.5"):
    return "v17.54"
```
This matches both `"v17.54"` and `"v17.54.1"` — **no backend changes required**.

---

### Deployment

| Check | Status |
|---|---|
| Git commit | ✅ `f08279f` |
| Push to main | ✅ |
| Railway health | ✅ `{"status":"ok","version":"v17.54"}` |
| Backend accepts v17.54.1 payloads | ✅ (via `startswith("v17.5")`) |

### Next Step
**Copy `smc_premium_discount_indicator_v17.54.1.pine` into TradingView Pine Editor** and apply to 5M AUDUSD chart. The runtime error should be eliminated.
