"""ndb-gate — model-local No-Direct-Bind execution-gate witness.

Within this package, the supplied effect function is attempted only through
`Gate.bind` after the declared model checks pass. This package does not
authenticate an external issuer, provide trusted time, or establish complete
mediation in a caller's application.
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
