"""Tests for the model-local No-Direct-Bind witness."""

import dataclasses
import threading
import time

import pytest

from ndb_gate import (
    Gate,
    Outcome,
    AuthorityToken,
    Evidence,
    EvidenceClass,
    verify_chain,
)


def make_effect(sink: list):
    def _fn():
        sink.append("EXECUTED")
        return "EXECUTED"
    return _fn


def proved_token(action="deploy", scope="prod", ttl=300.0, single_use=True):
    return AuthorityToken(
        action=action,
        scope=scope,
        evidence=Evidence("authorised by Ricky", EvidenceClass.PROVED, "first-party"),
        ttl_seconds=ttl,
        single_use=single_use,
    )


# --- NEGATIVE: no bind without authority -----------------------------------

def test_no_token_holds_and_does_not_execute():
    sink = []
    g = Gate()
    d = g.bind("deploy", "prod", None, make_effect(sink))
    assert d.outcome is Outcome.HOLD
    assert d.effect is None
    assert sink == []


def test_not_admissible_evidence_denies():
    sink = []
    g = Gate()
    bad = AuthorityToken(
        "deploy", "prod",
        Evidence("vibes", EvidenceClass.NOT_ADMISSIBLE, "unknown"),
    )
    d = g.bind("deploy", "prod", bad, make_effect(sink))
    assert d.outcome is Outcome.DENY
    assert sink == []


@pytest.mark.parametrize("weak", [EvidenceClass.PLAUSIBLE, EvidenceClass.PATTERN_ONLY])
def test_weak_evidence_holds(weak):
    sink = []
    g = Gate(required=EvidenceClass.PROVED)
    tok = AuthorityToken("deploy", "prod", Evidence("maybe", weak, "secondary"))
    d = g.bind("deploy", "prod", tok, make_effect(sink))
    assert d.outcome is Outcome.HOLD
    assert sink == []


def test_scope_mismatch_denies_no_widening():
    sink = []
    g = Gate()
    tok = proved_token(action="deploy", scope="staging")
    d = g.bind("deploy", "prod", tok, make_effect(sink))
    assert d.outcome is Outcome.DENY
    assert sink == []


def test_expired_authority_holds():
    sink = []
    g = Gate()
    tok = proved_token(ttl=10.0)
    later = time.time() + 100.0
    d = g.bind("deploy", "prod", tok, make_effect(sink), now=later)
    assert d.outcome is Outcome.HOLD
    assert sink == []


def test_batch_authority_does_not_carry():
    sink = []
    g = Gate()
    tok = proved_token(single_use=True)
    d1 = g.bind("deploy", "prod", tok, make_effect(sink))
    d2 = g.bind("deploy", "prod", tok, make_effect(sink))
    assert d1.outcome is Outcome.ALLOW
    assert d2.outcome is Outcome.DENY
    assert sink == ["EXECUTED"]


def test_copied_single_use_token_keeps_identity_and_is_denied():
    sink = []
    g = Gate()
    tok = proved_token(single_use=True)
    copied = dataclasses.replace(tok)

    assert copied.token_id == tok.token_id

    d1 = g.bind("deploy", "prod", tok, make_effect(sink))
    d2 = g.bind("deploy", "prod", copied, make_effect(sink))

    assert d1.outcome is Outcome.ALLOW
    assert d2.outcome is Outcome.DENY
    assert sink == ["EXECUTED"]


def test_separately_issued_tokens_get_distinct_identity():
    assert proved_token().token_id != proved_token().token_id


def test_single_use_consume_is_atomic_for_concurrent_callers():
    g = Gate()
    tok = proved_token(single_use=True)
    start = threading.Barrier(9)
    outcomes = []
    outcomes_lock = threading.Lock()
    sink = []

    def worker():
        start.wait()
        decision = g.bind("deploy", "prod", tok, make_effect(sink))
        with outcomes_lock:
            outcomes.append(decision.outcome)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    start.wait()
    for thread in threads:
        thread.join(timeout=2)

    assert all(not thread.is_alive() for thread in threads)
    assert outcomes.count(Outcome.ALLOW) == 1
    assert outcomes.count(Outcome.DENY) == 7
    assert sink == ["EXECUTED"]


# --- POSITIVE: the unique allow path ---------------------------------------

def test_proved_authority_allows_and_executes_once():
    sink = []
    g = Gate()
    d = g.bind("deploy", "prod", proved_token(), make_effect(sink))
    assert d.outcome is Outcome.ALLOW
    assert d.effect == "EXECUTED"
    assert sink == ["EXECUTED"]


def test_failed_effect_emits_error_receipt_not_allow():
    g = Gate()
    tok = proved_token()

    def boom():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        g.bind("deploy", "prod", tok, boom)

    receipts = list(g.chain)
    assert len(receipts) == 1
    assert receipts[0].outcome == "ERROR"
    assert receipts[0].reason == "effect raised RuntimeError"

    d = g.bind("deploy", "prod", tok, lambda: "SHOULD_NOT_RUN")
    assert d.outcome is Outcome.DENY
    assert len(g.chain) == 2


# --- RECEIPTS: every attempt is recorded and the chain verifies ------------

def test_every_attempt_emits_a_receipt():
    g = Gate()
    g.bind("a", "s", None, lambda: None)
    g.bind("a", "s", proved_token("a", "s"), lambda: None)
    assert len(g.chain) == 2


def test_receipt_chain_verifies():
    g = Gate()
    g.bind("a", "s", None, lambda: None)
    g.bind("b", "s", proved_token("b", "s"), lambda: None)
    g.bind("c", "s", None, lambda: None)
    assert verify_chain(list(g.chain)) is True


def test_tampering_breaks_the_chain():
    g = Gate()
    g.bind("a", "s", None, lambda: None)
    g.bind("b", "s", proved_token("b", "s"), lambda: None)
    receipts = list(g.chain)
    forged = dataclasses.replace(receipts[0], outcome="ALLOW", reason="forged")
    receipts[0] = forged
    assert verify_chain(receipts) is False
