#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de validation SHACL pour le graphe de connaissances TourGuide.
Valide les données RDF contre les formes SHACL définies.
"""

import sys
from pathlib import Path
from rdflib import Graph
from pyshacl import validate

def validate_kg_with_shacl(data_file, shapes_file):
    """
    Valide un fichier RDF avec des contraintes SHACL.
    
    Args:
        data_file: Chemin vers le fichier de données RDF
        shapes_file: Chemin vers le fichier de formes SHACL
    
    Returns:
        Tuple (conforms, results_graph, results_text)
    """
    print(f"\n{'='*60}")
    print(f"Validation SHACL: {Path(data_file).name}")
    print(f"{'='*60}\n")
    
    # Charger le graphe de données
    print(f"📊 Chargement des données: {data_file}")
    data_graph = Graph()
    try:
        data_graph.parse(data_file, format='turtle')
        print(f"   ✓ {len(data_graph)} triples chargés")
    except Exception as e:
        print(f"   ✗ Erreur de chargement: {e}")
        return False, None, str(e)
    
    # Charger les formes SHACL
    print(f"\n📋 Chargement des formes SHACL: {shapes_file}")
    shapes_graph = Graph()
    try:
        shapes_graph.parse(shapes_file, format='turtle')
        print(f"   ✓ {len(shapes_graph)} triples de contraintes chargés")
    except Exception as e:
        print(f"   ✗ Erreur de chargement: {e}")
        return False, None, str(e)
    
    # Validation SHACL
    print(f"\n🔍 Validation en cours...")
    try:
        conforms, results_graph, results_text = validate(
            data_graph,
            shacl_graph=shapes_graph,
            inference='rdfs',
            abort_on_first=False,
            allow_warnings=True,
            meta_shacl=False,
            advanced=True,
            js=False
        )
        
        if conforms:
            print(f"\n✅ VALIDATION RÉUSSIE!")
            print(f"   Toutes les contraintes SHACL sont respectées.")
        else:
            print(f"\n❌ VALIDATION ÉCHOUÉE")
            print(f"\n📄 Rapport de validation:")
            print(results_text)
        
        return conforms, results_graph, results_text
        
    except Exception as e:
        print(f"\n✗ Erreur pendant la validation: {e}")
        return False, None, str(e)

def main():
    """Point d'entrée principal."""
    
    # Chemins par défaut
    shapes_file = "shacl/shapes.ttl"
    
    # Fichiers à valider
    data_files = [
        "data/kg_final.ttl",
        "data/kg_reviews_attraction.ttl",
        "data/kg_reviews_poi.ttl",
        "data/kg_reviews_restaurant.ttl"
    ]
    
    # Si un fichier est spécifié en argument
    if len(sys.argv) > 1:
        data_files = [sys.argv[1]]
    
    # Valider chaque fichier
    results = {}
    for data_file in data_files:
        if not Path(data_file).exists():
            print(f"\n⚠️  Fichier introuvable: {data_file}")
            continue
        
        conforms, _, _ = validate_kg_with_shacl(data_file, shapes_file)
        results[data_file] = conforms
    
    # Résumé final
    print(f"\n{'='*60}")
    print("RÉSUMÉ DE VALIDATION")
    print(f"{'='*60}\n")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    for file, conforms in results.items():
        status = "✅ VALIDE" if conforms else "❌ INVALIDE"
        print(f"{status:15} {Path(file).name}")
    
    print(f"\n📊 Total: {passed}/{total} fichiers valides")
    
    # Code de sortie
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()
