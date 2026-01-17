#!/usr/bin/env python3
"""
Script pour régénérer le cache d'embeddings avec les MEILLEURS lieux
Stratégie : Sélectionner les lieux avec le plus d'avis et les meilleures notes
"""
import os
import sys
from pathlib import Path

# Ajouter le dossier parent au path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.embedding_service import EmbeddingGraphRAGService
from app.config import KG_FILE, OPENROUTER_API_KEY

def main():
    print("🔨 Régénération du cache d'embeddings OPTIMISÉ")
    print("=" * 60)
    
    # Initialiser le service
    service = EmbeddingGraphRAGService(
        kg_file=str(KG_FILE),
        api_key=OPENROUTER_API_KEY
    )
    
    # Supprimer l'ancien cache si existant
    cache_file = Path("data/embeddings_cache.pkl")
    if cache_file.exists():
        cache_file.unlink()
        print("✓ Ancien cache supprimé")
    
    # Réinitialiser les embeddings
    service.entity_embeddings = {}
    service.entity_info = {}
    
    # Générer les embeddings pour les 500 MEILLEURS lieux
    # (triés par nombre d'avis DESC, puis note DESC)
    print("\n🎯 Génération des embeddings pour les 500 meilleurs lieux...")
    print("   Critères : Nombre d'avis (priorité) + Note")
    
    service.build_embeddings(limit=500)
    
    print("\n" + "=" * 60)
    print("✅ Cache d'embeddings optimisé généré !")
    print(f"📊 Total : {len(service.entity_embeddings)} embeddings")
    print(f"💾 Fichier : data/embeddings_cache.pkl")
    
    # Afficher quelques exemples
    print("\n📋 Quelques exemples (5 premiers) :")
    for i, (uri, info) in enumerate(list(service.entity_info.items())[:5], 1):
        name = info.get('name', 'N/A')
        polarity = info.get('polarity', 'N/A')
        num_reviews = info.get('numReviews', 'N/A')
        entity_type = info.get('type', 'N/A')
        print(f"   {i}. {name} ({entity_type})")
        print(f"      ⭐ {polarity}/10  📝 {num_reviews} avis")

if __name__ == '__main__':
    main()
