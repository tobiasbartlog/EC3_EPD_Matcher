Create a .env file in the main directory.

Use the following:
AZURE_OPENAI_API_KEY= [INSERT HERE]
ENDPOINT_URL=[INSERT HERE]
DEPLOYMENT_NAME=gpt-4o-mini
ONLINE_EPD_API_BASE_URL=https://susinfra.onpraxis.de
ONLINE_EPD_API_USERNAME=[INSERT HERE]
ONLINE_EPD_API_PASSWORT=[INSERT HERE]

#=============================================================================
# STAGE 1: CONTEXT EXTRACTION
# ==============================================================================
# Priorität: NAME-Feld für Schicht-Erkennung bevorzugen
EPD_PREFER_NAME_FIELD=true

# Volumen für LCA extrahieren
EPD_EXTRACT_VOLUME=true

# ==============================================================================
# STAGE 2: MATERIAL CODE PARSING (Glossar/TL Asphalt-StB)
# ==============================================================================
# Aktiviert intelligentes Parsing der Asphalt-Bezeichnungen
# z.B. "AC 16 B S" → Typ=AC, Schicht=Binder, Beanspruchung=S
EPD_USE_GLOSSAR=true

# Debug-Output für Parsing-Ergebnisse
EPD_GLOSSAR_DEBUG=true

# ==============================================================================
# STAGE 3: EPD PRE-FILTERING
# ==============================================================================
# Aktiviert Vorfilterung basierend auf geparsten Material-Eigenschaften
# Reduziert EPD-Menge vor dem LLM-Call erheblich
EPD_USE_GLOSSAR_FILTER=true

# Maximale EPDs pro Material nach Filterung
EPD_GLOSSAR_FILTER_MAX=10000

# Legacy: Einfacher Label-Filter (nur wenn USE_GLOSSAR=false)
EPD_USE_FILTER_LABELS=false
EPD_FILTER_LABELS=Asphalt,Bitumen,Tragschicht,Deckschicht,Binder

# ==============================================================================
# STAGE 4: SEMANTIC MATCHING (LLM)
# ==============================================================================
# Maximale EPDs die an GPT gesendet werden (Token-Limit beachten!)
PROMPT_MAX_EPD=10360

# Detail-Matching: Lädt technischeBeschreibung, Anmerkungen etc.
# true = mehr Kontext für GPT, aber langsamer + mehr Tokens
# false = nur Name + Klassifizierung (schneller)
EPD_USE_DETAIL_MATCHING=false

# Spalten für Detail-Matching (kommasepariert)
EPD_MATCHING_COLUMNS=name,technischeBeschreibung,anmerkungen

# Parallele API-Calls beim Laden von EPD-Details
EPD_PARALLEL_WORKERS=10

# Batch-Modus: Alle Schichten in einem GPT-Call
EPD_USE_BATCH_MODE=true

# Maximale Ergebnisse pro Material
EPD_MAX_RESULTS=10

# ==============================================================================
# STAGE 5: RESULT AGGREGATION / CONFIDENCE VALIDATION
# ==============================================================================
# Nachträgliche Validierung der GPT-Confidence-Werte
# Korrigiert offensichtliche Fehler (z.B. Bitumenbahnen für Asphalt)
EPD_USE_CONFIDENCE_VALIDATION=true

# Minimale Confidence für Ergebnisse (darunter wird gefiltert)
EPD_MIN_CONFIDENCE=25

# Maximale Confidence für Ausschluss-Begriffe
EPD_MAX_CONFIDENCE_EXCLUDED=20
