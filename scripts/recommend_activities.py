#!/usr/bin/env python3
"""
Script pour recommander des activités (randonnées vélo, restaurants, etc.) 
à un touriste via link prediction avec TransE
"""

import json
import torch
from pathlib import Path
from pykeen.models import TransE
from pykeen.triples import TriplesFactory
from rdflib import Graph, Namespace, RDF, RDFS

# Namespaces
TG = Namespace("https://example.org/tourguide#")
SCHEMA = Namespace("http://schema.org/")

def load_model(model_dir="models"):
    """Charge le modèle TransE entraîné"""
    print(f"Loading TransE model from {model_dir}...")
    import pickle
    import gzip
    import pandas as pd
    
    model_dir = Path(model_dir)
    
    # Charger le modèle avec weights_only=False pour PyTorch 2.6+
    model_path = model_dir / "trained_model.pkl"
    with open(model_path, 'rb') as f:
        model = torch.load(f, weights_only=False)
    
    # Charger les mappings entity/relation depuis les fichiers .tsv.gz
    triples_dir = model_dir / "training_triples"
    
    # Charger entity_to_id
    with gzip.open(triples_dir / "entity_to_id.tsv.gz", 'rt', encoding='utf-8') as f:
        entity_df = pd.read_csv(f, sep='\t', header=None, names=['entity', 'id'])
    entity_to_id = dict(zip(entity_df['entity'], entity_df['id']))
    id_to_entity = dict(zip(entity_df['id'], entity_df['entity']))
    
    # Charger relation_to_id
    with gzip.open(triples_dir / "relation_to_id.tsv.gz", 'rt', encoding='utf-8') as f:
        relation_df = pd.read_csv(f, sep='\t', header=None, names=['relation', 'id'])
    relation_to_id = dict(zip(relation_df['relation'], relation_df['id']))
    id_to_relation = dict(zip(relation_df['id'], relation_df['relation']))
    
    # Créer un objet simple pour stocker les mappings
    class SimpleTripleFactory:
        def __init__(self, entity_to_id, relation_to_id, id_to_entity, id_to_relation):
            self.entity_to_id = entity_to_id
            self.relation_to_id = relation_to_id
            self.id_to_entity = id_to_entity
            self.id_to_relation = id_to_relation
            self.num_entities = len(entity_to_id)
            self.num_relations = len(relation_to_id)
    
    triples_factory = SimpleTripleFactory(entity_to_id, relation_to_id, id_to_entity, id_to_relation)
    
    print(f"  ✓ Model loaded")
    print(f"  - Entities: {triples_factory.num_entities}")
    print(f"  - Relations: {triples_factory.num_relations}")
    return model, triples_factory

def load_knowledge_graph(kg_path="data/kg_inferred.ttl"):
    """Charge le graphe de connaissances pour récupérer les métadonnées"""
    print(f"\nLoading knowledge graph: {kg_path}")
    g = Graph()
    g.parse(kg_path, format="turtle")
    print(f"  ✓ {len(g)} triples loaded")
    return g

def get_places_by_category(kg, category):
    """
    Récupère tous les lieux d'une catégorie donnée
    
    Categories disponibles:
    - tg:Attraction (musées, monuments)
    - tg:Restaurant
    - tg:Accommodation
    - tg:POI (points d'intérêt divers)
    """
    query = f"""
    PREFIX tg: <https://example.org/tourguide#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT DISTINCT ?place ?name ?lat ?lng
    WHERE {{
        ?place rdf:type tg:{category} .
        OPTIONAL {{ ?place rdfs:label ?name }}
        OPTIONAL {{ ?place tg:lat ?lat }}
        OPTIONAL {{ ?place tg:lng ?lng }}
    }}
    LIMIT 100
    """
    results = kg.query(query)
    places = []
    for row in results:
        places.append({
            'uri': str(row.place),
            'name': str(row.name) if row.name else "Unknown",
            'lat': float(row.lat) if row.lat else None,
            'lng': float(row.lng) if row.lng else None
        })
    return places

def search_places_by_keyword(kg, keyword):
    """Recherche des lieux contenant un mot-clé (vélo, musée, etc.)"""
    query = f"""
    PREFIX tg: <https://example.org/tourguide#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT DISTINCT ?place ?name ?type
    WHERE {{
        ?place rdfs:label ?name .
        ?place rdf:type ?type .
        FILTER(CONTAINS(LCASE(?name), LCASE("{keyword}")))
    }}
    LIMIT 50
    """
    results = kg.query(query)
    places = []
    for row in results:
        places.append({
            'uri': str(row.place),
            'name': str(row.name),
            'type': str(row.type)
        })
    return places

def predict_likes(model, triples_factory, tourist_uri, place_uris, relation="likes"):
    """
    Prédit les scores de "like" pour un touriste et une liste de lieux
    
    Returns: Liste de (place_uri, score) triée par score décroissant
    """
    # Mapper les URIs vers les IDs du modèle
    entity_to_id = triples_factory.entity_to_id
    relation_to_id = triples_factory.relation_to_id
    
    if tourist_uri not in entity_to_id:
        print(f"⚠ Tourist {tourist_uri} not in training data")
        return []
    
    if relation not in relation_to_id:
        print(f"⚠ Relation {relation} not found")
        return []
    
    tourist_id = entity_to_id[tourist_uri]
    relation_id = relation_to_id[relation]
    
    # Préparer les triplets à prédire
    predictions = []
    for place_uri in place_uris:
        if place_uri not in entity_to_id:
            continue
        
        place_id = entity_to_id[place_uri]
        
        # Créer le tenseur (head, relation, tail)
        batch = torch.tensor([[tourist_id, relation_id, place_id]], dtype=torch.long)
        
        # Prédire le score (plus bas = meilleur)
        with torch.no_grad():
            score = model.score_hrt(batch).item()
        
        predictions.append((place_uri, -score))  # Négatif car TransE minimise
    
    # Trier par score décroissant
    predictions.sort(key=lambda x: x[1], reverse=True)
    return predictions

def recommend_activities(tourist_uri, activity_type="bike", top_k=10):
    """
    Recommande des activités à un touriste
    
    Args:
        tourist_uri: URI du touriste (ex: "http://example.org/tourist/1")
        activity_type: Type d'activité ("bike", "museum", "restaurant")
        top_k: Nombre de recommandations
    """
    print(f"\n{'='*60}")
    print(f"  RECOMMENDATIONS FOR: {tourist_uri}")
    print(f"  Activity type: {activity_type}")
    print(f"{'='*60}\n")
    
    # Charger le modèle et le graphe
    model, triples_factory = load_model()
    kg = load_knowledge_graph()
    
    # Rechercher les lieux selon le type d'activité
    if activity_type == "bike":
        keyword = "vélo"
    elif activity_type == "museum":
        keyword = "musée"
    elif activity_type == "restaurant":
        keyword = "restaurant"
    else:
        keyword = activity_type
    
    places = search_places_by_keyword(kg, keyword)
    print(f"\nFound {len(places)} places matching '{keyword}'")
    
    if not places:
        print("⚠ No places found, trying by category...")
        places = get_places_by_category(kg, "Attraction")
    
    # Prédire les scores
    place_uris = [p['uri'] for p in places]
    predictions = predict_likes(model, triples_factory, tourist_uri, place_uris)
    
    if not predictions:
        print("\n❌ No predictions available")
        return
    
    # Afficher les top-k recommandations
    print(f"\n{'='*60}")
    print(f"  TOP {top_k} RECOMMENDATIONS")
    print(f"{'='*60}\n")
    
    place_dict = {p['uri']: p for p in places}
    
    for i, (place_uri, score) in enumerate(predictions[:top_k], 1):
        place_info = place_dict.get(place_uri, {})
        name = place_info.get('name', place_uri)
        print(f"{i}. {name}")
        print(f"   Score: {score:.4f}")
        print(f"   URI: {place_uri}")
        if place_info.get('lat') and place_info.get('lng'):
            print(f"   Location: {place_info['lat']}, {place_info['lng']}")
        print()
    
    # Sauvegarder les résultats
    output = {
        'tourist': tourist_uri,
        'activity_type': activity_type,
        'recommendations': [
            {
                'rank': i,
                'place_uri': uri,
                'place_name': place_dict.get(uri, {}).get('name', uri),
                'score': score
            }
            for i, (uri, score) in enumerate(predictions[:top_k], 1)
        ]
    }
    
    output_file = f"data/recommendations_{activity_type}_{tourist_uri.split('/')[-1]}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Recommendations saved to: {output_file}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Recommend activities using TransE link prediction")
    parser.add_argument("--tourist", required=True, help="Tourist URI (e.g., http://example.org/tourist/1)")
    parser.add_argument("--activity", default="bike", help="Activity type: bike, museum, restaurant")
    parser.add_argument("--top_k", type=int, default=10, help="Number of recommendations")
    
    args = parser.parse_args()
    
    recommend_activities(args.tourist, args.activity, args.top_k)
