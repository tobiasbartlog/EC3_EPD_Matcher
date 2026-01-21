"""Azure OpenAI basierter EPD-Matcher mit Glossar-Integration.

Nutzt die Stage-basierte Konfiguration aus settings.py.
"""
import json
import re
from typing import Dict, Any, List, Optional
from openai import AzureOpenAI

from config.settings import (
    AzureConfig,
    MatchingConfig,
    FilterConfig,
    GlossarConfig,
    ValidationConfig
)
from api.auth import TokenManager
from api.epd_client import EPDAPIClient
from matching.prompt_builder import PromptBuilder
from utils.cost_tracker import get_tracker, record_usage

# Glossar-Import (optional, nur wenn aktiviert)
if GlossarConfig.USE_GLOSSAR:
    from matching.epd_filter import EPDFilter, ConfidenceValidator
    from utils.asphalt_glossar import parse_material_input


class AzureEPDMatcher:
    """EPD-Matcher mit Azure OpenAI und Online-API (mit EPD-Cache und Glossar)."""

    def __init__(self):
        self._validate_config()
        self._init_clients()
        self._last_results: List[Dict[str, Any]] = []
        self._batch_detailed_results: List[List[Dict[str, Any]]] = []
        self._epd_cache: Optional[List[Dict[str, Any]]] = None

        # Glossar-Filter initialisieren (Stage 3)
        self._epd_filter = None
        if GlossarConfig.USE_GLOSSAR and FilterConfig.USE_GLOSSAR_FILTER:
            self._epd_filter = EPDFilter(
                max_epds_per_material=FilterConfig.FILTER_MAX_PER_MATERIAL,
                debug=GlossarConfig.DEBUG
            )

        self._print_initialization_info()

        # EPDs einmalig laden
        print("🔄 Lade EPD-Datenbank einmalig...")
        self._load_and_cache_epds()

    def match_materials_batch(
        self,
        materials: List[Dict[str, Any]],
        max_results: int = None
    ) -> List[Dict[str, Any]]:
        """
        Findet passende EPDs für MEHRERE Materialien auf einmal (Batch).

        Args:
            materials: Liste von Material-Dicts mit keys: material_name, context
            max_results: Maximale Anzahl Ergebnisse pro Material

        Returns:
            Liste von Ergebnis-Dicts: [{"ids": [...], "confidence": {...}}, ...]
        """
        if max_results is None:
            max_results = MatchingConfig.MAX_RESULTS

        print(f"\n{'='*70}\nBATCH-MATCHING: {len(materials)} Materialien\n{'='*70}")

        epds = self._epd_cache
        if not epds:
            print("❌ Keine EPDs im Cache verfügbar!")
            return [{"ids": [], "confidence": {}} for _ in materials]

        # ===============================================
        # STAGE 3: Glossar-basierte Vorfilterung
        # ===============================================
        if self._epd_filter:
            print("\n📊 [Stage 3] Glossar-Vorfilterung aktiv...")
            filter_result = self._epd_filter.filter_for_materials(epds, materials)
            filtered_epds = filter_result["combined_epds"]

            print(f"   {len(epds)} → {len(filtered_epds)} EPDs ({filter_result['stats']['reduction_percent']}% Reduktion)")

            if GlossarConfig.DEBUG:
                print(EPDFilter.get_filter_summary(filter_result['stats']))
        else:
            filtered_epds = epds
            print(f"✅ [Stage 3] Übersprungen - Verwende {len(filtered_epds)} EPDs")

        # ===============================================
        # STAGE 4: Azure LLM Anfrage
        # ===============================================
        print(f"\n🤖 [Stage 4] Sende an Azure OpenAI ({AzureConfig.DEPLOYMENT})...")
        response = self._query_azure_batch(materials, filtered_epds, max_results)

        # Response parsen
        all_matches = self._parse_batch_response(response, len(materials))

        # ===============================================
        # STAGE 5: Confidence-Nachvalidierung
        # ===============================================
        if GlossarConfig.USE_GLOSSAR and ValidationConfig.USE_CONFIDENCE_VALIDATION:
            print("\n🔍 [Stage 5] Confidence-Nachvalidierung...")
            all_matches = ConfidenceValidator.validate_batch_results(
                all_matches, materials, filtered_epds
            )
        else:
            print("\n⏭️  [Stage 5] Übersprungen")

        # Ergebnisse formatieren
        results = []
        enriched_all = []

        for schicht_idx, matches in enumerate(all_matches):
            ids = [m["uuid"] for m in matches[:max_results]]
            confidence_map = {
                m["uuid"]: m["confidence"]
                for m in matches
                if m.get("confidence") is not None
            }

            enriched = self._enrich_results(matches, filtered_epds)
            enriched_all.append(enriched)
            if schicht_idx == 0:
                self._last_results = enriched

            results.append({
                "ids": ids,
                "confidence": confidence_map
            })

            mat_name = materials[schicht_idx].get("material_name", "Unbekannt")
            print(f"  Schicht {schicht_idx+1} ({mat_name}): {len(ids)} Matches")

        self._batch_detailed_results = enriched_all

        print(f"\n✅ Batch-Matching abgeschlossen\n{'='*70}\n")
        return results

    def match_material(
        self,
        material_name: str,
        context: Optional[Dict[str, Any]] = None,
        max_results: int = None
    ) -> List[str]:
        """
        Findet passende EPDs für ein Material (Einzelmodus).

        Args:
            material_name: Name des zu matchenden Materials
            context: Zusätzlicher Kontext (NAME, Volumen, GUID)
            max_results: Maximale Anzahl Ergebnisse

        Returns:
            Liste von EPD-IDs (Top-Matches)
        """
        if max_results is None:
            max_results = MatchingConfig.MAX_RESULTS

        print(f"\n{'='*70}\nMATCHING: {material_name}\n{'='*70}")

        epds = self._epd_cache
        if not epds:
            print("❌ Keine EPDs im Cache verfügbar!")
            return []

        # Stage 3: Glossar-Vorfilterung für einzelnes Material
        if self._epd_filter:
            schicht_name = context.get("NAME", "") if context else ""
            filtered_epds, parsed = self._epd_filter.filter_for_single_material(
                epds, material_name, schicht_name
            )
            print(f"📊 [Stage 3] Gefiltert: {len(epds)} → {len(filtered_epds)} EPDs")

            if GlossarConfig.DEBUG and parsed.get("ist_asphalt"):
                print(f"   Parsed: {parsed.get('typ', 'N/A')} / {parsed.get('schicht', 'N/A')}")
        else:
            filtered_epds = epds

        # Stage 4: Azure abfragen
        response = self._query_azure(material_name, filtered_epds, context, max_results)

        # Ergebnisse parsen
        matches = self._parse_response(response)

        # Stage 5: Nachvalidierung
        if GlossarConfig.USE_GLOSSAR and ValidationConfig.USE_CONFIDENCE_VALIDATION:
            schicht_name = context.get("NAME", "") if context else ""
            parsed = parse_material_input(material_name, schicht_name)

            validated_matches = []
            for match in matches:
                epd = next((e for e in filtered_epds if str(e.get("id")) == match["uuid"]), {})
                new_conf, grund = ConfidenceValidator.validate_match(
                    epd, parsed, match.get("confidence", 50)
                )
                match["confidence"] = new_conf
                if new_conf != match.get("confidence"):
                    match["begruendung"] += f" [Korrigiert: {grund}]"
                validated_matches.append(match)

            matches = sorted(validated_matches, key=lambda x: x.get("confidence", 0), reverse=True)

            # Filter by MIN_CONFIDENCE
            matches = [m for m in matches if m.get("confidence", 0) >= ValidationConfig.MIN_CONFIDENCE]

        self._last_results = self._enrich_results(matches, filtered_epds)

        self._print_results(matches)
        return [m["uuid"] for m in matches[:max_results]]

    def get_last_results(self) -> List[Dict[str, Any]]:
        """Gibt detaillierte Ergebnisse des letzten Matchings zurück."""
        return list(self._last_results)

    def get_batch_detailed_results(self) -> List[List[Dict[str, Any]]]:
        """Gibt detaillierte Ergebnisse für alle Schichten aus dem letzten Batch zurück."""
        return self._batch_detailed_results

    # -------------------- Private Methoden --------------------

    def _validate_config(self) -> None:
        """Validiert Azure-Konfiguration."""
        if not AzureConfig.API_KEY:
            raise ValueError("❌ AZURE_OPENAI_API_KEY fehlt in .env")

    def _init_clients(self) -> None:
        """Initialisiert Azure und API Clients."""
        self.azure_client = AzureOpenAI(
            azure_endpoint=AzureConfig.ENDPOINT,
            api_key=AzureConfig.API_KEY,
            api_version=AzureConfig.API_VERSION,
            timeout=AzureConfig.TIMEOUT,
            max_retries=AzureConfig.MAX_RETRIES
        )

        token_manager = TokenManager()
        self.api_client = EPDAPIClient(token_manager)

    def _print_initialization_info(self) -> None:
        """Gibt Initialisierungs-Informationen aus."""
        print("\n" + "=" * 70)
        print("AZURE EPD MATCHER - INITIALISIERUNG")
        print("=" * 70)
        print(f"✓ Endpoint: {AzureConfig.ENDPOINT}")
        print(f"✓ Deployment: {AzureConfig.DEPLOYMENT}")
        print(f"✓ Online-DB: ~{self.api_client.count_epds()} EPDs total")
        print()
        print("Stage-Konfiguration:")
        print(f"  [2] Material Parsing:    {'✓' if GlossarConfig.USE_GLOSSAR else '✗'}")
        print(f"  [3] EPD Pre-filtering:   {'✓' if FilterConfig.USE_GLOSSAR_FILTER else '✗'}")
        print(f"  [4] LLM Matching:        ✓ (immer aktiv)")
        print(f"  [5] Confidence Valid.:   {'✓' if ValidationConfig.USE_CONFIDENCE_VALIDATION else '✗'}")
        print("=" * 70 + "\n")

    def _load_and_cache_epds(self) -> None:
        """Lädt EPDs einmal und speichert sie im Cache."""
        print("[1/2] Lade EPD-Liste...")

        # Label-Filter nur wenn Glossar NICHT aktiv (Legacy-Modus)
        labels = []
        if not GlossarConfig.USE_GLOSSAR and FilterConfig.USE_FILTER_LABELS:
            labels = FilterConfig.FILTER_LABELS

        epds_list = self.api_client.list_epds(labels=labels, fields=None)

        if not epds_list:
            print("❌ Keine EPDs gefunden!")
            self._epd_cache = []
            return

        print(f"✅ {len(epds_list)} EPDs gefunden")

        # Limit anwenden
        if len(epds_list) > MatchingConfig.MAX_EPD_IN_PROMPT:
            print(f"⚠️  Begrenze auf {MatchingConfig.MAX_EPD_IN_PROMPT} EPDs")
            epds_list = epds_list[:MatchingConfig.MAX_EPD_IN_PROMPT]

        # Detail-Daten laden (Stage 4 Erweiterung)
        if MatchingConfig.USE_DETAIL_MATCHING:
            print(f"\n[2/2] Lade Detail-Daten...")
            epd_ids = [epd["id"] for epd in epds_list if epd.get("id")]

            if epd_ids:
                epds_details = self.api_client.get_epd_details(
                    epd_ids, max_workers=MatchingConfig.PARALLEL_WORKERS
                )
                if epds_details:
                    self._epd_cache = epds_details
                    print(f"✅ Cache bereit: {len(self._epd_cache)} EPDs mit Details")
                    return

        self._epd_cache = epds_list
        print(f"✅ Cache bereit: {len(self._epd_cache)} EPDs (nur Namen)\n")

    def _query_azure_batch(
        self,
        materials: List[Dict[str, Any]],
        epds: List[Dict[str, Any]],
        max_results: int
    ) -> str:
        """Sendet Batch-Prompt an Azure OpenAI."""
        print("\n[Stage 4a] Erstelle Batch-Prompt...")

        prompt = PromptBuilder.build_batch_matching_prompt(
            materials=materials,
            epds=epds,
            max_results=max_results
        )

        print(f"  Prompt: {len(prompt)} Zeichen (~{len(prompt)//4} Tokens)")
        print(f"  Enthält: {len(materials)} Schichten + {len(epds)} EPDs")

        response = self._call_azure_api(prompt)
        print(f"✅ [Stage 4b] Response: {len(response)} Zeichen")

        return response

    def _query_azure(
        self,
        material_name: str,
        epds: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]],
        max_results: int
    ) -> str:
        """Sendet Prompt an Azure OpenAI."""
        print("\n[Stage 4a] Erstelle Prompt...")

        prompt = PromptBuilder.build_matching_prompt(
            material_name=material_name,
            epds=epds,
            context=context,
            max_results=max_results
        )

        print(f"  Prompt: {len(prompt)} Zeichen (~{len(prompt)//4} Tokens)")

        response = self._call_azure_api(prompt)
        print(f"✅ [Stage 4b] Response: {len(response)} Zeichen")

        return response

    def _call_azure_api(self, prompt: str) -> str:
        """Führt Azure OpenAI API-Call durch."""
        try:
            is_reasoning = any(
                x in AzureConfig.DEPLOYMENT.lower()
                for x in ["gpt-5", "o1", "o3", "o4"]
            )

            params = {
                "model": AzureConfig.DEPLOYMENT,
                "messages": [
                    {
                        "role": "system",
                        "content": "Du bist Experte für Baumaterial-EPD-Matching. Antworte NUR mit JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "timeout": 180.0
            }

            if is_reasoning:
                params["max_completion_tokens"] = 16000
            else:
                params["max_tokens"] = 4000
                params["temperature"] = 0.2

            response = self.azure_client.chat.completions.create(**params)
            content = response.choices[0].message.content

            # ===== Token-Tracking =====
            if response.usage:
                record = record_usage(
                    model=AzureConfig.DEPLOYMENT,
                    usage={
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    },
                    context="epd_matching"
                )
                get_tracker().print_call_summary(record)
            # ===== Ende Token-Tracking =====

            return content.strip() if content else json.dumps({"matches": []})

        except Exception as e:
            print(f"❌ Azure Fehler: {type(e).__name__}: {e}")
            return json.dumps({"matches": []})

    def _parse_batch_response(self, response: str, expected_count: int) -> List[List[Dict[str, Any]]]:
        """Parst Batch-Response und extrahiert Matches für alle Schichten."""
        print("\n[Stage 4c] Parse Batch-Matches...")

        if not response:
            return [[] for _ in range(expected_count)]

        # JSON aus Markdown extrahieren
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
        if fence_match:
            response = fence_match.group(1)

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            json_match = re.search(r"\{[\s\S]*\"results\"[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group(0))
            else:
                return [[] for _ in range(expected_count)]

        if not isinstance(data, dict) or "results" not in data:
            return [[] for _ in range(expected_count)]

        all_matches = []
        results = data.get("results", [])

        for i in range(expected_count):
            schicht_result = None
            for r in results:
                if r.get("schicht") == i + 1:
                    schicht_result = r
                    break

            if not schicht_result:
                all_matches.append([])
                continue

            matches = []
            for item in schicht_result.get("matches", []):
                if not isinstance(item, dict):
                    continue

                identifier = item.get("id") or item.get("uuid")
                if identifier is None:
                    continue

                confidence = self._normalize_confidence(item.get("confidence"))

                matches.append({
                    "uuid": str(identifier).strip(),
                    "begruendung": item.get("begruendung", ""),
                    "confidence": confidence
                })

            all_matches.append(matches)

        return all_matches

    def _parse_response(self, response: str) -> List[Dict[str, Any]]:
        """Parst Azure-Response und extrahiert Matches."""
        print("\n[Stage 4c] Parse Matches...")

        if not response:
            return []

        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
        if fence_match:
            response = fence_match.group(1)

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            json_match = re.search(r"\{[\s\S]*\"matches\"[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group(0))
            else:
                return []

        if not isinstance(data, dict):
            return []

        results = []
        for item in data.get("matches", []):
            if not isinstance(item, dict):
                continue

            identifier = item.get("id") or item.get("uuid")
            if identifier is None:
                continue

            confidence = self._normalize_confidence(item.get("confidence"))

            results.append({
                "uuid": str(identifier).strip(),
                "begruendung": item.get("begruendung", ""),
                "confidence": confidence
            })

        return results

    @staticmethod
    def _normalize_confidence(value: Any) -> Optional[int]:
        """Normalisiert Confidence-Wert auf 0-100."""
        if value is None:
            return None
        try:
            return max(0, min(100, int(value)))
        except (ValueError, TypeError):
            return None

    def _enrich_results(
        self,
        matches: List[Dict[str, Any]],
        epds: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Reichert Matches mit EPD-Namen an."""
        name_map = {
            str(e.get("id")): e.get("name", "")
            for e in epds
        }

        return [
            {
                "uuid": m["uuid"],
                "name": name_map.get(m["uuid"], ""),
                "confidence": m.get("confidence"),
                "begruendung": m.get("begruendung", "")
            }
            for m in matches
        ]

    def _print_results(self, matches: List[Dict[str, Any]]) -> None:
        """Gibt Matching-Ergebnisse aus."""
        if matches:
            print(f"✅ {len(matches)} Matches gefunden:")
            for i, m in enumerate(matches[:5], 1):
                conf = f" ({m['confidence']}%)" if m.get('confidence') is not None else ""
                reason = m.get('begruendung', '')[:80]
                print(f"  {i}. ID {m['uuid']}{conf} – {reason}...")
        else:
            print("⚠️  Keine Matches gefunden")

        print(f"\n✅ Matching abgeschlossen\n{'='*70}\n")