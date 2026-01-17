#!/usr/bin/env python3
"""
Demo simple de recommandation via link prediction TransE
Utilise les entités réellement présentes dans le modèle entraîné
"""

import json
import torch
import gzip
import pandas as pd
from pathlib import Path
from rdflib import Graph, Namespace

# Namespaces
TG = Namespace("https://example.org/tourguide#")
SCHEMA = Namespace("http://schema.org/")

def load_model_and_mappings():
    """Charge le modèle TransE et les mappings"""
    print("Loading TransE model...")
    model_dir = Path("models")
    
    # Charger le modèle
    model_path = model_dir / "trained_model.pkl"
    model = torch.load(model_path, weights_only=False)
    
    # Charger les mappings
    triples_dir = model_dir / "training_triples"
    
    with gzip.open(triples_dir / "entity_to_id.tsv.gz", 'rt') as f:
        entity_df = pd.read_csv(f, sep='\t', header=None, names=['entity', 'id'])
    
    with gzip.open(triples_dir / "relation_to_id.tsv.gz", 'rt') as f:
        relation_df = pd.read_csv(f, sep='\t', header=None, names=['relation', 'id'])
    
    entity_to_id = dict(zip(entity_df['entity'], entity_df['id']))
    id_to_entity = dict(zip(entity_df['id'], entity_df['entity']))
    relation_to_id = dict(zip(relation_df['relation'], relation_df['id']))
    
    print(f"  ✓ Loaded {len(entity_to_id)} entities, {len(relation_to_id)} relations")
    
    return model, entity_to_id, id_to_entity, relation_to_id

def get_place_info(kg, place_uri):
    """Récupère les infos d'un lieu"""
    query = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    SELECT ?name ?type WHERE {{
        <{place_uri}> rdfs:label ?name .
        <{place_uri}> rdf:type ?type .
    }} LIMIT 1
    """
    results = list(kg.query(query))
    if results:
        return {
            'name': str(results[0][0]),
            'type': str(results[0][1]).split('#')[-1]
        }
    return {'name': place_uri, 'type': 'Unknown'}

def predict_top_places(model, entity_to_id, id_to_entity, relation_to_id, subject_uri, relation="likes", top_k=10):
    """
    Prédit les top-k lieux pour un sujet donné via une relation
    """
    if subject_uri not in entity_to_id:
        print(f"⚠ {subject_uri} not in training data")
        return []
    
    if relation not in relation_to_id:
        print(f"⚠ Relation {relation} not found. Available: {list(relation_to_id.keys())}")
        return []
    
    subject_id = entity_to_id[subject_uri]
    relation_id = relation_to_id[relation]
    
    print(f"\nPredicting top-{top_k} places for relation '{relation}'...")
    
    # Tester tous les objets possibles
    predictions = []
    all_entities = list(id_to_entity.keys())
    
    # Batch prediction pour aller plus vite
    batch_size = 1000
    for i in range(0, len(all_entities), batch_size):
        batch_ids = all_entities[i:i+batch_size]
        
        # Créer batch de triplets (subject, relation, object_candidate)
        batch = torch.tensor(
            [[subject_id, relation_id, obj_id] for obj_id in batch_ids],
            dtype=torch.long
        )
        
        # Prédire les scores
        with torch.no_grad():
            scores = model.score_hrt(batch)
        
        # Stocker (object_uri, score)
        for obj_id, score in zip(batch_ids, scores):
            obj_uri = id_to_entity[obj_id]
            # Filtrer les entités qui ressemblent à des lieux
            if 'place' in obj_uri or 'resource' in obj_uri:
                predictions.append((obj_uri, -score.item()))
    
    # Trier par score décroissant
    predictions.sort(key=lambda x: x[1], reverse=True)
    
    return predictions[:top_k]

def main():
    print("="*60)
    print("  DEMO: Link Prediction avec TransE")
    print("="*60)
    
    # Charger le modèle
    model, entity_to_id, id_to_entity, relation_to_id = load_model_and_mappings()
    
    # Charger le KG pour les métadonnées
    print("\nLoading knowledge graph for metadata...")
    kg = Graph()
    kg.parse("data/kg_inferred.ttl", format="turtle")
    print(f"  ✓ {len(kg)} triples loaded")
    
    # Trouver un exemple de sujet (review, touriste, etc.)
    print("\nFinding example entities...")
    example_subjects = [uri for uri in entity_to_id.keys() if 'review' in uri][:3]
    
    if not example_subjects:
        print("⚠ No suitable subjects found")
        return
    
    print(f"\nExample subjects found:")
    for i, subj in enumerate(example_subjects, 1):
        print(f"  {i}. {subj}")
    
    # Choisir le premier
    subject = example_subjects[0]
    
    print(f"\n{'='*60}")
    print(f"  PREDICTIONS FOR: {subject}")
    print(f"{'='*60}")
    
    # Relations disponibles
    print("\nAvailable relations:")
    for rel in relation_to_id.keys():
        print(f"  - {rel}")
    
    # Essayer de prédire avec la première relation
    relation = list(relation_to_id.keys())[0]
    
    predictions = predict_top_places(model, entity_to_id, id_to_entity, relation_to_id, subject, relation, top_k=10)
    
    if not predictions:
        print("\n❌ No predictions generated")
        return
    
    print(f"\n{'='*60}")
    print(f"  TOP-10 RECOMMENDATIONS")
    print(f"{'='*60}\n")
    
    for i, (place_uri, score) in enumerate(predictions, 1):
        place_info = get_place_info(kg, place_uri)
        print(f"{i}. {place_info['name']}")
        print(f"   Type: {place_info['type']}")
        print(f"   Score: {score:.4f}")
        print(f"   URI: {place_uri}")
        print()
    
    # Sauvegarder
    output = {
        'subject': subject,
        'relation': relation,
        'recommendations': [
            {'rank': i, 'uri': uri, 'score': score, 'info': get_place_info(kg, uri)}
            for i, (uri, score) in enumerate(predictions, 1)
        ]
    }
    
    output_file = "data/demo_recommendations.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Saved to: {output_file}")
    print("\n" + "="*60)
    print("  ✅ DEMO COMPLETED!")
    print("="*60)

if __name__ == "__main__":
    main()
