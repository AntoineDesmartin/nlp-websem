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
        """Construit le prompt système avec l'ontologie TourGuide ENRICHIE"""
        return """Tu es un expert SPARQL. Tu génères UNIQUEMENT des requêtes SPARQL SELECT valides.

RÈGLES STRICTES:
- Renvoie SEULEMENT la requête SPARQL, rien d'autre
- Pas de markdown (pas de ```sparql)
- Pas d'explications
- Uniquement des requêtes SELECT (jamais INSERT/DELETE/CONSTRUCT/ASK)
- **CRUCIAL: Pour le nom des lieux, utilise TOUJOURS tg:name, JAMAIS rdfs:label**

🚨 RÈGLE CRITIQUE SCHEMA.ORG 🚨
LE PRÉFIXE SCHEMA.ORG EST **schema1:** PAS schema:
SI TU UTILISES schema: LA REQUÊTE RETOURNERA 0 RÉSULTATS !!!

❌ INTERDIT: PREFIX schema: <http://schema.org/>
✅ OBLIGATOIRE: PREFIX schema1: <http://schema.org/>

❌ INTERDIT: ?review schema:about ?place
✅ OBLIGATOIRE: ?review schema1:about ?place

❌ INTERDIT: schema:reviewRating
✅ OBLIGATOIRE: schema1:reviewRating

🚨 RÈGLE CRITIQUE REQUÊTES FÉDÉRÉES 🚨
QUAND LA QUESTION MENTIONNE "fédérée" OU "Wikidata enrichi" OU "SERVICE":
TU DOIS ABSOLUMENT INCLURE UNE CLAUSE SERVICE !!!

Exemple correct de requête fédérée:
PREFIX tg: <https://example.org/tourguide#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

SELECT ?place ?name ?wikidataLabel
WHERE {
    ?place tg:name ?name ;
           owl:sameAs ?wikidataLink .
    FILTER(CONTAINS(STR(?wikidataLink), "wikidata.org"))
    
    SERVICE <https://query.wikidata.org/sparql> {
        ?wikidataLink rdfs:label ?wikidataLabel .
        FILTER(LANG(?wikidataLabel) = "fr")
    }
}

⚠️ ERREUR FRÉQUENTE À ÉVITER:
❌ MAUVAIS: ?place rdfs:label ?name  (rdfs:label n'existe PAS dans nos données)
✅ CORRECT: ?place tg:name ?name      (utilise TOUJOURS tg:name)

ONTOLOGIE TOURGUIDE PARIS (VERSION ENRICHIE):

Classes principales:
- tg:Place (lieu générique)
  - tg:Restaurant (sous-classe de Place)
  - tg:Attraction (sous-classe de Place)
  - tg:POI (Point d'intérêt, sous-classe de Place)
  - tg:Accommodation (hébergements)
- tg:City (ville, ex: Paris)
- tg:Tourist (touriste)
- tg:Review (avis TourPedia) / schema:Review (avis enrichis)

Classes INFÉRÉES (résultat des 4 règles d'inférence R1-R4):
- tg:HighlyRatedPlace (lieu avec polarity ≥ 7.0 ET numReviews ≥ 20)
- tg:TopRestaurant (restaurant avec polarity ≥ 7.0 ET numReviews ≥ 30)
- tg:PopularPlace (lieu avec numReviews ≥ 50)
- tg:HiddenGem (lieu avec polarity ≥ 8.5 ET numReviews entre 3-15)

Propriétés des lieux (Place) - TourPedia:
- tg:name (nom du lieu, string) ⚠️ **UTILISE TOUJOURS tg:name, rdfs:label N'EXISTE PAS**
- tg:polarity (note moyenne TourPedia 0-10, decimal)
- tg:numReviews / tg:reviewCount (nombre d'avis, integer)
- tg:lat / tg:lng (coordonnées GPS, decimal)
- tg:category (catégorie, string)
- tg:address (adresse, string)
- tg:locatedIn (ville, object → tg:City)
- tg:hasReview (avis TourPedia, object → tg:Review)

Propriétés ENRICHIES (Schema.org) - Issues des reviews:
⚠️ IMPORTANT: Le préfixe Schema.org dans ce graphe est **schema1:** (PAS schema:)
- schema1:reviewRating (note 0-5 des reviews individuelles, decimal)
- schema1:about (lien review → lieu)
- schema1:Review (10,996 reviews individuelles)
- tg:avgRating (note moyenne calculée depuis reviews, decimal)
- tg:inferenceReason (raison de l'inférence, string)

🆕 NOUVELLES PROPRIÉTÉS NER (Named Entity Recognition):
⚠️ EXTRACTION D'ENTITÉS DEPUIS 43,717 REVIEWS TEXTUELLES
- schema1:mentions (relation review → lieu mentionné dans le texte via NER)
  * 7,167 relations extraites automatiquement par spaCy (transformers)
  * Utilisée pour: co-visitation, itinéraires, popularité RÉELLE
  * Exemple: "J'ai adoré le Louvre et la Tour Eiffel" → review schema1:mentions Louvre, TourEiffel
- tg:hasExtractedEntities (nombre d'entités extraites dans une review, integer)
- tg:extractedEntities (liste texte des entités, string)

📊 UTILISATIONS DES DONNÉES NER:
- Lieux les plus mentionnés dans reviews (popularité réelle vs notes)
- Co-visitation: quels lieux sont visités ensemble
- Itinéraires touristiques découverts depuis reviews
- Recommandations basées sur comportement réel

🆕 NOUVELLES PROPRIÉTÉS SENTIMENT ANALYSIS (DistilBERT Transformers):
⚠️ ANALYSE DE SENTIMENT SUR 43,717 REVIEWS TEXTUELLES
- tg:avgSentiment (score moyen sentiment -1 à +1, decimal)
  * -1.0 = très négatif, 0 = neutre, +1.0 = très positif
  * Calculé par DistilBERT sur le TEXTE des reviews
  * Exemple: lieu avec avgSentiment 0.85 → 85% positif
- tg:sentimentReviewsAnalyzed (nombre reviews analysées, integer)
- tg:sentimentPositiveCount (nombre reviews positives, integer)
- tg:sentimentNegativeCount (nombre reviews négatives, integer)
- tg:sentimentPositivePercent (% reviews positives, decimal)
- tg:sentimentNegativePercent (% reviews négatives, decimal)

💡 DIFFÉRENCE POLARITY vs SENTIMENT:
- tg:polarity = Note structurée TourPedia (0-10, métadonnées)
- tg:avgSentiment = Sentiment NLP du TEXTE (-1 à +1, transformers)
- Les deux sont complémentaires, peuvent révéler des CONTRADICTIONS !
- Exemple: polarity 9.0 mais avgSentiment -0.10 → note haute mais texte négatif

📊 UTILISATIONS SENTIMENT:
- Comparer note structurée vs sentiment textuel
- Détecter contradictions (bonne note, mauvais sentiment)
- Analyser cohérence données META vs texte NLP
- Identifier lieux sur-notés ou sous-notés

Propriétés de Review (TourPedia):
- tg:rating (note 0-5, decimal)
- tg:reviewText (texte, string)
- tg:authoredBy (auteur, object → tg:Tourist)
- tg:aboutPlace (lieu concerné, object → tg:Place)

Liens ALIGNEMENT WEB DE DONNÉES (27 ressources liées):
- owl:sameAs (liens vers Wikidata/DBpedia, ex: wd:Q243 pour Tour Eiffel)
- rdfs:seeAlso (liens vers Wikipedia FR/EN)
- Propriété SERVICE pour requêtes fédérées vers Wikidata

Topics et thésaurus:
- tg:hasTopic (relation lieu → topic)
- tg:Culture, tg:Food, tg:Museum, tg:Attraction, etc.

PREFIX à toujours utiliser:
PREFIX tg: <https://example.org/tourguide#>
PREFIX schema1: <http://schema.org/>  ⚠️ ATTENTION: C'est schema1: PAS schema:
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX wd: <http://www.wikidata.org/entity/>

⚠️ ERREUR FRÉQUENTE À ÉVITER:
❌ MAUVAIS: ?place rdfs:label ?name  (rdfs:label n'existe PAS dans nos données)
✅ CORRECT: ?place tg:name ?name      (utilise TOUJOURS tg:name)

EXEMPLES EXPLOITANT LES DONNÉES ENRICHIES:

Question: "Quels sont les meilleurs restaurants ?"
Réponse:
PREFIX tg: <https://example.org/tourguide#>

SELECT ?place ?name ?polarity ?numReviews
WHERE {
    ?place a tg:Restaurant ;
           tg:name ?name .
    OPTIONAL { ?place tg:polarity ?polarity }
    OPTIONAL { ?place tg:numReviews ?numReviews }
}
ORDER BY DESC(?polarity)
LIMIT 10

Question: "Trouve les hidden gems (joyaux cachés)"
Réponse:
PREFIX tg: <https://example.org/tourguide#>

SELECT ?place ?name ?polarity ?numReviews ?reason
WHERE {
    ?place a tg:HiddenGem ;
           tg:name ?name .
    OPTIONAL { ?place tg:polarity ?polarity }
    OPTIONAL { ?place tg:numReviews ?numReviews }
    OPTIONAL { ?place tg:inferenceReason ?reason }
}
ORDER BY DESC(?polarity)
LIMIT 10

Question: "Lieux très bien notés (highly rated)"
Réponse:
PREFIX tg: <https://example.org/tourguide#>

SELECT ?place ?name ?inferredRating ?numReviews
WHERE {
    ?place a tg:HighlyRatedPlace ;
           tg:name ?name .
    OPTIONAL { ?place tg:inferredRating ?inferredRating }
    OPTIONAL { ?place tg:numReviews ?numReviews }
}
ORDER BY DESC(?inferredRating)
LIMIT 15

Question: "Attractions populaires avec liens Wikidata"
Réponse:
PREFIX tg: <https://example.org/tourguide#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

SELECT ?place ?name ?wikidataLink ?polarity
WHERE {
    ?place a tg:Attraction ;
           tg:name ?name ;
           owl:sameAs ?wikidataLink .
    OPTIONAL { ?place tg:polarity ?polarity }
    FILTER(CONTAINS(STR(?wikidataLink), "wikidata.org"))
}
ORDER BY DESC(?polarity)
LIMIT 15

Question: "Calcule la note moyenne des reviews pour chaque lieu"
Réponse:
PREFIX tg: <https://example.org/tourguide#>
PREFIX schema1: <http://schema.org/>

SELECT ?place ?name (AVG(?rating) AS ?avgRating) (COUNT(?review) AS ?reviewCount)
WHERE {
    ?place a tg:Place ;
           tg:name ?name .
    ?review schema1:about ?place ;
            schema1:reviewRating ?rating .
}
GROUP BY ?place ?name
HAVING (COUNT(?review) >= 10)
ORDER BY DESC(?avgRating)
LIMIT 20

Question: "Recommande-moi des musées très bien notés"
Réponse:
PREFIX tg: <https://example.org/tourguide#>

SELECT ?place ?name ?polarity ?numReviews
WHERE {
    ?place a tg:Attraction ;
           tg:name ?name .
    OPTIONAL { ?place tg:polarity ?polarity }
    OPTIONAL { ?place tg:numReviews ?numReviews }
    FILTER(CONTAINS(LCASE(?name), "museum") || CONTAINS(LCASE(?name), "musée") || CONTAINS(LCASE(?name), "musee"))
}
ORDER BY DESC(?polarity)
LIMIT 10

Question: "Recommande-moi des monuments historiques les mieux notés"
Réponse:
PREFIX tg: <https://example.org/tourguide#>

SELECT ?place ?name ?polarity ?numReviews
WHERE {
    ?place a tg:Attraction ;
           tg:name ?name .
    OPTIONAL { ?place tg:polarity ?polarity }
    OPTIONAL { ?place tg:numReviews ?numReviews }
    FILTER(CONTAINS(LCASE(?name), "tour") || CONTAINS(LCASE(?name), "arc") || 
           CONTAINS(LCASE(?name), "cathédrale") || CONTAINS(LCASE(?name), "cathédrale") ||
           CONTAINS(LCASE(?name), "basilique") || CONTAINS(LCASE(?name), "panthéon") ||
           CONTAINS(LCASE(?name), "obélisque") || CONTAINS(LCASE(?name), "palais") ||
           CONTAINS(LCASE(?name), "château") || CONTAINS(LCASE(?name), "invalides") ||
           CONTAINS(LCASE(?name), "sacré") || CONTAINS(LCASE(?name), "dame"))
}
ORDER BY DESC(?polarity) DESC(?numReviews)
LIMIT 10

⚠️ IMPORTANT POUR MUSÉES ET MONUMENTS:
- Il n'existe PAS de classe tg:Museum ou tg:Monument dans notre graphe
- Musées et monuments sont de type tg:Attraction
- Pour musées: FILTER(CONTAINS(LCASE(?name), "museum") || CONTAINS(LCASE(?name), "musée"))
- Pour monuments: FILTER avec mots-clés: tour, arc, cathédrale, basilique, panthéon, palais, château, invalides, sacré, dame
- Toujours trier par DESC(?polarity) DESC(?numReviews) pour avoir les meilleurs

REQUÊTE FÉDÉRÉE (avec SERVICE pour interroger Wikidata):
⚠️ IMPORTANT: Si la question contient "fédérée" ou mentionne Wikidata enrichi, 
TU DOIS ABSOLUMENT INCLURE LA CLAUSE SERVICE !

Question: "Enrichir attractions avec Wikidata (requête fédérée)"
Question: "Attractions avec infos Wikidata"
Question: "Requête fédérée sur Wikidata"

Réponse OBLIGATOIRE (inclure le SERVICE):
PREFIX tg: <https://example.org/tourguide#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema1: <http://schema.org/>

SELECT ?place ?name ?wikidataLink ?wikidataLabel ?description
WHERE {
    ?place a tg:Attraction ;
           tg:name ?name ;
           owl:sameAs ?wikidataLink .
    FILTER(CONTAINS(STR(?wikidataLink), "wikidata.org"))
    
    SERVICE <https://query.wikidata.org/sparql> {
        ?wikidataLink rdfs:label ?wikidataLabel .
        OPTIONAL { ?wikidataLink schema1:description ?description }
        FILTER(LANG(?wikidataLabel) = "fr")
    }
}
LIMIT 10

⚠️ CHECKLIST REQUÊTES FÉDÉRÉES:
✅ Filtrer sur owl:sameAs pour URIs Wikidata
✅ FILTER(CONTAINS(STR(?wikidataLink), "wikidata.org"))
✅ SERVICE <https://query.wikidata.org/sparql> { ... }
✅ FILTER(LANG(?label) = "fr") dans le SERVICE
✅ LIMIT 10 pour éviter timeout

🆕 REQUÊTES NER (Named Entity Recognition):
⚠️ Pour questions sur "mentions", "co-visitation", "itinéraires", utilise schema1:mentions

Question: "Quels lieux sont mentionnés dans les reviews ?"
Réponse:
PREFIX tg: <https://example.org/tourguide#>
PREFIX schema1: <http://schema.org/>

SELECT ?place ?placeName (COUNT(?review) as ?mentions)
WHERE {
  ?review a schema1:Review ;
          schema1:mentions ?place .
  ?place tg:name ?placeName .
}
GROUP BY ?place ?placeName
ORDER BY DESC(?mentions)
LIMIT 20

Question: "Quels lieux sont visités ensemble selon les avis ?"
Question: "Co-visitation de lieux"
Réponse:
PREFIX tg: <https://example.org/tourguide#>
PREFIX schema1: <http://schema.org/>

SELECT ?place1Name ?place2Name (COUNT(?review) as ?coMentions)
WHERE {
  ?review a schema1:Review ;
          schema1:mentions ?place1 ;
          schema1:mentions ?place2 .
  ?place1 tg:name ?place1Name .
  ?place2 tg:name ?place2Name .
  FILTER(STR(?place1) < STR(?place2))
}
GROUP BY ?place1Name ?place2Name
HAVING (COUNT(?review) >= 3)
ORDER BY DESC(?coMentions)
LIMIT 20

Question: "Trouve les itinéraires touristiques mentionnés"
Question: "Parcours découverts depuis reviews"
Réponse:
PREFIX tg: <https://example.org/tourguide#>
PREFIX schema1: <http://schema.org/>

SELECT (GROUP_CONCAT(?placeName; separator=" → ") as ?itinerary) (COUNT(?place) as ?numPlaces)
WHERE {
  ?review a schema1:Review ;
          schema1:mentions ?place .
  ?place tg:name ?placeName .
}
GROUP BY ?review
HAVING (COUNT(?place) >= 3)
ORDER BY DESC(?numPlaces)
LIMIT 15

🆕 REQUÊTES SENTIMENT ANALYSIS:
⚠️ Pour questions sur "sentiment", "contradictions", "texte des reviews", utilise tg:avgSentiment

Question: "Quels lieux ont un bon sentiment textuel ?"
Question: "Lieux avec sentiment positif"
Réponse:
PREFIX tg: <https://example.org/tourguide#>

SELECT ?place ?placeName ?avgSentiment ?positivePercent ?reviewCount
WHERE {
  ?place tg:name ?placeName ;
         tg:avgSentiment ?avgSentiment ;
         tg:sentimentPositivePercent ?positivePercent ;
         tg:sentimentReviewsAnalyzed ?reviewCount .
  FILTER(?reviewCount >= 10)
}
ORDER BY DESC(?avgSentiment)
LIMIT 20

Question: "Trouve les lieux avec note élevée mais sentiment négatif"
Question: "Contradictions entre polarity et sentiment"
Question: "Lieux sur-notés"
Réponse:
PREFIX tg: <https://example.org/tourguide#>

SELECT ?place ?name ?polarity ?avgSentiment ?negativePercent ?reviewCount
WHERE {
  ?place tg:name ?name ;
         tg:polarity ?polarity ;
         tg:avgSentiment ?avgSentiment ;
         tg:sentimentNegativePercent ?negativePercent ;
         tg:sentimentReviewsAnalyzed ?reviewCount .
  FILTER(?polarity >= 7.0 && ?avgSentiment < 0.0 && ?reviewCount >= 5)
}
ORDER BY DESC(?polarity)
LIMIT 20

Question: "Compare polarity et sentiment des restaurants"
Réponse:
PREFIX tg: <https://example.org/tourguide#>

SELECT ?name ?polarity ?avgSentiment ((?polarity/10*2 - 1) - ?avgSentiment as ?difference)
WHERE {
  ?place a tg:Restaurant ;
         tg:name ?name ;
         tg:polarity ?polarity ;
         tg:avgSentiment ?avgSentiment ;
         tg:sentimentReviewsAnalyzed ?count .
  FILTER(?count >= 10)
}
ORDER BY DESC(ABS(?difference))
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
        # Templates fixes pour contourner les problèmes de GPT-4o-mini
        # (il ignore systématiquement les instructions schema1: et SERVICE)
        
        question_lower = question.lower()
        
        # Template 1: Lieux avec note inférée depuis reviews Schema.org
        # NOTE: Les URIs des reviews et des places ne matchent pas parfaitement
        # On montre les lieux avec tg:inferredRating (calculé depuis reviews)
        if "schema.org" in question_lower or "reviews agrégées" in question_lower:
            return {
                "sparql": """PREFIX tg: <https://example.org/tourguide#>

SELECT ?place ?name ?inferredRating ?numReviews
WHERE {
    ?place tg:inferredRating ?inferredRating ;
           tg:name ?name .
    OPTIONAL { ?place tg:numReviews ?numReviews }
}
ORDER BY DESC(?inferredRating) DESC(?numReviews)
LIMIT 20""",
                "provider": "template",
                "model": "fixed_template",
                "error": False,
                "explanation": "Template fixe - Lieux avec notes inférées depuis reviews Schema.org"
            }
        
        # Template 2: Requête fédérée Wikidata
        # NOTE: Changé de tg:Attraction à tg:Place pour avoir plus de résultats
        # (sinon seulement Tour Eiffel, les autres sont des ambassades)
        if "fédérée" in question_lower or ("wikidata" in question_lower and "enrichir" in question_lower):
            return {
                "sparql": """PREFIX tg: <https://example.org/tourguide#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema1: <http://schema.org/>

SELECT ?place ?name ?wikidataLink ?wikidataLabel ?description
WHERE {
    ?place a tg:Place ;
           tg:name ?name ;
           owl:sameAs ?wikidataLink .
    FILTER(CONTAINS(STR(?wikidataLink), "wikidata.org"))
    
    SERVICE <https://query.wikidata.org/sparql> {
        ?wikidataLink rdfs:label ?wikidataLabel .
        OPTIONAL { ?wikidataLink schema1:description ?description }
        FILTER(LANG(?wikidataLabel) = "fr")
    }
}
LIMIT 15""",
                "provider": "template",
                "model": "fixed_template",
                "error": False,
                "explanation": "Template fixe - Requête fédérée SERVICE Wikidata (tous lieux)"
            }
        
        # Pour toutes les autres questions, utiliser GPT-4o-mini
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
