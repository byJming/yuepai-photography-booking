from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MAGIC = b"YPAIBAK1"
NONCE_SIZE = 12
TAG_SIZE = 16
CHUNK_SIZE = 1024 * 1024


def load_key(key_file: Path) -> bytes:
    """Load one base64-encoded 256-bit backup key."""

    try:
        key = base64.b64decode(key_file.read_text(encoding="ascii").strip(), validate=True)
    except Exception as exc:
        raise ValueError("backup key must be valid base64") from exc
    if len(key) != 32:
        raise ValueError("backup key must decode to exactly 32 bytes")
    return key


def encrypt_file(source: Path, target: Path, key_file: Path) -> None:
    """Encrypt a file with streaming AES-256-GCM and atomically publish the result."""

    key = load_key(key_file)
    nonce = os.urandom(NONCE_SIZE)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(MAGIC)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp-{os.getpid()}")
    try:
        with source.open("rb") as source_stream, temporary.open("xb") as target_stream:
            target_stream.write(MAGIC)
            target_stream.write(nonce)
            while chunk := source_stream.read(CHUNK_SIZE):
                target_stream.write(encryptor.update(chunk))
            target_stream.write(encryptor.finalize())
            target_stream.write(encryptor.tag)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def decrypt_file(source: Path, target: Path, key_file: Path) -> None:
    """Authenticate and decrypt one backup file before atomically publishing plaintext."""

    key = load_key(key_file)
    source_size = source.stat().st_size
    header_size = len(MAGIC) + NONCE_SIZE
    if source_size <= header_size + TAG_SIZE:
        raise ValueError("encrypted backup is truncated")

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp-{os.getpid()}")
    try:
        with source.open("rb") as source_stream:
            if source_stream.read(len(MAGIC)) != MAGIC:
                raise ValueError("encrypted backup has an invalid header")
            nonce = source_stream.read(NONCE_SIZE)
            source_stream.seek(-TAG_SIZE, os.SEEK_END)
            tag = source_stream.read(TAG_SIZE)
            source_stream.seek(header_size)
            remaining = source_size - header_size - TAG_SIZE
            decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
            decryptor.authenticate_additional_data(MAGIC)
            with temporary.open("xb") as target_stream:
                while remaining:
                    chunk = source_stream.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        raise ValueError("encrypted backup is truncated")
                    remaining -= len(chunk)
                    target_stream.write(decryptor.update(chunk))
                try:
                    target_stream.write(decryptor.finalize())
                except InvalidTag as exc:
                    raise ValueError("backup authentication failed") from exc
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    """Encrypt or decrypt a backup file from the command line."""

    parser = argparse.ArgumentParser(description="Yuepai authenticated backup file encryption")
    parser.add_argument("operation", choices=("encrypt", "decrypt"))
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("key_file", type=Path)
    args = parser.parse_args()
    if args.operation == "encrypt":
        encrypt_file(args.source, args.target, args.key_file)
    else:
        decrypt_file(args.source, args.target, args.key_file)


if __name__ == "__main__":
    main()
