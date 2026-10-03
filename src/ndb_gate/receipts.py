"""Hash-linked receipt chain.

Every completed gate decision emits a Receipt. Receipts are linked by the hash
of the previous receipt, so edits to a chain already held by a reviewer break
link verification.

Boundary: verify_chain checks internal consistency only. A completely rewritten,
internally consistent chain can verify unless an external anchor preserves the
original head or some other independently held reference.
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
    """An integrity-linked record of one gate outcome."""

    index: int
    action: str
    scope: str
    outcome: str
    reason: str
    evidence_class: str
    prev_hash: str
    timestamp: float = field(default_factory=time.time)

    def body(self) -> dict:
        """The fields covered by the receipt hash."""
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
    """An in-memory append-only, hash-linked sequence of receipts."""

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
    """Check the supplied chain's internal hash-link consistency.

    This is not an external authenticity check. It returns True iff:
      * indices are contiguous from 0
      * each receipt's prev_hash equals the previous receipt's self_hash
      * the first receipt links to GENESIS_HASH
    """
    prev = GENESIS_HASH
    for expected_index, receipt in enumerate(receipts):
        if receipt.index != expected_index:
            return False
        if receipt.prev_hash != prev:
            return False
        prev = receipt.self_hash()
    return True
