#!/usr/bin/env python3
"""
Démo fonctionnelle de link prediction avec TransE
Recommande des lieux basés sur les préférences
"""

import json
import torch
import gzip
import pandas as pd
from pathlib import Path
from rdflib import Graph, Namespace, RDF, RDFS

def load_model_and_mappings():
    """Charge le modèle TransE et les mappings"""
    print("Loading TransE model...")
    model_dir = Path("models")
    
    # Charger le modèle
    model_path = model_dir / "trained_model.pkl"
    model = torch.load(model_path, weights_only=False)
    
    # Charger les mappings (skip header row)
    triples_dir = model_dir / "training_triples"
    
    with gzip.open(triples_dir / "entity_to_id.tsv.gz", 'rt', encoding='utf-8') as f:
        lines = [line.strip().split('\t') for line in f if '\t' in line]
        # Skip if first column is not numeric
        entity_to_id = {}
        id_to_entity = {}
        for parts in lines:
            if len(parts) >= 2:
                try:
                    eid = int(parts[0])
                    entity = parts[1]
                    entity_to_id[entity] = eid
                    id_to_entity[eid] = entity
                except ValueError:
                    continue
    
    with gzip.open(triples_dir / "relation_to_id.tsv.gz", 'rt', encoding='utf-8') as f:
        lines = [line.strip().split('\t') for line in f if '\t' in line]
        relation_to_id = {}
        id_to_relation = {}
        for parts in lines:
            if len(parts) >= 2:
                try:
                    rid = int(parts[0])
                    relation = parts[1]
                    relation_to_id[relation] = rid
                    id_to_relation[rid] = relation
                except ValueError:
                    continue
    
    print(f"  ✓ Loaded {len(entity_to_id)} entities, {len(relation_to_id)} relations")
    
    return model, entity_to_id, id_to_entity, relation_to_id, id_to_relation

def get_place_info(kg, place_uri):
    """Récupère les infos d'un lieu depuis le KG"""
    query = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    SELECT ?name ?type WHERE {{
        <{place_uri}> rdfs:label ?name .
        OPTIONAL {{ <{place_uri}> rdf:type ?type }}
    }} LIMIT 1
    """
    results = list(kg.query(query))
    if results:
        type_name = str(results[0][1]).split('#')[-1] if results[0][1] else 'Place'
        return {
            'name': str(results[0][0]),
            'type': type_name
        }
    return {'name': place_uri.split('/')[-1], 'type': 'Unknown'}

def predict_places_for_topic(model, entity_to_id, id_to_entity, relation_to_id, topic_uri, top_k=10):
    """
    Prédit les lieux qui correspondent à un topic via hasTopic
    Ex: Culture -> quels lieux ont le topic Culture?
    """
    relation = "https://example.org/tourguide#hasTopic"
    
    if topic_uri not in entity_to_id:
        print(f"⚠ Topic {topic_uri} not in model")
        return []
    
    if relation not in relation_to_id:
        print(f"⚠ Relation {relation} not found")
        return []
    
    topic_id = entity_to_id[topic_uri]
    relation_id = relation_to_id[relation]
    
    print(f"Predicting places for topic: {topic_uri}...")
    
    # Filtrer les entités qui sont des lieux (places)
    place_ids = [eid for uri, eid in entity_to_id.items() 
                 if 'place' in uri.lower() or 'resource' in uri.lower()]
    
    if not place_ids:
        print("⚠ No places found in model")
        return []
    
    print(f"  Testing {len(place_ids)} places...")
    
    # Batch prediction
    predictions = []
    batch_size = 1000
    
    for i in range(0, len(place_ids), batch_size):
        batch_ids = place_ids[i:i+batch_size]
        
        # (place, hasTopic, topic)
        batch = torch.tensor(
            [[place_id, relation_id, topic_id] for place_id in batch_ids],
            dtype=torch.long
        )
        
        with torch.no_grad():
            scores = model.score_hrt(batch)
        
        for place_id, score in zip(batch_ids, scores):
            place_uri = id_to_entity[place_id]
            predictions.append((place_uri, -score.item()))  # Negative because TransE minimizes
    
    # Trier par score décroissant
    predictions.sort(key=lambda x: x[1], reverse=True)
    
    return predictions[:top_k]

def main():
    print("="*70)
    print("  DEMO: Recommandation de lieux par topic (Link Prediction TransE)")
    print("="*70)
    
    # Charger le modèle
    model, entity_to_id, id_to_entity, relation_to_id, id_to_relation = load_model_and_mappings()
    
    # Charger le KG
    print("\nLoading knowledge graph...")
    kg = Graph()
    kg.parse("data/kg_inferred.ttl", format="turtle")
    print(f"  ✓ {len(kg)} triples loaded")
    
    # Trouver les topics disponibles
    topics = [uri for uri in entity_to_id.keys() if 'tourguide#' in uri and uri.split('#')[-1][0].isupper()]
    
    print(f"\n=== AVAILABLE TOPICS ({len(topics)}) ===")
    for i, topic in enumerate(topics, 1):
        print(f"  {i}. {topic.split('#')[-1]}")
    
    if not topics:
        print("⚠ No topics found")
        return
    
    # Prédire pour chaque topic
    all_results = {}
    
    for topic in topics[:3]:  # Top 3 topics pour la demo
        topic_name = topic.split('#')[-1]
        print(f"\n{'='*70}")
        print(f"  RECOMMENDATIONS FOR TOPIC: {topic_name}")
        print(f"{'='*70}")
        
        predictions = predict_places_for_topic(
            model, entity_to_id, id_to_entity, relation_to_id, topic, top_k=10
        )
        
        if not predictions:
            print("  ❌ No predictions")
            continue
        
        print(f"\n  TOP-10 PLACES:")
        print(f"  {'-'*66}\n")
        
        results = []
        for i, (place_uri, score) in enumerate(predictions, 1):
            place_info = get_place_info(kg, place_uri)
            print(f"  {i}. {place_info['name']}")
            print(f"     Type: {place_info['type']} | Score: {score:.4f}")
            print(f"     URI: {place_uri}\n")
            
            results.append({
                'rank': i,
                'uri': place_uri,
                'name': place_info['name'],
                'type': place_info['type'],
                'score': score
            })
        
        all_results[topic_name] = results
    
    # Sauvegarder
    output_file = "data/topic_recommendations.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*70}")
    print(f"  ✅ DEMO COMPLETED!")
    print(f"  Results saved to: {output_file}")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
