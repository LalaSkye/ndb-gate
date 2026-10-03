"""The No-Direct-Bind gate.

THEOREM 1 (No-Direct-Bind):
    An unresolved latent intent cannot bind to a terminal action.
    bind(intent) -> effect  IFF  resolve(authority, evidence) == ALLOW.
    Otherwise the outcome is HOLD (fail-closed) or DENY. Never silent execution.

The gate is the ONLY path to a terminal effect. There is no second code path
that executes an action without passing through `Gate.bind`. That single-entry
design is what makes the property hold by construction rather than by convention.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .authority import AuthorityToken, EvidenceClass
from .receipts import ReceiptChain, Receipt


class Outcome(Enum):
    ALLOW = "ALLOW"
    HOLD = "HOLD"
    DENY = "DENY"
    ERROR = "ERROR"


@dataclass(frozen=True)
class Decision:
    outcome: Outcome
    reason: str
    receipt: Receipt
    effect: object | None = None  # populated ONLY on successful ALLOW


class Gate:
    """Fail-closed execution gate.

    `required` is the minimum evidence class needed to authorise. Default PROVED:
    nothing weaker than first-party, verified evidence can bind a terminal action.
    """

    def __init__(self, required: EvidenceClass = EvidenceClass.PROVED) -> None:
        self.required = required
        self.chain = ReceiptChain()
        self._spent_tokens: set[int] = set()

    def bind(
        self,
        action: str,
        scope: str,
        token: AuthorityToken | None,
        effect_fn: Callable[[], object],
        now: float | None = None,
    ) -> Decision:
        """Attempt to bind `action` in `scope` to its terminal effect.

        A successful effect emits ALLOW. If the effect raises, the chain records
        ERROR and the original exception is re-raised. Every attempted bind emits
        a receipt.
        """
        now = time.time() if now is None else now

        def _record(
            outcome: Outcome, reason: str, ev: str, effect: object | None = None
        ) -> Decision:
            receipt = self.chain.append(action, scope, outcome.value, reason, ev)
            return Decision(outcome=outcome, reason=reason, receipt=receipt, effect=effect)

        # --- Fail-closed checks, strongest reason first ---

        if token is None:
            return _record(Outcome.HOLD, "no authority token presented", "NOT_ADMISSIBLE")

        if not token.evidence.evidence_class.is_admissible:
            return _record(Outcome.DENY, "evidence not admissible", token.evidence.evidence_class.value)

        if not token.covers(action, scope):
            return _record(
                Outcome.DENY,
                f"token does not cover ({action!r},{scope!r}); no scope widening",
                token.evidence.evidence_class.value,
            )

        if not token.is_live(now):
            return _record(Outcome.HOLD, "authority expired", token.evidence.evidence_class.value)

        if token.single_use and id(token) in self._spent_tokens:
            return _record(
                Outcome.DENY,
                "single-use authority already spent; batch authority does not carry",
                token.evidence.evidence_class.value,
            )

        if not token.evidence.satisfies(self.required):
            return _record(
                Outcome.HOLD,
                f"evidence {token.evidence.evidence_class.value} below required {self.required.value}",
                token.evidence.evidence_class.value,
            )

        # All checks passed -> consume single-use authority before attempting the
        # effect. A failed effect does not refund authority because it may have
        # produced a partial external consequence before raising.
        if token.single_use:
            self._spent_tokens.add(id(token))

        try:
            effect = effect_fn()  # the ONLY place an effect is ever attempted
        except Exception as exc:
            self.chain.append(
                action,
                scope,
                Outcome.ERROR.value,
                f"effect raised {type(exc).__name__}",
                token.evidence.evidence_class.value,
            )
            raise

        return _record(
            Outcome.ALLOW,
            "evidenced authority resolved; effect completed",
            token.evidence.evidence_class.value,
            effect,
        )
