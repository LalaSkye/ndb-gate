"""The No-Direct-Bind gate.

Model-local property (No-Direct-Bind):
    An unresolved latent intent cannot bind to a terminal action.
    Within this reference witness, the supplied effect function is invoked only
    after the gate resolves the presented token and evidence to ALLOW.

This module does not authenticate an external issuer or prove that callers have
no other effect path. Those are integration responsibilities outside this model.
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


@dataclass(frozen=True)
class Decision:
    outcome: Outcome
    reason: str
    receipt: Receipt
    effect: object | None = None  # populated ONLY on completed ALLOW


class Gate:
    """Fail-closed reference gate over caller-supplied token/evidence objects.

    `required` is the minimum evidence class label accepted by this model.
    The library does not authenticate who assigned that label.
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
        """Attempt to bind `action` in `scope` to its supplied effect.

        A successful ALLOW receipt is appended only after `effect_fn` returns.
        If an authorised effect raises, an ERROR receipt is appended and the
        original exception is re-raised. Every ordinary call path therefore
        records what completed rather than pre-recording success.
        """
        now = time.time() if now is None else now

        def _record(outcome: Outcome, reason: str, ev: str) -> Decision:
            receipt = self.chain.append(action, scope, outcome.value, reason, ev)
            return Decision(outcome=outcome, reason=reason, receipt=receipt, effect=None)

        # --- Fail-closed checks, strongest reason first ---

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

        # The token is consumed before attempting the effect, preserving the
        # existing single-use behaviour even when the effect itself raises.
        if token.single_use:
            self._spent_tokens.add(id(token))

        evidence_class = token.evidence.evidence_class.value
        reason = "evidenced authority resolved"
        try:
            effect = effect_fn()
        except Exception as exc:
            self.chain.append(
                action,
                scope,
                "ERROR",
                f"effect raised {type(exc).__name__}",
                evidence_class,
            )
            raise

        receipt = self.chain.append(
            action,
            scope,
            Outcome.ALLOW.value,
            reason,
            evidence_class,
        )
        return Decision(
            outcome=Outcome.ALLOW,
            reason=reason,
            receipt=receipt,
            effect=effect,
        )
