import base64

import pytest

from app.core.security import FieldCipher, hash_password, hash_secret, new_token, verify_password


def test_field_cipher_round_trip_and_aad_binding() -> None:
    cipher = FieldCipher(base64.b64encode(b"x" * 32).decode())
    encrypted = cipher.encrypt("13800138000", "bookings.contact_phone:YP1")

    assert encrypted.startswith(b"v1:")
    assert cipher.decrypt(encrypted, "bookings.contact_phone:YP1") == "13800138000"
    with pytest.raises(ValueError):
        cipher.decrypt(encrypted, "bookings.contact_phone:YP2")


def test_password_hash_is_not_plaintext() -> None:
    encoded = hash_password("a-strong-test-password")
    assert encoded != "a-strong-test-password"
    assert verify_password(encoded, "a-strong-test-password") is True
    assert verify_password(encoded, "wrong-password") is False


def test_tokens_are_random_and_hashable() -> None:
    first = new_token()
    second = new_token()
    assert first != second
    assert hash_secret(first, "pepper") == hash_secret(first, "pepper")
    assert hash_secret(first, "pepper") != hash_secret(first, "other")
