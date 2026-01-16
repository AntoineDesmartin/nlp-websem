"""
Service GraphRAG avec OpenRouter pour génération SPARQL
Utilise GPT-4o-mini via OpenRouter pour transformer questions en requêtes SPARQL
"""
import os
import re
import requests
from typing import Dict, Any
import urllib3

# Désactiver les warnings SSL (car on désactive la vérification)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class OpenRouterSPARQLService:
    """
    Service qui transforme des questions en langage naturel en requêtes SPARQL
    en utilisant GPT-4o-mini via OpenRouter
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialise le service OpenRouter
        
        Args:
            api_key: Clé API OpenRouter (ou via variable d'environnement OPENROUTER_API_KEY)
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY manquante. "
                "Définis-la avec: $env:OPENROUTER_API_KEY='sk-or-v1-...'"
            )
        
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "openai/gpt-4o-mini"
        
        # Prompt système avec l'ontologie complète
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Construit le prompt système avec l'ontologie TourGuide"""
        return """Tu es un expert SPARQL. Tu génères UNIQUEMENT des requêtes SPARQL SELECT valides.

RÈGLES STRICTES:
- Renvoie SEULEMENT la requête SPARQL, rien d'autre
- Pas de markdown (pas de ```sparql)
- Pas d'explications
- Uniquement des requêtes SELECT (jamais INSERT/DELETE/CONSTRUCT/ASK)

ONTOLOGIE TOURGUIDE PARIS:

Classes principales:
- tg:Place (lieu générique)
  - tg:Restaurant (sous-classe de Place)
  - tg:Attraction (sous-classe de Place)
  - tg:POI (Point d'intérêt, sous-classe de Place)
- tg:City (ville, ex: Paris)
- tg:Tourist (touriste)
- tg:Review (avis)

Propriétés des lieux (Place):
- tg:name (nom du lieu, string)
- tg:polarity (note moyenne 0-1, decimal)
- tg:reviewCount (nombre d'avis, integer)
- tg:latitude / tg:longitude (coordonnées GPS, decimal)
- tg:category (catégorie, string)
- tg:locatedIn (ville, object → tg:City)
- tg:hasReview (avis, object → tg:Review)

Propriétés de Review:
- tg:rating (note 0-5, decimal)
- tg:reviewText (texte, string)
- tg:authoredBy (auteur, object → tg:Tourist)
- tg:aboutPlace (lieu concerné, object → tg:Place)

Liens externes (optionnels):
- owl:sameAs (lien vers Wikidata/DBpedia)

Règles inférées (peuvent être présentes):
- tg:HighlyRatedPlace (lieu avec polarity ≥ 0.8)
- tg:TopRestaurant (restaurant avec ≥ 50 avis ET polarity ≥ 0.75)
- tg:PopularPlace (lieu avec ≥ 100 avis)
- tg:HiddenGem (lieu avec < 20 avis ET polarity ≥ 0.85)

PREFIX à toujours utiliser:
PREFIX tg: <https://example.org/tourguide#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

EXEMPLES:

Question: "Quels sont les meilleurs restaurants ?"
Réponse:
PREFIX tg: <https://example.org/tourguide#>

SELECT ?place ?name ?polarity ?reviewCount
WHERE {
    ?place a tg:Restaurant ;
           tg:name ?name ;
           tg:polarity ?polarity .
    OPTIONAL { ?place tg:reviewCount ?reviewCount }
}
ORDER BY DESC(?polarity)
LIMIT 10

Question: "Trouve les attractions avec plus de 100 avis"
Réponse:
PREFIX tg: <https://example.org/tourguide#>

SELECT ?place ?name ?reviewCount ?polarity
WHERE {
    ?place a tg:Attraction ;
           tg:name ?name ;
           tg:reviewCount ?reviewCount .
    OPTIONAL { ?place tg:polarity ?polarity }
    FILTER(?reviewCount > 100)
}
ORDER BY DESC(?reviewCount)

Question: "Lieux avec des liens vers Wikidata"
Réponse:
PREFIX tg: <https://example.org/tourguide#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

SELECT ?place ?name ?wikidataLink
WHERE {
    ?place a tg:Place ;
           tg:name ?name ;
           owl:sameAs ?wikidataLink .
    FILTER(CONTAINS(STR(?wikidataLink), "wikidata"))
}
LIMIT 20
"""
    
    def question_to_sparql(self, question: str) -> Dict[str, Any]:
        """
        Transforme une question en langage naturel en requête SPARQL
        
        Args:
            question: Question en français
            
        Returns:
            Dict avec:
            - sparql: requête SPARQL générée
            - provider: "openrouter"
            - model: nom du modèle utilisé
            - error: True si erreur
            - explanation: message d'erreur ou confirmation
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f'Question: """{question}"""'},
                ],
                "temperature": 0.0,  # Déterministe pour requêtes SPARQL
            }
            
            response = requests.post(
                self.api_url, 
                headers=headers, 
                json=payload, 
                timeout=120,
                verify=False  # Désactive vérification SSL (temporaire)
            )
            response.raise_for_status()
            
            sparql = response.json()["choices"][0]["message"]["content"].strip()
            
            # Validation et nettoyage
            sparql = self._clean_and_validate_sparql(sparql)
            
            return {
                "sparql": sparql,
                "provider": "openrouter",
                "model": self.model,
                "error": False,
                "explanation": f"Requête générée avec {self.model}"
            }
            
        except requests.exceptions.ConnectionError as e:
            return {
                "sparql": None,
                "provider": "openrouter",
                "error": True,
                "explanation": f"Erreur de connexion à OpenRouter: {str(e)}\nVérifie ta connexion internet ou ton proxy/firewall."
            }
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                return {
                    "sparql": None,
                    "provider": "openrouter",
                    "error": True,
                    "explanation": "Clé API OpenRouter invalide. Vérifie OPENROUTER_API_KEY."
                }
            else:
                return {
                    "sparql": None,
                    "provider": "openrouter",
                    "error": True,
                    "explanation": f"Erreur HTTP {e.response.status_code}: {str(e)}"
                }
        except ValueError as e:
            return {
                "sparql": None,
                "provider": "openrouter",
                "error": True,
                "explanation": f"Requête SPARQL invalide: {str(e)}"
            }
        except Exception as e:
            return {
                "sparql": None,
                "provider": "openrouter",
                "error": True,
                "explanation": f"Erreur inattendue: {str(e)}"
            }
    
    def _clean_and_validate_sparql(self, sparql: str) -> str:
        """
        Nettoie et valide la requête SPARQL générée par le LLM
        
        Args:
            sparql: requête brute du LLM
            
        Returns:
            requête SPARQL nettoyée
            
        Raises:
            ValueError: si la requête est invalide
        """
        # Supprimer les blocs markdown si présents
        if "```" in sparql:
            # Extraire le contenu entre ```sparql et ```
            match = re.search(r"```(?:sparql)?\s*(.*?)\s*```", sparql, re.DOTALL | re.IGNORECASE)
            if match:
                sparql = match.group(1).strip()
            else:
                raise ValueError(
                    "Le modèle a renvoyé du markdown (```) mais impossible d'extraire la requête"
                )
        
        # Vérifier que c'est bien une requête SELECT
        if "SELECT" not in sparql.upper():
            raise ValueError(
                f"Le modèle n'a pas renvoyé une requête SELECT:\n{sparql[:200]}"
            )
        
        # Interdire les requêtes de modification
        forbidden_keywords = ["INSERT", "DELETE", "CONSTRUCT", "ASK", "DESCRIBE", "DROP", "CREATE"]
        for keyword in forbidden_keywords:
            if keyword in sparql.upper():
                raise ValueError(
                    f"Requête non autorisée (mot-clé {keyword} détecté). "
                    "Seulement SELECT est permis."
                )
        
        return sparql.strip()
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Retourne les capacités du service
        
        Returns:
            Dict avec informations sur le service
        """
        return {
            "provider": "openrouter",
            "model": self.model,
            "api_url": self.api_url,
            "supports_streaming": False,
            "supports_json_mode": False,
            "is_local": False,
            "requires_api_key": True,
            "cost_per_1k_tokens": {
                "input": 0.00015,   # $0.15 / 1M tokens
                "output": 0.0006    # $0.60 / 1M tokens
            }
        }
