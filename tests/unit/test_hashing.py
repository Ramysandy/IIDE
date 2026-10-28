import pytest

from iide.hashing import canonical_json_hash, hash_files, hash_patterns, sha256_bytes


def test_sha256_bytes_known_vector():
    assert sha256_bytes(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_canonical_json_hash_ignores_key_order_and_whitespace():
    assert canonical_json_hash({"a": 1, "b": [1, 2]}) == canonical_json_hash({"b": [1, 2], "a": 1})
    assert canonical_json_hash({"a": 1}) != canonical_json_hash({"a": 2})


def test_hash_changes_when_content_or_path_changes(tmp_path):
    (tmp_path / "a.txt").write_text("one")
    base = hash_patterns(tmp_path, ["*.txt"])
    assert base == hash_patterns(tmp_path, ["*.txt"])
    (tmp_path / "a.txt").write_text("two")
    assert hash_patterns(tmp_path, ["*.txt"]) != base


def test_hash_includes_relative_path(tmp_path):
    (tmp_path / "a.txt").write_text("same")
    one = hash_patterns(tmp_path, ["*.txt"])
    (tmp_path / "a.txt").rename(tmp_path / "b.txt")
    assert hash_patterns(tmp_path, ["*.txt"]) != one


def test_hash_ignores_caches_and_bytecode(tmp_path):
    (tmp_path / "m.py").write_text("x=1")
    base = hash_patterns(tmp_path, ["**/*"])
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "m.cpython-313.pyc").write_bytes(b"junk")
    (tmp_path / "m.pyc").write_bytes(b"junk")
    assert hash_patterns(tmp_path, ["**/*"]) == base


def test_hashing_nothing_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        hash_patterns(tmp_path, ["*.nothing"])
    with pytest.raises(FileNotFoundError):
        hash_files(tmp_path, [])
