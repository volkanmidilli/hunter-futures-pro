# Ranking-Input JSON Format

> **Research only.** This file is a local input you provide to Hunter — Hunter does not fetch it from any
> network source. Verified against `src/hunter/pairlist_export/cli.py` at commit `08a78d9` by direct source
> reading and CLI testing.

## Complete Example

```json
{
  "as_of_date": "2026-07-21",
  "universe_total": 412,
  "eligible_pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT"],
  "rs_scores": {"BTC/USDT:USDT": "88.1", "ETH/USDT:USDT": null},
  "oi_scores": {"BTC/USDT:USDT": "70.0", "ETH/USDT:USDT": "65.0"},
  "data_quality": {"BTC/USDT:USDT": "100"}
}
```

## Field Reference

| Field | Type | Required | Notes |
|---|---|---|---|
| `as_of_date` | string, `YYYY-MM-DD` | Optional in the file | The CLI's `--as-of` flag always wins over this field — it is not read by `_rank_from_payload` at all (verified: `cli.py::_rank_from_payload` never accesses `payload["as_of_date"]`; only `args.as_of` is used downstream). Include it for your own record-keeping, but it has no runtime effect. |
| `universe_total` | integer | Optional | Size of the full universe before eligibility filtering, for the audit record. Defaults to `len(eligible_pairs)` **only when the key is entirely absent**. An explicit `0` (or any other integer) is preserved as-is — verified by direct test. |
| `eligible_pairs` | array of strings | **Required** (functionally — omitting it or supplying an empty list yields zero candidates) | Ordered list of pair symbols already filtered to eligibility by your own pipeline. Hunter does not itself apply stablecoin/leveraged-token/benchmark exclusion in this version (the `INELIGIBLE_*` reason codes are reserved but not currently raised by any code path) — pre-filter these yourself. |
| `rs_scores` | object, `{pair: string \| null}` | Optional (defaults to `{}`) | Relative-strength score per pair. String values are parsed as `Decimal`; `null`/absent means "no data," not zero. |
| `oi_scores` | object, `{pair: string \| null}` | Optional (defaults to `{}`) | Open-interest / liquidity score per pair. Same `Decimal`/`null` semantics as `rs_scores`. |
| `data_quality` | object, `{pair: string \| null}` | Optional (defaults to `{}`) | Data-quality percentage (0–100 by convention; not range-enforced) per pair. Used as the third tie-break dimension. |

## Exact Data Types

- **Scores are strings, not JSON numbers**, by convention (e.g. `"88.1"` not `88.1`) — this avoids float
  precision loss, since they are parsed with `Decimal(str(value))`. A JSON number value (e.g. `88.1` without
  quotes) is also accepted (Python `json` loads it as `float`, then `str(88.1)` → `"88.1"` → `Decimal` — works
  but re-introduces the float-precision risk that string input avoids; **prefer quoted strings**).
- **`null` explicitly means "no data available,"** distinct from omitting the pair from the map entirely
  (both are treated identically at lookup time via `.get(pair)`, but `null` documents intent for a
  human/pipeline reading the file).
- **Booleans are rejected.** `true`/`false` as a score value fails to parse as `Decimal` (see error below).

## Valid Pair Format

`BASE/USDT:USDT` — matches the regex `^[A-Z0-9]{2,20}/USDT:USDT$` (verified,
`pairlist_export/validator.py:33`). Examples: `BTC/USDT:USDT`, `ETH/USDT:USDT`, `1000SHIB/USDT:USDT`.
**Invalid**: `BTCUSDT` (no slash/settle suffix), `btc/usdt:usdt` (lowercase — rejected, uppercase only),
`BTC/USD:USD` (wrong quote/settle currency — must be `USDT`).

Pair-format validation happens at the **publish gate**, not at `coins rank` time — `hunter coins rank` will
happily rank an invalid-format pair (it only affects downstream `pairlist build`/`daily-pairlist`, which
reject the whole publish with `INVALID_PAIR_FORMAT` if any *selected* pair fails the shape check).

## Complete (Valid) Example — Minimal

```json
{
  "eligible_pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "XRP/USDT:USDT", "ADA/USDT:USDT"],
  "rs_scores": {"BTC/USDT:USDT": "80", "ETH/USDT:USDT": "70", "SOL/USDT:USDT": "60", "XRP/USDT:USDT": "50", "ADA/USDT:USDT": "40"},
  "oi_scores": {"BTC/USDT:USDT": "80", "ETH/USDT:USDT": "70", "SOL/USDT:USDT": "60", "XRP/USDT:USDT": "50", "ADA/USDT:USDT": "40"}
}
```

This is the minimum shape that clears the default gate (5 pairs = `min_pairs`, all with both RS and OI data,
all valid format, no duplicates). `as_of_date`, `universe_total`, and `data_quality` are all omittable.

## Invalid Examples and Their Exact Errors (verified by direct CLI execution)

**Missing/empty `eligible_pairs`:**

```json
{"as_of_date": "2026-07-29", "rs_scores": {}, "oi_scores": {}}
```

```text
Error: no eligible pairs provided for ranking
```

Exit 1. Raised by `ranking_adapter.rank_pairs` before any gate logic runs.

**Non-numeric score value:**

```json
{"eligible_pairs": ["BTC/USDT:USDT"], "rs_scores": {"BTC/USDT:USDT": "eighty"}, "oi_scores": {}}
```

```text
Error: ranking input contains a non-numeric score: [<class 'decimal.ConversionSyntax'>]
```

Exit 1. Same message (and same underlying `decimal.ConversionSyntax`) for a JSON boolean (`true`/`false`) as
a score value, since it's coerced via `str()` before the `Decimal()` call.

**Both RS and OI missing for every pair** (insufficient evidence at the ranking stage, not the gate):

```json
{"eligible_pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "XRP/USDT:USDT", "ADA/USDT:USDT"], "rs_scores": {}, "oi_scores": {}}
```

```text
Error: no eligible pairs have sufficient evidence (RS and/or OI data)
```

Exit 1.

**Invalid pair format** (only rejected at `pairlist build`/`daily-pairlist`, not `coins rank`):

```json
{"eligible_pairs": ["BTCUSDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "XRP/USDT:USDT", "ADA/USDT:USDT"], "rs_scores": {"BTCUSDT": "80", "ETH/USDT:USDT": "70", "SOL/USDT:USDT": "60", "XRP/USDT:USDT": "50", "ADA/USDT:USDT": "40"}, "oi_scores": {"BTCUSDT": "80", "ETH/USDT:USDT": "70", "SOL/USDT:USDT": "60", "XRP/USDT:USDT": "50", "ADA/USDT:USDT": "40"}}
```

```text
Publish gate rejected pairlist: INVALID_PAIR_FORMAT
```

Exit 1 (from `pairlist build`; `coins rank` would succeed and rank it normally).

**Duplicate pair:**

```json
{"eligible_pairs": ["BTC/USDT:USDT", "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "XRP/USDT:USDT", "ADA/USDT:USDT"], "rs_scores": {...}, "oi_scores": {...}}
```

```text
Publish gate rejected pairlist: DUPLICATE_PAIR
```

Exit 1.

**Malformed JSON (syntax error), or a missing `--input` file**: neither is caught by Hunter's own error
handling — you will see a raw Python traceback ending in `json.decoder.JSONDecodeError` or
`FileNotFoundError`, exit 1. See `docs/user/TROUBLESHOOTING.md`.

**Input JSON that isn't an object** (e.g. a bare list or a JSON string):

```text
Error: ranking input must be a JSON object: <path>
```

Exit 1 (raised by `_load_ranking_input`).
