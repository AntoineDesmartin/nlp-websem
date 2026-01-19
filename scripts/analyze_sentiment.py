"""
Analyse de sentiment avec DistilBERT sur les reviews TourPedia
"""

import json
import argparse
from pathlib import Path
from collections import Counter
from datetime import datetime
from tqdm import tqdm

# Transformers
from transformers import pipeline
import torch

def load_reviews(reviews_dir: str, sample_size: int = None):
    """Charge les reviews depuis les fichiers JSON"""
    print(f"📖 Chargement des reviews depuis {reviews_dir}")
    
    reviews_dir = Path(reviews_dir)
    all_reviews = []
    
    for json_file in sorted(reviews_dir.glob("paris-*-reviews.json")):
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            for place_data in data:
                place_id = place_data.get('id')
                place_name = place_data.get('name', 'Unknown')
                polarity_str = place_data.get('polarity', '0')
                polarity = float(polarity_str) if polarity_str else 0.0
                
                for review in place_data.get('reviews_data', []):
                    if isinstance(review, dict):  # S'assurer que c'est un dict
                        text = review.get('text', '').strip()
                        if len(text) > 10:  # Ignorer reviews trop courtes
                            all_reviews.append({
                                'place_id': place_id,
                                'place_name': place_name,
                                'polarity': polarity,
                                'text': text,
                                'rating': review.get('polarity', 0)
                            })
    
    print(f"   ✓ {len(all_reviews):,} reviews avec texte chargées")
    
    # Échantillonner si demandé
    if sample_size and sample_size < len(all_reviews):
        import random
        random.seed(42)  # Reproductible
        all_reviews = random.sample(all_reviews, sample_size)
        print(f"   ✓ Échantillon de {sample_size:,} reviews sélectionnées")
    
    return all_reviews


def analyze_sentiment_batch(reviews: list, batch_size: int = 16):
    """
    Analyse le sentiment avec DistilBERT (transformers)
    
    Args:
        reviews: Liste de dicts avec 'text'
        batch_size: Taille des batchs pour performance
    
    Returns:
        Liste avec sentiment ajouté à chaque review
    """
    print(f"\n🤖 Initialisation du modèle DistilBERT...")
    
    # Modèle multilingue 5-étoiles (optimisé pour reviews)
    # Plus rapide que BERT complet, fonctionne bien sur français
    sentiment_pipeline = pipeline(
        "sentiment-analysis",
        model="nlptown/bert-base-multilingual-uncased-sentiment",
        device=-1,  # CPU
        truncation=True,
        max_length=512
    )
    
    print(f"   ✓ Modèle chargé (DistilBERT multilingue)")
    print(f"\n🔍 Analyse de {len(reviews):,} reviews...")
    print(f"   Batch size: {batch_size}")
    
    # Extraire textes
    texts = [r['text'][:512] for r in reviews]  # Limiter longueur
    
    # Analyse par batch avec progression
    results = []
    for i in tqdm(range(0, len(texts), batch_size), desc="Sentiment Analysis"):
        batch = texts[i:i + batch_size]
        batch_results = sentiment_pipeline(batch)
        results.extend(batch_results)
    
    # Mapper résultats (1-5 stars → score -1 à +1)
    for review, sentiment in zip(reviews, results):
        # Le modèle retourne "1 star", "2 stars", ..., "5 stars"
        stars = int(sentiment['label'].split()[0])
        confidence = sentiment['score']
        
        # Convertir en score normalized
        # 1-2 stars = négatif, 3 = neutre, 4-5 = positif
        normalized_score = (stars - 3) / 2  # -1, -0.5, 0, 0.5, 1
        
        review['sentiment_stars'] = stars
        review['sentiment_score'] = normalized_score
        review['sentiment_confidence'] = confidence
        review['sentiment_label'] = 'positive' if stars >= 4 else ('negative' if stars <= 2 else 'neutral')
    
    return reviews


def find_contradictions(reviews: list, threshold: float = 2.0):
    """
    Trouve les contradictions entre note structurée et sentiment textuel
    
    Args:
        reviews: Reviews avec sentiment_score et polarity
        threshold: Différence minimale pour contradiction (étoiles)
    
    Returns:
        Liste de contradictions
    """
    print(f"\n🔍 Détection des contradictions (seuil: {threshold} étoiles)...")
    
    contradictions = []
    
    for review in reviews:
        polarity = review.get('polarity', 0)  # Note lieu 0-10
        sentiment_stars = review.get('sentiment_stars', 3)  # Sentiment 1-5
        
        # Convertir polarity en échelle 1-5 pour comparaison
        polarity_stars = (polarity / 10) * 5
        
        # Différence
        diff = abs(polarity_stars - sentiment_stars)
        
        if diff >= threshold:
            contradictions.append({
                'place_name': review['place_name'],
                'polarity': polarity,
                'polarity_stars': round(polarity_stars, 1),
                'sentiment_stars': sentiment_stars,
                'sentiment_label': review['sentiment_label'],
                'difference': round(diff, 1),
                'text': review['text'][:200] + '...' if len(review['text']) > 200 else review['text'],
                'type': 'positive_text_bad_rating' if sentiment_stars > polarity_stars else 'negative_text_good_rating'
            })
    
    # Trier par différence
    contradictions.sort(key=lambda x: x['difference'], reverse=True)
    
    print(f"   ✓ {len(contradictions):,} contradictions détectées")
    
    return contradictions


def generate_stats(reviews: list, contradictions: list):
    """Génère statistiques sentiment"""
    sentiment_dist = Counter([r['sentiment_label'] for r in reviews])
    stars_dist = Counter([r['sentiment_stars'] for r in reviews])
    
    stats = {
        'total_reviews_analyzed': len(reviews),
        'sentiment_distribution': {
            'positive': sentiment_dist.get('positive', 0),
            'neutral': sentiment_dist.get('neutral', 0),
            'negative': sentiment_dist.get('negative', 0),
        },
        'sentiment_percentages': {
            'positive': round(sentiment_dist.get('positive', 0) / len(reviews) * 100, 1),
            'neutral': round(sentiment_dist.get('neutral', 0) / len(reviews) * 100, 1),
            'negative': round(sentiment_dist.get('negative', 0) / len(reviews) * 100, 1),
        },
        'stars_distribution': dict(stars_dist),
        'average_sentiment_score': round(sum(r['sentiment_score'] for r in reviews) / len(reviews), 3),
        'contradictions_found': len(contradictions),
        'contradiction_rate': round(len(contradictions) / len(reviews) * 100, 1),
        'top_contradictions': contradictions[:20],
        'model_used': 'nlptown/bert-base-multilingual-uncased-sentiment (DistilBERT)',
        'timestamp': datetime.now().isoformat()
    }
    
    return stats


def aggregate_by_place(reviews: list):
    """Agrège les sentiments par lieu pour intégration KG"""
    print(f"\n📊 Agrégation des sentiments par lieu...")
    
    place_sentiments = {}
    
    for review in reviews:
        place_id = review['place_id']
        
        if place_id not in place_sentiments:
            place_sentiments[place_id] = {
                'place_id': place_id,
                'place_name': review['place_name'],
                'polarity': review['polarity'],
                'reviews': []
            }
        
        place_sentiments[place_id]['reviews'].append({
            'sentiment_score': review['sentiment_score'],
            'sentiment_label': review['sentiment_label'],
            'sentiment_stars': review['sentiment_stars']
        })
    
    # Calculer stats par lieu
    by_place = {}
    for place_id, data in place_sentiments.items():
        reviews_data = data['reviews']
        sentiments = [r['sentiment_score'] for r in reviews_data]
        labels = Counter([r['sentiment_label'] for r in reviews_data])
        
        by_place[place_id] = {
            'place_name': data['place_name'],
            'polarity': data['polarity'],
            'total_reviews': len(reviews_data),
            'avg_sentiment': round(sum(sentiments) / len(sentiments), 3) if sentiments else 0,
            'positive_count': labels.get('positive', 0),
            'neutral_count': labels.get('neutral', 0),
            'negative_count': labels.get('negative', 0),
            'positive_percent': round(labels.get('positive', 0) / len(reviews_data) * 100, 1),
            'negative_percent': round(labels.get('negative', 0) / len(reviews_data) * 100, 1)
        }
    
    print(f"   ✓ {len(by_place):,} lieux avec sentiments agrégés")
    
    return by_place


def main():
    parser = argparse.ArgumentParser(description='Analyse de sentiment avec DistilBERT')
    parser.add_argument('--sample', type=int, default=5000,
                       help='Nombre de reviews à analyser (défaut: 5000)')
    args = parser.parse_args()
    
    # Chemins
    reviews_dir = "data/reviews"
    output_file = "data/sentiment_stats.json"
    
    # 1. Charger reviews
    reviews = load_reviews(reviews_dir, sample_size=args.sample)
    
    # 2. Analyser sentiment
    reviews = analyze_sentiment_batch(reviews, batch_size=16)
    
    # 3. Trouver contradictions
    contradictions = find_contradictions(reviews, threshold=2.0)
    
    # 4. Générer stats
    stats = generate_stats(reviews, contradictions)
    
    # 5. Agréger par lieu
    by_place = aggregate_by_place(reviews)
    
    # 6. Sauvegarder stats globales
    print(f"\n💾 Sauvegarde : {output_file}")
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    
    # 7. Sauvegarder sentiments par lieu (pour KG)
    by_place_file = "data/sentiment_by_place.json"
    print(f"💾 Sauvegarde : {by_place_file}")
    with open(by_place_file, 'w', encoding='utf-8') as f:
        json.dump(by_place, f, indent=2, ensure_ascii=False)
    
    # Afficher résumé
    print("\n" + "="*70)
    print("✅ ANALYSE DE SENTIMENT TERMINÉE")
    print("="*70)
    print(f"Reviews analysées:        {stats['total_reviews_analyzed']:,}")
    print(f"\nRépartition sentiment:")
    print(f"  😊 Positif:              {stats['sentiment_distribution']['positive']:,} ({stats['sentiment_percentages']['positive']}%)")
    print(f"  😐 Neutre:               {stats['sentiment_distribution']['neutral']:,} ({stats['sentiment_percentages']['neutral']}%)")
    print(f"  😞 Négatif:              {stats['sentiment_distribution']['negative']:,} ({stats['sentiment_percentages']['negative']}%)")
    print(f"\nScore moyen:              {stats['average_sentiment_score']:.2f} (-1 à +1)")
    print(f"Contradictions détectées: {stats['contradictions_found']:,} ({stats['contradiction_rate']}%)")
    print(f"\nModèle:                   {stats['model_used']}")
    print("="*70)
    
    # Top 5 contradictions
    if contradictions:
        print("\n📊 TOP 5 CONTRADICTIONS:")
        for i, c in enumerate(contradictions[:5], 1):
            print(f"\n{i}. {c['place_name']}")
            print(f"   Note structurée: {c['polarity_stars']}/5 (polarity: {c['polarity']}/10)")
            print(f"   Sentiment texte: {c['sentiment_stars']}/5 ({c['sentiment_label']})")
            print(f"   Différence: {c['difference']} étoiles")
            print(f"   Type: {c['type']}")
            print(f"   Texte: \"{c['text'][:100]}...\"")
    
    print(f"\n📝 Résultats sauvegardés dans:")
    print(f"   - {output_file} (stats globales)")
    print(f"   - {by_place_file} (sentiments par lieu)")
    print("\n💡 Prochaine étape: python3 scripts/integrate_sentiment_to_kg.py")


if __name__ == "__main__":
    main()
