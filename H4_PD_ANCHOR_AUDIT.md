# H4 Premium/Discount Anchor Audit Report

**Date**: 2026-05-24  
**Auditor**: Automated code analysis  
**Scope**: Full comparison of H4 P&D logic between v17.25 (predecessor) and v17.54 (current)  
**Method**: `grep`, `diff`, `sed` — exact line-by-line extraction and comparison  

> **NOTE**: No file named `v17.53` exists in the repo. The immediate predecessor to v17.54 is **v17.25**. Git history confirms: `afaf11b feat(v17.54): upgrade entire stack from v17.25 to v17.54`. All comparisons are v17.25 ↔ v17.54.

---

## Section 1: H4 P&D Code Comparison (Side-by-Side)

### 1.1 H4 Range Source — `request.security()` Calls

| Component | v17.25 Line | v17.54 Line | Code | Identical? |
|-----------|-------------|-------------|------|------------|
| H4 Range High | 740 | 740 | `float h4RangeHighRaw = request.security(syminfo.tickerid, "240", ta.highest(high, effectiveLookback), lookahead=barmerge.lookahead_off)` | ✅ YES |
| H4 Range Low | 741 | 741 | `float h4RangeLowRaw = request.security(syminfo.tickerid, "240", ta.lowest(low, effectiveLookback), lookahead=barmerge.lookahead_off)` | ✅ YES |

### 1.2 Range Compression / Clamping Logic

| Component | v17.25 Lines | v17.54 Lines | Identical? |
|-----------|--------------|--------------|------------|
| Raw zone height calc | 752 | 752 | ✅ YES |
| Initial assignment | 756–757 | 756–757 | ✅ YES |
| Compressed range override | 764–765 | 764–765 | ✅ YES |
| Midpoint-based clamping | 768–771 | 768–771 | ✅ YES |
| Min height expansion | 777–781 | 777–781 | ✅ YES |

### 1.3 Equilibrium (EQ) Calculation

| Component | v17.25 Line | v17.54 Line | Code | Identical? |
|-----------|-------------|-------------|------|------------|
| h4Eq | 784 | 784 | `h4Eq = (h4RangeHigh + h4RangeLow) / 2.0` | ✅ YES |
| h4Range | 785 | 785 | `h4Range = h4RangeHigh - h4RangeLow` | ✅ YES |

### 1.4 Premium/Discount Threshold Definitions

| Variable | v17.25 Line | v17.54 Line | Code | Identical? |
|----------|-------------|-------------|------|------------|
| h4PremiumTop | 795 | 795 | `h4PremiumTop = h4RangeHigh` | ✅ YES |
| h4PremiumBottom | 796 | 796 | `h4PremiumBottom = h4Eq + (h4Range * neutralZoneWidth / 200.0)` | ✅ YES |
| h4DiscountTop | 797 | 797 | `h4DiscountTop = h4Eq - (h4Range * neutralZoneWidth / 200.0)` | ✅ YES |
| h4DiscountBottom | 798 | 798 | `h4DiscountBottom = h4RangeLow` | ✅ YES |
| neutralZoneWidth input | 590 | 590 | `neutralZoneWidth = input.float(33.3, ...)` | ✅ YES |

### 1.5 Bias Classification

| Variable | v17.25 Line | v17.54 Line | Code | Identical? |
|----------|-------------|-------------|------|------------|
| h4Close | 801 | 801 | `h4Close = request.security(syminfo.tickerid, "240", close, lookahead=barmerge.lookahead_off)` | ✅ YES |
| h4Bias | 805 | 805 | `h4Bias = h4Close > h4PremiumBottom ? 1 : h4Close < h4DiscountTop ? -1 : 0` | ✅ YES |
| inPremiumZone | 809 | 809 | `inPremiumZone = close > h4PremiumBottom` | ✅ YES |
| inDiscountZone | 810 | 810 | `inDiscountZone = close < h4DiscountTop` | ✅ YES |
| inEquilibriumZone | 811 | 811 | `inEquilibriumZone = not inPremiumZone and not inDiscountZone` | ✅ YES |
| pdZone | 812 | 812 | `pdZone = inPremiumZone ? 1 : inDiscountZone ? 0 : -1` | ✅ YES |
| h4ZoneStr | 815 | 815 | `string h4ZoneStr = inPremiumZone ? "PZ (red)" : inDiscountZone ? "DZ (green)" : "EQ (gray)"` | ✅ YES |
| h4BiasNeutral | 825 | 825 | `bool h4BiasNeutral = h4Bias == 0` | ✅ YES |
| h4BiasBullish | 826 | 826 | `bool h4BiasBullish = h4Bias == 1` | ✅ YES |
| h4BiasBearish | 827 | 827 | `bool h4BiasBearish = h4Bias == -1` | ✅ YES |
| h4FibLevel | 830 | 830 | `h4FibLevel = h4Range > 0 ? (close - h4RangeLow) / h4Range * 100 : 50.0` | ✅ YES |

### 1.6 Bias Alignment & Counter-Trend Logic

| Variable | v17.25 Line | v17.54 Line | Code | Identical? |
|----------|-------------|-------------|------|------------|
| h4BiasChanged | 975 | 975 | `h4BiasChanged = ta.change(h4Bias) != 0` | ✅ YES |
| biasAlignedLong | 981 | 981 | `biasAlignedLong = h4Bias == 1 or h4Bias == 0` | ✅ YES |
| biasAlignedShort | 982 | 982 | `biasAlignedShort = h4Bias == -1 or h4Bias == 0` | ✅ YES |
| isCounterTrendLong | 988 | 988 | `isCounterTrendLong = h4Bias == -1` | ✅ YES |
| isCounterTrendShort | 989 | 989 | `isCounterTrendShort = h4Bias == 1` | ✅ YES |

---

## Section 2: Change Analysis

### Verified diff command:
```bash
diff <(sed -n '590p;740,830p;975,989p' v17.25.pine) \
     <(sed -n '590p;740,830p;975,989p' v17.54.pine)
# Result: NO OUTPUT (files identical in these ranges)
```

### Comprehensive logic block diff:
```bash
diff <(sed -n '1p;590p;600,700p;740,830p;975,1000p;1100,1200p;1200,1500p;1500,1600p' v17.25.pine) \
     <(sed -n '1p;590p;600,700p;740,830p;975,1000p;1100,1200p;1200,1500p;1500,1600p' v17.54.pine)
# Result: NO OUTPUT (files identical in these ranges)
```

### Summary of ALL code differences between v17.25 and v17.54

Only **3 categories** of changes exist between the two files:

| Category | Location | Nature |
|----------|----------|--------|
| **1. Version string substitutions** | ~30 comment lines scattered throughout | `"v17.25"` → `"v17.54"` in comments and HUD table cell |
| **2. S&D zone rendering** | Lines 2035–2137 (v17.54) | Scalar → array-based zone tracking (visual only, see Section 3) |
| **3. Alert architecture** | Lines 2463–2528 (v17.54) | `alertcondition()` message format changed + `alert()` calls added |

**The entire H4 P&D calculation engine (lines 590, 740–830, 975–989, 1100–1600) is byte-for-byte identical.**

---

## Section 3: Dependency Map — What Uses H4 P&D Variables

### 3.1 Complete Variable Usage Catalog

#### `h4RangeHigh` / `h4RangeLow`

| Line (both versions) | Usage | Category |
|---|---|---|
| 740–741 | Defined via `request.security()` | **Definition** |
| 752, 756–757, 764–771, 777–781 | Range compression/clamping | **Calculation** |
| 784–785 | Input to `h4Eq` and `h4Range` | **Calculation** |
| 2029 | `pdPremiumBox` top coordinate | **Visual only** |
| 2030 | `pdDiscountBox` bottom coordinate | **Visual only** |
| 2125–2126 (v17.25) / 2165–2166 (v17.54) | EQ line rendering | **Visual only** |
| 2659 (v17.25) / 2705 (v17.54) | Debug table display | **Visual only** |

#### `h4Eq`

| Line (both versions) | Usage | Category |
|---|---|---|
| 784 | Defined as `(h4RangeHigh + h4RangeLow) / 2.0` | **Definition** |
| 796 | Input to `h4PremiumBottom` | **Calculation** |
| 797 | Input to `h4DiscountTop` | **Calculation** |
| 1239–1240 | Guardian EQ high/low boundaries | **Filtering** (Guardian validation) |
| 1479–1480 | P&D shift detection (`pdShiftAgainstLong/Short`) | **Filtering** (setup invalidation) |

#### `h4Bias`

| Line (both versions) | Usage | Category |
|---|---|---|
| 805 | Defined from `h4Close` vs thresholds | **Definition** |
| 975 | `h4BiasChanged` detection | **Filtering** |
| 981–982 | `biasAlignedLong/Short` | **Filtering** (alert prerequisite) |
| 988–989 | `isCounterTrendLong/Short` | **Filtering** (counter-trend gate) |
| 1141 | POI score bonus | **Scoring** |
| 1159 | State machine reset on bias change | **Filtering** |
| 1177, 1181 | IPM sweep direction check | **Filtering** |
| 1311, 1315 | IPM induce sweep + bias gate | **Filtering** |
| 1395–1397 | `alignmentOK_long/short`, `alignmentConflict` | **Filtering** (critical alert gate) |
| 1449 | Guardian code assignment | **Filtering** |
| 1467 | Guardian waiting condition | **Filtering** |
| 1553–1554 | Counter-trend signal raw conditions | **Alert firing** |
| 1785, 1821, 1826, 1832, 1855 | Action plan text | **Visual only** (HUD) |
| 2166 (v17.25) / 2206 (v17.54) | `plot(h4Bias, ...)` for webhook | **Alert payload data** |
| 2266, 2272 (v17.25) / 2306, 2312 (v17.54) | Display ID generation | **Visual only** (labels) |
| 2594 (v17.25) / 2640 (v17.54) | HUD table cell | **Visual only** |

#### `pdZone` / `inPremiumZone` / `inDiscountZone` / `inEquilibriumZone`

| Line (both versions) | Usage | Category |
|---|---|---|
| 809–812 | Defined from `close` vs thresholds | **Definition** |
| 1804 | `inCorrectZoneForBias` | **Visual only** (action plan) |
| 1861, 1864 | Action plan text decisions | **Visual only** (HUD) |
| 2029–2033 | P&D background box rendering | **Visual only** |
| 2167 (v17.25) / 2207 (v17.54) | `plot(pdZone, ...)` for webhook | **Alert payload data** |
| **2331** (v17.25) / **2371** (v17.54) | `retrace_long_in_zone = inDiscountZone` | **🔴 ALERT FIRING** |
| **2339** (v17.25) / **2379** (v17.54) | `retrace_short_in_zone = inPremiumZone` | **🔴 ALERT FIRING** |
| 2670 (v17.25) / 2716 (v17.54) | Debug table zone booleans | **Visual only** |

#### `h4FibLevel`

| Line (both versions) | Usage | Category |
|---|---|---|
| 830 | Defined from `close` position in range | **Definition** |
| 1976–1980 | Fib warning labels | **Visual only** |
| 2174 (v17.25) / 2214 (v17.54) | `plot(h4FibLevel, ...)` for webhook | **Alert payload data** |

---

## Section 4: Alert Impact Analysis

### 4.1 Sniper Long/Short Fire Conditions

```pine
// v17.25 line 2318 / v17.54 line 2358 — IDENTICAL
fire_sniper_long = sniper_long_action_ready       // actionStep == "READY"
             and sniper_long_confluence_ok         // confluenceScore >= threshold
             and sniper_long_stage_ok              // dtStage >= threshold
             and sniper_long_guardian_ok            // guardLong != 5 and guardLong != 6
             and sniper_long_state_ok              // smStateLong == 0
             and sniper_long_not_duplicate         // f_alert_ready(...)
             and barstate.isconfirmed
```

**H4 P&D impact on Sniper signals**: **INDIRECT via `actionStep`**
- `actionStep == "READY"` is set by the action plan logic (lines ~1785–1870)
- The action plan uses `h4BiasNeutral`, `inCorrectZoneForBias`, `inEquilibriumZone`, etc.
- However, `actionStep` is not solely gated by H4 P&D — it depends on confluence, DT stage, kill zone, etc.
- **H4 P&D does NOT directly appear in any `sniper_*` component variable.**

### 4.2 Retrace Long/Short Fire Conditions

```pine
// v17.25 line 2336 / v17.54 line 2376 — IDENTICAL
fire_retrace_long = retrace_long_in_zone           // inDiscountZone  ← USES H4 P&D
                and retrace_long_mode_ok           // Guardian allows retrace/buy
                and retrace_long_confluence_ok      // confluenceScore >= threshold
                and retrace_long_not_duplicate     // f_alert_ready(...)
                and barstate.isconfirmed
```

**H4 P&D impact on Retrace signals**: **DIRECT**
- `retrace_long_in_zone = inDiscountZone` (line 2331/2371) — price must be below `h4DiscountTop`
- `retrace_short_in_zone = inPremiumZone` (line 2339/2379) — price must be above `h4PremiumBottom`
- **Both conditions are byte-for-byte identical between v17.25 and v17.54.**

### 4.3 Counter-Trend (CT Lite) Signals

```pine
// v17.25 line 1553 / v17.54 line 1553 — IDENTICAL
ctLiteLongRaw = h4Bias == -1                       // ← USES H4 P&D
            and structureDir == 1
            and structureStateCode >= 3
            and kzActive
            and poiScore >= 2
            and not h4Invalidated
            and not alignmentConflict               // ← USES H4 P&D (h4Bias vs structureDir)
            and (guardLong == 1 or guardLong == 3 or not enableGuardian)
```

**H4 P&D impact on Counter-Trend**: **DIRECT** — `h4Bias == -1` and `alignmentConflict` both use `h4Bias`.  
**Both conditions are byte-for-byte identical between v17.25 and v17.54.**

### 4.4 Continuation Signals
No explicit `fire_continuation` variable exists in either version. Continuation logic is handled through the `actionStep` state machine.

### 4.5 Guardian Validation

```pine
// v17.25 lines 1239–1240 / v17.54 lines 1239–1240 — IDENTICAL
guardianEqHigh = h4Eq + (h4Range * guardianNeutralPct / 200.0)
guardianEqLow  = h4Eq - (h4Range * guardianNeutralPct / 200.0)
```

Guardian uses `h4Eq` and `h4Range` to define its neutral band. **Identical in both versions.**

### 4.6 Setup Invalidation

```pine
// v17.25 lines 1395–1397 / v17.54 lines 1395–1397 — IDENTICAL
alignmentOK_long  = h4Bias >= 0 and not h4Invalidated
alignmentOK_short = h4Bias <= 0 and not h4Invalidated
alignmentConflict = (h4Bias == 1 and structureDir == -1) or (h4Bias == -1 and structureDir == 1)

// v17.25 lines 1479–1480 / v17.54 lines 1479–1480 — IDENTICAL
pdShiftAgainstLong  = confirmed and close < h4Eq and close[1] >= h4Eq
pdShiftAgainstShort = confirmed and close > h4Eq and close[1] <= h4Eq
```

All setup invalidation logic using H4 P&D is **identical in both versions.**

### 4.7 TP Calculation (uses H4 P&D thresholds)

```pine
// v17.25 lines 1419–1420 / v17.54 lines 1419–1420 — IDENTICAL
tpLong  = tpModeInput == "Fixed R:R" ? entryLong + (entryLong - slLong) * defaultRR : h4PremiumBottom
tpShort = tpModeInput == "Fixed R:R" ? entryShort - (slShort - entryShort) * defaultRR : h4DiscountTop
```

When TP mode is NOT "Fixed R:R", TP targets use `h4PremiumBottom`/`h4DiscountTop`. **Identical in both versions.**

---

## Section 5: Conclusion

### Finding: H4 P&D Anchor Logic Is 100% IDENTICAL Between v17.25 and v17.54

Every line of code in the H4 Premium/Discount calculation and filtering pipeline — from `request.security()` calls through bias classification, alignment gates, guardian validation, setup invalidation, and alert fire conditions — is **byte-for-byte identical** between v17.25 and v17.54.

### What Actually Changed (3 items only)

| # | Change | Affects Alert Firing? | Evidence |
|---|--------|----------------------|----------|
| 1 | Version strings in comments/HUD (`"v17.25"` → `"v17.54"`) | ❌ No | ~30 comment-only substitutions |
| 2 | S&D zone rendering: scalar → array multi-zone | ❌ No — **visual only**, zone boxes have zero connection to `fire_*` conditions | Lines 2035–2137 (v17.54) — `demandTop`/`supplyTop` etc. are never read by any alert logic |
| 3 | Alert message format: `{{plot_X}}` → simplified JSON + `alert()` calls added | ❌ No — message format doesn't affect **when** alerts fire, only **what data** they carry | Lines 2463–2528 (v17.54) |

### Definitive Answer

**The H4 P&D anchor system has ZERO impact on any alert firing difference between v17.25 and v17.54, because it was never changed.**

If alerts are behaving differently in v17.54 vs v17.25, the cause is NOT in:
- H4 range calculation
- EQ line calculation
- Premium/Discount thresholds
- Bias classification
- Zone detection logic
- Guardian validation
- Alignment/conflict logic
- Setup invalidation
- Any fire condition formula

The only functional code changes between the two versions are:
1. **S&D zone box rendering** (visual only — no signal impact)
2. **Alert message payload format** (when alerts fire is unchanged; what they contain differs)
