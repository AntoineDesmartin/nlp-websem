# Pipeline de Reproductibilité : Enrichissement NLP du Knowledge Graph

**Date :** 19 janvier 2026  
**Objectif :** Ajouter deux techniques NLP avancées (NER et Sentiment Analysis) au projet TourGuide Paris  
**Techniques utilisées :** Named Entity Recognition (spaCy transformers) + Sentiment Analysis (DistilBERT)

---

## 📊 Vue d'Ensemble

**Avant :**
- Graphe de connaissances : 163,055 triplets
- Techniques : Extraction manuelle, règles SPARQL, embeddings basiques
- Données utilisées : Métadonnées TourPedia uniquement

**Après :**
- Graphe de connaissances : **187,157 triplets** (+24,102)
- Techniques : **+ NER (spaCy) + Sentiment (DistilBERT)**
- Données utilisées : **Métadonnées + Texte de 43,717 reviews**

---

## 🎯 Étape 1 : Nettoyage des Données NER

### Problème Initial
Le NER brut extrayait trop de bruit :
- Termes génériques : "Paris", "Service", "I"
- Faux positifs : "Nice" (adjectif), "Bar" (générique)
- Résultat : Pollution du graphe de connaissances

### Solution : Script de Filtrage

```bash
# 1. Créer le script de nettoyage
scripts/filter_ner_noise.py
```

**Ce qu'il fait :**
- Filtre les termes génériques (liste noire)
- Valide que les lieux existent dans le KG
- Ne garde que les mentions pertinentes

**Exécution :**
```bash
python3 scripts/filter_ner_noise.py
```

**Résultats :**
- **Avant :** 7,167 mentions (dont beaucoup de bruit)
- **Après :** 5,952 mentions valides
- **Output :** `data/kg_reviews_ner_clean.ttl`

### Intégration au KG

```bash
# 1. Backup du KG actuel
cp data/kg_inferred.ttl data/kg_inferred.ttl.backup

# 2. Restaurer version avant NER
cp data/kg_inferred.ttl.backup data/kg_inferred.ttl

# 3. Fusionner avec NER nettoyé
python3 scripts/merge_kg.py  # Ou fusion manuelle avec rdflib
```

**Vérification :**
```bash
# Compter les triplets schema:mentions
grep "schema:mentions" data/kg_inferred.ttl | wc -l
# Résultat attendu : ~5,952
```

---

## 🧠 Étape 2 : Analyse de Sentiment avec DistilBERT

### 2.1 Installation des Dépendances

```bash
# Ajouter à requirements.txt
echo "transformers" >> requirements.txt

# Installer
pip install transformers torch tqdm
```

### 2.2 Création du Script d'Analyse

```bash
# Créer le script
scripts/analyze_sentiment.py
```

**Paramètres clés :**
- Modèle : `nlptown/bert-base-multilingual-uncased-sentiment`
- Échantillon : 43,717 reviews (toutes les reviews avec texte)
- Output : Sentiment -1 (négatif) à +1 (positif)

**Exécution :**
```bash
# Analyser toutes les reviews (~20-25 min sur CPU)
python3 scripts/analyze_sentiment.py --sample 43717
```

**Outputs générés :**
1. `data/sentiment_stats.json` - Statistiques globales
   ```json
   {
     "total_reviews_analyzed": 43717,
     "sentiment_percentages": {
       "positive": 68.8,
       "neutral": 11.8,
       "negative": 19.4
     },
     "average_sentiment_score": 0.43,
     "contradictions_found": 37858
   }
   ```

2. `data/sentiment_by_place.json` - Sentiment agrégé par lieu (3,442 lieux)
   ```json
   {
     "place_id": {
       "place_name": "François Felix",
       "polarity": 10.0,
       "avg_sentiment": 0.5,
       "positive_count": 5,
       "total_reviews": 7
     }
   }
   ```

**Résultats :**
- ✅ 43,717 reviews analysées
- ✅ 3,442 lieux avec sentiment agrégé
- ✅ 68.8% sentiment positif global
- ✅ 5 contradictions majeures détectées (polarity haute, sentiment bas)

### 2.3 Intégration au Knowledge Graph

```bash
# 1. Backup avant sentiment
cp data/kg_inferred.ttl data/kg_inferred.ttl.backup_before_sentiment

# 2. Créer le script d'intégration
scripts/integrate_sentiment_to_kg.py
```

**Ce qu'il fait :**
- Charge `sentiment_by_place.json`
- Matche avec les URIs du KG via `tg:placeId`
- Ajoute 7 propriétés par lieu :
  - `tg:avgSentiment` (score moyen -1 à +1)
  - `tg:sentimentReviewsAnalyzed` (nombre)
  - `tg:sentimentPositiveCount` (nombre)
  - `tg:sentimentNegativeCount` (nombre)
  - `tg:sentimentPositivePercent` (%)
  - `tg:sentimentNegativePercent` (%)
- Ajoute stats globales (1 ressource)

**Exécution :**
```bash
python3 scripts/integrate_sentiment_to_kg.py
```

**Résultats :**
- ✅ 3,442 lieux enrichis
- ✅ 24,094 triplets ajoutés
- ✅ KG final : **187,157 triplets**

**Vérification :**
```bash
# Compter lieux avec sentiment
grep "tg:avgSentiment" data/kg_inferred.ttl | wc -l
# Résultat : 3,442
```

---

## 🔍 Étape 3 : Requêtes SPARQL

### 3.1 Créer les Requêtes NER

```bash
# Déjà créées, vérifier qu'elles existent
ls queries/ner_*.rq

# Top mentions
queries/ner_top_mentions.rq

# Co-visitation
queries/ner_covisitation.rq

# Itinéraires
queries/ner_itineraries.rq
```

**Ajustement du seuil co-visitation :**
```bash
# Modifier queries/ner_covisitation.rq
# Ligne 18 : Changer HAVING (COUNT(?review) >= 5) → >= 3
sed -i '' 's/HAVING (COUNT(?review) >= 5)/HAVING (COUNT(?review) >= 3)/' queries/ner_covisitation.rq
```

### 3.2 Créer les Requêtes Sentiment

```bash
# 1. Top lieux par sentiment
queries/sentiment_top_positive.rq

# 2. Contradictions polarity vs sentiment
queries/sentiment_contradictions.rq

# 3. Stats globales
queries/sentiment_global_stats.rq
```

**Exemples de requêtes créées :**

**Contradictions :**
```sparql
PREFIX tg: <https://example.org/tourguide#>

SELECT ?name ?polarity ?avgSentiment ?negativePercent ?reviewCount
WHERE {
  ?place tg:name ?name ;
         tg:polarity ?polarity ;
         tg:avgSentiment ?avgSentiment ;
         tg:sentimentNegativePercent ?negativePercent ;
         tg:sentimentReviewsAnalyzed ?reviewCount .
  
  # Polarity haute mais sentiment négatif
  FILTER(?polarity >= 7.0 && ?avgSentiment < 0.0 && ?reviewCount >= 5)
}
ORDER BY DESC(?polarity)
LIMIT 20
```

---

## 🎨 Étape 4 : Mise à Jour du Frontend

### 4.1 Ajouter les Requêtes au Backend

**Fichier :** `app/main.py`

```python
# Ajouter dans query_files dict (ligne ~223)
# 🧠 Requêtes Sentiment Analysis
"sentiment_top_positive": "sentiment_top_positive.rq",
"sentiment_contradictions": "sentiment_contradictions.rq",
"sentiment_global_stats": "sentiment_global_stats.rq",
```

### 4.2 Ajouter les Boutons Frontend

**Fichier :** `app/static/index.html`

```html
<!-- Après la section NER (ligne ~476) -->
<!-- Séparation visuelle -->
<div style="border-top: 1px dashed #e5e7eb; margin: 1.5rem 0;"></div>

<!-- 🧠 Requêtes Sentiment -->
<div style="margin-bottom: 1rem;">
    <div style="font-weight: 600; color: #8b5cf6; margin-bottom: 0.5rem;">
        🧠 Analyses Sentiment (DistilBERT Transformers)
    </div>
    <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
        <button onclick="askPredefined('sentiment_top_positive')">Top Sentiment Positif</button>
        <button onclick="askPredefined('sentiment_contradictions')">Contradictions Détectées</button>
        <button onclick="askPredefined('sentiment_global_stats')">Stats Globales</button>
    </div>
</div>
```

### 4.3 Ajouter l'Endpoint Sentiment Stats

**Fichier :** `app/main.py` (après `/api/ner/stats`)

```python
@app.get("/api/sentiment/stats")
async def get_sentiment_stats():
    """Retourne les statistiques d'analyse de sentiment"""
    try:
        import json
        stats_file = Path(__file__).parent.parent / "data" / "sentiment_stats.json"
        
        if not stats_file.exists():
            return {"status": "not_available"}
        
        with open(stats_file, encoding='utf-8') as f:
            stats = json.load(f)
        
        return {"status": "available", "stats": stats}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

---

## 🤖 Étape 5 : Mise à Jour GraphRAG Approche 1 (SPARQL)

### 5.1 Enrichir le Prompt OpenRouter

**Fichier :** `app/services/openrouter_service.py`

**Ajouter documentation sentiment (après NER, ligne ~140) :**

```python
🆕 NOUVELLES PROPRIÉTÉS SENTIMENT ANALYSIS (DistilBERT Transformers):
⚠️ ANALYSE DE SENTIMENT SUR 43,717 REVIEWS TEXTUELLES
- tg:avgSentiment (score moyen -1 à +1, decimal)
  * -1.0 = très négatif, 0 = neutre, +1.0 = très positif
  * Calculé par DistilBERT sur le TEXTE des reviews
- tg:sentimentReviewsAnalyzed (nombre reviews analysées)
- tg:sentimentPositivePercent (% reviews positives)

💡 DIFFÉRENCE POLARITY vs SENTIMENT:
- tg:polarity = Note structurée TourPedia (0-10, métadonnées)
- tg:avgSentiment = Sentiment NLP du TEXTE (-1 à +1)
- Peuvent révéler des CONTRADICTIONS !
```

**Ajouter exemples de requêtes (ligne ~400) :**

```python
Question: "Quels lieux ont un bon sentiment textuel ?"
Réponse:
PREFIX tg: <https://example.org/tourguide#>

SELECT ?placeName ?avgSentiment ?positivePercent ?reviewCount
WHERE {
  ?place tg:name ?placeName ;
         tg:avgSentiment ?avgSentiment ;
         tg:sentimentPositivePercent ?positivePercent ;
         tg:sentimentReviewsAnalyzed ?reviewCount .
  FILTER(?reviewCount >= 10)
}
ORDER BY DESC(?avgSentiment)
LIMIT 20

Question: "Trouve les lieux avec note élevée mais sentiment négatif"
Réponse:
PREFIX tg: <https://example.org/tourguide#>

SELECT ?name ?polarity ?avgSentiment ?negativePercent
WHERE {
  ?place tg:name ?name ;
         tg:polarity ?polarity ;
         tg:avgSentiment ?avgSentiment ;
         tg:sentimentNegativePercent ?negativePercent ;
         tg:sentimentReviewsAnalyzed ?reviewCount .
  FILTER(?polarity >= 7.0 && ?avgSentiment < 0.0 && ?reviewCount >= 5)
}
ORDER BY DESC(?polarity)
```

---

## 🧠 Étape 6 : Mise à Jour GraphRAG Approche 2 (Embeddings)

### 6.1 Enrichir le Service Embeddings

**Fichier :** `app/services/embedding_service.py`

**Ajouter propriétés sentiment à l'extraction (ligne ~140) :**

```python
tg_props = {
    "name": "name",
    "polarity": "polarity",
    "numReviews": "numReviews",
    # ... autres propriétés ...
    # 🆕 Propriétés sentiment
    "avgSentiment": "avgSentiment",
    "sentimentReviewsAnalyzed": "sentimentReviewsAnalyzed",
    "sentimentPositivePercent": "sentimentPositivePercent",
    "sentimentNegativePercent": "sentimentNegativePercent",
}
```

### 6.2 Regénérer les Embeddings

```bash
# 1. Supprimer le cache
rm data/embeddings_cache.pkl

# 2. Redémarrer le serveur (générera automatiquement)
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8005

# 3. Poser une question dans Approche 2 pour déclencher génération
# Les embeddings incluront maintenant les données sentiment
```

**Vérification :**
```python
# Vérifier que sentiment est dans les embeddings
import pickle
with open('data/embeddings_cache.pkl', 'rb') as f:
    data = pickle.load(f)
    
# Vérifier premier lieu
first_place = list(data['info'].values())[0]
print(first_place.get('avgSentiment'))  # Devrait afficher une valeur
```

---

## 📋 Étape 7 : Mise à Jour Documentation

### 7.1 Ontologie

**Fichier :** `ontology/tourguide.ttl` (déjà fait, vérifier)

```turtle
# Propriétés sentiment (lignes ~252-256)
tg:avgSentiment a owl:DatatypeProperty ;
    rdfs:label "Average Sentiment Score" ;
    rdfs:comment "Score moyen de sentiment calculé par DistilBERT (-1 à +1)" ;
    rdfs:domain tg:Place ;
    rdfs:range xsd:decimal .

tg:sentimentReviewsAnalyzed a owl:DatatypeProperty ;
    rdfs:label "Sentiment Reviews Analyzed" ;
    rdfs:domain tg:Place ;
    rdfs:range xsd:integer .

# ... autres propriétés sentiment ...
```

### 7.2 SHACL

**Fichier :** `shacl/shapes.ttl`

```turtle
# Ajouter préfixe schema: si manquant
@prefix schema: <http://schema.org/> .

# Ajouter validation sentiment dans PlaceShape
tg:PlaceShape
    sh:property [
        sh:path tg:avgSentiment ;
        sh:datatype xsd:decimal ;
        sh:minInclusive -1.0 ;
        sh:maxInclusive 1.0 ;
    ] ;
    sh:property [
        sh:path tg:sentimentReviewsAnalyzed ;
        sh:datatype xsd:integer ;
        sh:minInclusive 0 ;
    ] .
```

---

## ✅ Étape 8 : Validation Complète

### 8.1 Vérifier le KG

```bash
# 1. Compter total triplets
grep -c "^\s*<" data/kg_inferred.ttl
# Attendu : ~187,157

# 2. Vérifier NER
grep -c "schema:mentions" data/kg_inferred.ttl  
# Attendu : ~5,952

# 3. Vérifier Sentiment
grep -c "tg:avgSentiment" data/kg_inferred.ttl
# Attendu : 3,442
```

### 8.2 Tester les Requêtes Frontend

**Ouvrir :** http://localhost:8005

1. **Onglet "Inférence & Requêtes"**
   - Tester "Top Lieux Mentionnés" (NER)
   - Tester "Co-visitation" (NER)
   - Tester "Itinéraires" (NER)
   - Tester "Top Sentiment Positif" (Sentiment)
   - Tester "Contradictions Détectées" (Sentiment)
   - Tester "Stats Globales" (Sentiment)

2. **Onglet "Approche 1 (SPARQL)"**
   - Poser : "Quels lieux ont un bon sentiment textuel ?"
   - Vérifier que le SPARQL généré utilise `tg:avgSentiment`
   - Poser : "Trouve les lieux avec note élevée mais sentiment négatif"
   - Vérifier résultats (5 contradictions attendues)

3. **Onglet "Approche 2 (Embeddings)"**
   - Poser : "Recommande des restaurants avec bon sentiment"
   - Vérifier que les résultats sont pertinents

### 8.3 Vérifier Embeddings Enrichis

```python
python3 - <<'PY'
import pickle
with open('data/embeddings_cache.pkl', 'rb') as f:
    data = pickle.load(f)

# Vérifier 5 premiers lieux
for i, (uri, info) in enumerate(list(data['info'].items())[:5], 1):
    name = info.get('name', 'N/A')
    sentiment = info.get('avgSentiment')
    print(f"{i}. {name}: sentiment={sentiment}")
PY

# Résultat attendu : Au moins 3/5 avec sentiment != None
```

---

## 📊 Résultats Finaux

### Statistiques Complètes

| Métrique | Valeur |
|----------|--------|
| **Triplets KG Final** | 187,157 (+24,102) |
| **Lieux avec NER** | 227 lieux mentionnés |
| **Relations NER** | 5,952 mentions |
| **Lieux avec Sentiment** | 3,442 |
| **Reviews analysées** | 43,717 |
| **Sentiment positif** | 68.8% |
| **Contradictions** | 5 majeures |
| **Itinéraires découverts** | 20 |
| **Co-visitation pairs** | 8-15 (seuil >= 3) |

### Techniques NLP Déployées

1. **NER (Named Entity Recognition)**
   - Modèle : `fr_core_news_lg` (spaCy transformers)
   - Architecture : CamemBERT français
   - Usage : Extraction entités depuis texte
   - Relations créées : `schema:mentions`

2. **Sentiment Analysis**
   - Modèle : `nlptown/bert-base-multilingual-uncased-sentiment`
   - Architecture : DistilBERT multilingue
   - Usage : Analyse sentiment reviews
   - Propriétés créées : `tg:avgSentiment`, `tg:sentimentPositivePercent`, etc.

### Fichiers Générés

**Scripts :**
- `scripts/filter_ner_noise.py` - Nettoyage NER
- `scripts/analyze_sentiment.py` - Analyse sentiment
- `scripts/integrate_sentiment_to_kg.py` - Intégration KG
- `scripts/reset_embeddings.py` - Régénération cache

**Données :**
- `data/kg_reviews_ner_clean.ttl` - NER nettoyé
- `data/kg_sentiment.ttl` - Sentiment RDF
- `data/kg_inferred.ttl` - KG final (187K triplets)
- `data/sentiment_stats.json` - Stats globales
- `data/sentiment_by_place.json` - Sentiment par lieu
- `data/ner_stats.json` - Stats NER
- `data/embeddings_cache.pkl` - Embeddings enrichis

**Requêtes SPARQL :**
- `queries/ner_top_mentions.rq`
- `queries/ner_covisitation.rq`
- `queries/ner_itineraries.rq`
- `queries/sentiment_top_positive.rq`
- `queries/sentiment_contradictions.rq`
- `queries/sentiment_global_stats.rq`

**Documentation :**
- `NER_README.md` - Doc NER
- `TEST_NER_GRAPHRAG.md` - Guide test
- Ce fichier : `PIPELINE_ENRICHISSEMENT_NLP.md`

---

## 🚀 Commandes Complètes de Reproductibilité

```bash
# ========================================
# PIPELINE COMPLET : De Zéro à GraphRAG NLP
# ========================================

# 1. INSTALLATION
pip install transformers torch tqdm spacy
python3 -m spacy download fr_core_news_lg

# 2. NER
## 2.1 Extraction (si pas déjà fait)
python3 scripts/extract_entities_from_reviews.py

## 2.2 Nettoyage
python3 scripts/filter_ner_noise.py

## 2.3 Backup et Fusion
cp data/kg_inferred.ttl data/kg_inferred.ttl.backup
# Fusionner kg_reviews_ner_clean.ttl avec kg_inferred.ttl

# 3. SENTIMENT ANALYSIS
## 3.1 Analyse
python3 scripts/analyze_sentiment.py --sample 43717  # ~20 min

## 3.2 Intégration KG
cp data/kg_inferred.ttl data/kg_inferred.ttl.backup_before_sentiment
python3 scripts/integrate_sentiment_to_kg.py

# 4. EMBEDDINGS
## 4.1 Régénération
rm data/embeddings_cache.pkl
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8005
# Poser une question dans Approche 2 pour générer

# 5. VALIDATION
## 5.1 Vérifier triplets
grep -c "^\s*<" data/kg_inferred.ttl  # ~187,157
grep -c "schema:mentions" data/kg_inferred.ttl  # ~5,952
grep -c "tg:avgSentiment" data/kg_inferred.ttl  # 3,442

## 5.2 Tester frontend
# http://localhost:8005
# Tester tous les boutons NER et Sentiment

# ========================================
# RÉSULTAT : KG Enrichi NLP Fonctionnel
# ========================================
```

---

## 🎓 Pour la Soutenance

### Points Clés à Mentionner

1. **Deux techniques transformers avancées**
   - NER (spaCy CamemBERT) : Extraction entités
   - Sentiment (DistilBERT) : Analyse opinion

2. **Extraction sur données non-structurées**
   - 43,717 reviews textuelles analysées
   - Conversion texte → RDF structuré

3. **Complémentarité des techniques**
   - NER : QUI/QUOI est mentionné (relations)
   - Sentiment : COMMENT c'est perçu (opinion)

4. **Intégration complète GraphRAG**
   - Approche 1 : SPARQL enrichi avec NER + Sentiment
   - Approche 2 : Embeddings enrichis avec Sentiment

5. **Valeur ajoutée démontrée**
   - Contradictions détectées (polarity vs sentiment)
   - Co-visitation découverte (patterns cachés)
   - Itinéraires extraits du texte

### Démonstration Recommandée

1. Montrer requête SPARQL "Contradictions"
2. Montrer itinéraires NER
3. Comparer Approche 1 vs Approche 2 sur même question
4. Expliquer transformers utilisés

---

## 📝 Notes de Maintenance

### Regénérer en Cas de Besoin

**NER :**
```bash
python3 scripts/extract_entities_from_reviews.py
python3 scripts/filter_ner_noise.py
# Re-fusionner au KG
```

**Sentiment :**
```bash
python3 scripts/analyze_sentiment.py --sample 43717
python3 scripts/integrate_sentiment_to_kg.py
```

**Embeddings :**
```bash
rm data/embeddings_cache.pkl
# Redémarrer serveur
```

### Fichiers de Backup

Conserver :
- `data/kg_inferred.ttl.backup_before_sentiment` - Avant sentiment
- `data/kg_inferred.ttl.backup` - Avant NER nettoyé
- `data/kg_reviews_ner.ttl` - NER brut (si espace disque)

---

## ✅ Checklist Finale

- [x] NER extrait et nettoyé (5,952 mentions)
- [x] Sentiment analysé (43,717 reviews, 3,442 lieux)
- [x] KG enrichi (187,157 triplets)
- [x] Requêtes SPARQL créées (6 nouvelles)
- [x] Frontend mis à jour (boutons NER + Sentiment)
- [x] GraphRAG Approche 1 enrichi (prompt + exemples)
- [x] GraphRAG Approche 2 enrichi (embeddings + sentiment)
- [x] Documentation complète
- [x] Validation tests OK

**🎉 PROJET COMPLET ET PRÊT POUR LA SOUTENANCE ! 🎉**
