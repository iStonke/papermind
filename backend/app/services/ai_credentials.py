"""Encrypted credentials for optional note text-generation providers.

Credentials deliberately live outside ``AppSettingsRead`` so a normal settings
request can never return an API key. Environment variables remain supported for
deployments that manage secrets outside PaperMind.
"""

from __future__ import annotations

import base64
import os
import secrets
from pathlib import Path
from typing import Literal

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.global_setting import GlobalSetting
from app.schemas.notes import AICredentialsStatus, AIProviderCredentialStatus
from app.services.backup_crypto import backup_encryption_key, decrypt_secret, encrypt_secret
from app.core.config import get_settings


Provider = Literal["openai", "anthropic"]
_ENV_KEYS: dict[Provider, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


def _decode_key(raw: str) -> bytes:
    try:
        key = bytes.fromhex(raw) if len(raw) == 64 else base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("AI_CREDENTIALS_ENCRYPTION_KEY muss Hex oder Base64 sein") from exc
    if len(key) != 32:
        raise RuntimeError("AI_CREDENTIALS_ENCRYPTION_KEY muss genau 32 Byte enthalten")
    return key


def _managed_credentials_key() -> bytes:
    """Load or create PaperMind's installation-local credential key.

    This fallback keeps secret management out of the UI while retaining an
    independent, persistent encryption key outside the settings database.
    Explicit deployment secrets and the backup key still take precedence.
    """
    configured_path = str(os.environ.get("AI_CREDENTIALS_MANAGED_KEY_FILE") or "").strip()
    path = (
        Path(configured_path)
        if configured_path
        else Path(get_settings().storage_path) / ".papermind" / "ai-credentials.key"
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.parent.chmod(0o700)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError:
            fd = None
        if fd is not None:
            with os.fdopen(fd, "wb") as handle:
                handle.write(secrets.token_bytes(32))
                handle.flush()
                os.fsync(handle.fileno())
        path.chmod(0o600)
        key = path.read_bytes()
    except OSError as exc:
        raise RuntimeError("PaperMind konnte den Schutz für KI-Zugangsdaten nicht einrichten") from exc
    if len(key) != 32:
        raise RuntimeError("Der interne Schutz für KI-Zugangsdaten ist beschädigt")
    return key


def ai_credentials_encryption_key() -> bytes | None:
    raw = str(os.environ.get("AI_CREDENTIALS_ENCRYPTION_KEY") or "").strip()
    key_file = str(os.environ.get("AI_CREDENTIALS_ENCRYPTION_KEY_FILE") or "").strip()
    if not raw and key_file:
        try:
            raw = Path(key_file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError(f"KI-Schlüsseldatei kann nicht gelesen werden: {exc}") from exc
    if raw:
        return _decode_key(raw)
    # Bestehende PaperMind-Installationen besitzen häufig bereits den separat
    # gemounteten Backup-Schlüssel. Er darf auch die KI-Credentials schützen,
    # ohne dass das Secret selbst in die Settings-Datenbank gelangt.
    backup_key = backup_encryption_key()
    if backup_key is not None:
        return backup_key
    return _managed_credentials_key()


class AICredentialService:
    def __init__(self, db: Session):
        self.db = db

    def _row(self, *, for_update: bool = False) -> GlobalSetting | None:
        stmt = select(GlobalSetting).where(GlobalSetting.id == 1)
        if for_update:
            stmt = stmt.with_for_update()
        return self.db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def _stored_credentials(row: GlobalSetting | None) -> dict[str, object]:
        settings = row.settings_json if row is not None and isinstance(row.settings_json, dict) else {}
        credentials = settings.get("ai_credentials")
        return dict(credentials) if isinstance(credentials, dict) else {}

    def get_key(self, provider: Provider) -> str:
        row = self._row()
        stored = self._stored_credentials(row).get(provider)
        # Nur serverseitig erfolgreich geprüfte UI-Schlüssel verwenden. Frühere
        # Klarformat-Einträge bleiben absichtlich inaktiv, bis sie erneut
        # eingegeben und gegen den Anbieter geprüft wurden.
        ciphertext = (
            str(stored.get("ciphertext") or "")
            if isinstance(stored, dict) and stored.get("validated") is True
            else ""
        )
        if ciphertext:
            key = ai_credentials_encryption_key()
            if key is None:
                raise RuntimeError("Gespeicherte KI-Zugangsdaten können ohne Verschlüsselungsschlüssel nicht gelesen werden")
            try:
                return decrypt_secret(ciphertext, key).strip()
            except RuntimeError as exc:
                raise RuntimeError("Gespeicherter KI-Zugang kann nicht entschlüsselt werden") from exc
        return str(os.environ.get(_ENV_KEYS[provider]) or "").strip()

    def status(self) -> AICredentialsStatus:
        row = self._row()
        stored = self._stored_credentials(row)

        def provider_status(provider: Provider) -> AIProviderCredentialStatus:
            entry = stored.get(provider)
            if (
                isinstance(entry, dict)
                and entry.get("validated") is True
                and str(entry.get("ciphertext") or "")
            ):
                return AIProviderCredentialStatus(configured=True, source="stored", masked="••••••••••••")
            if str(os.environ.get(_ENV_KEYS[provider]) or "").strip():
                return AIProviderCredentialStatus(configured=True, source="environment", masked="••••••••••••")
            if entry:
                return AIProviderCredentialStatus(configured=False, source="stored", masked="••••••••••••")
            return AIProviderCredentialStatus()

        return AICredentialsStatus(
            encryption_configured=ai_credentials_encryption_key() is not None,
            openai=provider_status("openai"),
            anthropic=provider_status("anthropic"),
        )

    @staticmethod
    def _validate_key(provider: Provider, api_key: str) -> None:
        if provider == "openai":
            url = "https://api.openai.com/v1/models"
            headers = {"Authorization": f"Bearer {api_key}"}
            label = "OpenAI"
        else:
            url = "https://api.anthropic.com/v1/models"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
            label = "Anthropic"
        try:
            response = httpx.get(url, headers=headers, timeout=15.0)
        except httpx.RequestError as exc:
            raise RuntimeError(f"{label} konnte zur Prüfung des API-Schlüssels nicht erreicht werden") from exc
        if response.status_code in {401, 403}:
            raise ValueError(f"Der {label}-API-Schlüssel wurde abgelehnt")
        if response.status_code >= 400:
            raise RuntimeError(
                f"Der {label}-API-Schlüssel konnte nicht geprüft werden ({response.status_code})"
            )

    def set_key(self, provider: Provider, api_key: str) -> AICredentialsStatus:
        value = str(api_key or "").strip()
        if len(value) < 10:
            raise ValueError("Der API-Schlüssel ist zu kurz")
        self._validate_key(provider, value)
        key = ai_credentials_encryption_key()
        if key is None:
            raise ValueError(
                "Zum Speichern muss AI_CREDENTIALS_ENCRYPTION_KEY oder BACKUP_ENCRYPTION_KEY konfiguriert sein"
            )
        row = self._row(for_update=True)
        if row is None:
            row = GlobalSetting(id=1, settings_json={})
            self.db.add(row)
        current = dict(row.settings_json) if isinstance(row.settings_json, dict) else {}
        credentials = self._stored_credentials(row)
        credentials[provider] = {
            "ciphertext": encrypt_secret(value, key),
            "validated": True,
        }
        current["ai_credentials"] = credentials
        row.settings_json = current
        self.db.commit()
        return self.status()

    def delete_key(self, provider: Provider) -> AICredentialsStatus:
        row = self._row(for_update=True)
        if row is None:
            return self.status()
        current = dict(row.settings_json) if isinstance(row.settings_json, dict) else {}
        credentials = self._stored_credentials(row)
        credentials.pop(provider, None)
        current["ai_credentials"] = credentials
        row.settings_json = current
        self.db.commit()
        return self.status()
