"""
Script de test pour GraphRAG Approche 2 : Embeddings
Teste la génération de réponses en langage naturel via embeddings
"""
import os
import sys
sys.path.append('.')

from app.services.embedding_service import EmbeddingGraphRAGService


def test_embedding_approach():
    """Test de l'approche embeddings"""
    print("="*70)
    print("TEST : GraphRAG Approche 2 - Embeddings + Réponses NL")
    print("="*70)
    
    # Vérifier la clé API
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("\n❌ OPENROUTER_API_KEY non définie !")
        print("💡 Définis-la avec:")
        print('   $env:OPENROUTER_API_KEY="sk-or-v1-..."')
        return
    
    print(f"\n✓ Clé API détectée : {api_key[:20]}...{api_key[-8:]}")
    
    # Initialiser le service
    try:
        service = EmbeddingGraphRAGService(
            kg_file="data/kg_linked.ttl",
            api_key=api_key
        )
        print("✓ Service embeddings initialisé")
        
    except Exception as e:
        print(f"\n❌ Erreur d'initialisation : {e}")
        return
    
    # Générer les embeddings (première fois seulement)
    print("\n" + "="*70)
    print("GÉNÉRATION DES EMBEDDINGS (peut prendre 1-2 minutes)")
    print("="*70)
    service.build_embeddings(limit=30)  # Limiter à 30 pour le test
    
    # Questions de test
    questions = [
        "Quels sont les meilleurs restaurants ?",
        "Je cherche une attraction touristique populaire",
        "Où puis-je manger de la cuisine française ?",
    ]
    
    for i, question in enumerate(questions, 1):
        print("\n" + "="*70)
        print(f"TEST {i}/{len(questions)}")
        print("="*70)
        
        result = service.answer_question(question, top_k=5)
        
        if result.get("error"):
            print(f"\n❌ Erreur : {result['answer']}")
        else:
            print(f"\n✅ RÉPONSE EN LANGAGE NATUREL :")
            print("-" * 70)
            print(result['answer'])
            print("-" * 70)
            
            print(f"\n📊 Entités utilisées ({len(result['entities'])}) :")
            for entity in result['entities'][:3]:
                print(f"   - {entity['name']} ({entity['type']}) - Score: {entity['score']:.3f}")


def main():
    print("\n🧪 TESTS GraphRAG Approche 2 : Embeddings + Réponses NL\n")
    
    test_embedding_approach()
    
    print("\n" + "="*70)
    print("✅ TESTS TERMINÉS")
    print("="*70)
    print("\n💡 Les embeddings sont maintenant en cache (data/embeddings_cache.pkl)")
    print("   Les prochains tests seront plus rapides !")


if __name__ == "__main__":
    main()
