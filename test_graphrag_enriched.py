"""
Test de comparaison GraphRAG AMÉLIORÉ
Montre l'impact des données enrichies (kg_inferred.ttl) vs kg_linked.ttl
"""
import os
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from app.services.openrouter_service import OpenRouterSPARQLService
from app.services.embedding_service import EmbeddingGraphRAGService
from app.services.sparql_client import SPARQLClient

# Configuration
API_KEY = os.getenv("OPENROUTER_API_KEY")

def print_separator(title="", char="="):
    """Affiche un séparateur visuel"""
    print("\n" + char*70)
    if title:
        print(f"  {title}")
        print(char*70)

def compare_kg_versions():
    """Compare les résultats sur kg_linked vs kg_inferred"""
    print_separator("COMPARAISON DES VERSIONS DU GRAPHE", "=")
    
    questions_test = [
        "Trouve les hidden gems (joyaux cachés)",
        "Quels sont les lieux très bien notés (highly rated) ?",
        "Restaurants populaires avec beaucoup d'avis"
    ]
    
    for kg_file, kg_name in [
        ("data/kg_linked.ttl", "KG_LINKED (sans inférence)"),
        ("data/kg_inferred.ttl", "KG_INFERRED (avec inférence)")
    ]:
        print_separator(f"GRAPHE: {kg_name}")
        
        try:
            client = SPARQLClient(kg_file)
            service = OpenRouterSPARQLService(api_key=API_KEY)
            
            # Tester une question sur les classes inférées
            question = "Trouve les hidden gems (joyaux cachés)"
            print(f"\n🎯 Question: {question}\n")
            
            result = service.question_to_sparql(question)
            
            if not result.get("error"):
                print("📝 SPARQL généré:")
                print("-" * 70)
                print(result["sparql"][:500] + "..." if len(result["sparql"]) > 500 else result["sparql"])
                print("-" * 70)
                
                # Exécuter
                try:
                    results = client.query(result["sparql"])
                    print(f"\n✅ Résultats: {len(results)} trouvé(s)")
                    
                    if len(results) > 0:
                        print("\nTop 3:")
                        for i, r in enumerate(results[:3], 1):
                            name = r.get("name") or r.get("label", "N/A")
                            rating = r.get("polarity") or r.get("inferredRating", "N/A")
                            print(f"  {i}. {name} - Note: {rating}")
                    else:
                        print("  ⚠️ Aucun résultat (classe inférée non disponible)")
                except Exception as e:
                    print(f"  ❌ Erreur exécution: {e}")
            
        except FileNotFoundError:
            print(f"\n⚠️ Fichier {kg_file} non trouvé")
        except Exception as e:
            print(f"\n❌ Erreur: {e}")
        
        time.sleep(1)

def test_enriched_queries():
    """Teste des requêtes exploitant les données enrichies"""
    print_separator("TESTS DES REQUÊTES ENRICHIES", "=")
    
    if not API_KEY:
        print("\n❌ OPENROUTER_API_KEY non définie!")
        return
    
    service = OpenRouterSPARQLService(api_key=API_KEY)
    client = SPARQLClient("data/kg_inferred.ttl")
    
    questions_enrichies = [
        "Quels sont les TopRestaurant ?",
        "Lieux HighlyRated avec leurs raisons d'inférence",
        "Places populaires (PopularPlace) avec liens Wikidata",
        "Calcule la note moyenne des reviews Schema.org par lieu"
    ]
    
    for i, question in enumerate(questions_enrichies, 1):
        print(f"\n{'='*70}")
        print(f"TEST {i}/{len(questions_enrichies)}: {question}")
        print("="*70)
        
        result = service.question_to_sparql(question)
        
        if result.get("error"):
            print(f"❌ Erreur: {result['explanation']}")
        else:
            print("\n📝 SPARQL généré:")
            print("-" * 70)
            print(result["sparql"])
            print("-" * 70)
            
            try:
                results = client.query(result["sparql"])
                print(f"\n✅ Résultats: {len(results)}")
                
                if results:
                    print("\nExtraits:")
                    for j, r in enumerate(results[:3], 1):
                        print(f"  {j}. {r}")
            except Exception as e:
                print(f"❌ Erreur exécution: {e}")
        
        if i < len(questions_enrichies):
            time.sleep(2)

def test_embedding_enriched():
    """Teste l'approche embeddings avec données enrichies"""
    print_separator("TEST EMBEDDINGS AVEC DONNÉES ENRICHIES", "=")
    
    if not API_KEY:
        print("\n❌ OPENROUTER_API_KEY non définie!")
        return
    
    try:
        service = EmbeddingGraphRAGService(
            kg_file="data/kg_inferred.ttl",
            api_key=API_KEY
        )
        
        # Tester avec une limite pour la démo
        if len(service.entity_embeddings) == 0:
            print("\n🔨 Génération des embeddings (limité à 50 pour le test)...")
            service.build_embeddings(limit=50)
        
        questions = [
            "Recommande-moi un hidden gem",
            "Je cherche un TopRestaurant",
            "Lieux très bien notés (highly rated)"
        ]
        
        for i, question in enumerate(questions, 1):
            print(f"\n{'='*70}")
            print(f"TEST {i}/{len(questions)}: {question}")
            print("="*70)
            
            result = service.answer_question(question, top_k=3)
            
            if result.get("error"):
                print(f"❌ Erreur: {result['answer']}")
            else:
                print(f"\n💬 RÉPONSE ENRICHIE:")
                print("-" * 70)
                print(result["answer"])
                print("-" * 70)
                
                print(f"\n📊 Entités utilisées:")
                for entity in result["entities"][:3]:
                    info = entity.get("info", {})
                    print(f"  • {info.get('name', 'N/A')}")
                    if "inferredClasses" in info:
                        print(f"    🏆 {info['inferredClasses']}")
                    if "inferenceReason" in info:
                        print(f"    💡 {info['inferenceReason']}")
            
            if i < len(questions):
                time.sleep(2)
    
    except Exception as e:
        print(f"❌ Erreur: {e}")

def main():
    """Fonction principale"""
    print("\n" + "="*70)
    print("  🎯 TESTS GRAPHRAG AVEC DONNÉES ENRICHIES")
    print("="*70)
    
    if not API_KEY:
        print("\n❌ OPENROUTER_API_KEY non définie !")
        print("\nPour la configurer, exécute :")
        print('  $env:OPENROUTER_API_KEY="sk-or-v1-..."')
        return
    
    print(f"\n✓ Clé API détectée : {API_KEY[:20]}...")
    
    # Test 1 : Comparaison kg_linked vs kg_inferred
    print("\n" + "#"*70)
    print("# PARTIE 1 : IMPACT DE L'INFÉRENCE")
    print("#"*70)
    compare_kg_versions()
    
    # Test 2 : Requêtes enrichies
    print("\n\n" + "#"*70)
    print("# PARTIE 2 : EXPLOITATION DES DONNÉES ENRICHIES (SPARQL)")
    print("#"*70)
    test_enriched_queries()
    
    # Test 3 : Embeddings enrichis
    print("\n\n" + "#"*70)
    print("# PARTIE 3 : EMBEDDINGS AVEC MÉTADONNÉES ENRICHIES")
    print("#"*70)
    test_embedding_enriched()
    
    # Résumé final
    print("\n\n" + "="*70)
    print("  ✅ TOUS LES TESTS TERMINÉS")
    print("="*70)
    
    print("\n📊 AMÉLIORATIONS APPORTÉES:")
    print("\n✅ Approche 1 (SPARQL):")
    print("   • Exploitation des 7 classes inférées (HighlyRated, TopRestaurant, etc.)")
    print("   • Support des propriétés d'inférence (inferredRating, inferenceReason)")
    print("   • Requêtes sur reviews Schema.org (10,996 reviews)")
    print("   • Exploitation des liens Wikidata/DBpedia (27 ressources)")
    
    print("\n🧠 Approche 2 (Embeddings):")
    print("   • Embeddings enrichis avec classes inférées")
    print("   • Métadonnées complètes (topics, liens LOD, raisons d'inférence)")
    print("   • Réponses contextuelles avec badges de qualité")
    print("   • Exploitation de tous les types de reviews")
    
    print("\n⚖️ Les deux approches exploitent maintenant TOUTES les données enrichies !")
    print("\n📱 Interface web : http://localhost:8000")
    print("   → Utilise kg_inferred.ttl automatiquement\n")

if __name__ == "__main__":
    main()
