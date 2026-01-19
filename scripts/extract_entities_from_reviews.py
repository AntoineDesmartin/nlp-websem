
"""
Extraction d'entités (NER) depuis les reviews avec spaCy
"""

import argparse
import json
import re
from collections import defaultdict, Counter
from pathlib import Path
from typing import Dict, List, Set, Tuple
from datetime import datetime

try:
    import spacy
    from spacy.language import Language
except ImportError:
    print("❌ spaCy non installé. Installez avec :")
    print("   pip install spacy")
    print("   python -m spacy download fr_core_news_lg")
    exit(1)

from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, XSD

# Définir SCHEMA manuellement
SCHEMA = Namespace("http://schema.org/")


TG = Namespace("https://example.org/tourguide#")
PLACE_NS = Namespace("https://example.org/tourguide/place/")
REVIEW_NS = Namespace("https://example.org/tourguide/review/")
AUTHOR_NS = Namespace("https://example.org/tourguide/author/")


def load_spacy_model(model_name: str = "fr_core_news_lg") -> Language:
    """Charge le modèle spaCy français"""
    print(f"📦 Chargement du modèle spaCy : {model_name}")
    try:
        nlp = spacy.load(model_name)
        print(f"   ✓ Modèle chargé : {len(nlp.pipe_names)} composants")
        return nlp
    except OSError:
        print(f"❌ Modèle {model_name} non trouvé.")
        print(f"   Téléchargez avec : python -m spacy download {model_name}")
        exit(1)


def load_existing_places(kg_path: str) -> Dict[str, Dict]:
    """Charge les lieux existants du KG pour matching"""
    print(f"📖 Chargement du KG existant : {kg_path}")
    
    kg = Graph()
    kg.parse(kg_path, format="turtle")
    
    places = {}
    
    # Récupérer tous les lieux avec leurs noms
    query = """
    PREFIX tg: <https://example.org/tourguide#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?place ?name ?placeId
    WHERE {
        ?place a tg:Place ;
               tg:name ?name .
        OPTIONAL { ?place tg:placeId ?placeId }
    }
    """
    
    for row in kg.query(query):
        place_uri = str(row.place)
        place_id = place_uri.split('/')[-1]  # Extraire ID depuis URI
        
        name = str(row.name).strip()
        name_lower = name.lower()
        
        places[name_lower] = {
            'uri': place_uri,
            'id': place_id,
            'name': name
        }
    
    print(f"   ✓ {len(places):,} lieux chargés pour matching")
    return places


def normalize_text(text: str) -> str:
    """Normalise le texte pour matching"""
    if not text:
        return ""
    # Minuscules, suppression accents basique
    text = text.lower().strip()
    # Supprimer ponctuation de fin
    text = re.sub(r'[^\w\s-]', '', text)
    return text


def match_entity_to_place(entity_text: str, places_dict: Dict) -> Tuple[str, str, str]:
    """
    Tente de matcher une entité extraite avec un lieu du KG
    
    Returns:
        (place_uri, place_id, matched_name) or (None, None, None)
    """
    entity_norm = normalize_text(entity_text)
    
    # Matching exact
    if entity_norm in places_dict:
        place = places_dict[entity_norm]
        return place['uri'], place['id'], place['name']
    
    # Matching partiel (l'entité contient le nom du lieu)
    for place_name, place_info in places_dict.items():
        if place_name in entity_norm or entity_norm in place_name:
            return place_info['uri'], place_info['id'], place_info['name']
    
    return None, None, None


def extract_entities_from_reviews(
    reviews_dir: str,
    kg_input: str,
    output_ttl: str,
    stats_output: str,
    sample_size: int = 0,
    entity_types: Set[str] = {"LOC", "FAC", "ORG"}
) -> None:
    """
    Extrait les entités des reviews et génère le graphe RDF enrichi
    
    Args:
        reviews_dir: Dossier contenant les fichiers JSON de reviews
        kg_input: Chemin vers le KG existant
        output_ttl: Fichier de sortie RDF
        stats_output: Fichier de sortie JSON pour statistiques
        sample_size: Nombre de reviews par fichier (0 = tout)
        entity_types: Types d'entités spaCy à conserver
    """
    
    print("="*70)
    print("🚀 EXTRACTION NER DEPUIS REVIEWS")
    print("="*70)
    
    # 1. Charger spaCy
    nlp = load_spacy_model()
    
    # 2. Charger les lieux du KG
    places_dict = load_existing_places(kg_input)
    
    # 3. Charger les reviews
    reviews_path = Path(reviews_dir)
    review_files = sorted(reviews_path.glob("paris-*-reviews.json"))
    
    print(f"\n📂 Fichiers de reviews trouvés : {len(review_files)}")
    
    # 4. Structures pour collecte
    kg = Graph()
    kg.bind("tg", TG)
    kg.bind("schema", SCHEMA)
    kg.bind("rdfs", RDFS)
    
    stats = {
        'total_reviews_processed': 0,
        'reviews_with_entities': 0,
        'total_entities_extracted': 0,
        'entities_matched_to_kg': 0,
        'entities_not_matched': 0,
        'entity_counter': Counter(),
        'matched_places': Counter(),
        'sample_annotations': [],
        'entity_types_dist': Counter(),
        'processing_time': None
    }
    
    start_time = datetime.now()
    
    # 5. Traiter chaque fichier
    for file in review_files:
        print(f"\n📄 Traitement de {file.name}")
        
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        file_reviews_count = 0
        
        for place_data in data:
            place_id = place_data.get('id')
            reviews = place_data.get('reviews_data', [])
            
            if sample_size > 0:
                reviews = reviews[:sample_size]
            
            for idx, review in enumerate(reviews):
                review_text = review.get('text', '').strip()
                
                if not review_text or len(review_text) < 10:
                    continue
                
                stats['total_reviews_processed'] += 1
                file_reviews_count += 1
                
                # Créer URI de review
                review_id = f"{place_id}_r{idx}"
                review_uri = REVIEW_NS[review_id]
                
                # Appliquer NER
                doc = nlp(review_text)
                
                entities_found = []
                matched_places_in_review = []
                
                for ent in doc.ents:
                    if ent.label_ not in entity_types:
                        continue
                    
                    entity_text = ent.text.strip()
                    entity_label = ent.label_
                    
                    stats['total_entities_extracted'] += 1
                    stats['entity_counter'][entity_text] += 1
                    stats['entity_types_dist'][entity_label] += 1
                    
                    entities_found.append({
                        'text': entity_text,
                        'label': entity_label,
                        'start': ent.start_char,
                        'end': ent.end_char
                    })
                    
                    # Tenter matching avec KG
                    place_uri, matched_place_id, matched_name = match_entity_to_place(
                        entity_text, places_dict
                    )
                    
                    if place_uri:
                        # Ajouter triplet schema:mentions
                        kg.add((review_uri, SCHEMA.mentions, URIRef(place_uri)))
                        
                        stats['entities_matched_to_kg'] += 1
                        stats['matched_places'][matched_name] += 1
                        matched_places_in_review.append(matched_name)
                    else:
                        stats['entities_not_matched'] += 1
                
                # Si entités trouvées, marquer la review
                if entities_found:
                    stats['reviews_with_entities'] += 1
                    
                    # Ajouter métadonnées sur la review
                    kg.add((review_uri, RDF.type, SCHEMA.Review))
                    kg.add((review_uri, TG.hasExtractedEntities, 
                           Literal(len(entities_found), datatype=XSD.integer)))
                    
                    # Stocker les entités brutes comme string (optionnel)
                    entities_str = ", ".join([f"{e['text']} ({e['label']})" 
                                             for e in entities_found])
                    kg.add((review_uri, TG.extractedEntities, 
                           Literal(entities_str, datatype=XSD.string)))
                    
                    # Garder quelques exemples pour stats
                    if len(stats['sample_annotations']) < 20:
                        stats['sample_annotations'].append({
                            'review_id': review_id,
                            'text': review_text[:200],
                            'entities': entities_found,
                            'matched_places': matched_places_in_review
                        })
        
        print(f"   ✓ {file_reviews_count:,} reviews traitées")
        
        # Affichage progression
        if stats['total_reviews_processed'] % 10000 == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = stats['total_reviews_processed'] / elapsed
            print(f"   📊 Progression : {stats['total_reviews_processed']:,} reviews "
                  f"({rate:.0f} reviews/sec)")
    
    # 6. Sauvegarder le graphe RDF
    print(f"\n💾 Sauvegarde du graphe RDF : {output_ttl}")
    Path(output_ttl).parent.mkdir(parents=True, exist_ok=True)
    kg.serialize(output_ttl, format="turtle")
    print(f"   ✓ {len(kg):,} triplets RDF sauvegardés")
    
    # 7. Calculer statistiques finales
    end_time = datetime.now()
    stats['processing_time'] = str(end_time - start_time)
    
    # Top entités
    stats['top_entities'] = stats['entity_counter'].most_common(50)
    stats['top_matched_places'] = stats['matched_places'].most_common(20)
    
    # 8. Sauvegarder statistiques JSON
    print(f"\n📊 Sauvegarde des statistiques : {stats_output}")
    
    # Convertir Counter en dict pour JSON
    stats_serializable = {
        'total_reviews_processed': stats['total_reviews_processed'],
        'reviews_with_entities': stats['reviews_with_entities'],
        'total_entities_extracted': stats['total_entities_extracted'],
        'entities_matched_to_kg': stats['entities_matched_to_kg'],
        'entities_not_matched': stats['entities_not_matched'],
        'match_rate': f"{stats['entities_matched_to_kg'] / stats['total_entities_extracted'] * 100:.1f}%" 
                      if stats['total_entities_extracted'] > 0 else "0%",
        'entity_types_distribution': dict(stats['entity_types_dist']),
        'top_entities': stats['top_entities'],
        'top_matched_places': stats['top_matched_places'],
        'sample_annotations': stats['sample_annotations'],
        'processing_time': stats['processing_time'],
        'timestamp': datetime.now().isoformat()
    }
    
    with open(stats_output, 'w', encoding='utf-8') as f:
        json.dump(stats_serializable, f, ensure_ascii=False, indent=2)
    
    # 9. Afficher résumé
    print("\n" + "="*70)
    print("✅ EXTRACTION TERMINÉE")
    print("="*70)
    print(f"Reviews traitées:           {stats['total_reviews_processed']:,}")
    print(f"Reviews avec entités:       {stats['reviews_with_entities']:,} "
          f"({stats['reviews_with_entities']/stats['total_reviews_processed']*100:.1f}%)")
    print(f"Entités extraites (total):  {stats['total_entities_extracted']:,}")
    print(f"  - Matchées au KG:         {stats['entities_matched_to_kg']:,}")
    print(f"  - Non matchées:           {stats['entities_not_matched']:,}")
    print(f"  - Taux de matching:       {stats_serializable['match_rate']}")
    print(f"\nTop 5 lieux mentionnés:")
    for place, count in stats['top_matched_places'][:5]:
        print(f"  • {place}: {count:,} mentions")
    print(f"\nTemps de traitement:        {stats['processing_time']}")
    print(f"Triplets RDF générés:       {len(kg):,}")
    print("="*70)


def main():
    parser = argparse.ArgumentParser(
        description="Extraction NER depuis reviews avec spaCy"
    )
    parser.add_argument(
        "--reviews_dir",
        default="data/reviews",
        help="Dossier contenant les fichiers JSON de reviews"
    )
    parser.add_argument(
        "--kg_input",
        default="data/kg_inferred.ttl",
        help="Graphe de connaissances d'entrée"
    )
    parser.add_argument(
        "--output",
        default="data/kg_reviews_ner.ttl",
        help="Fichier de sortie RDF avec mentions"
    )
    parser.add_argument(
        "--stats_output",
        default="data/ner_stats.json",
        help="Fichier de sortie JSON pour statistiques"
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=0,
        help="Nombre de reviews par fichier (0 = tout)"
    )
    
    args = parser.parse_args()
    
    extract_entities_from_reviews(
        reviews_dir=args.reviews_dir,
        kg_input=args.kg_input,
        output_ttl=args.output,
        stats_output=args.stats_output,
        sample_size=args.sample
    )


if __name__ == "__main__":
    main()
