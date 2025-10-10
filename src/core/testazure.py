# azure_matcher.py

import os
import json
import sqlite3
from typing import List, Dict, Any
from pathlib import Path
from openai import AzureOpenAI
import openai
from dotenv import load_dotenv

load_dotenv()


class AzureEPDMatcher:
    """
    EPD Matcher mit Azure OpenAI gpt-4o-mini.
    Single-Request-Matching gegen gefilterte EPDs.
    """

    def __init__(self):
        """Initialisiert Matcher mit Azure OpenAI"""

        print("\n" + "=" * 70)
        print("AZURE EPD MATCHER INITIALISIERUNG")
        print("=" * 70)

        # Azure Config
        self.endpoint = os.getenv("ENDPOINT_URL")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.deployment = os.getenv("DEPLOYMENT_NAME", "gpt-4o-mini")

        print(f"✓ Endpoint: {self.endpoint}")
        print(f"✓ Deployment: {self.deployment}")

        # DB Config
        self.db_path = Path(os.getenv("EPD_DATABASE_PATH"))
        columns_str = os.getenv("EPD_MATCHING_COLUMNS", "name,general_comment_de,tech_desc_de")
        self.matching_columns = [col.strip() for col in columns_str.split(",")]

        # Filter Config
        filter_labels_str = os.getenv("EPD_FILTER_LABELS", "")
        self.filter_labels = [label.strip() for label in filter_labels_str.split(",") if label.strip()]

        print(f"✓ Datenbank: {self.db_path}")
        print(f"✓ Matching-Spalten: {', '.join(self.matching_columns)}")
        if self.filter_labels:
            print(f"✓ Filter (application_labels): {', '.join(self.filter_labels)}")

        # Validierung
        if not self.api_key:
            raise ValueError("❌ AZURE_OPENAI_API_KEY fehlt in .env")
        if not self.db_path.exists():
            raise FileNotFoundError(f"❌ Datenbank nicht gefunden: {self.db_path}")

        # Azure Client
        print(f"\nErstelle Azure Client...")
        self.client = AzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version="2024-08-01-preview",
            timeout=240.0,  # 4 Minuten für große Requests
            max_retries=3
        )
        print("✓ Azure Client erstellt")

        # Info
        total_epds = self._count_epds()
        filtered_epds = self._count_filtered_epds()
        print(f"✓ Datenbank: {total_epds} EPDs total")
        if self.filter_labels:
            print(f"✓ Nach Filter: {filtered_epds} EPDs")
        print("=" * 70 + "\n")

    def match_material(
            self,
            material_name: str,
            context: Dict[str, Any] = None,
            max_results: int = 10
    ) -> List[str]:
        """
        Matched Material gegen ALLE gefilterten EPDs in einem einzigen Request.

        Args:
            material_name: Name des Baumaterials
            context: Zusätzlicher Kontext (Schichtname, Volumen, etc.)
            max_results: Maximale Anzahl von Ergebnissen

        Returns:
            Liste von UUIDs der besten Matches
        """
        print(f"\n{'=' * 70}")
        print(f"MATCHING: {material_name}")
        print(f"{'=' * 70}")

        # [1] Lade ALLE gefilterten EPDs
        print(f"[1/3] Lade gefilterte EPDs aus Datenbank...")
        all_epds = self._load_filtered_epds()

        if not all_epds:
            print(f"❌ Keine EPDs gefunden!")
            return []

        print(f"✓ {len(all_epds)} EPDs geladen")

        # [2] Erstelle einen großen Prompt mit ALLEN EPDs
        print(f"\n[2/3] Erstelle Prompt und sende an Azure...")
        prompt = self._build_prompt(material_name, all_epds, context, max_results)
        print(f"  Prompt-Länge: {len(prompt)} Zeichen (~{len(prompt) // 4} Tokens)")

        # [3] Ein einziger API-Call
        response = self._call_azure(prompt)
        print(f"✓ Response erhalten ({len(response)} Zeichen)")

        # [4] Parse Matches
        print(f"\n[3/3] Parse Matches...")
        matches = self._extract_matches(response)

        if matches:
            print(f"✓ {len(matches)} Matches gefunden:")
            for i, match in enumerate(matches[:5], 1):  # Zeige Top-5
                uuid = match.get('uuid', 'N/A')
                reason = match.get('begruendung', 'N/A')
                print(f"  {i}. {uuid[:36]} - {reason[:50]}...")
        else:
            print(f"⚠ Keine Matches gefunden")

        # Top-N UUIDs extrahieren
        top_uuids = [m["uuid"] for m in matches[:max_results]]
        print(f"\n✓ {len(top_uuids)} UUIDs werden zurückgegeben")
        print(f"{'=' * 70}\n")

        return top_uuids

    def _load_filtered_epds(self) -> List[Dict[str, Any]]:
        """
        Lädt EPDs wo application_labels das gesuchte Label ENTHÄLT.
        Funktioniert auch wenn mehrere Labels vorhanden sind.
        """
        columns = ["uuid"] + self.matching_columns
        columns_str = ", ".join(columns)

        if self.filter_labels:
            # WHERE-Klausel mit LIKE für jeden Label
            # Findet "Strassenbau" auch in "Hochbau, Strassenbau, Tiefbau"
            where_clauses = []
            params = []

            for label in self.filter_labels:
                where_clauses.append("application_labels LIKE ?")
                params.append(f"%{label}%")  # % für Wildcard-Suche

            where_str = " OR ".join(where_clauses)
            query = f"SELECT {columns_str} FROM epds WHERE {where_str}"
            params = tuple(params)
        else:
            # Kein Filter - alle EPDs
            query = f"SELECT {columns_str} FROM epds"
            params = ()

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [{col: row[col] for col in row.keys()} for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"❌ DB-Fehler: {e}")
            return []

    def _count_epds(self) -> int:
        """Zählt alle EPDs"""
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM epds").fetchone()[0]

    def _count_filtered_epds(self) -> int:
        """Zählt EPDs die den Filter-Label enthalten"""
        if not self.filter_labels:
            return self._count_epds()

        where_clauses = []
        params = []

        for label in self.filter_labels:
            where_clauses.append("application_labels LIKE ?")
            params.append(f"%{label}%")

        where_str = " OR ".join(where_clauses)
        query = f"SELECT COUNT(*) FROM epds WHERE {where_str}"

        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(query, tuple(params)).fetchone()[0]

    def _build_prompt(
            self,
            material: str,
            epds: List[Dict],
            context: Dict,
            max_results: int
    ) -> str:
        """Erstellt Prompt mit ALLEN EPDs"""

        prompt = f"""Baumaterial-Matching für Straßenbau

Zu matchen: "{material}"
"""

        if context:
            prompt += "\nKontext:\n"
            if context.get("NAME"):
                prompt += f"- Schicht: {context['NAME']}\n"
            if context.get("Volumen"):
                prompt += f"- Volumen: {context['Volumen']} m³\n"
            if context.get("GUID"):
                prompt += f"- IFC GUIDs: {len(context['GUID'])} Elemente\n"

        prompt += f"\n{'=' * 70}\n"
        prompt += f"VERFÜGBARE EPD-EINTRÄGE ({len(epds)})\n"
        prompt += f"{'=' * 70}\n"

        for i, epd in enumerate(epds, 1):
            prompt += f"\n{i}. UUID: {epd['uuid']}\n"

            name = str(epd.get('name', 'N/A'))[:120]
            prompt += f"   Name: {name}\n"

            if 'general_comment_de' in epd and epd['general_comment_de']:
                comment = str(epd['general_comment_de'])[:100]
                prompt += f"   Info: {comment}\n"

        prompt += f"\n{'=' * 70}\n"
        prompt += f"AUFGABE\n"
        prompt += f"{'=' * 70}\n"
        prompt += f"""
Finde die {max_results} BESTEN EPD-Matches für das Material "{material}".

Bewertungskriterien:
"You are an assistant helping to match user requests to EPDs. "
            "Respond ONLY with a valid JSON object. The object must contain "
            "a key 'matches' which is a list of up to 3 match objects, each "
            "with 'uuid', and 'begruendung'."

Antwort-Format (NUR JSON):
{{
  "matches": [
    {{"uuid": "VOLLSTÄNDIGE-UUID", "begruendung": "Warum passt dieser EPD?"}},
    {{"uuid": "VOLLSTÄNDIGE-UUID", "begruendung": "..."}},
    ...
  ]
}}

KRITISCH: 
- Verwende die EXAKTE vollständige UUID aus der Liste oben
- Sortiere nach Relevanz (beste zuerst)
- Beispiel RICHTIG: "35d1b480d-243f-4ff2-aa16-428e1a93f5d8"
- Beispiel FALSCH: "35" oder "35d1b480d"
"""
        return prompt

    def _call_azure(self, prompt: str) -> str:
        """Azure OpenAI API Call"""

        try:
            is_reasoning_model = "gpt-5" in self.deployment.lower() or "o1" in self.deployment.lower()

            params = {
                "model": self.deployment,
                "messages": [
                    {
                        "role": "system",
                        "content": "Du bist Experte für Baumaterial-EPD-Matching im Straßenbau. Antworte NUR mit JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "timeout": 180.0
            }

            if is_reasoning_model:
                params["max_completion_tokens"] = 16000
            else:
                params["max_tokens"] = 4000  # Mehr Tokens für lange Listen
                params["temperature"] = 0.2  # Niedriger für präzisere Matches

            completion = self.client.chat.completions.create(**params)

            response_text = completion.choices[0].message.content

            if not response_text:
                print(f"⚠ Leere Response!")
                return json.dumps({"matches": []})

            return response_text.strip()

        except Exception as e:
            print(f"❌ Fehler: {type(e).__name__}: {e}")
            return json.dumps({"matches": []})

    def _extract_matches(self, response: str) -> List[Dict[str, str]]:
        """Extrahiert und validiert Matches"""
        import re

        if not response:
            return []

        # Entferne Code-Blöcke
        json_match = re.search(r'``````', response, re.DOTALL)
        if json_match:
            response = json_match.group(1)

        try:
            data = json.loads(response)

            if "matches" in data and isinstance(data["matches"], list):
                # UUID-Validierung
                valid_matches = []
                for match in data["matches"]:
                    uuid = match.get("uuid", "")
                    if len(uuid) >= 36:  # Standard UUID-Länge
                        valid_matches.append(match)
                    else:
                        print(f"  ⚠ Ungültige UUID ignoriert: '{uuid}'")

                return valid_matches

        except json.JSONDecodeError as e:
            print(f"  ⚠ JSON Parse Error: {e}")
            # Fallback
            json_match = re.search(r'\{[\s\S]*"matches"[\s\S]*\}', response)
            if json_match:
                try:
                    data = json.loads(json_match.group(0))
                    return data.get("matches", [])
                except:
                    pass

        return []


# Singleton
_matcher = None


def get_matcher() -> AzureEPDMatcher:
    """Holt Matcher-Instanz"""
    global _matcher
    if _matcher is None:
        _matcher = AzureEPDMatcher()
    return _matcher
