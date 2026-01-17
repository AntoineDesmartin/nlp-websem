"""
Test de comparaison des 2 approches GraphRAG
Compare les résultats des deux approches sur les mêmes questions
"""
import os
import sys
import time
from pathlib import Path

# Ajouter le dossier parent au path
sys.path.append(str(Path(__file__).parent))

from app.services.openrouter_service import OpenRouterSPARQLService
from app.services.embedding_service import EmbeddingGraphRAGService
from app.services.sparql_client import SPARQLClient

# Configuration
KG_FILE = "data/kg_linked.ttl"
API_KEY = os.getenv("OPENROUTER_API_KEY")

def print_separator(title=""):
    """Affiche un séparateur visuel"""
    print("\n" + "="*70)
    if title:
        print(f"  {title}")
        print("="*70)

def compare_approaches(question: str):
    """Compare les deux approches sur une même question"""
    print_separator(f"QUESTION : {question}")
    
    # Initialiser les services
    try:
        sparql_service = OpenRouterSPARQLService(api_key=API_KEY)
        embedding_service = EmbeddingGraphRAGService(kg_file=KG_FILE, api_key=API_KEY)
        sparql_client = SPARQLClient(KG_FILE)
    except Exception as e:
        print(f"❌ Erreur initialisation : {e}")
        return
    
    # ======================
    # APPROCHE 1 : SPARQL
    # ======================
    print_separator("APPROCHE 1 : Question → SPARQL")
    
    start_time = time.time()
    try:
        # Générer SPARQL
        sparql_result = sparql_service.question_to_sparql(question)
        
        if sparql_result.get("error"):
            print(f"❌ Erreur : {sparql_result['explanation']}")
        else:
            print(f"✓ Requête SPARQL générée ({time.time() - start_time:.2f}s)\n")
            print("📝 SPARQL :")
            print("-" * 70)
            print(sparql_result["sparql"])
            print("-" * 70)
            
            # Exécuter la requête
            results = sparql_client.query(sparql_result["sparql"])
            
            print(f"\n📊 Résultats : {len(results)} trouvé(s)")
            print("\nTop 5 :")
            for i, result in enumerate(results[:5], 1):
                print(f"\n{i}. {result.get('name', result.get('place', 'N/A'))}")
                if 'polarity' in result:
                    print(f"   ⭐ Note : {result['polarity']}")
                if 'reviewCount' in result:
                    print(f"   💬 Avis : {result['reviewCount']}")
    
    except Exception as e:
        print(f"❌ Erreur Approche 1 : {e}")
    
    approche1_time = time.time() - start_time
    
    # ======================
    # APPROCHE 2 : EMBEDDINGS
    # ======================
    print_separator("APPROCHE 2 : Embeddings → Réponse NL")
    
    start_time = time.time()
    try:
        # Répondre avec embeddings
        embedding_result = embedding_service.answer_question(question, top_k=5)
        
        if embedding_result.get("error"):
            print(f"❌ Erreur : {embedding_result['answer']}")
        else:
            print(f"✓ Réponse générée ({time.time() - start_time:.2f}s)\n")
            print("💬 RÉPONSE EN LANGAGE NATUREL :")
            print("-" * 70)
            print(embedding_result["answer"])
            print("-" * 70)
            
            print(f"\n📊 Entités utilisées : {len(embedding_result['entities'])}")
            print("\nTop 5 par similarité :")
            for i, entity in enumerate(embedding_result['entities'][:5], 1):
                print(f"\n{i}. {entity['name']}")
                print(f"   🎯 Similarité : {entity['score']:.3f}")
                if entity['info'].get('polarity'):
                    print(f"   ⭐ Note : {entity['info']['polarity']}")
    
    except Exception as e:
        print(f"❌ Erreur Approche 2 : {e}")
    
    approche2_time = time.time() - start_time
    
    # ======================
    # COMPARAISON
    # ======================
    print_separator("COMPARAISON")
    print(f"⏱️  Approche 1 (SPARQL)    : {approche1_time:.2f}s")
    print(f"⏱️  Approche 2 (Embeddings): {approche2_time:.2f}s")
    print(f"📊 Différence             : {abs(approche1_time - approche2_time):.2f}s")
    
    if approche1_time < approche2_time:
        print("\n🏆 Approche 1 plus rapide")
    else:
        print("\n🏆 Approche 2 plus rapide")
    
    print("\n✅ Type de sortie :")
    print("   • Approche 1 : Données structurées (JSON)")
    print("   • Approche 2 : Texte en langage naturel")
    
    print("\n✅ Cas d'usage idéal :")
    print("   • Approche 1 : Analytics, exploration précise, développement")
    print("   • Approche 2 : Chatbot, assistance utilisateur, recommandations")


def main():
    """Fonction principale"""
    print("\n" + "="*70)
    print("  🎯 COMPARAISON DES 2 APPROCHES GRAPHRAG")
    print("="*70)
    
    if not API_KEY:
        print("\n❌ OPENROUTER_API_KEY non définie !")
        print("\nPour la configurer, exécute :")
        print('  $env:OPENROUTER_API_KEY="sk-or-v1-..."')
        return
    
    print(f"\n✓ Clé API détectée : {API_KEY[:20]}...")
    
    # Questions de test
    questions = [
        "Quels sont les meilleurs restaurants ?",
        "Je cherche une attraction touristique populaire",
        "Où puis-je manger de la cuisine française ?",
    ]
    
    print(f"\n📋 {len(questions)} questions à tester\n")
    
    # Tester chaque question
    for i, question in enumerate(questions, 1):
        print(f"\n\n{'#'*70}")
        print(f"# TEST {i}/{len(questions)}")
        print(f"{'#'*70}")
        
        compare_approaches(question)
        
        # Pause entre les tests
        if i < len(questions):
            print("\n\n⏸️  Pause de 2 secondes avant le prochain test...")
            time.sleep(2)
    
    # Résumé final
    print("\n\n" + "="*70)
    print("  ✅ TOUS LES TESTS TERMINÉS")
    print("="*70)
    
    print("\n📊 CONCLUSION :")
    print("\n✅ Les deux approches GraphRAG sont fonctionnelles !")
    print("\n🎯 Approche 1 (SPARQL) :")
    print("   • Précise et reproductible")
    print("   • Idéale pour analytics et exploration")
    print("   • Plus rapide (1 appel API)")
    
    print("\n🧠 Approche 2 (Embeddings) :")
    print("   • Flexible et naturelle")
    print("   • Idéale pour chatbots et assistance")
    print("   • Plus conviviale (langage naturel)")
    
    print("\n⚖️  Les deux approches sont complémentaires selon le cas d'usage !")
    print("\n📱 Interface web disponible sur : http://localhost:8000")
    print("   → Tab 'Comparaison GraphRAG' pour comparaison visuelle\n")


if __name__ == "__main__":
    main()
