import hashlib

import pytest

from iide.ids import replay_correlation_id, replay_id, stable_id


def test_stable_id_matches_spec_formula():
    expected = hashlib.sha256(b"billing_api|F1-A|ambiguous|agent|3|v1").hexdigest()[:16]
    assert stable_id("billing_api", "F1-A", "ambiguous", "agent", "3", "v1") == expected


def test_stable_id_is_deterministic_and_length_controlled():
    assert stable_id("a", "b") == stable_id("a", "b")
    assert len(stable_id("a", "b")) == 16
    assert len(stable_id("a", "b", length=8)) == 8


def test_stable_id_depends_on_every_part_and_order():
    assert stable_id("a", "b") != stable_id("b", "a")
    assert stable_id("a", "b") != stable_id("a", "c")


@pytest.mark.parametrize(
    "parts", [(), ("",), ("a", ""), ("a|b", "c")], ids=["none", "empty", "empty-2nd", "separator"]
)
def test_stable_id_rejects_ambiguous_parts(parts):
    with pytest.raises(ValueError):
        stable_id(*parts)


def test_stable_id_rejects_non_strings_and_bad_length():
    with pytest.raises(TypeError):
        stable_id("a", 3)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        stable_id("a", length=0)
    with pytest.raises(ValueError):
        stable_id("a", length=65)


def test_replay_id_is_deterministic_and_index_sensitive():
    a = replay_id("billing_api", "credential_bruteforce", "baseline", "v1", 1)
    assert a == replay_id("billing_api", "credential_bruteforce", "baseline", "v1", 1)
    assert a != replay_id("billing_api", "credential_bruteforce", "baseline", "v1", 2)
    assert a != replay_id("billing_api", "credential_bruteforce", "baseline", "v2", 1)


def test_replay_correlation_id_format():
    assert replay_correlation_id("credential_bruteforce", 1) == "replay-credential_bruteforce-001"
    assert replay_correlation_id("x", 12) == "replay-x-012"


@pytest.mark.parametrize("index", [0, -1])
def test_replay_index_is_one_based(index):
    with pytest.raises(ValueError):
        replay_correlation_id("x", index)
    with pytest.raises(ValueError):
        replay_id("t", "a", "p", "v", index)


def test_replay_index_must_be_int():
    with pytest.raises(TypeError):
        replay_correlation_id("x", True)  # bools are not valid indices
    with pytest.raises(TypeError):
        replay_correlation_id("x", 1.0)  # type: ignore[arg-type]
