"""Authority and evidence primitives for the reference model.

EvidenceClass values are declared model inputs. They express the classification
that the caller supplied; this module does not authenticate an issuer or prove
that a PROVED label came from an external first party.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4


class EvidenceClass(Enum):
    """Evidence classes, strongest first, as model labels."""

    PROVED = "PROVED"
    PLAUSIBLE = "PLAUSIBLE"
    PATTERN_ONLY = "PATTERN_ONLY"
    NOT_ADMISSIBLE = "NOT_ADMISSIBLE"

    @property
    def is_admissible(self) -> bool:
        return self is not EvidenceClass.NOT_ADMISSIBLE


@dataclass(frozen=True)
class Evidence:
    """A caller-supplied evidence record used by the model."""

    claim: str
    evidence_class: EvidenceClass
    source: str

    def satisfies(self, required: EvidenceClass) -> bool:
        """True iff this declared evidence class is at least as strong as required."""
        order = {
            EvidenceClass.PROVED: 3,
            EvidenceClass.PLAUSIBLE: 2,
            EvidenceClass.PATTERN_ONLY: 1,
            EvidenceClass.NOT_ADMISSIBLE: 0,
        }
        return order[self.evidence_class] >= order[required]


@dataclass(frozen=True)
class AuthorityToken:
    """An explicit, scoped, time-bounded model grant.

    `token_id` is stable token identity. Copying the dataclass preserves it,
    so a value-equal copy of a single-use token is still the same grant for
    replay purposes.
    """

    action: str
    scope: str
    evidence: Evidence
    issued_at: float = field(default_factory=time.time)
    ttl_seconds: float = 300.0
    single_use: bool = True
    token_id: str = field(default_factory=lambda: uuid4().hex)

    @property
    def expires_at(self) -> float:
        return self.issued_at + self.ttl_seconds

    def is_live(self, now: float | None = None) -> bool:
        """Evaluate liveness against the supplied model clock or process clock."""
        now = time.time() if now is None else now
        return now <= self.expires_at

    def covers(self, action: str, scope: str) -> bool:
        """Authority must match the exact action and scope. No widening."""
        return self.action == action and self.scope == scope
