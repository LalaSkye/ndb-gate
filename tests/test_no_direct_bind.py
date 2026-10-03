"""Tests for the model-local No-Direct-Bind reference gate."""

import dataclasses
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


def test_proved_authority_allows_and_executes_once():
    sink = []
    g = Gate()
    d = g.bind("deploy", "prod", proved_token(), make_effect(sink))
    assert d.outcome is Outcome.ALLOW
    assert d.effect == "EXECUTED"
    assert sink == ["EXECUTED"]


def test_allow_receipt_is_written_only_after_effect_returns():
    g = Gate()
    observed_chain_lengths = []

    def effect():
        observed_chain_lengths.append(len(g.chain))
        return "done"

    d = g.bind("deploy", "prod", proved_token(), effect)
    assert observed_chain_lengths == [0]
    assert d.outcome is Outcome.ALLOW
    assert d.effect == "done"
    assert len(g.chain) == 1
    assert list(g.chain)[0].outcome == "ALLOW"


def test_effect_exception_emits_error_receipt_not_allow():
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
    assert verify_chain(receipts) is True


def test_every_completed_decision_emits_a_receipt():
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
