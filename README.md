# ndb-gate

A minimal, runnable reference implementation of a **No-Direct-Bind execution gate** for AI agents:
fail-closed by construction, evidenced authority, and a tamper-evident receipt chain.

> Papers describe pre-execution safety gates. This is a small thing you can `git clone`, run,
> and break — a proof you can hold, not just read.

## The claim

**Theorem 1 — No-Direct-Bind.**
An unresolved latent intent cannot bind to a terminal action.

```
bind(intent) -> effect   IF AND ONLY IF   resolve(authority, evidence) == ALLOW
```

Absence of a resolved `ALLOW` yields `HOLD` (fail-closed) or `DENY`. There is no second
code path that produces an effect. The effect function is invoked in exactly one place in
the entire library — inside the `ALLOW` branch of `Gate.bind`. That single-entry design is
what makes the property hold **by construction**, not by convention.

## What it enforces

| Rule | How |
|---|---|
| Fail-closed default | No token, weak evidence, or any doubt → `HOLD`. Effect never runs. |
| Evidenced authority only | Evidence classes: `PROVED > PLAUSIBLE > PATTERN_ONLY > NOT_ADMISSIBLE`. Default gate requires `PROVED`. |
| No silent scope widening | A token authorises one exact `(action, scope)` pair. Mismatch → `DENY`. |
| Bounded authority | Tokens expire (`ttl_seconds`). Expired → `HOLD`. |
| Batch authority does not carry | Tokens are single-use by default. Reuse → `DENY`. |
| Receipts are the product | Every decision (ALLOW/HOLD/DENY) emits a hash-linked receipt. The chain is replayable and tamper-evident. |

## Quickstart

```bash
pip install -e ".[test]"
pytest -q          # 11 passing, incl. the property-critical negative tests
```

```python
from ndb_gate import Gate, Outcome, AuthorityToken, Evidence, EvidenceClass

gate = Gate()                              # requires PROVED evidence by default
effects = []

# 1. No authority -> HOLD, effect never runs
d = gate.bind("deploy", "prod", None, lambda: effects.append("ran"))
assert d.outcome is Outcome.HOLD and effects == []

# 2. PROVED, scoped, live authority -> ALLOW, effect runs exactly once
token = AuthorityToken(
    action="deploy", scope="prod",
    evidence=Evidence("authorised by operator", EvidenceClass.PROVED, "first-party"),
)
d = gate.bind("deploy", "prod", token, lambda: effects.append("ran"))
assert d.outcome is Outcome.ALLOW and effects == ["ran"]

# 3. Reusing the same single-use token -> DENY (batch authority does not carry)
d = gate.bind("deploy", "prod", token, lambda: effects.append("ran"))
assert d.outcome is Outcome.DENY and effects == ["ran"]   # still ran only once
```

## Verifying the receipt chain

```python
from ndb_gate import verify_chain
assert verify_chain(list(gate.chain)) is True   # replays and confirms integrity
```

Any change to a past receipt breaks the hash link of every receipt after it, so
`verify_chain` returns `False`. The decision history is tamper-evident.

## Design notes

- ~300 lines of dependency-free Python. The smallness is the point: the property is
  auditable in one sitting.
- `Gate.bind` is the sole entry point to a terminal effect. Reviewers should check that
  no other code path invokes an effect — that single fact is the whole guarantee.

## Status & claim discipline

This is a **reference implementation**, not a security product. It demonstrates the
property on a clean model; it does not by itself harden a real deployment. Claim class:
**PROVED** that the property holds in this model (see tests); **PLAUSIBLE** that the pattern
generalises to production agent stacks.

## License

Apache-2.0.
