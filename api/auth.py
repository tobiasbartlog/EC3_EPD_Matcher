"""Token-Management für API-Authentifizierung."""
import time
import requests
from typing import Dict, Any, Optional

from config.settings import APIConfig


class TokenManager:
    """Verwaltet JWT-Token mit automatischer Erneuerung."""

    def __init__(self):
        if not all([APIConfig.BASE_URL, APIConfig.USERNAME, APIConfig.PASSWORD]):
            raise ValueError("❌ API-Konfiguration unvollständig (BASE_URL/USERNAME/PASSWORD)")

        self._token: Optional[str] = None
        self._exp_ts: float = 0.0

    def get_token(self) -> str:
        """Gibt gültigen Token zurück (erneuert bei Bedarf)."""
        if self._is_valid():
            return self._token

        self._refresh_token()
        return self._token

    def get_headers(self) -> Dict[str, str]:
        """Gibt Auth-Header für API-Requests zurück."""
        return {
            "Authorization": f"Bearer {self.get_token()}",
            "Accept": "application/json"
        }

    def _is_valid(self) -> bool:
        """Prüft ob aktueller Token noch gültig ist."""
        return self._token is not None and time.time() < self._exp_ts

    def _refresh_token(self) -> None:
        """Holt neuen Token vom Auth-Endpoint."""
        url = f"{APIConfig.BASE_URL}/api/Auth/getToken"
        body = {
            "username": APIConfig.USERNAME,
            "passwort": APIConfig.PASSWORD
        }

        response = requests.post(url, json=body, timeout=20)
        response.raise_for_status()

        try:
            payload = response.json()
        except ValueError:
            payload = response.text.strip()

        token, ttl = self._extract_token_info(payload)

        if not token:
            raise RuntimeError("❌ Kein Token in Auth-Antwort gefunden")

        # Token mit Sicherheitsmarge cachen
        self._token = token
        self._exp_ts = time.time() + max(1, ttl - min(60, ttl // 10))

    @staticmethod
    def _extract_token_info(payload: Any) -> tuple[str, int]:
        """Extrahiert Token und TTL aus Auth-Response."""
        if isinstance(payload, dict):
            token = (
                    payload.get("token") or
                    payload.get("access_token") or
                    payload.get("jwt")
            )
            ttl = int(payload.get("expires_in", 3600))
            return token, ttl

        # Fallback: Payload ist direkt der Token
        return str(payload), 3600