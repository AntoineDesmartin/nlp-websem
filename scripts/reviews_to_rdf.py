"""
Convertit les avis JSON en triples RDF pour intégration au knowledge graph
Usage: python scripts/reviews_to_rdf.py <reviews_json> <output_ttl>
"""

import json
import sys
from datetime import datetime
from pathlib import Path


def escape_literal(text):
    """Échappe les caractères spéciaux pour RDF"""
    if not text:
        return ""
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')


def reviews_to_rdf(json_file, output_ttl):
    """Convertit les avis JSON en RDF Turtle"""
    
    print(f"\n🔄 Conversion {json_file} → {output_ttl}\n")
    
    with open(json_file, encoding='utf-8') as f:
        data = json.load(f)
    
    # En-tête Turtle
    ttl_lines = [
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "@prefix schema: <http://schema.org/> .",
        "@prefix tg: <http://tour-guide.org/ontology#> .",
        "@prefix place: <http://tour-guide.org/resource/place/> .",
        "@prefix review: <http://tour-guide.org/resource/review/> .",
        "",
        "# Generated: " + datetime.now().isoformat(),
        "# Source: " + json_file,
        "",
    ]
    
    review_count = 0
    place_count = 0
    
    for place in data:
        place_id = place['id']
        place_uri = f"place:{place_id}"
        
        reviews = place.get('reviews_data', [])
        if not reviews:
            continue
        
        place_count += 1
        
        # Triples pour le lieu
        ttl_lines.append(f"{place_uri} a tg:Place ;")
        ttl_lines.append(f'    rdfs:label "{escape_literal(place.get("name", ""))}" ;')
        ttl_lines.append(f'    schema:aggregateRating [')
        ttl_lines.append(f'        a schema:AggregateRating ;')
        ttl_lines.append(f'        schema:ratingCount {place["reviews_count"]} ;')
        ttl_lines.append(f'        schema:ratingValue {place["avg_rating"]:.2f} ;')
        ttl_lines.append(f'    ] ;')
        
        # Lister les reviews référencées
        for idx, review_data in enumerate(reviews):
            review_id = f"{place_id}_r{idx}"
            review_uri = f"review:{review_id}"
            
            # Si c'est le dernier review, pas de point-virgule
            if idx < len(reviews) - 1:
                ttl_lines.append(f'    schema:review {review_uri} ;')
            else:
                ttl_lines.append(f'    schema:review {review_uri} .')
        
        ttl_lines.append("")
        
        # Définitions complètes des reviews
        for idx, review_data in enumerate(reviews):
            review_id = f"{place_id}_r{idx}"
            review_uri = f"review:{review_id}"
            review_count += 1
            
            text = escape_literal(review_data.get('text', ''))
            rating = review_data.get('rating', 0)
            user = escape_literal(review_data.get('user', 'Anonymous'))
            
            ttl_lines.append(f"{review_uri} a schema:Review ;")
            ttl_lines.append(f'    schema:author "{user}" ;')
            ttl_lines.append(f'    schema:reviewBody "{text}" ;')
            
            if rating > 0:
                ttl_lines.append(f'    schema:reviewRating [')
                ttl_lines.append(f'        a schema:Rating ;')
                ttl_lines.append(f'        schema:ratingValue {rating} ;')
                ttl_lines.append(f'    ] ;')
            
            ttl_lines.append(f'    schema:about {place_uri} .')
            ttl_lines.append("")
    
    # Écriture du fichier
    Path(output_ttl).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_ttl, 'w', encoding='utf-8') as f:
        f.write('\n'.join(ttl_lines))
    
    print(f"✓ {place_count} lieux convertis")
    print(f"✓ {review_count} avis convertis")
    print(f"✓ {len(ttl_lines)} triples générés")
    print(f"✓ Fichier sauvegardé: {output_ttl}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/reviews_to_rdf.py <reviews_json> <output_ttl>")
        print("\nExemple:")
        print("  python scripts/reviews_to_rdf.py data/reviews/paris-poi-reviews.json data/kg_reviews_poi.ttl")
        sys.exit(1)
    
    reviews_to_rdf(sys.argv[1], sys.argv[2])
