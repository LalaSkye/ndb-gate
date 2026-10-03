import dataclasses
import threading

import pytest

from ndb_gate import AuthorityToken, Evidence, EvidenceClass, Gate, Outcome, verify_chain


def token():
    return AuthorityToken(
        action="deploy",
        scope="prod",
        evidence=Evidence("operator grant", EvidenceClass.PROVED, "fixture"),
    )


def test_copied_token_is_still_spent():
    gate = Gate()
    original = token()
    copied = dataclasses.replace(original)
    seen = []

    first = gate.bind("deploy", "prod", original, lambda: seen.append("ran"))
    second = gate.bind("deploy", "prod", copied, lambda: seen.append("ran"))

    assert copied.token_id == original.token_id
    assert first.outcome is Outcome.ALLOW
    assert second.outcome is Outcome.DENY
    assert seen == ["ran"]


def test_single_use_is_atomic_across_threads():
    gate = Gate()
    grant = token()
    barrier = threading.Barrier(9)
    outcomes = []
    effects = []
    lock = threading.Lock()

    def effect():
        with lock:
            effects.append("ran")

    def worker():
        barrier.wait()
        decision = gate.bind("deploy", "prod", grant, effect)
        with lock:
            outcomes.append(decision.outcome)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=2)
        assert not thread.is_alive()

    assert outcomes.count(Outcome.ALLOW) == 1
    assert outcomes.count(Outcome.DENY) == 7
    assert effects == ["ran"]


def test_allow_receipt_is_written_after_effect_returns():
    gate = Gate()
    grant = token()

    def effect():
        assert list(gate.chain) == []
        return "done"

    decision = gate.bind("deploy", "prod", grant, effect)

    assert decision.outcome is Outcome.ALLOW
    assert list(gate.chain)[-1].outcome == Outcome.ALLOW.value


def test_effect_error_records_failure_not_allow():
    gate = Gate()
    grant = token()

    def fail():
        raise RuntimeError("fixture failure")

    with pytest.raises(RuntimeError, match="fixture failure"):
        gate.bind("deploy", "prod", grant, fail)

    receipts = list(gate.chain)
    assert len(receipts) == 1
    assert receipts[0].outcome == Outcome.EFFECT_FAILED.value
    assert all(receipt.outcome != Outcome.ALLOW.value for receipt in receipts)
    assert verify_chain(receipts)

    retry = gate.bind("deploy", "prod", grant, lambda: "not run")
    assert retry.outcome is Outcome.DENY
