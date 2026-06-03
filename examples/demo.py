"""Runnable demo: python examples/demo.py

Walks the gate through HOLD, DENY, ALLOW, and a tamper check, printing receipts.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ndb_gate import Gate, AuthorityToken, Evidence, EvidenceClass, verify_chain

gate = Gate()
ran = []
effect = lambda: ran.append("EXECUTED") or "EXECUTED"

print("1) no token        ->", gate.bind("deploy", "prod", None, effect).outcome.value)

weak = AuthorityToken("deploy", "prod", Evidence("hunch", EvidenceClass.PLAUSIBLE, "2nd-hand"))
print("2) weak evidence   ->", gate.bind("deploy", "prod", weak, effect).outcome.value)

proved = AuthorityToken("deploy", "prod", Evidence("operator", EvidenceClass.PROVED, "first-party"))
print("3) proved authority->", gate.bind("deploy", "prod", proved, effect).outcome.value)

print("4) reuse token     ->", gate.bind("deploy", "prod", proved, effect).outcome.value)

print("\neffect ran:", ran, "(exactly once)")
print("chain verifies:", verify_chain(list(gate.chain)))
print("\nReceipts:")
for r in gate.chain.to_list():
    print(f"  #{r['index']} {r['outcome']:5} {r['action']}/{r['scope']:7} {r['reason']}")
