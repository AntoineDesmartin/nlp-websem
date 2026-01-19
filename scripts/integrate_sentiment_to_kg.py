#!/usr/bin/env python3
"""
Intègre les résultats d'analyse de sentiment dans le graphe de connaissances
Ajoute les scores de sentiment PAR LIEU pour requêtes SPARQL

"""

import json
from pathlib import Path
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, XSD

# Namespaces
TG = Namespace("https://example.org/tourguide#")
SCHEMA = Namespace("http://schema.org/")
PLACE_NS = Namespace("https://example.org/tourguide/place/")

def load_sentiment_by_place():
    """Charge les sentiments agrégés par lieu"""
    sentiment_file = Path("data/sentiment_by_place.json")
    
    if not sentiment_file.exists():
        raise FileNotFoundError(
            "sentiment_by_place.json not found. "
            "Run: python3 scripts/analyze_sentiment.py --sample 43717"
        )
    
    with open(sentiment_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_kg_places():
    """Charge les URIs des lieux depuis le KG"""
    print("📖 Chargement des lieux du KG...")
    kg = Graph()
    kg.parse("data/kg_inferred.ttl", format="turtle")
    
    # Récupérer mapping place_id → URI
    query = """
    PREFIX tg: <https://example.org/tourguide#>
    SELECT ?place ?id
    WHERE {
        ?place a ?type ;
               tg:placeId ?id .
        FILTER(?type IN (tg:Place, tg:Restaurant, tg:Attraction, tg:POI, tg:Accommodation))
    }
    """
    
    place_map = {}
    for row in kg.query(query):
        place_id = str(row.id)
        place_uri = str(row.place)
        place_map[place_id] = URIRef(place_uri)
    
    print(f"   ✓ {len(place_map):,} lieux trouvés")
    return place_map


def generate_sentiment_rdf(sentiment_data, place_map):
    """
    Génère triplets RDF avec sentiment PAR LIEU
    
    Args:
        sentiment_data: Dict {place_id: {sentiment stats}}
        place_map: Dict {place_id: URI}
    
    Returns:
        Graph RDF
    """
    print(f"\n🔧 Génération des triplets RDF sentiment...")
    
    g = Graph()
    g.bind("tg", TG)
    g.bind("schema", SCHEMA)
    
    matched = 0
    skipped = 0
    
    for place_id, stats in sentiment_data.items():
        # Vérifier si le lieu existe dans le KG
        if place_id not in place_map:
            skipped += 1
            continue
        
        place_uri = place_map[place_id]
        
        # Ajouter triplets sentiment
        g.add((place_uri, TG.avgSentiment, 
               Literal(stats['avg_sentiment'], datatype=XSD.decimal)))
        
        g.add((place_uri, TG.sentimentReviewsAnalyzed, 
               Literal(stats['total_reviews'], datatype=XSD.integer)))
        
        g.add((place_uri, TG.sentimentPositiveCount, 
               Literal(stats['positive_count'], datatype=XSD.integer)))
        
        g.add((place_uri, TG.sentimentNeutralCount, 
               Literal(stats['neutral_count'], datatype=XSD.integer)))
        
        g.add((place_uri, TG.sentimentNegativeCount, 
               Literal(stats['negative_count'], datatype=XSD.integer)))
        
        g.add((place_uri, TG.sentimentPositivePercent, 
               Literal(stats['positive_percent'], datatype=XSD.decimal)))
        
        g.add((place_uri, TG.sentimentNegativePercent, 
               Literal(stats['negative_percent'], datatype=XSD.decimal)))
        
        matched += 1
    
    # Stats globales
    stats_uri = URIRef("https://example.org/tourguide/sentiment-stats")
    
    # Charger stats globales
    with open("data/sentiment_stats.json", 'r', encoding='utf-8') as f:
        global_stats = json.load(f)
    
    g.add((stats_uri, RDF.type, TG.SentimentStatistics))
    g.add((stats_uri, TG.totalReviewsAnalyzed, 
           Literal(global_stats['total_reviews_analyzed'], datatype=XSD.integer)))
    g.add((stats_uri, TG.positivePercentage, 
           Literal(global_stats['sentiment_percentages']['positive'], datatype=XSD.decimal)))
    g.add((stats_uri, TG.neutralPercentage, 
           Literal(global_stats['sentiment_percentages']['neutral'], datatype=XSD.decimal)))
    g.add((stats_uri, TG.negativePercentage, 
           Literal(global_stats['sentiment_percentages']['negative'], datatype=XSD.decimal)))
    g.add((stats_uri, TG.averageSentimentScore, 
           Literal(global_stats['average_sentiment_score'], datatype=XSD.decimal)))
    g.add((stats_uri, TG.contradictionsFound, 
           Literal(global_stats['contradictions_found'], datatype=XSD.integer)))
    g.add((stats_uri, RDFS.label, Literal("Sentiment Analysis Statistics", lang="en")))
    
    print(f"   ✓ {matched:,} lieux enrichis avec sentiment")
    print(f"   ⚠ {skipped:,} lieux skippés (pas dans KG)")
    print(f"   ✓ {len(g):,} triplets générés")
    
    return g


def main():
    print("="*70)
    print("🔄 INTÉGRATION SENTIMENT → GRAPHE DE CONNAISSANCES")
    print("="*70)
    
    # 1. Charger données
    sentiment_data = load_sentiment_by_place()
    print(f"✓ {len(sentiment_data):,} lieux avec sentiment chargés")
    
    place_map = load_kg_places()
    
    # 2. Générer RDF
    sentiment_graph = generate_sentiment_rdf(sentiment_data, place_map)
    
    # 3. Sauvegarder graph sentiment
    output_file = "data/kg_sentiment.ttl"
    print(f"\n💾 Sauvegarde : {output_file}")
    sentiment_graph.serialize(output_file, format="turtle")
    
    # 4. Fusionner avec kg_inferred
    print("\n🔗 Fusion avec kg_inferred.ttl...")
    kg = Graph()
    kg.parse("data/kg_inferred.ttl", format="turtle")
    before = len(kg)
    
    # Ajouter sentiment
    kg += sentiment_graph
    after = len(kg)
    
    # Sauvegarder
    kg.serialize("data/kg_inferred.ttl", format="turtle")
    
    print("\n" + "="*70)
    print("✅ INTÉGRATION TERMINÉE")
    print("="*70)
    print(f"Triplets avant:         {before:,}")
    print(f"Triplets sentiment:     {after - before:,}")
    print(f"Triplets après:         {after:,}")
    print(f"\nFichiers:")
    print(f"  - {output_file}")
    print(f"  - data/kg_inferred.ttl (mis à jour)")
    print("\n💡 Exemple requête SPARQL:")
    print("""
    PREFIX tg: <https://example.org/tourguide#>
    
    SELECT ?place ?name ?polarity ?sentiment ?posPercent
    WHERE {
      ?place tg:name ?name ;
             tg:polarity ?polarity ;
             tg:avgSentiment ?sentiment ;
             tg:sentimentPositivePercent ?posPercent ;
             tg:sentimentReviewsAnalyzed ?count .
      FILTER(?count >= 10)
    }
    ORDER BY DESC(?sentiment)
    LIMIT 20
    """)
    print("="*70)


if __name__ == "__main__":
    main()
