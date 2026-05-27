# SMC P&D Indicator v17.54.2 — Fix Report

**Date:** May 27, 2026  
**Commit:** `2330c11`  
**Deployed:** Railway auto-deploy (main branch)

---

## Issues Fixed

### 1. "Indicator error" Crash on Data-Dense Charts (5M USDJPY)

**Root Cause:** The indicator declaration had `max_bars_back=5000` as a global parameter:
```pine
indicator(..., max_bars_back=5000)  // Line 4
max_bars_back(time, 5000)           // Line 5
```
This forced TradingView to maintain **5000-bar deep buffers for EVERY variable** in the script. On data-dense timeframes like 5M USDJPY (which loads thousands of bars), this exceeded TradingView's internal memory limits, producing the generic "Indicator error" crash.

The original fix in v17.54 was meant to address a "historical offset (1810) beyond buffer limit (1809)" error on zone `bar_index` arrays — but the sledgehammer approach of applying 5000 bars globally caused more problems than it solved.

**Fix:**
- Removed `max_bars_back=5000` from `indicator()` declaration
- Removed `max_bars_back(time, 5000)` global override
- Added **zone age pruning** (`maxZoneAge = 500` bars) so zone `dBar`/`sBar` arrays never reference bar indices older than 500 bars back — eliminating the deep lookback that originally caused the offset error without needing a global buffer override

### 2. HUD Table Disappearing Intermittently

**Root Cause:** The HUD table was created inside `barstate.islast`:
```pine
if showHUD and barstate.islast
    var table hud = table.new(...)  // Only created when last bar is reached
```
While `var` makes it persist, the table object only gets initialized when TradingView first reaches the last bar. During chart navigation, replay mode, or when the script reloads, the `barstate.islast` condition may not fire immediately, causing the HUD to appear blank or disappear temporarily.

**Fix:**
```pine
var table hud = na                           // Created at global scope on first bar
if showHUD and na(hud)
    hud := table.new(...)                    // Initialized once, persists via var
if showHUD and barstate.islast and not na(hud)
    table.cell(hud, ...)                     // Populated only on last bar
```
The table object now exists from bar 1, but only gets populated with data on the last bar. This ensures the HUD is always available and renders reliably.

### 3. Zone Rendering Optimization

**Issues:**
- `for _i = 0 to math.max(array.size(dTop) - 1, 0)` — when array is empty, this still runs once with `_i = 0` (wasteful iteration that relies on an inner `if` guard)
- No age-based pruning meant arrays could accumulate zones from the entire chart history

**Fix:**
- Added explicit `if array.size(dTop) > 0` guards before drawing loops
- Added `maxZoneAge = 500` — zones older than 500 bars are auto-removed during the invalidation pass
- Invalidation now checks both price breach AND age: `if _priceBreach or _tooOld`

---

## Question: Do Premium & Discount Zones Dynamically Adjust?

### ✅ YES — H4 P&D zones are fully dynamic

The Premium/Discount zone boundaries recalculate on **every bar** using a rolling H4 lookback window:

#### Code Evidence (Lines 740-741):
```pine
h4RangeHigh = request.security("240", ta.highest(high, effectiveLookback))
h4RangeLow  = request.security("240", ta.lowest(low, effectiveLookback))
```

#### How It Works:
1. **`request.security("240", ...)`** — pulls H4 timeframe data regardless of chart timeframe
2. **`ta.highest(high, effectiveLookback)`** — rolling highest high over the lookback period (default 14 H4 bars = ~2.3 trading days)
3. **`ta.lowest(low, effectiveLookback)`** — rolling lowest low over the same window
4. As new H4 bars form, old bars fall out of the window → `h4RangeHigh`/`h4RangeLow` shift

#### Derived Zones (Lines 784-798):
```pine
h4Eq            = (h4RangeHigh + h4RangeLow) / 2     // Equilibrium midpoint
h4PremiumBottom = h4Eq + (h4RangeHigh - h4Eq) * 0.0  // = h4Eq
h4DiscountTop   = h4Eq - (h4Eq - h4RangeLow) * 0.0   // = h4Eq
h4PremiumTop    = h4RangeHigh                          // Top of premium
h4DiscountBottom = h4RangeLow                          // Bottom of discount
```

All five zone boundaries derive from `h4RangeHigh` and `h4RangeLow` → **all dynamic**.

#### Practical Impact:
- **Strong trend up:** H4 range shifts higher → old discount zones become equilibrium → new premium zones form above
- **Range-bound market:** H4 range stays stable → zones stay roughly constant
- **After large candle:** Next H4 bar extends the range → zones expand in that direction
- **After consolidation:** Old extremes drop out of the 14-bar window → zones contract

---

## Files Changed

| File | Action |
|------|--------|
| `smc_premium_discount_indicator_v17.54.2.pine` | **NEW** — v17.54.2 with all fixes |
| `smc_premium_discount_indicator_v17.54.1.pine` | Preserved (unchanged) for rollback reference |

---

## Deployment Status

- ✅ Git committed and pushed to `main`
- ✅ Railway health check: `https://web-production-b63af.up.railway.app/api/v1/health` → `status: ok`
- ✅ Backend accepts v17.54.2 alerts (version check: `startswith("v17.5")`)
- ⚠️ User must paste the new Pine Script into TradingView to activate v17.54.2

## Next Steps for User

1. Open TradingView → Pine Editor
2. Replace current indicator code with contents of `smc_premium_discount_indicator_v17.54.2.pine`
3. Click "Save" → "Add to chart"
4. Test on 5M USDJPY to confirm no "Indicator error"
5. Verify HUD table appears and stays visible during chart navigation
