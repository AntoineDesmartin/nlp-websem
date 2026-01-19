#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Construit un graphe de recommandations à partir des VRAIES reviews TourPedia
au lieu de créer des touristes synthétiques.

Usage:
    python3 scripts/build_reco_from_real_reviews.py \
        data/kg_inferred.ttl \
        data/kg_reco.ttl \
        --triples_tsv data/reco_triples.tsv \
        --like_threshold 3
"""

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD


TG = Namespace("https://example.org/tourguide#")
PLACE_NS = Namespace("https://example.org/tourguide/place/")
REVIEW_NS = Namespace("https://example.org/tourguide/review/")
AUTHOR_NS = Namespace("https://example.org/tourguide/author/")


def get_season(date_str: str) -> str:
    """Détermine la saison depuis une date (YYYY-MM-DD)."""
    if not date_str:
        return "unknown"
    try:
        month = int(date_str.split('-')[1])
        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        else:
            return "autumn"
    except:
        return "unknown"


def get_budget_level(subcategory: str) -> str:
    """Estime le niveau de budget depuis la sous-catégorie du lieu."""
    if not subcategory:
        return "medium"
    
    subcategory_lower = subcategory.lower()
    
    # Indicateurs de luxe
    luxury_keywords = ['hotel', 'palace', 'luxury', 'gourmet', 'fine dining', 
                       'michelin', 'spa', 'resort', 'lounge', 'cocktail bar']
    
    # Indicateurs de budget économique
    budget_keywords = ['fast food', 'food truck', 'café', 'bistro', 'bakery',
                       'sandwich', 'pizza', 'burger', 'kebab', 'hostel']
    
    if any(kw in subcategory_lower for kw in luxury_keywords):
        return "luxury"
    elif any(kw in subcategory_lower for kw in budget_keywords):
        return "budget"
    else:
        return "medium"


def create_tourist_persona(language: str, season: str, budget: str) -> str:
    """
    Crée un ID de touriste persona basé sur ses caractéristiques.
    
    Ex: "tourist_fr_summer_medium", "tourist_de_winter_luxury"
    """
    # Normaliser la langue
    lang_map = {
        'fr': 'french',
        'en': 'english', 
        'de': 'german',
        'es': 'spanish',
        'it': 'italian',
        'zh': 'chinese',
        'ja': 'japanese',
        'pt': 'portuguese',
        'ru': 'russian',
        'ar': 'arabic',
        'nl': 'dutch',
        'sv': 'swedish',
        'ko': 'korean'
    }
    
    lang_name = lang_map.get(language, language if language else 'unknown')
    
    return f"tourist_{lang_name}_{season}_{budget}"


def load_reviews(reviews_dir: Path) -> List[Dict]:
    """Charge tous les fichiers de reviews JSON."""
    all_places = []
    
    for file in sorted(reviews_dir.glob("paris-*-reviews.json")):
        print(f"📂 Chargement de {file.name}...")
        with open(file, 'r', encoding='utf-8') as f:
            places = json.load(f)
            all_places.extend(places)
    
    return all_places


def build_reco_graph(kg_path: str, output_path: str, triples_tsv: str,
                     reviews_dir: str = "data/reviews",
                     like_threshold: int = 3) -> None:
    """
    Construit le graphe de recommandations depuis les vraies reviews.
    
    Args:
        kg_path: Chemin vers le graphe de connaissances existant
        output_path: Chemin de sortie pour le graphe enrichi
        triples_tsv: Chemin de sortie pour le TSV PyKEEN
        reviews_dir: Dossier contenant les fichiers JSON de reviews
        like_threshold: Polarity minimum pour créer un likesPlace (1-5)
    """
    
    print("="*60)
    print("🚀 Construction du graphe de recommandations depuis vraies reviews")
    print("="*60)
    
    # 1. Charger le graphe existant
    print(f"\n📖 Chargement du graphe: {kg_path}")
    kg = Graph()
    kg.parse(kg_path, format="turtle")
    print(f"   ✓ {len(kg):,} triplets chargés")
    
    # 2. Récupérer les place IDs existants dans le graphe
    existing_places = set()
    for s in kg.subjects(RDF.type, TG.Place):
        # Extraire l'ID depuis l'URI (ex: https://example.org/tourguide/place/83254 -> 83254)
        place_id = str(s).split('/')[-1]
        existing_places.add(place_id)
    
    print(f"   ✓ {len(existing_places):,} lieux trouvés dans le graphe")
    
    # 3. Charger les reviews
    reviews_path = Path(reviews_dir)
    all_places = load_reviews(reviews_path)
    print(f"\n📝 {len(all_places):,} lieux avec reviews chargés")
    
    # 4. Définir les propriétés dans l'ontologie
    kg.add((TG.likesPlace, RDF.type, OWL.ObjectProperty))
    kg.add((TG.likesPlace, RDFS.domain, TG.Tourist))
    kg.add((TG.likesPlace, RDFS.range, TG.Place))
    
    kg.add((TG.Tourist, RDF.type, OWL.Class))
    kg.add((TG.Tourist, RDFS.label, Literal("Tourist", lang="en")))
    
    # Propriétés de caractérisation des touristes
    kg.add((TG.prefersLanguage, RDF.type, OWL.DatatypeProperty))
    kg.add((TG.prefersLanguage, RDFS.domain, TG.Tourist))
    
    kg.add((TG.prefersSeason, RDF.type, OWL.DatatypeProperty))
    kg.add((TG.prefersSeason, RDFS.domain, TG.Tourist))
    
    kg.add((TG.budgetLevel, RDF.type, OWL.DatatypeProperty))
    kg.add((TG.budgetLevel, RDFS.domain, TG.Tourist))
    
    # 5. Extraire les reviews et construire les triplets
    print("\n🔍 Extraction des reviews et création des relations...")
    
    triplets_for_tsv = []
    stats = {
        'total_reviews': 0,
        'likes': 0,
        'neutral': 0,
        'dislikes': 0,
        'unique_authors': set(),
        'places_with_reviews': 0,
        'skipped_no_polarity': 0,
        'skipped_place_not_in_kg': 0
    }
    
    for place_data in all_places:
        place_id = place_data.get('id')
        place_subcategory = place_data.get('subCategory', '')
        
        # Ignorer si le lieu n'est pas dans le graphe
        if place_id not in existing_places:
            stats['skipped_place_not_in_kg'] += 1
            continue
        
        reviews = place_data.get('reviews_data', [])
        if not reviews:
            continue
        
        stats['places_with_reviews'] += 1
        place_uri = PLACE_NS[place_id]
        
        # Déterminer le niveau de budget de ce lieu
        place_budget = get_budget_level(place_subcategory)
        
        for review in reviews:
            stats['total_reviews'] += 1
            
            polarity = review.get('polarity', None)
            if polarity is None or polarity == 0:
                stats['skipped_no_polarity'] += 1
                continue
            
            # Créer un persona de touriste basé sur les caractéristiques
            language = review.get('language', 'en')
            season = get_season(review.get('time', ''))
            
            # Le budget du touriste correspond au budget des lieux qu'il visite
            tourist_budget = place_budget
            
            # Créer l'ID du persona
            persona_id = create_tourist_persona(language, season, tourist_budget)
            
            stats['unique_authors'].add(persona_id)
            author_uri = AUTHOR_NS[persona_id]
            
            # Créer l'entité touriste avec un label lisible
            kg.add((author_uri, RDF.type, TG.Tourist))
            
            # Ajouter des propriétés descriptives
            tourist_label = f"{language.upper()} Tourist ({season.title()}, {tourist_budget.title()} budget)"
            kg.add((author_uri, RDFS.label, Literal(tourist_label, lang="en")))
            kg.add((author_uri, TG.prefersLanguage, Literal(language, datatype=XSD.string)))
            kg.add((author_uri, TG.prefersSeason, Literal(season, datatype=XSD.string)))
            kg.add((author_uri, TG.budgetLevel, Literal(tourist_budget, datatype=XSD.string)))
            
            # Créer la relation basée sur la polarity
            if polarity >= like_threshold:
                kg.add((author_uri, TG.likesPlace, place_uri))
                stats['likes'] += 1
                
                # Ajouter au TSV pour PyKEEN
                triplets_for_tsv.append((
                    str(author_uri),
                    str(TG.likesPlace),
                    str(place_uri)
                ))
            elif polarity <= 2:
                stats['dislikes'] += 1
            else:
                stats['neutral'] += 1
    
    # 6. Ajouter les triplets structurels au TSV (pour aider l'apprentissage)
    print("\n📊 Ajout des triplets structurels pour PyKEEN...")
    
    # Garder seulement certaines propriétés utiles pour l'apprentissage
    keep_predicates = {
        RDF.type,
        TG.likesPlace,
        TG.locatedIn,
        TG.hasTopic,
    }
    
    for s, p, o in kg:
        if p not in keep_predicates:
            continue
        if not isinstance(s, URIRef):
            continue
        
        # Pour rdf:type, garder seulement si l'objet est un URIRef
        if p == RDF.type:
            if isinstance(o, URIRef):
                triplets_for_tsv.append((str(s), str(p), str(o)))
        # Pour les autres, garder seulement si l'objet est un URIRef
        elif isinstance(o, URIRef):
            triplets_for_tsv.append((str(s), str(p), str(o)))
    
    # 7. Sauvegarder le graphe enrichi
    print(f"\n💾 Sauvegarde du graphe enrichi: {output_path}")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    kg.serialize(output_path, format="turtle")
    print(f"   ✓ {len(kg):,} triplets sauvegardés")
    
    # 8. Sauvegarder le TSV pour PyKEEN
    print(f"\n💾 Sauvegarde du TSV pour PyKEEN: {triples_tsv}")
    Path(triples_tsv).parent.mkdir(parents=True, exist_ok=True)
    
    # Dédupliquer les triplets
    unique_triplets = list(set(triplets_for_tsv))
    
    with open(triples_tsv, 'w', encoding='utf-8') as f:
        for h, r, t in unique_triplets:
            f.write(f"{h}\t{r}\t{t}\n")
    
    print(f"   ✓ {len(unique_triplets):,} triplets uniques sauvegardés")
    
    # 9. Afficher les statistiques
    print("\n" + "="*60)
    print("📊 STATISTIQUES")
    print("="*60)
    print(f"Reviews totales:           {stats['total_reviews']:,}")
    print(f"  - Likes (polarity ≥ {like_threshold}):   {stats['likes']:,}")
    print(f"  - Neutral (polarity 3):  {stats['neutral']:,}")
    print(f"  - Dislikes (≤ 2):        {stats['dislikes']:,}")
    print(f"  - Sans polarity:         {stats['skipped_no_polarity']:,}")
    print(f"\nAuteurs uniques:           {len(stats['unique_authors']):,}")
    print(f"Lieux avec reviews:        {stats['places_with_reviews']:,}")
    print(f"Lieux ignorés (pas dans KG): {stats['skipped_place_not_in_kg']:,}")
    print(f"\nTriplets pour PyKEEN:      {len(unique_triplets):,}")
    print(f"Triplets dans le graphe:   {len(kg):,}")
    print("="*60)
    print("✅ TERMINÉ!")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description="Construit un graphe de recommandations depuis les vraies reviews"
    )
    parser.add_argument(
        "kg_input",
        help="Graphe de connaissances d'entrée (ex: data/kg_inferred.ttl)"
    )
    parser.add_argument(
        "kg_output",
        help="Graphe de connaissances de sortie (ex: data/kg_reco.ttl)"
    )
    parser.add_argument(
        "--triples_tsv",
        default="data/reco_triples.tsv",
        help="Fichier TSV de sortie pour PyKEEN"
    )
    parser.add_argument(
        "--reviews_dir",
        default="data/reviews",
        help="Dossier contenant les fichiers JSON de reviews"
    )
    parser.add_argument(
        "--like_threshold",
        type=int,
        default=3,
        help="Polarity minimum pour créer un likesPlace (1-5, défaut: 3)"
    )
    
    args = parser.parse_args()
    
    build_reco_graph(
        kg_path=args.kg_input,
        output_path=args.kg_output,
        triples_tsv=args.triples_tsv,
        reviews_dir=args.reviews_dir,
        like_threshold=args.like_threshold
    )


if __name__ == "__main__":
    main()
