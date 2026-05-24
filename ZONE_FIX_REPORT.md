# 5M P&D Zone Rendering Fix — Report

**Date**: 2026-05-24  
**Commit**: `43b9bae`  
**File Modified**: `smc_premium_discount_indicator_v17.54.pine`  
**Lines Changed**: 2035–2137 (zone section only)  
**Railway**: ✅ Deployed & Healthy  

---

### Problem
On 5M charts, only **one Supply zone** was visible and **no Demand zones** were painting. H4 Premium/Discount background zones worked correctly (separate system).

### Root Cause Analysis

A detailed diff of **all 11 Pine Script versions** (v17.15 through v17.54) revealed that the Supply/Demand zone code was **identical** across every version. The zone rendering used **scalar `var` variables**:

```pine
// OLD (broken) — scalar tracking, ONE zone per type
var float demandTop    = na      // ← overwritten each detection
var float demandBot    = na
var int   demandBar    = 0
var bool  demandActive = false
var box   demandBox    = na      // ← only ONE box ever drawn
```

Each time a new swing point was detected, it **overwrote** the previous zone data. Only the most recent zone of each type could ever render. On 5M charts (high swing frequency), zones appeared and disappeared rapidly, leaving at most one visible.

### Fix: Array-Based Multi-Zone Tracking

Converted from scalar to array-based tracking (lines 2056–2137):

| Component | Before (scalar) | After (array) |
|---|---|---|
| Zone storage | `var float demandTop = na` | `var array<float> dTop = array.new_float(0)` |
| Detection | `demandBot := swLow` (overwrites) | `array.push(dBot, swLow)` (accumulates) |
| Max zones | 1 per type | **10 per type** (oldest auto-trimmed) |
| Invalidation | Single `if` check | Reverse `while` loop over all zones |
| Rendering | 1 `box.new()` per type | `for` loop draws all active zones |

### What Changed (Line-by-Line)

| Lines | Change |
|---|---|
| 2035–2054 | Updated section header + documentation |
| 2056 | Added `int maxZones = 10` cap |
| 2058–2068 | Replaced 10 scalar `var` declarations with 8 `var array<>` declarations |
| 2072–2083 | Demand detection: `array.push()` + `array.shift()` trim instead of scalar overwrite |
| 2086–2097 | Supply detection: same array-push pattern |
| 2099–2107 | Demand invalidation: reverse-iteration `while` loop with `array.remove()` |
| 2109–2117 | Supply invalidation: same reverse-iteration pattern |
| 2119–2137 | Rendering: `for` loops drawing ALL active zone boxes (was 1 each) |

### What Was NOT Changed

| Component | Status |
|---|---|
| Zone detection trigger | ✅ Same: `swLow/swHigh + displacement > 0.5` |
| Zone height calculation | ✅ Same: `atrValue * 0.5` |
| Zone invalidation threshold | ✅ Same: `atrValue * 0.3` beyond boundary |
| Box styling (colors, borders, text) | ✅ Identical `box.new()` params |
| H4 Premium/Discount background zones | ✅ Completely separate system, untouched |
| `alert()` architecture | ✅ Zero changes |
| `alertcondition()` messages | ✅ Zero changes |
| Signal firing logic | ✅ Zero changes |
| SL/TP calculations | ✅ Zero changes |
| HUD table | ✅ Zero changes |
| All other files | ✅ Zero changes |

### Expected Behavior After Fix

On **5M charts**:
- ✅ Multiple filled **Supply** zones (orange, "⬤ SUPPLY" label)
- ✅ Multiple filled **Demand** zones (green, "⬤ DEMAND" label)
- ✅ Up to 10 active zones per type simultaneously
- ✅ Zones auto-invalidate when price breaks through
- ✅ Oldest zones trimmed when >10 accumulate

On **H4 charts**:
- ✅ H4 Premium/Discount background zones unchanged
- ✅ Supply/Demand zones also render (fewer due to slower swing detection)

### Deployment Verification

```json
{"service":"SMC Performance Tracker","status":"ok","version":"v17.54"}
```

### Next Step for User
**Paste the updated Pine Script into TradingView** to see the multi-zone rendering. The `.pine` file in the repo is the source of truth — copy it into TradingView's Pine Editor and apply to a 5M chart.
