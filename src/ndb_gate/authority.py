"""Authority and evidence primitives.

These encode the witness's claim classes directly:
    PROVED / PLAUSIBLE / PATTERN_ONLY / NOT_ADMISSIBLE

Important boundary: the classes and source strings are caller-supplied metadata.
This module does not authenticate an issuer or independently establish that a
piece of evidence is true. External issuer verification is outside this witness.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class EvidenceClass(Enum):
    """Evidence classes, strongest first, within this witness."""

    PROVED = "PROVED"
    PLAUSIBLE = "PLAUSIBLE"
    PATTERN_ONLY = "PATTERN_ONLY"
    NOT_ADMISSIBLE = "NOT_ADMISSIBLE"

    @property
    def is_admissible(self) -> bool:
        return self is not EvidenceClass.NOT_ADMISSIBLE


@dataclass(frozen=True)
class Evidence:
    """A caller-supplied evidence descriptor backing an authority claim.

    evidence_class and source are labels consumed by this model. Their
    authenticity and truth are not established by this module.
    """

    claim: str
    evidence_class: EvidenceClass
    source: str

    def satisfies(self, required: EvidenceClass) -> bool:
        """True iff this evidence label is at least as strong as required."""
        order = {
            EvidenceClass.PROVED: 3,
            EvidenceClass.PLAUSIBLE: 2,
            EvidenceClass.PATTERN_ONLY: 1,
            EvidenceClass.NOT_ADMISSIBLE: 0,
        }
        return order[self.evidence_class] >= order[required]


@dataclass(frozen=True)
class AuthorityToken:
    """An explicit, scoped, time-bounded grant represented in this witness.

    Key design choices:
      * scope is explicit and bounded -> no silent scope upgrade
      * token_id is stable across object copies -> single-use is value-bound
      * single_use is True by default -> one token id can be consumed once
      * expires_at bounds the represented grant

    The object does not authenticate who issued it. token_id is a runtime
    identity for replay control, not a cryptographic credential.
    """

    action: str
    scope: str
    evidence: Evidence
    issued_at: float = field(default_factory=time.time)
    ttl_seconds: float = 300.0
    single_use: bool = True
    token_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @property
    def expires_at(self) -> float:
        return self.issued_at + self.ttl_seconds

    def is_live(self, now: float | None = None) -> bool:
        """Check liveness against now.

        now is injectable for tests/simulation. Supplying it does not establish
        an external trusted-clock guarantee.
        """
        now = time.time() if now is None else now
        return now <= self.expires_at

    def covers(self, action: str, scope: str) -> bool:
        """Authority must match the exact action and scope. No widening."""
        return self.action == action and self.scope == scope
