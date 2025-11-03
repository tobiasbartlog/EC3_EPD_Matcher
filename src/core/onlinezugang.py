# onlinezugang_CC.py

import os, json, time, requests
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()  # .env Variablen laden

# -------------------- ENV / Konfiguration --------------------
# Azure
AZURE_ENDPOINT= os.getenv("ENDPOINT_URL", "").strip()
AZURE_KEY= os.getenv("AZURE_OPENAI_API_KEY", "").strip()
AZURE_DEPLOYMENT= os.getenv("DEPLOYMENT_NAME", "gpt-4o-mini").strip()

# Online-API (Swagger /api/Datasets)
API_BASE= os.getenv("ONLINE_EPD_API_BASE_URL", "").strip().rstrip("/")
API_USERNAME= os.getenv("ONLINE_EPD_API_USERNAME", "").strip()
API_PASSWORD= (os.getenv("ONLINE_EPD_API_PASSWORD") or os.getenv("ONLINE_EPD_API_PASSWORT") or "").strip()

# Prompt-Optionen
EPD_MATCHING_COLUMNS= [c.strip() for c in os.getenv("EPD_MATCHING_COLUMNS", "name,general_comment_de,tech_desc_de").split(",")]
EPD_FILTER_LABELS= [s.strip() for s in os.getenv("EPD_FILTER_LABELS", "").split(",") if s.strip()]
PROMPT_MAX_EPD= int(os.getenv("PROMPT_MAX_EPD", "400"))
USE_FILTER_LABELS= os.getenv("EPD_USE_FILTER_LABELS", "false").lower() == "true"  # Standard: keine Vorfilterung
EPD_GROUP_VALUE= os.getenv("ONLINE_EPD_GROUP_VALUE", "").strip()

# -------------------- Token -> Auth --------------------
class TokenManager:
    """Holt & cached ein JWT; erneuert es automatisch bei Ablauf."""
    def __init__(self):
        if not (API_BASE and API_USERNAME and API_PASSWORD):
            raise ValueError("❌ ONLINE_EPD_API_* (.env) unvollständig (BASE_URL/USERNAME/PASSWORD)")
        self._token: Optional[str] = None
        self._exp_ts: float = 0.0

    def _fetch(self) -> Any:
        url = f"{API_BASE}/api/Auth/getToken"
        body = {"username": API_USERNAME, "passwort": API_PASSWORD}
        r = requests.post(url, json=body, timeout=20)
        r.raise_for_status()
        try:
            return r.json()
        except ValueError:
            return r.text.strip()

    def token(self) -> str:
        now = time.time()
        if self._token and now < self._exp_ts:
            return self._token
        payload = self._fetch()
        if isinstance(payload, dict):
            tok = payload.get("token") or payload.get("access_token") or payload.get("jwt")
            ttl = int(payload.get("expires_in", 3600))
        else:
            tok, ttl = str(payload), 3600
        if not tok:
            raise RuntimeError("❌ Kein Token in Auth-Antwort gefunden.")
        # Sicherheitsmarge: verhindere „Ablauf genau beim Request“
        self._token = tok
        self._exp_ts = now + max(1, ttl - min(60, ttl // 10))
        return self._token

    def headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token()}", "Accept": "application/json"}

# -------------------- API-Client (/api/Datasets) --------------------
class EPDAPIClient:
    """Swagger-konformer, schlanker Client für EPD-Liste/Count."""
    def __init__(self, tm: TokenManager):
        self.tm = tm
        self.base = API_BASE

    def _get(self, params: Dict[str, Any]) -> requests.Response:
        # Zentrale GET-Funktion: hängt Auth-Header an und hebt Fehler an.

        if EPD_GROUP_VALUE:
            params = {**params, "gruppe": EPD_GROUP_VALUE}
        url = f"{self.base}/api/Datasets"
        r = requests.get(url, headers=self.tm.headers(), params=params, timeout=60)
        r.raise_for_status()
        return r

    @staticmethod
    def _items(data: Any) -> List[Dict[str, Any]]:
        # API kann Liste oder Objekt mit 'items' senden → beides unterstützen
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
            return data["items"]
        return []

    def list_epds(self, labels: Optional[List[str]], fields: List[str]) -> List[Dict[str, Any]]:
        """Lädt EPDs. Wenn labels=None/[], lädt es alle; sonst OR-Logik über name-Suche."""
        out: List[Dict[str, Any]] = []
        seen: set = set()
        terms = labels or [None]
        for term in terms:
            params: Dict[str, Any] = {}
            if term and str(term).strip():
                params.update({"search": "true", "name": str(term).strip()})
            data = self._get(params).json()
            for row in self._items(data):
                uid = row.get("uuid") or row.get("id")  # API liefert oft 'id' statt 'uuid'
                if not uid or uid in seen:
                    continue
                seen.add(uid)
                out.append(self._project(row))
        return out

    def count_epds(self, labels: Optional[List[str]] = None) -> int:
        """Zählt Datensätze via countOnly=true (ggf. mit name-Suche)."""
        def ask(extra: Optional[Dict[str, Any]] = None) -> int:
            p = {"countOnly": "true", **(extra or {})}
            data = self._get(p).json()
            if isinstance(data, int): return data
            if isinstance(data, dict):
                if "count" in data: return int(data["count"])
                if "total" in data: return int(data["total"])
                if "items" in data and isinstance(data["items"], list): return len(data["items"])
            if isinstance(data, list): return len(data)
            return 0

        if not labels:
            return ask()
        total = 0
        for term in (l for l in labels if l and l.strip()):
            total += ask({"search": "true", "name": term.strip()})
        return total

    @staticmethod
    def _project(row: Dict[str, Any]) -> Dict[str, Any]:
        # Map auf die Felder, die der Prompt sicher nutzt (robust gegen fehlende Felder)
        return {
            "uuid": row.get("uuid") or row.get("id"),
            "id": row.get("id"),
            "name": row.get("name") or "",
            "general_comment_de": row.get("general_comment_de") or row.get("beschreibung") or "",
            "tech_desc_de": row.get("tech_desc_de") or row.get("technical_description") or "",
            "klassifizierung": row.get("klassifizierung") or "",
            "referenzjahr": row.get("referenzjahr") or "",
            "gueltigkeit": row.get("gueltigkeit") or "",
        }

# -------------------- AzureEPDMatcher --------------------
class AzureEPDMatcher:
    """
    Behält die Original-Struktur:
    - __init__: Azure-Client + API-Client initialisieren
    - match_material: EPDs laden → Prompt → Azure → Matches parsen (Confidence %)
    """
    _last_results: List[Dict[str, Any]] = []  # TEST speichert die letzten Matches (id, confidence, begruendung, name)
    def __init__(self):
        print("\n" + "=" * 70)
        print("AZURE EPD MATCHER INITIALISIERUNG")
        print("=" * 70)

        if not AZURE_KEY:
            raise ValueError("❌ AZURE_OPENAI_API_KEY fehlt in .env")
        print(f"✓ Endpoint: {AZURE_ENDPOINT}")
        print(f"✓ Deployment: {AZURE_DEPLOYMENT}")

        # Azure OpenAI
        print("\nErstelle Azure Client...")
        self.client = AzureOpenAI(
            azure_endpoint=AZURE_ENDPOINT,
            api_key=AZURE_KEY,
            api_version="2024-08-01-preview",
            timeout=240.0,
            max_retries=3
        )
        print("✓ Azure Client erstellt")

        # Online-API
        self.matching_columns = EPD_MATCHING_COLUMNS
        self.filter_labels    = EPD_FILTER_LABELS
        self._tm  = TokenManager()
        self._api = EPDAPIClient(self._tm)

        # Info zur Datenbasis (nur zur Anzeige)
        total = self._count_epds()
        print(f"✓ Online-DB: ~{total} EPDs total")
        print("=" * 70 + "\n")

    def match_material(self, material_name: str,
                       context: Optional[Dict[str, Any]] = None,
                       max_results: int = 10) -> List[str]:
        print(f"\n{'='*70}\nMATCHING: {material_name}\n{'='*70}")



        # 1) Kandidaten laden (Standard: ohne Vorfilter; per .env aktivierbar)
        print("[1/3] Lade EPDs aus Online-API...")
        labels = (self.filter_labels if USE_FILTER_LABELS else [])
        epds = self._api.list_epds(labels=labels, fields=self.matching_columns)
        if not epds:
            print("❌ Keine EPDs gefunden!")
            return []
        if len(epds) > PROMPT_MAX_EPD:
            print(f"⚠ Kürze EPD-Liste im Prompt auf {PROMPT_MAX_EPD}")
            epds = epds[:PROMPT_MAX_EPD]
        print(f"✓ {len(epds)} EPDs im Prompt")

        # 2) Prompt bauen + senden
        print("\n[2/3] Erstelle Prompt und sende an Azure...")
        prompt = self._build_prompt(material_name, epds, context, max_results)
        print(f"  Prompt-Länge: {len(prompt)} Zeichen (~{len(prompt)//4} Tokens)")
        response = self._call_azure(prompt)
        print(f"✓ Response erhalten ({len(response)} Zeichen)")

        # 3) Matches parsen
        print("\n[3/3] Parse Matches...")
        matches = self._extract_matches(response)

        # Ergebnisse zusammenfassen & für main() zwischenspeichern
        # Map (id) → Name aus Kandidaten, damit wir Name im Output mitschreiben können
        name_map = {str(e.get("uuid") or e.get("id")): e.get("name", "") for e in epds}

        enriched: List[Dict[str, Any]] = []
        for m in matches:
            uid = str(m.get("uuid", "")).strip()
            if not uid:
                continue
            enriched.append({
                "uuid": uid,
                "name": name_map.get(uid, ""),
                "confidence": m.get("confidence", None),
                "begruendung": m.get("begruendung", "")
            })

        # Für spätere Abfrage in main.py zwischenspeichern
        self._last_results = enriched
        #TEST ENDE

        if matches:
            print(f"✓ {len(matches)} Matches gefunden:")
            for i, m in enumerate(matches[:5], 1):
                ident = m.get("uuid", "N/A")
                conf = m.get("confidence")
                reason = (m.get("begruendung") or "").replace("\n", " ")[:80]
                tag = f" ({conf}%)" if conf is not None else ""
                print(f"  {i}. {ident[:36]}{tag} – {reason}...")
        else:
            print("⚠ Keine Matches gefunden")

        top = [m["uuid"] for m in matches[:max_results] if "uuid" in m]
        print(f"\n✓ {len(top)} IDs werden zurückgegeben\n{'='*70}\n")
        return top

    # ---------- Hilfen ----------
    def _count_epds(self) -> int:
        return self._api.count_epds(labels=None)

    # Prompt: erlaubt uuid ODER id; zwingt confidence (%)
    def _build_prompt(self, material: str, epds: List[Dict[str, Any]],
                      context: Optional[Dict[str, Any]], max_results: int) -> str:
        # Prüfe, ob es echte UUIDs gibt – sonst IDs verwenden (viele Backends liefern nur 'id')
        has_uuid = any(e.get("uuid") and len(str(e["uuid"])) >= 36 for e in epds)
        ident_key = "uuid" if has_uuid else "id"

        p = [f"Baumaterial-Matching\n\nZu matchen: \"{material}\""]
        if context:
            ctx = []
            if context.get("NAME"):    ctx.append(f"- Schicht: {context['NAME']}")
            if context.get("Volumen"): ctx.append(f"- Volumen: {context['Volumen']} m³")
            if context.get("GUID"):    ctx.append(f"- IFC GUIDs: {len(context['GUID'])} Elemente")
            if ctx:
                p += ["\nKontext:", *ctx]

        p += [f"\n{'='*70}\nVERFÜGBARE EPD-EINTRÄGE ({len(epds)})\n{'='*70}"]
        for i, e in enumerate(epds, 1):
            ident = e.get(ident_key)
            name  = str(e.get("name", "N/A"))[:160]
            info  = str(e.get("general_comment_de") or "")[:100]
            p += [f"\n{i}. {ident_key.upper()}: {ident}", f"   Name: {name}"]
            if info:
                p += [f"   Info: {info}"]

        p += [f"""
{'='*70}
AUFGABE
{'='*70}

Finde die {max_results} BESTEN EPD-Matches für das Material "{material}".

Bewertungskriterien:
- Verwende nur die oben gelisteten Einträge.
- Gib eine kurze Begründung.
- Pflicht: Liefere zusätzlich einen Confidence-Score in Prozent (0–100).

Confidence-Kalibrierung (Richtwert):
- 85–100: exakte Nennung (z. B. "AC 11 D S" oder "Asphaltbeton EN 13108-1") + passende Spezifikation.
- 60–84: starke semantische Nähe ("Asphaltmischgut", "AC", korrekte Klasse) ohne exakten Typ.
- 30–59: allgemeiner Asphalt-Bezug ohne passende Typologie.
- <30: nicht listen.

Antwort-Format (NUR JSON, ohne Fließtext, ohne zusätzliche Schlüssel):
{{
  "matches": [
    {{
      "{ident_key}": "WERT",
      "begruendung": "kurze Begründung mit wörtlichen Treffern aus Name/Info",
      "confidence": 0-100
    }}
  ]
}}

KRITISCH:
- Verwende die EXAKTE {ident_key}-Kennung aus der Liste oben.
- Sortiere nach Relevanz (beste zuerst).
- Gib höchstens {max_results} Einträge zurück.
"""]
        return "\n".join(p)

    # Parser: akzeptiert uuid ODER id; confidence optional/normalisiert
    def _extract_matches(self, response: str) -> List[Dict[str, Any]]:
        import re
        if not response:
            return []
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
        if fence:
            response = fence.group(1)
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\"matches\"[\s\S]*\}", response)
            data = json.loads(m.group(0)) if m else None
        if not isinstance(data, dict):
            return []

        out: List[Dict[str, Any]] = []
        for it in data.get("matches", []):
            if not isinstance(it, dict):
                continue
            ident = it.get("uuid") or it.get("id")
            if ident is None:
                continue
            ident = str(ident).strip()  # numerisch oder UUID → String
            conf = it.get("confidence")
            try:
                conf = None if conf is None else max(0, min(100, int(conf)))
            except Exception:
                conf = None
            out.append({"uuid": ident, "begruendung": it.get("begruendung", ""), "confidence": conf})
        return out

    def _call_azure(self, prompt: str) -> str:
        """Chat Completions; niedrige Temperatur für deterministischere Auswahl."""
        try:
            is_reasoning = "gpt-5" in AZURE_DEPLOYMENT.lower() or "o1" in AZURE_DEPLOYMENT.lower()
            params: Dict[str, Any] = {
                "model": AZURE_DEPLOYMENT,
                "messages": [
                    {"role": "system", "content": "Du bist Experte für Baumaterial-EPD-Matching im Straßenbau. Antworte NUR mit JSON."},
                    {"role": "user",   "content": prompt},
                ],
                "timeout": 180.0
            }
            if is_reasoning:
                params["max_completion_tokens"] = 16000
            else:
                params["max_tokens"] = 4000
                params["temperature"] = 0.2
            resp = AzureOpenAI(
                azure_endpoint=AZURE_ENDPOINT,
                api_key=AZURE_KEY,
                api_version="2024-08-01-preview",
                timeout=240.0,
                max_retries=3
            ).chat.completions.create(**params)
            txt = resp.choices[0].message.content
            return txt.strip() if txt else json.dumps({"matches": []})
        except Exception as e:
            print(f"❌ Fehler: {type(e).__name__}: {e}")
            return json.dumps({"matches": []})


    def get_last_results(self) -> List[Dict[str, Any]]:
        """Liefert die letzten, angereicherten Matches (id, name, confidence)."""
        return list(self._last_results)


# -------------------- Singleton --------------------
_matcher: Optional[AzureEPDMatcher] = None

def get_matcher() -> AzureEPDMatcher:
    """Gibt eine globale, einmalig initialisierte Matcher-Instanz zurück (wie im Original)."""
    global _matcher
    if _matcher is None:
        _matcher = AzureEPDMatcher()
    return _matcher
