"""Model-local No-Direct-Bind execution-gate witness.

Within this witness, a terminal effect is attempted only through `Gate.bind`
after the declared authority/evidence checks pass. This is a property of this
implementation, not a claim that callers cannot have other effect paths.
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
    ERROR = "ERROR"


@dataclass(frozen=True)
class Decision:
    outcome: Outcome
    reason: str
    receipt: Receipt
    effect: object | None = None  # populated ONLY on successful ALLOW


class Gate:
    """Fail-closed reference gate over declared model inputs.

    `required` is the minimum caller-supplied evidence class accepted by this
    model. The class label is not external issuer authentication.
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
        """Attempt to bind `action` in `scope` to its terminal effect.

        `now` is an injected model input when supplied; otherwise the process
        clock is used. It is not a trusted-clock primitive.

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

        if not token.evidence.satisfies(self.required):
            return _record(
                Outcome.HOLD,
                f"evidence {token.evidence.evidence_class.value} below required {self.required.value}",
                token.evidence.evidence_class.value,
            )

        # Atomically consume stable token identity before attempting the effect.
        # A failed effect does not refund authority because it may have produced
        # a partial external consequence before raising.
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
            effect = effect_fn()  # the ONLY place this witness attempts an effect
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
