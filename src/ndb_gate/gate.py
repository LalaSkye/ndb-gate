"""The No-Direct-Bind gate.

Model-local property:
    An unresolved latent intent cannot bind to a terminal action inside this
    witness. The supplied effect function is invoked only after the represented
    authority checks resolve to ALLOW.

This module does not prove that a caller has no other effect path, authenticate
an issuer, or provide an external trusted clock. Those are integration duties.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Callable

from .authority import AuthorityToken, EvidenceClass
from .receipts import ReceiptChain, Receipt


class Outcome(Enum):
    ALLOW = "ALLOW"
    HOLD = "HOLD"
    DENY = "DENY"
    EFFECT_FAILED = "EFFECT_FAILED"


@dataclass(frozen=True)
class Decision:
    outcome: Outcome
    reason: str
    receipt: Receipt
    effect: object | None = None


class Gate:
    """Fail-closed execution-gate witness.

    required is the minimum caller-supplied evidence class accepted by this
    model. The gate does not independently authenticate that class or source.
    """

    def __init__(self, required: EvidenceClass = EvidenceClass.PROVED) -> None:
        self.required = required
        self.chain = ReceiptChain()
        self._spent_tokens: set[str] = set()
        self._spent_lock = Lock()

    def bind(
        self,
        action: str,
        scope: str,
        token: AuthorityToken | None,
        effect_fn: Callable[[], object],
        now: float | None = None,
    ) -> Decision:
        """Attempt to bind action in scope to the supplied effect function.

        A successful effect emits ALLOW only after effect_fn returns. If the
        effect raises, the chain records EFFECT_FAILED and the original
        exception is re-raised. The token remains spent after an attempted
        single-use execution.

        now is injectable for tests/simulation and is not a trusted-clock
        guarantee.
        """
        now = time.time() if now is None else now

        def _record(outcome: Outcome, reason: str, ev: str) -> Decision:
            receipt = self.chain.append(action, scope, outcome.value, reason, ev)
            return Decision(outcome=outcome, reason=reason, receipt=receipt)

        if token is None:
            return _record(Outcome.HOLD, "no authority token presented", "NOT_ADMISSIBLE")

        if not token.evidence.evidence_class.is_admissible:
            return _record(
                Outcome.DENY,
                "evidence not admissible",
                token.evidence.evidence_class.value,
            )

        if not token.covers(action, scope):
            return _record(
                Outcome.DENY,
                f"token does not cover ({action!r},{scope!r}); no scope widening",
                token.evidence.evidence_class.value,
            )

        if not token.is_live(now):
            return _record(
                Outcome.HOLD,
                "authority expired",
                token.evidence.evidence_class.value,
            )

        if not token.evidence.satisfies(self.required):
            return _record(
                Outcome.HOLD,
                f"evidence {token.evidence.evidence_class.value} below required {self.required.value}",
                token.evidence.evidence_class.value,
            )

        if token.single_use:
            with self._spent_lock:
                if token.token_id in self._spent_tokens:
                    return _record(
                        Outcome.DENY,
                        "single-use authority already spent; batch authority does not carry",
                        token.evidence.evidence_class.value,
                    )
                self._spent_tokens.add(token.token_id)

        try:
            effect = effect_fn()
        except Exception as exc:
            self.chain.append(
                action,
                scope,
                Outcome.EFFECT_FAILED.value,
                f"authority resolved but effect raised {type(exc).__name__}",
                token.evidence.evidence_class.value,
            )
            raise

        receipt = self.chain.append(
            action,
            scope,
            Outcome.ALLOW.value,
            "evidenced authority resolved and effect returned",
            token.evidence.evidence_class.value,
        )
        return Decision(
            outcome=Outcome.ALLOW,
            reason="evidenced authority resolved and effect returned",
            receipt=receipt,
            effect=effect,
        )
