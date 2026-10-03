# ndb-gate

A minimal, runnable **reference witness** for a No-Direct-Bind execution gate.

The repository demonstrates a model-local rule: the supplied effect function is
reached through `Gate.bind` only after the presented token satisfies this
library's checks. It is intentionally small enough to inspect and attack.

## Model property

Within this reference implementation:

```
bind(action, scope, token) -> supplied effect
only after the gate resolves the presented token to ALLOW
```

An absent or insufficient token produces `HOLD` or `DENY`. A successful
`ALLOW` receipt is recorded only after the supplied effect returns. If the
effect raises, the chain records `ERROR` and the exception is re-raised.

## What this model checks

| Rule | Behaviour |
|---|---|
| Fail-closed default | No token or insufficient evidence class → `HOLD` / `DENY`; supplied effect is not invoked. |
| Evidence threshold | `PROVED > PLAUSIBLE > PATTERN_ONLY > NOT_ADMISSIBLE`; the configured threshold defaults to `PROVED`. |
| Scope binding | Token action and scope must match the requested action and scope. |
| Time window | `ttl_seconds` bounds the token relative to the evaluated clock. |
| Single use | A deterministic key over the immutable token value prevents a value-equal copy from refreshing a spent token. |
| Receipt ordering | `ALLOW` is appended after the supplied effect returns; a raised effect records `ERROR`. |
| Hash-link integrity | Receipts link to the previous receipt hash; `verify_chain` checks internal chain consistency. |

## Claim ceiling

This library does **not** establish an external issuer, trusted provenance,
trusted time source, complete mediation of a caller's other code paths, or an
external anchor for the receipt chain.

In particular:

- `EvidenceClass.PROVED` is a caller-supplied classification in this reference model.
- `now=` is an optional caller-supplied clock override, retained for deterministic tests.
- `verify_chain` detects edits relative to the supplied chain structure; a wholly
  fabricated internally consistent chain is outside what that function can authenticate.
- The library is a reference implementation, not a security product or production gate.

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
    evidence=Evidence("operator record", EvidenceClass.PROVED, "declared-source"),
)

decision = gate.bind("deploy", "prod", token, lambda: effects.append("ran"))
assert decision.outcome is Outcome.ALLOW
assert effects == ["ran"]

# A value-equal copy carries the same single-use identity.
import dataclasses
copied = dataclasses.replace(token)
decision = gate.bind("deploy", "prod", copied, lambda: effects.append("ran"))
assert decision.outcome is Outcome.DENY
assert effects == ["ran"]
```

## Verifying the receipt chain

```python
from ndb_gate import verify_chain
assert verify_chain(list(gate.chain)) is True
```

That result means the supplied sequence is internally hash-link consistent. It
does not identify who created the sequence.

## Design notes

- The public object is deliberately small and dependency-free.
- `Gate.bind` is the only place in this library that invokes the supplied
  effect function.
- Integration claims require separate evidence that real effect-capable paths
  are bound to this gate.

## License

Apache-2.0.
