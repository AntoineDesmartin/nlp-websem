"""
Script de nettoyage des extractions NER
Filtre le bruit et améliore la qualité des mentions
"""

from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, XSD
from pathlib import Path
from collections import Counter

# Namespaces
TG = Namespace("https://example.org/tourguide#")
SCHEMA = Namespace("http://schema.org/")
REVIEW_NS = Namespace("https://example.org/tourguide/review/")

# ❌ BLACKLIST : Entités à ignorer (bruit)
NOISE_KEYWORDS = {
    # Génériques
    'paris', 'nice', 'france', 'europe',
    # Faux positifs communs
    'service', 'bar', 'cafe', 'restaurant', 'brasserie',
    'i', 'we', 'be', 'it', 'ca', 'top',
    # Expressions
    'accueil', 'ambiance', 'endroit', 'terrasse',
    # Produits/marques génériques
    'burger', 'burgers', 'pizza', 'mojito', 'nutella',
    # Mots courts
    'cb', 'us', 'psg',
}

# ❌ Pattern à ignorer (startswith/contains)
NOISE_PATTERNS = [
    "service ",
    "l'",
    "j'",
    "c'",
    "it'",
    "@",
    "&#",
]

def load_kg_places(kg_path: str) -> set:
    """Charge la liste des lieux valides du KG"""
    print(f"📖 Chargement du KG : {kg_path}")
    kg = Graph()
    kg.parse(kg_path, format="turtle")
    
    places = set()
    query = """
    PREFIX tg: <https://example.org/tourguide#>
    SELECT ?place ?name
    WHERE {
        ?place a ?type ;
               tg:name ?name .
        FILTER(?type IN (tg:Place, tg:Restaurant, tg:Attraction, tg:POI))
    }
    """
    
    for row in kg.query(query):
        place_uri = str(row.place)
        place_name = str(row.name).strip().lower()
        places.add((place_uri, place_name))
    
    print(f"   ✓ {len(places):,} lieux valides")
    return places


def is_noise(entity_text: str) -> bool:
    """Détermine si une entité est du bruit"""
    text_lower = entity_text.lower().strip()
    
    # Filtre 1: Blacklist
    if text_lower in NOISE_KEYWORDS:
        return True
    
    # Filtre 2: Patterns
    for pattern in NOISE_PATTERNS:
        if pattern in text_lower:
            return True
    
    # Filtre 3: Trop court (< 3 caractères)
    if len(text_lower) < 3:
        return True
    
    # Filtre 4: Que des chiffres ou symboles
    if not any(c.isalpha() for c in text_lower):
        return True
    
    return False


def filter_ner_graph(input_ttl: str, output_ttl: str, kg_places: set):
    """
    Filtre le graphe NER pour enlever le bruit
    
    Args:
        input_ttl: Graphe NER original
        output_ttl: Graphe NER nettoyé
        kg_places: Set de (place_uri, place_name_lower) du KG
    """
    print(f"\n🧹 Nettoyage de {input_ttl}")
    
    g = Graph()
    g.parse(input_ttl, format="turtle")
    g.bind("tg", TG)
    g.bind("schema", SCHEMA)
    
    stats = {
        'reviews_original': 0,
        'mentions_original': 0,
        'mentions_filtered': 0,
        'reviews_kept': 0,
    }
    
    # Créer nouveau graphe nettoyé
    clean_g = Graph()
    clean_g.bind("tg", TG)
    clean_g.bind("schema", SCHEMA)
    clean_g.bind("rdfs", RDFS)
    
    # Récupérer toutes les reviews avec leurs mentions
    query = """
    PREFIX schema: <http://schema.org/>
    PREFIX tg: <https://example.org/tourguide#>
    
    SELECT ?review ?place ?entities
    WHERE {
        ?review a schema:Review .
        OPTIONAL { ?review schema:mentions ?place }
        OPTIONAL { ?review tg:extractedEntities ?entities }
    }
    """
    
    review_data = {}
    for row in g.query(query):
        review_uri = row.review
        if review_uri not in review_data:
            review_data[review_uri] = {
                'places': [],
                'entities_text': str(row.entities) if row.entities else ""
            }
        if row.place:
            review_data[review_uri]['places'].append(row.place)
    
    stats['reviews_original'] = len(review_data)
    
    # Filtrer review par review
    place_uri_to_name = {uri: name for uri, name in kg_places}
    
    for review_uri, data in review_data.items():
        places = data['places']
        stats['mentions_original'] += len(places)
        
        # Filtrer les mentions
        clean_places = []
        for place_uri in places:
            # Vérifier si le lieu existe dans le KG
            place_name = place_uri_to_name.get(str(place_uri))
            
            if place_name and not is_noise(place_name):
                clean_places.append(place_uri)
        
        # Garder la review si au moins 1 mention valide
        if clean_places:
            # Ajouter review
            clean_g.add((review_uri, RDF.type, SCHEMA.Review))
            
            # Ajouter mentions nettoyées
            for place_uri in clean_places:
                clean_g.add((review_uri, SCHEMA.mentions, URIRef(place_uri)))
                stats['mentions_filtered'] += 1
            
            # Ajouter métadonnées
            clean_g.add((review_uri, TG.hasExtractedEntities, 
                        Literal(len(clean_places), datatype=XSD.integer)))
            
            stats['reviews_kept'] += 1
    
    # Sauvegarder
    print(f"\n💾 Sauvegarde : {output_ttl}")
    Path(output_ttl).parent.mkdir(parents=True, exist_ok=True)
    clean_g.serialize(output_ttl, format="turtle")
    
    # Stats
    print("\n" + "="*70)
    print("✅ NETTOYAGE TERMINÉ")
    print("="*70)
    print(f"Reviews originales:       {stats['reviews_original']:,}")
    print(f"Reviews conservées:       {stats['reviews_kept']:,} "
          f"({stats['reviews_kept']/stats['reviews_original']*100:.1f}%)")
    print(f"\nMentions originales:      {stats['mentions_original']:,}")
    print(f"Mentions après filtrage:  {stats['mentions_filtered']:,} "
          f"({stats['mentions_filtered']/stats['mentions_original']*100:.1f}%)")
    print(f"Mentions supprimées:      {stats['mentions_original'] - stats['mentions_filtered']:,} "
          f"(bruit éliminé)")
    print(f"\nTriplets RDF générés:     {len(clean_g):,}")
    print("="*70)
    
    return stats


def main():
    # Chemins
    kg_path = "data/kg_inferred.ttl"
    input_ner = "data/kg_reviews_ner.ttl"
    output_ner = "data/kg_reviews_ner_clean.ttl"
    
    # Charger lieux valides
    kg_places = load_kg_places(kg_path)
    
    # Filtrer
    stats = filter_ner_graph(input_ner, output_ner, kg_places)
    
    print("\n📝 Prochaine étape :")
    print("   1. Remplace kg_reviews_ner.ttl par kg_reviews_ner_clean.ttl")
    print("   2. ou Fusionne directement dans kg_inferred.ttl")
    print("\nCommandes:")
    print("   mv data/kg_reviews_ner.ttl data/kg_reviews_ner_original.ttl")
    print("   mv data/kg_reviews_ner_clean.ttl data/kg_reviews_ner.ttl")
    print("\nPuis refusionne avec kg_inferred.ttl")


if __name__ == "__main__":
    main()
