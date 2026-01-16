"""
Service pour convertir questions naturelles en requêtes SPARQL
"""
from typing import Dict, Optional

class ExplainService:
    """
    Service qui transforme des questions en langage naturel en requêtes SPARQL
    Approche basée sur des patterns (règles simples)
    """
    
    def __init__(self):
        # Patterns de questions reconnues
        self.patterns = {
            "top_rated": ["meilleur", "mieux noté", "top", "recommande", "populaire"],
            "restaurants": ["restaurant", "manger", "dîner", "déjeuner", "cuisine"],
            "attractions": ["attraction", "monument", "visiter", "voir", "musée"],
            "poi": ["point d'intérêt", "poi", "lieu"],
            "search": ["cherche", "trouve", "recherche", "où est"],
            "map": ["carte", "coordonnées", "localisation", "gps", "map"],
            "linked_data": ["wikidata", "dbpedia", "wikipedia", "lié", "externe"]
        }
    
    def question_to_sparql(self, question: str) -> Dict[str, any]:
        """
        Convertit une question en langage naturel en requête SPARQL
        
        Returns:
            Dict avec 'query_type', 'sparql', 'explanation'
        """
        question_lower = question.lower()
        
        # Détection du type de question
        query_type = self._detect_query_type(question_lower)
        
        # Extraction de termes de recherche si présents
        search_term = self._extract_search_term(question_lower)
        
        # Génération de la requête SPARQL appropriée
        sparql_query, explanation = self._generate_sparql(query_type, search_term)
        
        return {
            "query_type": query_type,
            "sparql": sparql_query,
            "explanation": explanation,
            "search_term": search_term
        }
    
    def _detect_query_type(self, question: str) -> str:
        """Détecte le type de question posée"""
        for query_type, keywords in self.patterns.items():
            if any(keyword in question for keyword in keywords):
                return query_type
        return "top_rated"  # Par défaut
    
    def _extract_search_term(self, question: str) -> Optional[str]:
        """Extrait un terme de recherche de la question"""
        # Cherche après des mots-clés comme "cherche", "trouve", etc.
        search_triggers = ["cherche", "trouve", "recherche", "où est", "connais"]
        
        for trigger in search_triggers:
            if trigger in question:
                parts = question.split(trigger, 1)
                if len(parts) > 1:
                    # Nettoie le terme
                    term = parts[1].strip().strip("?.,!").strip()
                    # Enlève les mots courants
                    term = term.replace("un", "").replace("une", "").replace("le", "").replace("la", "").replace("les", "").strip()
                    if term:
                        return term
        
        return None
    
    def _generate_sparql(self, query_type: str, search_term: Optional[str] = None) -> tuple[str, str]:
        """Génère la requête SPARQL et son explication"""
        
        if query_type == "top_rated":
            sparql = """
PREFIX tg: <https://example.org/tourguide#>

SELECT ?place ?name ?polarity ?category
WHERE {
    ?place a tg:Place ;
           tg:name ?name ;
           tg:polarity ?polarity .
    OPTIONAL { ?place tg:category ?category }
}
ORDER BY DESC(?polarity)
LIMIT 10
"""
            explanation = "Cette requête récupère les 10 lieux les mieux notés (polarity) dans le graphe."
        
        elif query_type == "restaurants":
            sparql = """
PREFIX tg: <https://example.org/tourguide#>

SELECT ?place ?name ?polarity ?category
WHERE {
    ?place a tg:Restaurant ;
           tg:name ?name .
    OPTIONAL { ?place tg:polarity ?polarity }
    OPTIONAL { ?place tg:category ?category }
}
ORDER BY DESC(?polarity)
LIMIT 15
"""
            explanation = "Cette requête récupère les restaurants triés par note."
        
        elif query_type == "attractions":
            sparql = """
PREFIX tg: <https://example.org/tourguide#>

SELECT ?place ?name ?polarity ?category
WHERE {
    ?place a tg:Attraction ;
           tg:name ?name .
    OPTIONAL { ?place tg:polarity ?polarity }
    OPTIONAL { ?place tg:category ?category }
}
ORDER BY DESC(?polarity)
LIMIT 15
"""
            explanation = "Cette requête récupère les attractions touristiques triées par note."
        
        elif query_type == "poi":
            sparql = """
PREFIX tg: <https://example.org/tourguide#>

SELECT ?place ?name ?polarity
WHERE {
    ?place a tg:POI ;
           tg:name ?name .
    OPTIONAL { ?place tg:polarity ?polarity }
}
ORDER BY DESC(?polarity)
LIMIT 15
"""
            explanation = "Cette requête récupère les points d'intérêt triés par note."
        
        elif query_type == "search" and search_term:
            sparql = f"""
PREFIX tg: <https://example.org/tourguide#>

SELECT DISTINCT ?place ?name ?polarity ?lat ?lng
WHERE {{
    ?place a tg:Place ;
           tg:name ?name .
    OPTIONAL {{ ?place tg:polarity ?polarity }}
    OPTIONAL {{ ?place tg:lat ?lat }}
    OPTIONAL {{ ?place tg:lng ?lng }}
    FILTER(CONTAINS(LCASE(?name), LCASE("{search_term}")))
}}
ORDER BY DESC(?polarity)
LIMIT 15
"""
            explanation = f"Cette requête recherche des lieux dont le nom contient '{search_term}'."
        
        elif query_type == "map":
            sparql = """
PREFIX tg: <https://example.org/tourguide#>

SELECT ?place ?name ?lat ?lng ?polarity
WHERE {
    ?place a tg:Place ;
           tg:name ?name ;
           tg:lat ?lat ;
           tg:lng ?lng .
    OPTIONAL { ?place tg:polarity ?polarity }
}
LIMIT 100
"""
            explanation = "Cette requête récupère tous les lieux avec leurs coordonnées GPS pour affichage sur carte."
        
        elif query_type == "linked_data":
            sparql = """
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX tg: <https://example.org/tourguide#>

SELECT ?place ?name ?wikidata ?wikipedia ?dbpedia
WHERE {
    ?place a tg:Place ;
           tg:name ?name .
    OPTIONAL { ?place owl:sameAs ?wikidata . FILTER(CONTAINS(STR(?wikidata), "wikidata.org")) }
    OPTIONAL { ?place rdfs:seeAlso ?wikipedia . FILTER(CONTAINS(STR(?wikipedia), "wikipedia.org")) }
    OPTIONAL { ?place owl:sameAs ?dbpedia . FILTER(CONTAINS(STR(?dbpedia), "dbpedia.org")) }
    FILTER(BOUND(?wikidata) || BOUND(?wikipedia) || BOUND(?dbpedia))
}
LIMIT 50
"""
            explanation = "Cette requête récupère les lieux liés au web de données (Wikidata, DBpedia, Wikipedia)."
        
        else:
            # Par défaut
            sparql = """
PREFIX tg: <https://example.org/tourguide#>

SELECT ?place ?name ?polarity
WHERE {
    ?place a tg:Place ;
           tg:name ?name ;
           tg:polarity ?polarity .
}
ORDER BY DESC(?polarity)
LIMIT 10
"""
            explanation = "Requête par défaut : top 10 des lieux."
        
        return sparql, explanation
