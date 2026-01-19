"""
Script d'enrichissement automatique SKOS
Ajoute des liens tg:hasTopic entre les lieux et les concepts SKOS du thesaurus
"""
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS
from pathlib import Path

# Namespaces
TG = Namespace("https://example.org/tourguide#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

def enrich_with_skos(kg_input: str, topics_file: str, kg_output: str):
    """
    Enrichit le graphe de connaissances avec des topics SKOS
    """
    print(f"\n🔧 Enrichissement SKOS du graphe de connaissances")
    print(f"   Input:  {kg_input}")
    print(f"   Topics: {topics_file}")
    print(f"   Output: {kg_output}\n")
    
    # 1. Charger le graphe de connaissances
    print("📂 Chargement du graphe...")
    kg = Graph()
    kg.parse(kg_input, format="turtle")
    print(f"   ✓ {len(kg)} triples chargés")
    
    # Compter les lieux par type AVANT enrichissement
    restaurants = list(kg.subjects(RDF.type, TG.Restaurant))
    attractions = list(kg.subjects(RDF.type, TG.Attraction))
    pois = list(kg.subjects(RDF.type, TG.POI))
    
    print(f"\n📊 Analyse des lieux:")
    print(f"   • {len(restaurants)} Restaurants")
    print(f"   • {len(attractions)} Attractions")
    print(f"   • {len(pois)} POI")
    print(f"   Total: {len(restaurants) + len(attractions) + len(pois)} lieux\n")
    
    # 2. Mapping type → topics SKOS
    # Basé sur l'analyse du thesaurus/topics.ttl
    topic_mappings = {
        TG.Restaurant: [TG.Food, TG.FrenchCuisine],  # Gastronomie + Cuisine Française
        TG.Attraction: [TG.Culture, TG.Monument],     # Culture + Monuments
        TG.POI: [TG.Culture, TG.Monument],            # POI → Culture aussi
    }
    
    # Types plus spécifiques si présents dans le graphe
    specific_mappings = {
        # Museums
        "museum": [TG.Museum, TG.Culture, TG.ArtMuseum],
        "musée": [TG.Museum, TG.Culture, TG.ArtMuseum],
        "louvre": [TG.Museum, TG.ArtMuseum, TG.Culture],
        "musee": [TG.Museum, TG.Culture],
        
        # Religious
        "cathedral": [TG.Cathedral, TG.ReligiousHeritage, TG.Culture],
        "cathédrale": [TG.Cathedral, TG.ReligiousHeritage, TG.Culture],
        "church": [TG.Church, TG.ReligiousHeritage, TG.Culture],
        "église": [TG.Church, TG.ReligiousHeritage, TG.Culture],
        "notre-dame": [TG.Cathedral, TG.ReligiousHeritage, TG.Monument],
        
        # Monuments
        "tower": [TG.Monument, TG.Culture, TG.Architecture],
        "tour": [TG.Monument, TG.Culture, TG.Architecture],
        "eiffel": [TG.Monument, TG.Culture, TG.Architecture],
        "arc": [TG.Monument, TG.Culture, TG.Architecture],
        
        # Cuisine types
        "bistro": [TG.Food, TG.BistroFood, TG.FrenchCuisine],
        "fine": [TG.Food, TG.FineDining, TG.FrenchCuisine],
        "italian": [TG.Food, TG.InternationalCuisine, TG.ItalianFood],
        "chinese": [TG.Food, TG.InternationalCuisine, TG.AsianFood],
        "asian": [TG.Food, TG.InternationalCuisine, TG.AsianFood],
    }
    
    # 3. Enrichir le graphe
    print("⚡ Enrichissement en cours...")
    added_count = 0
    
    for place_type, topics in topic_mappings.items():
        places = list(kg.subjects(RDF.type, place_type))
        
        for place in places:
            # Récupérer le nom pour matching spécifique
            place_name = None
            for name in kg.objects(place, TG.name):
                place_name = str(name).lower()
                break
            
            if not place_name:
                for label in kg.objects(place, RDFS.label):
                    place_name = str(label).lower()
                    break
            
            # Topics de base selon le type
            topics_to_add = set(topics)
            
            # Topics spécifiques basés sur le nom
            if place_name:
                for keyword, specific_topics in specific_mappings.items():
                    if keyword in place_name:
                        topics_to_add.update(specific_topics)
            
            # Ajouter les triplets tg:hasTopic
            for topic in topics_to_add:
                if (place, TG.hasTopic, topic) not in kg:
                    kg.add((place, TG.hasTopic, topic))
                    added_count += 1
    
    print(f"   ✓ {added_count} liens tg:hasTopic ajoutés\n")
    
    # 4. Sauvegarder le graphe enrichi
    print(f"💾 Sauvegarde du graphe enrichi...")
    kg.serialize(kg_output, format="turtle")
    print(f"   ✓ Graphe sauvegardé: {kg_output}")
    print(f"   ✓ Total: {len(kg)} triples (+ {added_count} nouveaux)\n")
    
    # 5. Statistiques finales
    print("📈 Statistiques de l'enrichissement:")
    print(f"   • Triples avant: {len(kg) - added_count}")
    print(f"   • Triples ajoutés: {added_count}")
    print(f"   • Triples après: {len(kg)}")
    print(f"   • Lieux enrichis: {len(restaurants) + len(attractions) + len(pois)}")
    print(f"\n✅ Enrichissement SKOS terminé !\n")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Enrichir le graphe avec des topics SKOS")
    parser.add_argument(
        "--input",
        default="data/kg_inferred.ttl",
        help="Graphe d'entrée (défaut: data/kg_inferred.ttl)"
    )
    parser.add_argument(
        "--topics",
        default="thesaurus/topics.ttl",
        help="Thesaurus SKOS (défaut: thesaurus/topics.ttl)"
    )
    parser.add_argument(
        "--output",
        default="data/kg_inferred.ttl",
        help="Graphe de sortie (défaut: data/kg_inferred.ttl - écrase l'input!)"
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Créer une sauvegarde de l'input avant de l'écraser"
    )
    
    args = parser.parse_args()
    
    # Créer une sauvegarde si demandé
    if args.backup and args.input == args.output:
        import shutil
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{args.input}.backup_{timestamp}"
        print(f"📦 Création de la sauvegarde: {backup_path}")
        shutil.copy(args.input, backup_path)
    
    enrich_with_skos(args.input, args.topics, args.output)
