"""Client für EPD-Datenbank API."""
import requests
import concurrent.futures
from typing import Dict, Any, List, Optional

from config.settings import APIConfig
from api.auth import TokenManager


class EPDAPIClient:
    """Client für /api/Datasets Endpoint."""

    def __init__(self, token_manager: TokenManager):
        self.token_manager = token_manager

    def list_epds(
            self,
            labels: Optional[List[str]] = None,
            fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Lädt EPDs aus der Datenbank (mit clientseitiger Filterung).

        Args:
            labels: Filter-Labels (werden clientseitig gefiltert)
            fields: Benötigte Felder (aktuell nicht genutzt)

        Returns:
            Liste normalisierter EPD-Einträge (gefiltert)
        """
        # Lade ALLE EPDs (ohne API-Filter)
        params = {}  # Keine Suchparameter!
        data = self._request(params)

        all_epds = []
        seen = set()

        for row in self._extract_items(data):
            uid = row.get("id")
            if not uid or uid in seen:
                continue

            seen.add(uid)
            all_epds.append(self._normalize_epd_list(row))

        # Clientseitige Filterung (wenn Labels vorhanden)
        if labels and len(labels) > 0:
            filtered = []
            for epd in all_epds:
                name = epd.get("name", "").lower()
                # Prüfe ob IRGENDEIN Label im Namen vorkommt
                if any(label.lower() in name for label in labels):
                    filtered.append(epd)

            print(f"  Filter aktiv: {len(all_epds)} → {len(filtered)} EPDs (Labels: {len(labels)})")
            return filtered

        return all_epds

    def get_epd_details(self, epd_ids: List[int], max_workers: int = 50) -> List[Dict[str, Any]]:
        """
        Lädt Detail-Daten für mehrere EPDs PARALLEL.

        Args:
            epd_ids: Liste von EPD-IDs
            max_workers: Anzahl paralleler Requests (Standard: 10)

        Returns:
            Liste detaillierter EPD-Einträge
        """
        total = len(epd_ids)
        print(f"📥 Lade Details für {total} EPDs (parallel mit {max_workers} Workers)...")

        details = []
        errors = 0

        # Parallel laden mit ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Starte alle Requests parallel
            future_to_id = {
                executor.submit(self._get_single_detail, epd_id): epd_id
                for epd_id in epd_ids
            }

            # Sammle Ergebnisse
            completed = 0
            for future in concurrent.futures.as_completed(future_to_id):
                completed += 1

                # Progress alle 10%
                if completed % max(1, total // 10) == 0 or completed == total:
                    print(f"  Progress: {completed}/{total}")

                try:
                    detail = future.result()
                    if detail:
                        details.append(self._normalize_epd_detail(detail))
                    else:
                        errors += 1
                except Exception as e:
                    epd_id = future_to_id[future]
                    errors += 1
                    if errors <= 3:  # Zeige nur erste 3 Fehler
                        print(f"  ⚠️ Fehler bei EPD {epd_id}: {e}")

        if errors > 0:
            print(f"  ⚠️ {errors} Fehler beim Laden")

        print(f"✅ {len(details)} Detail-Einträge geladen\n")
        return details

    def _get_single_detail(self, epd_id: int) -> Optional[Dict[str, Any]]:
        """
        Lädt Detail-Daten für eine einzelne EPD.

        Args:
            epd_id: EPD-ID

        Returns:
            Detail-Eintrag oder None
        """
        url = f"{APIConfig.BASE_URL}/api/Datasets/{epd_id}"
        headers = self.token_manager.get_headers()

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()

        # API könnte Liste oder Objekt zurückgeben
        if isinstance(data, list) and data:
            return data[0]
        elif isinstance(data, dict):
            return data

        return None

    def count_epds(self, labels: Optional[List[str]] = None) -> int:
        """
        Zählt EPDs in der Datenbank.

        Args:
            labels: Filter-Labels (OR-Logik), None = alle EPDs

        Returns:
            Anzahl der EPDs
        """
        if not labels:
            return self._count_request()

        total = 0
        for term in (l for l in labels if l and l.strip()):
            params = {"search": "true", "name": term.strip()}
            total += self._count_request(params)

        return total

    def _request(self, params: Dict[str, Any]) -> Any:
        """Führt GET-Request an /api/Datasets aus."""
        if APIConfig.GROUP_VALUE:
            params["gruppe"] = APIConfig.GROUP_VALUE

        url = f"{APIConfig.BASE_URL}/api/Datasets"
        response = requests.get(
            url,
            headers=self.token_manager.get_headers(),
            params=params,
            timeout=60
        )
        response.raise_for_status()
        return response.json()

    def _count_request(self, extra_params: Optional[Dict[str, Any]] = None) -> int:
        """Führt Count-Request aus."""
        params = {"countOnly": "true", **(extra_params or {})}
        data = self._request(params)

        # Verschiedene Response-Formate unterstützen
        if isinstance(data, int):
            return data

        if isinstance(data, dict):
            for key in ["count", "total"]:
                if key in data:
                    return int(data[key])
            if "items" in data and isinstance(data["items"], list):
                return len(data["items"])

        if isinstance(data, list):
            return len(data)

        return 0

    @staticmethod
    def _build_params(search_term: Optional[str]) -> Dict[str, Any]:
        """Erstellt Request-Parameter."""
        params = {}
        if search_term and str(search_term).strip():
            params.update({
                "search": "true",
                "name": str(search_term).strip()
            })
        return params

    @staticmethod
    def _extract_items(data: Any) -> List[Dict[str, Any]]:
        """Extrahiert Items aus verschiedenen Response-Formaten."""
        if isinstance(data, list):
            return data

        if isinstance(data, dict) and "items" in data:
            items = data["items"]
            return items if isinstance(items, list) else []

        return []

    @staticmethod
    def _normalize_epd_list(row: Dict[str, Any]) -> Dict[str, Any]:
        """Normalisiert EPD-Listen-Felder (nur Basis-Info)."""
        return {
            "id": row.get("id"),
            "name": row.get("name") or "",
            "klassifizierung": row.get("klassifizierung") or "",
            "referenzjahr": row.get("referenzjahr") or "",
            "gueltigkeit": row.get("gueltigkeit") or "",
        }

    @staticmethod
    def _normalize_epd_detail(row: Dict[str, Any]) -> Dict[str, Any]:
        """Normalisiert EPD-Detail-Felder (vollständige Info)."""
        return {
            "id": row.get("id"),
            "name": row.get("name") or "",
            "klassifizierung": row.get("klassifizierung") or "",
            "referenzjahr": row.get("referenzjahr") or "",
            "gueltigkeit": row.get("gueltigkeit") or "",
            # Detail-Felder (die wichtigen für Matching!)
            "technischeBeschreibung": row.get("technischeBeschreibung") or "",
            "anmerkungen": row.get("anmerkungen") or "",
            "anwendungsgebiet": row.get("anwendungsgebiet") or "",
            "anwendungshinweis": row.get("anwendungshinweis") or "",
            "gliederungsnummer": row.get("gliederungsnummer") or "",
            "bauDatRef": row.get("bauDatRef") or "",
        }