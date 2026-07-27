from app.auth.passwords import hash_password, verify_password


def test_hash_is_not_the_plaintext():
    hashed = hash_password("correct horse battery")

    assert hashed != "correct horse battery"
    assert hashed.startswith("$argon2id$")


def test_correct_password_verifies():
    assert verify_password("s3cret-password", hash_password("s3cret-password")) is True


def test_wrong_password_does_not_verify():
    assert verify_password("wrong-password", hash_password("s3cret-password")) is False


def test_none_hash_returns_false_without_raising():
    assert verify_password("anything", None) is False


def test_malformed_hash_returns_false_without_raising():
    assert verify_password("anything", "not-a-real-hash") is False


def test_same_password_hashes_differently():
    assert hash_password("repeated") != hash_password("repeated")
