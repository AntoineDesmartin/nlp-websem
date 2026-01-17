"""
Regénération du cache d'embeddings avec une distribution équilibrée
100 Restaurants + 100 Attractions + 100 POI (top rated)
"""

import os
from app.services.embedding_service import EmbeddingGraphRAGService

def regenerate_balanced_embeddings():
    """Regénère les embeddings avec une distribution équilibrée par type"""
    
    print("=" * 80)
    print("🔄 RÉGÉNÉRATION DU CACHE D'EMBEDDINGS (ÉQUILIBRÉ)")
    print("=" * 80)
    
    # Vérifier la clé API
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ OPENROUTER_API_KEY non définie dans l'environnement")
        return
    
    # Supprimer l'ancien cache
    cache_file = "data/embeddings_cache.pkl"
    if os.path.exists(cache_file):
        os.remove(cache_file)
        print(f"✓ Ancien cache supprimé : {cache_file}")
    
    # Initialiser le service
    service = EmbeddingGraphRAGService(
        kg_file="data/kg_inferred.ttl",
        api_key=api_key
    )
    
    print("\n📊 Génération des embeddings par type...")
    print("-" * 80)
    
    # Requête SPARQL pour obtenir des entités équilibrées
    query = """
    PREFIX tg: <https://example.org/tourguide#>
    PREFIX schema: <http://schema.org/>
    
    SELECT ?place ?type
    WHERE {
        ?place a ?type .
        FILTER (?type IN (tg:Restaurant, tg:Attraction, tg:POI))
        
        # Prioriser les lieux avec des avis
        OPTIONAL { ?place tg:numReviews ?reviews }
    }
    ORDER BY DESC(?reviews)
    """
    
    results = service.graph.query(query)
    
    # Organiser par type
    entities_by_type = {
        "Restaurant": [],
        "Attraction": [],
        "POI": []
    }
    
    for row in results:
        place_uri = str(row.place)
        type_str = str(row.type).split("#")[-1]
        
        if type_str in entities_by_type and len(entities_by_type[type_str]) < 100:
            entities_by_type[type_str].append(place_uri)
    
    print("\n📋 Distribution des entités sélectionnées :")
    for type_name, entities in entities_by_type.items():
        print(f"   - {type_name}: {len(entities)} entités")
    
    # Générer les embeddings pour chaque type
    total_count = 0
    for type_name, entities in entities_by_type.items():
        print(f"\n🔄 Génération des embeddings pour {type_name}...")
        
        for i, entity_uri in enumerate(entities, 1):
            if entity_uri in service.entity_embeddings:
                continue
            
            # Extraire infos
            info = service._extract_entity_info(entity_uri)
            text = service._build_entity_text(info)
            
            # Générer embedding
            embedding = service._get_embedding(text)
            
            if embedding is not None:
                # Stocker
                service.entity_embeddings[entity_uri] = embedding
                service.entity_info[entity_uri] = info
                total_count += 1
            
            if i % 20 == 0:
                print(f"   Progression : {i}/{len(entities)}")
    
    print(f"\n✓ {total_count} embeddings générés au total")
    
    # Sauvegarder
    service._save_embeddings()
    
    print("\n" + "=" * 80)
    print("✅ CACHE RÉGÉNÉRÉ AVEC SUCCÈS")
    print("=" * 80)
    
    # Vérifier la distribution
    type_counts = {}
    for info in service.entity_info.values():
        entity_type = info.get("type", "Unknown")
        type_counts[entity_type] = type_counts.get(entity_type, 0) + 1
    
    print("\n📊 Distribution finale du cache :")
    for type_name, count in type_counts.items():
        print(f"   - {type_name}: {count}")

if __name__ == "__main__":
    regenerate_balanced_embeddings()
