"""ndb-gate — model-local No-Direct-Bind reference gate.

The package demonstrates a bounded property over the supplied token, evidence
record, clock value and effect function. It does not authenticate an external
issuer, prove complete mediation, or turn receipt-chain consistency into
external provenance.
"""

from .gate import Gate, Decision, Outcome
from .authority import AuthorityToken, Evidence, EvidenceClass
from .receipts import Receipt, ReceiptChain, verify_chain

__all__ = [
    "Gate",
    "Decision",
    "Outcome",
    "AuthorityToken",
    "Evidence",
    "EvidenceClass",
    "Receipt",
    "ReceiptChain",
    "verify_chain",
]

__version__ = "0.1.0"
