"""
Configuration pour l'application TourGuide
"""
import os
from pathlib import Path

# Chemins des fichiers
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

# Fichier du graphe de connaissances (VERSION ENRICHIE avec inférences)
KG_FILE = DATA_DIR / "kg_inferred.ttl"

# Fichiers intermédiaires disponibles (pour tests/comparaisons)
KG_LINKED_FILE = DATA_DIR / "kg_linked.ttl"  # Avant inférence
KG_ENRICHED_FILE = DATA_DIR / "kg_enriched.ttl"  # Avec reviews
KG_FINAL_FILE = DATA_DIR / "kg_final.ttl"  # Base TourPedia + Wikivoyage

# Fichier des recommandations TransE
RECOMMENDATIONS_FILE = DATA_DIR / "recommendations_transe.json"

# Namespace du projet
TOURGUIDE_NS = "https://example.org/tourguide#"

# Configuration de l'application
APP_TITLE = "TourGuide Paris - Assistant Touristique Intelligent"
APP_VERSION = "1.0.0"

# Configuration GraphRAG
# Options: "patterns" (règles simples) ou "openrouter" (GPT-4o-mini via OpenRouter)
# Pour OpenRouter: créer un compte sur https://openrouter.ai et obtenir une clé API
# puis définir: $env:OPENROUTER_API_KEY="sk-or-v1-..."
GRAPHRAG_MODE = os.getenv("GRAPHRAG_MODE", "openrouter")  # ou "patterns"

# Clé API OpenRouter (obligatoire si GRAPHRAG_MODE="openrouter")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", None)
