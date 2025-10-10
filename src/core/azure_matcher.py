# azure_matcher.py

import os
import re
import json
import sqlite3
from typing import List, Dict, Any
from pathlib import Path
from openai import AzureOpenAI
import openai
from dotenv import load_dotenv

# Lade Umgebungsvariablen
load_dotenv()


class AzureEPDMatcher:
    """
    Einfacher EPD Matcher: Material-String rein → UUID-Liste raus.
    """

    def __init__(self):
        """Initialisiert Matcher mit Werten aus .env"""

        # Azure OpenAI Config
        self.endpoint = os.getenv("ENDPOINT_URL")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.deployment = os.getenv("DEPLOYMENT_NAME", "gpt-5-nano")

        # EPD Datenbank Config
        self.db_path = Path(os.getenv("EPD_DATABASE_PATH"))
        columns_str = os.getenv("EPD_MATCHING_COLUMNS", "name,general_comment_de,tech_desc_de")
        self.matching_columns = [col.strip() for col in columns_str.split(",")]

        # Validierung
        if not self.api_key:
            raise ValueError("AZURE_OPENAI_API_KEY fehlt in .env")
        if not self.db_path.exists():
            raise FileNotFoundError(f"Datenbank nicht gefunden: {self.db_path}")

        # Azure Client
        self.client = AzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version="2025-01-01-preview",
            timeout=60.0
        )

        # Info
        epd_count = self._count_epds()
        print(f"Azure EPD Matcher bereit:")
        print(f"  Datenbank: {epd_count} EPDs")
        print(f"  Matching-Felder: {', '.join(self.matching_columns)}\n")

    def match_material(
            self,
            material_name: str,
            context: Dict[str, Any] = None,
            max_results: int = 10
    ) -> List[str]:
        """
        DER KERN: Material-String → UUID-Liste

        Args:
            material_name: Das zu matchende Material
            context: Optional - zusätzliche Infos (Schichtname, Volumen)
            max_results: Max. Anzahl UUIDs

        Returns:
            Liste von UUIDs (oder leer bei Fehler)
        """
        # 1. Lade relevante EPDs aus DB
        epds = self._load_epds_from_db(limit=50)

        if not epds:
            print(f"  ⚠ Keine EPDs in Datenbank gefunden!")
            return []

        # 2. Erstelle Prompt
        prompt = self._build_prompt(material_name, epds, context, max_results)

        # 3. Frage Azure OpenAI
        response = self._call_azure(prompt)

        # 4. Extrahiere UUIDs aus JSON-Response
        uuids = self._extract_uuids(response)

        return uuids[:max_results]

    def _load_epds_from_db(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Lädt EPDs aus SQLite mit konfigurierten Spalten"""
        columns = ["uuid"] + self.matching_columns
        columns_str = ", ".join(columns)

        query = f"SELECT {columns_str} FROM epds LIMIT ?"

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, (limit,))

                return [{col: row[col] for col in row.keys()} for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"  DB-Fehler: {e}")
            return []

    def _build_prompt(
            self,
            material: str,
            epds: List[Dict],
            context: Dict,
            max_results: int
    ) -> str:
        """Baut den Prompt für Azure"""

        prompt = f"""Material zum Matchen: {material}

"""

        if context:
            if context.get("NAME"):
                prompt += f"Kontext - Schicht: {context['NAME']}\n"
            if context.get("Volumen"):
                prompt += f"Kontext - Volumen: {context['Volumen']} m³\n"
            prompt += "\n"

        prompt += f"Verfügbare EPD-Einträge ({len(epds)}):\n\n"

        for i, epd in enumerate(epds, 1):
            prompt += f"{i}. UUID: {epd['uuid']}\n"
            for col in self.matching_columns:
                val = epd.get(col)
                if val:
                    val_str = str(val)[:150]  # Kürzen
                    prompt += f"   {col}: {val_str}\n"
            prompt += "\n"

        prompt += f"""Finde die {max_results} besten Matches.

Antworte NUR mit JSON:
{{
  "matches": [
    {{"uuid": "...", "begruendung": "..."}},
    ...
  ]
}}
"""
        return prompt

    def _call_azure(self, prompt: str) -> str:
        """Schickt Prompt an Azure OpenAI"""
        try:
            completion = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {
                        "role": "developer",
                        "content": [{"type": "text", "text":
                            "Du bist EPD-Matching-Experte. Antworte NUR mit JSON."}]
                    },
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": prompt}]
                    }
                ],
                max_completion_tokens=2000
            )
            return completion.choices[0].message.content.strip()

        except Exception as e:
            print(f"  Azure-Fehler: {e}")
            return json.dumps({"error": str(e)})

    def _extract_uuids(self, response: str) -> List[str]:
        """Extrahiert UUIDs aus Azure-Response"""

        # JSON aus Response holen (auch wenn in Code-Block)
        json_match = re.search(r'``````', response, re.DOTALL)
        if json_match:
            response = json_match.group(1)

        try:
            data = json.loads(response)

            # Standard: {"matches": [...]}
            if "matches" in data and isinstance(data["matches"], list):
                return [m["uuid"] for m in data["matches"] if "uuid" in m]

            # Fehler-Response
            if "error" in data:
                print(f"  Azure-Error: {data['error']}")
                return []

        except json.JSONDecodeError as e:
            print(f"  JSON-Parse-Fehler: {e}")
            print(f"  Response war: {response[:200]}")

        return []

    def _count_epds(self) -> int:
        """Zählt EPDs in DB"""
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM epds").fetchone()[0]


# Singleton
_matcher = None


def get_matcher() -> AzureEPDMatcher:
    """Holt oder erstellt Matcher-Instanz"""
    global _matcher
    if _matcher is None:
        _matcher = AzureEPDMatcher()
    return _matcher
