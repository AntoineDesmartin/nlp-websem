"""
Client SPARQL pour interroger le graphe de connaissances
"""
from rdflib import Graph, Namespace
from typing import List, Dict, Any

class SPARQLClient:
    def __init__(self, kg_file: str):
        """Initialise le client avec le fichier du graphe de connaissances"""
        print(f"Chargement du graphe de connaissances depuis {kg_file}...")
        self.graph = Graph()
        self.graph.parse(kg_file, format="turtle")
        print(f"✓ Graphe chargé : {len(self.graph)} triples")
        
        # Namespaces
        self.tg = Namespace("https://example.org/tourguide#")
        
    def query(self, sparql_query: str) -> List[Dict[str, Any]]:
        """Exécute une requête SPARQL et retourne les résultats"""
        results = []
        qres = self.graph.query(sparql_query)
        
        for row in qres:
            result_dict = {}
            for var in qres.vars:
                value = row[var]
                if value:
                    result_dict[str(var)] = str(value)
            results.append(result_dict)
        
        return results
    
    def get_top_rated_places(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Récupère les lieux les mieux notés"""
        query = f"""
        PREFIX tg: <https://example.org/tourguide#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?place ?name ?polarity ?category
        WHERE {{
            ?place a tg:Place ;
                   tg:name ?name ;
                   tg:polarity ?polarity .
            OPTIONAL {{ ?place tg:category ?category }}
        }}
        ORDER BY DESC(?polarity)
        LIMIT {limit}
        """
        return self.query(query)
    
    def get_places_by_type(self, place_type: str) -> List[Dict[str, Any]]:
        """Récupère les lieux par type (Restaurant, Attraction, POI)"""
        query = f"""
        PREFIX tg: <https://example.org/tourguide#>
        
        SELECT ?place ?name ?polarity
        WHERE {{
            ?place a tg:{place_type} ;
                   tg:name ?name .
            OPTIONAL {{ ?place tg:polarity ?polarity }}
        }}
        ORDER BY DESC(?polarity)
        LIMIT 20
        """
        return self.query(query)
    
    def get_place_details(self, place_uri: str) -> Dict[str, Any]:
        """Récupère tous les détails d'un lieu spécifique"""
        query = f"""
        PREFIX tg: <https://example.org/tourguide#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        
        SELECT ?property ?value
        WHERE {{
            <{place_uri}> ?property ?value .
        }}
        """
        results = self.query(query)
        
        # Organiser les résultats
        details = {"uri": place_uri}
        for row in results:
            prop = row["property"].split("#")[-1] if "#" in row["property"] else row["property"]
            details[prop] = row["value"]
        
        return details
    
    def search_places_by_name(self, search_term: str) -> List[Dict[str, Any]]:
        """Recherche des lieux par nom"""
        query = f"""
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
        return self.query(query)
    
    def get_places_with_coordinates(self) -> List[Dict[str, Any]]:
        """Récupère tous les lieux avec leurs coordonnées GPS"""
        query = """
        PREFIX tg: <https://example.org/tourguide#>
        
        SELECT ?place ?name ?lat ?lng ?polarity
        WHERE {
            ?place a tg:Place ;
                   tg:name ?name ;
                   tg:lat ?lat ;
                   tg:lng ?lng .
            OPTIONAL { ?place tg:polarity ?polarity }
        }
        """
        return self.query(query)
    
    def get_linked_data_info(self) -> List[Dict[str, Any]]:
        """Récupère les informations sur les liens vers le web de données"""
        query = """
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX tg: <https://example.org/tourguide#>
        
        SELECT ?place ?name ?link
        WHERE {
            ?place a tg:Place ;
                   tg:name ?name .
            {
                ?place owl:sameAs ?link .
                FILTER(CONTAINS(STR(?link), "wikidata.org") || CONTAINS(STR(?link), "dbpedia.org"))
            }
            UNION
            {
                ?place rdfs:seeAlso ?link .
                FILTER(CONTAINS(STR(?link), "wikipedia.org"))
            }
        }
        ORDER BY ?name
        LIMIT 100
        """
        return self.query(query)
