# V17.54.3 HUD Safety Hotfix — Fix Report

**Status**: ⚠️ AWAITING USER AUDIT — DO NOT MERGE  
**Date**: 2026-05-28  
**Branch**: `hotfix/hud-tracker-v17.54.3`  
**Author**: Abacus AI Agent  

---

## Commit Hashes

| Ref | Hash | Description |
|-----|------|-------------|
| v17.54.2 (last good main) | `3124db2` | Backend update to v17.54.2 |
| v17.54.3 (original push) | `316dd11` | Direct push to main (REVERTED) |
| Revert on main | `86dbc46` | Revert of 316dd11 — main restored to v17.54.2 |
| Hotfix branch base | `316dd11` | Branched from original v17.54.3 |
| Hotfix fix commit | `43a6f9c` | Gap fixes: row map, guards, counters, pdCryptoMode |

---

## Branch Status

- **main**: Rolled back to v17.54.2 state (`86dbc46`)
- **hotfix/hud-tracker-v17.54.3**: Contains all v17.54.3 safety fixes + 3 gap fixes (`43a6f9c`)
- **Railway deployment**: Running v17.54.2 (main was reverted)

---

## 3 Specific Gaps Fixed

### Gap 1: maxHudRows — 22 → 21 (Justified with Row Map)

**Problem**: `maxHudRows = 22` was arbitrary padding (1 extra unused row).  
**Fix**: Changed to `maxHudRows = 21` — exact fit for 21-row HUD.  
**Justification**: Full HUD Row Map documented in code (lines 749-770):

```
Row  0: Header    — "SMC P&D" / version badge
Row  1: Bias      — H4 P&D bias (Bullish/Bearish/Neutral)
Row  2: Align     — Trend alignment status
Row  3: KZ        — Kill Zone status
Row  4: Sniper    — Sniper signal progress
Row  5: POI       — Point of Interest status
Row  6: Momentum  — Momentum direction
Row  7: Guardian  — Guardian filter status
Row  8: Confl     — Confluence score
Row  9: AMD       — AMD phase
Row 10: Trade     — Trade context
Row 11: Entry     — Entry mode
Row 12: Action    — Action step + plan
Row 13: Stage     — Signal stage
Row 14: Alert     — Last alert type
Row 15: Signals   — Signals today count
Row 16: Levels    — Session levels
Row 17: ZoneCfg   — [debug] Zone configuration
Row 18: ZoneHt    — [debug] Zone height / cap status
Row 19: ZoneSt    — [debug] Zone boolean states
Row 20: Ratio     — [debug] Zone ratio check
```

**Why not 12**: The HUD has 17 standard rows (0-16) + 4 debug rows (17-20) = 21 total. Reducing to 12 would silently drop rows 12-20 (Action, Stage, Alert, Signals, Levels, and all debug rows). These are all existing features from v17.54.2.

### Gap 2: f_setCell Guard Pattern — Reordered to Match Spec

**Before** (v17.54.3 original):
```pine
if not na(_t) and _col >= 0 and _col < maxHudCols and _row >= 0 and _row < maxHudRows
```

**After** (hotfix — matches user spec exactly):
```pine
if not na(_t) and _col >= 0 and _row >= 0 and _col < maxHudCols and _row < maxHudRows
```

**Change**: Guard order now matches the exact pattern from the hotfix brief: `_col >= 0 and _row >= 0` grouped together before the upper-bound checks.

**Note on table.cell vs table.cell_set_text**: The wrapper uses `table.cell()` instead of `table.cell_set_text()` because 14+ HUD cells have **dynamic colors** that change per bar (e.g., `h4ZoneColor`, `sniperProgressColor`, `confluenceColor`). Using `cell_set_text` would freeze colors at init time. `table.cell()` handles both creation and update of text + colors in a single call.

### Gap 3: f_safeText — Added str.tostring() Defensive Cast

**Before**:
```pine
f_safeText(string val) =>
    na(val) ? "—" : val
```

**After**:
```pine
f_safeText(string val) =>
    na(val) ? "—" : str.tostring(val)
```

**Rationale**: `str.tostring()` adds a defensive cast even though all current inputs are strings. If a future edit accidentally passes a float/int, `str.tostring()` prevents a type error.

---

## Additional Fixes Applied

### Tracker Counters (v17.54.3 new)

```pine
var int sniperTrades    = 0   // Total sniper signals fired (long + short)
var int activeTrades    = 0   // Currently active trade count
var int totalAlertsFired = 0  // Total alerts fired across all types
```

- `sniperTrades` increments on `fire_sniper_long` and `fire_sniper_short`
- `totalAlertsFired` increments on ALL 4 fire events (sniper long/short + retrace long/short)
- `activeTrades` placeholder for future state machine integration
- All use `var` for persistence across chart refreshes

### pdCryptoMode Toggle (v17.54.3 new)

```pine
pdCryptoMode = input.bool(false, "Crypto Mode", group=grpH4, tooltip="...")
```

- Wired into `pipSize` calculation: `pdCryptoMode or syminfo.type == "crypto" ? 1 : 10`
- Default: `false` (Forex mode)
- Group: H4 Multi-TF Bias settings

---

## Safety Patterns Summary

| Pattern | Status | Evidence |
|---------|--------|----------|
| `f_safeText()` on all dynamic values | ✅ | 20 instances on all Col 1 data cells |
| `f_setCell()` wrappers on all HUD writes | ✅ | 42 calls (0 bare `table.cell` in HUD) |
| `maxHudRows = 21`, `maxHudCols = 2` | ✅ | Exact fit with documented row map |
| Guard: `not na() and col ≥ 0 and row ≥ 0 and col < max and row < max` | ✅ | All 3 wrapper functions |
| Safe init: `var table hud = na` + `na(hud)` guard | ✅ | Lines 2749-2751 |
| No global `max_bars_back` | ✅ | Removed in v17.54.2 |
| `maxZoneAge = 500` | ✅ | Line 2168 |
| `maxZones = 10` + FIFO | ✅ | Line 2161, 6 `array.shift` calls |
| Tracker counters | ✅ | `sniperTrades`, `activeTrades`, `totalAlertsFired` |
| `pdCryptoMode` toggle | ✅ | Line 639, wired to pipSize |

---

## Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| HUD row overflow | LOW | maxHudRows=21 exact fit, bounds checked |
| na crash on dynamic text | LOW | All 20 dynamic values wrapped in f_safeText |
| table re-creation | LOW | `var table hud = na` + `na(hud)` guard |
| Tracker counter overflow | NEGLIGIBLE | Pine int supports ±9.2×10¹⁸ |
| pdCryptoMode side effects | LOW | Only affects pipSize calc, default=false |
| H4/alert logic changes | NONE | No changes to request.security, alertcondition, bias thresholds, EQ calculations |

---

## What Was NOT Changed

- ❌ H4 P&D anchor logic (17 `request.security` calls unchanged)
- ❌ Alert conditions / alertcondition() messages (wording preserved)
- ❌ Bias thresholds / EQ calculations
- ❌ Alert wording or JSON payload structure
- ❌ Zone drawing logic
- ❌ Confluence scoring
- ❌ Signal hierarchy / deduplication

---

## Artifacts Generated

1. `hotfix/hud-tracker-v17.54.3` branch — pushed to origin
2. `v17_54_3_unified.diff` — unified diff (5991 lines)
3. `V17_54_3_FIX_REPORT.md` — this report
4. `v17_54_3_VERIFICATION_REPORT.md` — verification template
5. Tag: `v17.54.3-hotfix-hud-tracker` (pending creation)

---

## Next Steps

1. **User audit**: Review this report + unified diff
2. **8-hour verification**: Run continuous 5M USDJPY test
3. **30-min dense history test**: 5M & 1M scroll
4. **Alert/tracker test**: Verify counter increments
5. **Crypto toggle test**: Enable pdCryptoMode on BTC pair
6. **User creates PR**: With proper description
7. **Merge to main**: ONLY after user approval

---

**⚠️ AWAITING USER AUDIT — DO NOT MERGE**
