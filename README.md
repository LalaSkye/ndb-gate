# ndb-gate

A minimal, runnable **No-Direct-Bind execution-gate witness** for AI agents:
fail-closed by default, explicitly scoped authority metadata, single-use replay control,
and a hash-linked receipt chain.

> This repository demonstrates one model-local execution pattern. It is deliberately
> small enough to inspect and attack. It is not an external issuer, trusted clock,
> production security boundary, or proof about code paths outside this library.

## Model-local property

Within this library, the supplied effect function is invoked only after the represented
authority checks resolve to `ALLOW`.

There is one effect call site inside `Gate.bind`. That establishes the property for this
witness only. It does not establish that a surrounding application has no other route to
the same consequence.

## What it checks

| Rule | Behaviour |
|---|---|
| Fail-closed default | No token, inadmissible evidence, or insufficient evidence class → no effect |
| Exact scope | A token covers one exact `(action, scope)` pair |
| Bounded lifetime | Token expiry is checked against the supplied clock value |
| Single-use | A stable `token_id` is consumed once, including across object copies |
| Effect/receipt ordering | `ALLOW` is recorded only after the effect function returns successfully |
| Effect failure | A raised effect records `EFFECT_FAILED` and re-raises the original exception |
| Receipt consistency | Receipts are hash-linked so edits to a held chain break link verification |

## Important boundaries

### Evidence labels are not issuer authentication

`EvidenceClass.PROVED` and the `source` string are caller-supplied metadata in this witness.
The module does not independently authenticate an issuer or establish that the described
evidence is true.

### The clock is injectable

`Gate.bind(..., now=...)` exists for tests and simulation. The library does not claim an
external trusted-clock boundary.

### Receipt verification is not external authenticity

`verify_chain` checks indexes and hash links in the supplied chain. It detects edits relative
to a chain you already hold. A completely rewritten, internally consistent chain requires an
external anchor if you want to distinguish it from the original.

### Same-process callers remain inside the trust boundary

This is a reference witness, not a sandbox or security product. A caller that controls the
process can still replace objects, monkey-patch code, bypass this library, or invoke some
other effect path.

## Quickstart

```bash
pip install -e ".[test]"
pytest -q
```

```python
from ndb_gate import Gate, Outcome, AuthorityToken, Evidence, EvidenceClass

gate = Gate()
effects = []

token = AuthorityToken(
    action="deploy",
    scope="prod",
    evidence=Evidence("operator grant", EvidenceClass.PROVED, "fixture"),
)

decision = gate.bind("deploy", "prod", token, lambda: effects.append("ran"))

assert decision.outcome is Outcome.ALLOW
assert effects == ["ran"]

# A copy preserves token_id, so single-use does not reset.
import dataclasses
copied = dataclasses.replace(token)
assert gate.bind("deploy", "prod", copied, lambda: effects.append("ran")).outcome is Outcome.DENY
assert effects == ["ran"]
```

## Receipt behaviour

Every completed gate decision emits a receipt. If the represented authority checks pass
but the effect function raises, the call emits `EFFECT_FAILED` rather than `ALLOW` and
re-raises the exception.

That record means the effect function did not return successfully. It does not prove that
an external effect made no partial change before raising.

## Design notes

- Dependency-free runtime Python.
- Single-use identity is explicit (`token_id`), not Python object identity.
- Single-use consumption is serialised inside one `Gate` instance.
- The receipt chain is an integrity structure, not an external authenticity service.

## Status & claim discipline

This is a **reference implementation / model-local witness**.

Supported claim: within this library, the supplied effect function is reached only after the
represented checks pass, copied single-use tokens do not regain authority, and an `ALLOW`
receipt is emitted only after the effect function returns successfully.

Not claimed: external issuer authenticity, trusted time, complete mediation of a surrounding
system, production hardening, certification, adoption, or external receipt authenticity.

## License

Apache-2.0.
