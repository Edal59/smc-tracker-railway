# Alert Naming Fix — Deployment Report

**Date**: 2026-05-24  
**Commit**: `eed9026`  
**Branch**: `main`  
**Railway Status**: ✅ Deployed & Healthy  

---

### Changes Made

#### 1. `smc_premium_discount_indicator_v17.54.pine`
| Location | Before | After |
|---|---|---|
| `alertcondition()` messages (×4) | `"alert":"A_PLUS_SNIPER_BUY"` etc. | `"alert":"A+ SNIPER BUY"` etc. |
| `alert()` calls (×4) | `"alert":"A_PLUS_SNIPER_BUY"` etc. | `"alert":"A+ SNIPER BUY"` etc. |

**Total replacements**: 8 (2 each for SNIPER BUY, SNIPER SELL, RETRACE LONG, RETRACE SHORT)

#### 2. `src/oie_processor.py`
- Updated comments and docstring examples to reflect new canonical names
- **Backward compatibility preserved**: `_V17_54_ALERT_MAP` retains both underscore *and* space keys mapping to the same OIE types

### Alert Name Mapping (final state)

| Pine Script emits | `_V17_54_ALERT_MAP` resolves to |
|---|---|
| `A+ SNIPER BUY` | `sniper_long` |
| `A+ SNIPER SELL` | `sniper_short` |
| `RETRACE LONG` | `retrace_long` |
| `RETRACE SHORT` | `retrace_short` |
| `COUNTER BUY` *(future)* | `counter_long` |
| `COUNTER SELL` *(future)* | `counter_short` |

### What Was NOT Changed
- ❌ Signal firing logic
- ❌ SL/TP calculations
- ❌ Subtype logic
- ❌ HUD / zone rendering
- ❌ `settings.html` / frontend templates
- ❌ Any files other than the two listed above

### Health Check
```json
{"service":"SMC Performance Tracker","status":"ok","version":"v17.54"}
```
