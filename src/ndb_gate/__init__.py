"""ndb-gate — a model-local No-Direct-Bind execution-gate witness.

Within this package, the supplied effect function is invoked only after the
represented authority checks pass. The package does not authenticate an
external issuer, establish trusted time, prove complete mediation of a wider
application, or provide external receipt authenticity.
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
