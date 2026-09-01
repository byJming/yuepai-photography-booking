import base64
import importlib.util
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parents[2] / "deploy" / "scripts" / "file_crypto.py"


def load_crypto_module():
    spec = importlib.util.spec_from_file_location("yuepai_backup_crypto", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backup_crypto_round_trip_and_tamper_detection(tmp_path: Path) -> None:
    crypto = load_crypto_module()
    key_file = tmp_path / "backup.key"
    key_file.write_text(base64.b64encode(b"k" * 32).decode(), encoding="ascii")
    source = tmp_path / "source.bin"
    source.write_bytes((b"private-backup-data" * 100_000) + b"tail")
    encrypted = tmp_path / "backup.enc"
    restored = tmp_path / "restored.bin"

    crypto.encrypt_file(source, encrypted, key_file)
    crypto.decrypt_file(encrypted, restored, key_file)

    assert restored.read_bytes() == source.read_bytes()
    payload = bytearray(encrypted.read_bytes())
    payload[len(payload) // 2] ^= 0x01
    encrypted.write_bytes(payload)
    with pytest.raises(ValueError, match="authentication failed"):
        crypto.decrypt_file(encrypted, restored, key_file)
