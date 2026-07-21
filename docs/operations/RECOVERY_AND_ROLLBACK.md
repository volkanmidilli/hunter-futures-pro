# Recovery and Rollback (Pairlist Publishing)

> **Research only.** All procedures below are local file operations — none involve Freqtrade execution,
> orders, or positions.

Verified against `src/hunter/pairlist_export/publisher.py` and `snapshot.py`, and by direct reproduction
during this validation pass (commit `08a78d9`).

## Failed Publish (Gate Rejection)

**Symptom**: `Publish gate rejected pairlist: <REASON_CODE...>`, exit 1.

**State**: No write occurred. `hunter-pairs.json`/`hunter-pairs-audit.json` in `--output-dir` are exactly what
they were before the run. **No recovery action needed** — this is the intended fail-closed behavior. Fix the
input (per the reason codes) and rerun.

## Malformed Input

**Symptom**: A raw Python traceback (`json.decoder.JSONDecodeError`, `FileNotFoundError`,
`PairlistExportError` with a parse-related message), exit 1.

**State**: No write occurred (the error happens during input loading, before ranking or gating). Fix the
input file and rerun. See `docs/user/INPUT_FORMAT.md` for valid/invalid examples.

## Too-Short Shortlist

**Symptom**: `Publish gate rejected pairlist: BELOW_MIN_PAIRS`, exit 1.

**State**: No write occurred. Supply more eligible pairs with sufficient RS/OI evidence (need at least
`min_pairs`, default 5) and rerun.

## Snapshot Conflict — No Recovery Needed

**Symptom**: `Error: snapshot pairlist for <date> already exists with different content: <path>`, exit 1.

**State (fixed and verified by direct reproduction)**: the snapshot is validated/committed *before* the live
publish (`cli.py::_build_and_publish`), so a same-date-different-content conflict is rejected before
`publish_pairlist` ever runs. The live `hunter-pairs.json`/`hunter-pairs-audit.json` remain byte-identical to
their state before the run, and no `*.previous-good` file is created — proof publish never executed. The
dated snapshot for that date is also untouched.

**What to do**: nothing needs restoring. Either:

- Use a different `--snapshot-dir` if you intended a genuinely new snapshot series, or
- Correct `--as-of` to the intended date if it was a typo, or
- If the *new* content is actually correct and the originally-published snapshot for that date was wrong,
  that is a human decision outside Hunter's automated scope — a corrected snapshot for an already-snapshotted
  date is never produced silently, by design (snapshots are immutable evidence).

## Corrupted Pairlist (Manual/External Edit)

**Symptom**: `hunter pairlist validate <file>` reports `valid: False` with reason codes, or fails to parse
entirely.

**Recovery**: Restore from `*.previous-good` (same directory) or the most recent dated snapshot in
`--snapshot-dir` (`hunter-pairs-YYYYMMDD.json`) — copy it over the live filename and re-validate. Never
hand-edit `hunter-pairs.json` directly in production; always go through `hunter pairlist build`/
`daily-pairlist` so the audit trail stays consistent with what's actually served.

## Restore Previous-Good

```bash
cp hunter-pairs.json.previous-good hunter-pairs.json
cp hunter-pairs-audit.json.previous-good hunter-pairs-audit.json
hunter pairlist validate hunter-pairs.json
```

`*.previous-good` files exist only after at least one prior successful publish — on a first-ever publish
there is nothing to restore to (a failed first publish leaves no live files at all, per
`publisher.publish_pairlist`'s documented behavior).

## Restore a Dated Snapshot

```bash
cp <snapshot-dir>/hunter-pairs-YYYYMMDD.json hunter-pairs.json
cp <snapshot-dir>/hunter-pairs-YYYYMMDD-audit.json hunter-pairs-audit.json
hunter pairlist validate hunter-pairs.json
```

Snapshots are immutable and dated — use this to roll back to a specific known-good historical day, not just
the immediately prior publish.

## Freqtrade `keep_pairlist_on_failure` Behavior

Both deployment profiles set `keep_pairlist_on_failure: true` on the `RemotePairList` entry — if Freqtrade
itself fails to fetch or parse `hunter-pairs.json` (e.g. mid-restore, or a transient filesystem issue),
Freqtrade keeps serving its last successfully loaded whitelist rather than trading with none or with a
partial list. This is a Freqtrade-side safety net independent of, and in addition to, Hunter's own
previous-good mechanism.

## Safe Rollback Checklist

1. Identify the failure mode (gate rejection / malformed input / snapshot conflict / corruption) using
   `docs/user/TROUBLESHOOTING.md`.
2. For gate rejections, malformed input, and snapshot conflicts: no action needed — nothing was written to
   the live pairlist/audit in any of these cases.
3. For corruption (manual/external edit of a live file): restore from `*.previous-good` or the appropriate
   dated snapshot.
4. After any restore, run `hunter pairlist validate` before considering the pairlist trustworthy again.
5. Confirm Freqtrade is serving the expected content (check its own logs/whitelist inspection — outside
   Hunter's scope) after its next `refresh_period` tick, or restart it if urgency requires.
6. Document any incident for your own operational record.
