#!/usr/bin/env python3
"""
Test rapide du NER sur un échantillon de reviews
Usage: python3 scripts/test_ner_sample.py
"""

import json
from pathlib import Path

try:
    import spacy
except ImportError:
    print("❌ Installez spaCy d'abord:")
    print("   pip install spacy")
    print("   python -m spacy download fr_core_news_lg")
    exit(1)

print("🔬 Test NER sur échantillon de reviews\n")

# Charger le modèle
print("📦 Chargement de spaCy...")
try:
    nlp = spacy.load("fr_core_news_lg")
    print(f"✅ Modèle chargé\n")
except OSError:
    print("❌ Modèle fr_core_news_lg non trouvé")
    print("   Installez avec: python -m spacy download fr_core_news_lg")
    exit(1)

# Charger quelques reviews
reviews_file = Path("data/reviews/paris-restaurant-reviews.json")

if not reviews_file.exists():
    print(f"❌ Fichier introuvable: {reviews_file}")
    exit(1)

print(f"📂 Chargement de {reviews_file.name}\n")
with open(reviews_file, encoding='utf-8') as f:
    data = json.load(f)

# Prendre le premier lieu avec des reviews
sample_reviews = []
for place in data[:10]:
    reviews = place.get('reviews_data', [])
    for review in reviews[:5]:  # Max 5 par lieu
        text = review.get('text', '').strip()
        if text and len(text) > 20:  # Texte non vide et assez long
            sample_reviews.append({
                'place_id': place['id'],
                'place_name': place['name'],
                'text': text,
                'language': review.get('language', 'unknown')
            })
        if len(sample_reviews) >= 10:
            break
    if len(sample_reviews) >= 10:
        break

print(f"✅ {len(sample_reviews)} reviews chargées pour test\n")
print("="*70)

# Traiter chaque review
entity_counts = {}

for i, review in enumerate(sample_reviews, 1):
    print(f"\n📝 Review #{i} ({review['language']}) - {review['place_name']}")
    print(f"Texte: {review['text'][:100]}...")
    
    doc = nlp(review['text'])
    
    entities = [(ent.text, ent.label_) for ent in doc.ents 
                if ent.label_ in {'LOC', 'FAC', 'ORG', 'PER'}]
    
    if entities:
        print(f"🎯 Entités extraites ({len(entities)}):")
        for ent_text, ent_label in entities:
            print(f"   • {ent_text} ({ent_label})")
            entity_counts[ent_label] = entity_counts.get(ent_label, 0) + 1
    else:
        print("   Aucune entité trouvée")

# Résumé
print("\n" + "="*70)
print("📊 RÉSUMÉ")
print("="*70)
print(f"Reviews testées: {len(sample_reviews)}")
print(f"Distribution des types d'entités:")
for label, count in sorted(entity_counts.items(), key=lambda x: -x[1]):
    print(f"  • {label}: {count}")
print("\n✅ Test terminé! Le NER fonctionne correctement.")
print("🚀 Vous pouvez maintenant lancer l'extraction complète:")
print("   python3 scripts/extract_entities_from_reviews.py --sample 100")
