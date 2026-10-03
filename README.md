# ndb-gate

A minimal, runnable **model-local No-Direct-Bind execution-gate witness** for AI-agent experiments.

> This is a small thing you can clone, run and attack. Its claims stop at the
> declared Python model and the supplied effect function.

## The claim

**Model property — No-Direct-Bind.**

Within this witness, an effect is attempted only after the declared authority,
scope, liveness and evidence-class checks pass. An ALLOW receipt is written only
after the supplied effect function returns successfully.

This is not a claim that an external application has no other effect path, that
the evidence label came from an authenticated issuer, or that an injected clock
is authoritative.

## What this witness enforces

| Rule | How |
|---|---|
| Fail-closed default | No token, inadmissible evidence, scope mismatch or expiry produces no effect attempt. |
| Evidence threshold | `EvidenceClass` values are caller-supplied model labels. The default threshold is `PROVED`; this module does not authenticate an issuer. |
| Exact scope | A token covers one exact `(action, scope)` pair. |
| Bounded lifetime | Tokens have `issued_at` and `ttl_seconds`. `Gate.bind` uses the process clock by default and accepts an injected `now` for the model/tests; this is not a trusted-clock claim. |
| Single use | Each token carries a stable `token_id`. Dataclass copies preserve that identity, and consumption is synchronized per `Gate` instance. |
| Effect/receipt ordering | The effect is attempted after the checks. Successful completion records `ALLOW`; an exception records `ERROR` and is re-raised. |
| Receipt integrity | Receipts are hash-linked. `verify_chain` checks internal linkage of the supplied chain; it does not authenticate origin or provide an external anchor. |

## Quickstart

```bash
pip install -e ".[test]"
pytest -q
```

```python
from ndb_gate import Gate, Outcome, AuthorityToken, Evidence, EvidenceClass

gate = Gate()
effects = []

d = gate.bind("deploy", "prod", None, lambda: effects.append("ran"))
assert d.outcome is Outcome.HOLD and effects == []

token = AuthorityToken(
    action="deploy",
    scope="prod",
    evidence=Evidence("authorised by operator", EvidenceClass.PROVED, "declared-source"),
)
d = gate.bind("deploy", "prod", token, lambda: effects.append("ran"))
assert d.outcome is Outcome.ALLOW and effects == ["ran"]

# Reusing the token, including a dataclass copy that carries the same token_id,
# is refused by this Gate instance.
d = gate.bind("deploy", "prod", token, lambda: effects.append("ran"))
assert d.outcome is Outcome.DENY and effects == ["ran"]
```

## Verifying the receipt chain

```python
from ndb_gate import verify_chain
assert verify_chain(list(gate.chain)) is True
```

That establishes internal hash-link consistency for the supplied chain. It does
not prove who created the chain or whether a newly presented chain is externally
authentic.

## Design notes

- Small, dependency-free Python intended for inspection and falsification.
- Within this witness, `Gate.bind` is the only code path that invokes the
  supplied effect function.
- A failed effect consumes a single-use token because an external effect may
  have partially occurred before raising; retry requires a new grant.

## Status & claim discipline

This is a **reference model**, not a security product. It does not establish
external issuer authentication, trusted time, complete mediation in another
application, production hardening, certification, or adoption.

## License

Apache-2.0.
