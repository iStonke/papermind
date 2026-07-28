"""Streaming-Verschlüsselung und Secret-Schutz für PaperMind-Backups."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


_MAGIC = b"PMBK1"
_NONCE_BYTES = 12
_TAG_BYTES = 16
_SECRET_PREFIX = "enc:v1:"
_CHUNK_SIZE = 1024 * 1024


def backup_encryption_key() -> bytes | None:
    raw = str(os.environ.get("BACKUP_ENCRYPTION_KEY") or "").strip()
    key_file = str(os.environ.get("BACKUP_ENCRYPTION_KEY_FILE") or "").strip()
    if not raw and key_file:
        try:
            raw = Path(key_file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError(f"Backup-Schlüsseldatei kann nicht gelesen werden: {exc}") from exc
    if not raw:
        return None
    try:
        if len(raw) == 64:
            key = bytes.fromhex(raw)
        else:
            key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except (ValueError, TypeError) as exc:
        raise RuntimeError("BACKUP_ENCRYPTION_KEY muss 32 Byte als Hex oder Base64 enthalten") from exc
    if len(key) != 32:
        raise RuntimeError("BACKUP_ENCRYPTION_KEY muss genau 32 Byte enthalten")
    return key


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def encrypt_file(source: Path, destination: Path, key: bytes) -> None:
    nonce = os.urandom(_NONCE_BYTES)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    with source.open("rb") as src, destination.open("wb") as dst:
        dst.write(_MAGIC)
        dst.write(nonce)
        for chunk in iter(lambda: src.read(_CHUNK_SIZE), b""):
            dst.write(encryptor.update(chunk))
        dst.write(encryptor.finalize())
        dst.write(encryptor.tag)


def decrypt_file(source: Path, destination: Path, key: bytes) -> None:
    size = source.stat().st_size
    header_size = len(_MAGIC) + _NONCE_BYTES
    if size < header_size + _TAG_BYTES:
        raise RuntimeError(f"Verschlüsseltes Backup ist zu kurz: {source.name}")
    with source.open("rb") as src:
        if src.read(len(_MAGIC)) != _MAGIC:
            raise RuntimeError(f"Ungültiges verschlüsseltes Backupformat: {source.name}")
        nonce = src.read(_NONCE_BYTES)
        src.seek(size - _TAG_BYTES)
        tag = src.read(_TAG_BYTES)
        decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        src.seek(header_size)
        remaining = size - header_size - _TAG_BYTES
        with destination.open("wb") as dst:
            while remaining > 0:
                chunk = src.read(min(_CHUNK_SIZE, remaining))
                if not chunk:
                    raise RuntimeError(f"Verschlüsseltes Backup ist abgeschnitten: {source.name}")
                remaining -= len(chunk)
                dst.write(decryptor.update(chunk))
            try:
                dst.write(decryptor.finalize())
            except Exception as exc:
                destination.unlink(missing_ok=True)
                raise RuntimeError(f"Authentifizierung des Backups fehlgeschlagen: {source.name}") from exc


def encrypt_secret(value: str, key: bytes) -> str:
    nonce = os.urandom(_NONCE_BYTES)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    ciphertext = encryptor.update(value.encode("utf-8")) + encryptor.finalize()
    payload = nonce + encryptor.tag + ciphertext
    return _SECRET_PREFIX + base64.urlsafe_b64encode(payload).decode("ascii")


def decrypt_secret(value: str, key: bytes) -> str:
    if not value.startswith(_SECRET_PREFIX):
        return value
    try:
        payload = base64.urlsafe_b64decode(value[len(_SECRET_PREFIX):])
        nonce = payload[:_NONCE_BYTES]
        tag = payload[_NONCE_BYTES:_NONCE_BYTES + _TAG_BYTES]
        ciphertext = payload[_NONCE_BYTES + _TAG_BYTES:]
        decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        return (decryptor.update(ciphertext) + decryptor.finalize()).decode("utf-8")
    except Exception as exc:
        raise RuntimeError("Gespeichertes Backup-Secret kann nicht entschlüsselt werden") from exc


def canonical_json_bytes(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def manifest_hmac(manifest_without_hmac: dict, key: bytes) -> str:
    return hmac.new(key, canonical_json_bytes(manifest_without_hmac), hashlib.sha256).hexdigest()
