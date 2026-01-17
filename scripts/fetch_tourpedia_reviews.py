"""
Script pour enrichir les CSV TourPedia avec les avis complets depuis l'API
Usage: python scripts/fetch_tourpedia_reviews.py <input_csv> <output_json>
"""

import requests
import csv
import json
import time
import sys
from pathlib import Path


def fetch_reviews(place_id):
    """Récupère les avis depuis l'API TourPedia"""
    url = f"http://tour-pedia.org/api/getReviewsByPlaceId?placeId={place_id}"
    try:
        response = requests.get(url, timeout=10)
        return response.json() if response.ok else []
    except Exception as e:
        print(f"Erreur pour place_id {place_id}: {e}")
        return []


def enrich_csv_with_reviews(input_csv, output_json):
    """Enrichit un CSV TourPedia avec les avis complets"""
    places_with_reviews = []
    
    print(f"Lecture de {input_csv}...")
    with open(input_csv, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        total = len(rows)
        print(f"Total de {total} lieux à traiter\n")
        
        for idx, row in enumerate(rows, 1):
            place_id = row['id']
            place_name = row.get('name', 'Unknown')
            
            print(f"[{idx}/{total}] {place_name} (ID: {place_id})...", end=' ')
            
            reviews = fetch_reviews(place_id)
            
            if reviews:
                row['reviews_data'] = reviews
                row['reviews_count'] = len(reviews)
                # Convertir rating en float, gérer les strings et None
                ratings = []
                for r in reviews:
                    try:
                        rating_val = r.get('rating', 0)
                        if rating_val is None or rating_val == '':
                            ratings.append(0)
                        else:
                            ratings.append(float(rating_val))
                    except (ValueError, TypeError):
                        ratings.append(0)
                row['avg_rating'] = sum(ratings) / len(ratings) if ratings else 0
                print(f"✓ {len(reviews)} avis (avg: {row['avg_rating']:.1f})")
            else:
                row['reviews_data'] = []
                row['reviews_count'] = 0
                row['avg_rating'] = 0
                print("✗ Pas d'avis")
            
            places_with_reviews.append(row)
            time.sleep(0.5)  # Rate limiting
    
    print(f"\nÉcriture dans {output_json}...")
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(places_with_reviews, f, ensure_ascii=False, indent=2)
    
    # Statistiques
    with_reviews = sum(1 for p in places_with_reviews if p['reviews_count'] > 0)
    total_reviews = sum(p['reviews_count'] for p in places_with_reviews)
    
    print(f"\n=== RÉSULTATS ===")
    print(f"Lieux avec avis: {with_reviews}/{total} ({with_reviews/total*100:.1f}%)")
    print(f"Total avis récupérés: {total_reviews}")
    print(f"Moyenne par lieu: {total_reviews/with_reviews:.1f}" if with_reviews > 0 else "Aucun avis")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/fetch_tourpedia_reviews.py <input_csv> <output_json>")
        print("\nExemple:")
        print("  python scripts/fetch_tourpedia_reviews.py data/subset/paris-poi.subset.csv data/reviews/paris-poi-reviews.json")
        sys.exit(1)
    
    input_csv = sys.argv[1]
    output_json = sys.argv[2]
    
    # Créer le dossier de sortie si nécessaire
    Path(output_json).parent.mkdir(parents=True, exist_ok=True)
    
    enrich_csv_with_reviews(input_csv, output_json)
    print(f"\n✓ Terminé! Fichier sauvegardé: {output_json}")
