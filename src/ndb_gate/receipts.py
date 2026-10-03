"""Verifiable receipt chain.

Every gate attempt emits a Receipt. Receipts are hash-linked into a chain
(each receipt commits to the hash of the previous one), so edits to a chain
already in hand are detectable.

`verify_chain` checks internal linkage and ordering. It does not authenticate
the origin of a newly supplied chain and it does not provide an external anchor.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, asdict, field

GENESIS_HASH = "0" * 64


def _hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class Receipt:
    """A hash-linked record of one gate attempt."""

    index: int
    action: str
    scope: str
    outcome: str          # ALLOW / HOLD / DENY / ERROR
    reason: str
    evidence_class: str
    prev_hash: str
    timestamp: float = field(default_factory=time.time)

    def body(self) -> dict:
        """The fields covered by the hash (everything except self_hash)."""
        return {
            "index": self.index,
            "action": self.action,
            "scope": self.scope,
            "outcome": self.outcome,
            "reason": self.reason,
            "evidence_class": self.evidence_class,
            "prev_hash": self.prev_hash,
            "timestamp": self.timestamp,
        }

    def self_hash(self) -> str:
        return _hash(self.body())


class ReceiptChain:
    """An append-only, hash-linked sequence of receipts."""

    def __init__(self) -> None:
        self._receipts: list[Receipt] = []

    def __len__(self) -> int:
        return len(self._receipts)

    def __iter__(self):
        return iter(self._receipts)

    @property
    def head_hash(self) -> str:
        if not self._receipts:
            return GENESIS_HASH
        return self._receipts[-1].self_hash()

    def append(
        self, action: str, scope: str, outcome: str, reason: str, evidence_class: str
    ) -> Receipt:
        receipt = Receipt(
            index=len(self._receipts),
            action=action,
            scope=scope,
            outcome=outcome,
            reason=reason,
            evidence_class=evidence_class,
            prev_hash=self.head_hash,
        )
        self._receipts.append(receipt)
        return receipt

    def to_list(self) -> list[dict]:
        out = []
        for r in self._receipts:
            d = asdict(r)
            d["self_hash"] = r.self_hash()
            out.append(d)
        return out


def verify_chain(receipts: list[Receipt]) -> bool:
    """Replay a chain and confirm internal integrity.

    Returns True iff:
      * indices are contiguous from 0
      * each receipt's prev_hash equals the previous receipt's self_hash
      * the first receipt links to GENESIS_HASH

    This is an integrity check for supplied receipts, not external
    authentication of who produced the chain.
    """
    prev = GENESIS_HASH
    for expected_index, r in enumerate(receipts):
        if r.index != expected_index:
            return False
        if r.prev_hash != prev:
            return False
        prev = r.self_hash()
    return True
