"""Authority and evidence primitives for the reference model.

The evidence classes are caller-supplied classifications. This module compares
those classifications and token fields; it does not authenticate an external
issuer, provenance source, or clock.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum


class EvidenceClass(Enum):
    """Evidence-class labels, strongest first within this model."""

    PROVED = "PROVED"
    PLAUSIBLE = "PLAUSIBLE"
    PATTERN_ONLY = "PATTERN_ONLY"
    NOT_ADMISSIBLE = "NOT_ADMISSIBLE"

    @property
    def is_admissible(self) -> bool:
        return self is not EvidenceClass.NOT_ADMISSIBLE


@dataclass(frozen=True)
class Evidence:
    """A caller-supplied evidence record used by the reference gate."""

    claim: str
    evidence_class: EvidenceClass
    source: str

    def satisfies(self, required: EvidenceClass) -> bool:
        """Compare this record's class label with the configured threshold."""
        order = {
            EvidenceClass.PROVED: 3,
            EvidenceClass.PLAUSIBLE: 2,
            EvidenceClass.PATTERN_ONLY: 1,
            EvidenceClass.NOT_ADMISSIBLE: 0,
        }
        return order[self.evidence_class] >= order[required]


@dataclass(frozen=True)
class AuthorityToken:
    """A scoped, time-bounded token value used by this reference model.

    `identity_key` is a deterministic replay key over the immutable token
    fields. It prevents a value-equal copy from becoming a fresh single-use
    token. It is not a signature and does not authenticate who created the
    token.
    """

    action: str
    scope: str
    evidence: Evidence
    issued_at: float = field(default_factory=time.time)
    ttl_seconds: float = 300.0
    single_use: bool = True

    @property
    def identity_key(self) -> str:
        payload = {
            "action": self.action,
            "scope": self.scope,
            "evidence": {
                "claim": self.evidence.claim,
                "evidence_class": self.evidence.evidence_class.value,
                "source": self.evidence.source,
            },
            "issued_at": self.issued_at.hex(),
            "ttl_seconds": self.ttl_seconds.hex(),
            "single_use": self.single_use,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @property
    def expires_at(self) -> float:
        return self.issued_at + self.ttl_seconds

    def is_live(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        return now <= self.expires_at

    def covers(self, action: str, scope: str) -> bool:
        """Authority must match the requested action and scope."""
        return self.action == action and self.scope == scope
