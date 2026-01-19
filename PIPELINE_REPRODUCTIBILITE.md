# Pipeline de reproductibilité — TourGuide Paris Knowledge Graph

Ce document décrit la pipeline complète du projet et les commandes nécessaires pour reproduire le Knowledge Graph (KG) enrichi.

## Prérequis

### Environnement

```powershell
# Python 3.9+
python --version

# Java 11+ (pour RMLMapper)
java -version

# Créer et activer l'environnement virtuel
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Installer les dépendances
pip install -r requirements.txt
```

### Outils nécessaires

- RMLMapper : `tools/rmlmapper-8.1.0-r380-all.jar`
- Clé API OpenRouter (pour GraphRAG) :

```powershell
$env:OPENROUTER_API_KEY="sk-or-v1-..."
```

## Pipeline de construction du Knowledge Graph

### Étape 1 — Import des données brutes

But : placer toutes les données sources dans `data/raw/`.

```powershell
Get-ChildItem data\raw
```

Fichiers attendus (exemples) :

- `tourpedia_paris_*.csv` (restaurants, attractions, POI)
- `tourpedia_paris_*.json`
- `wikivoyage_paris_wikitext.json`

### Étape 2 — Nettoyage des CSV (robustesse avant mapping)

But : corriger les problèmes de parsing (ex. virgules dans les adresses) avant le mapping RML.

```powershell
python scripts/clean_tourpedia_csv.py
```

Résultat : CSV nettoyés prêts pour le mapping.

### Étape 3 — Réduction des sources volumineuses

But : réduire la taille des sources pour accélérer les traitements (conserver les lieux les plus pertinents).

```powershell
python scripts/reduce_tourpedia.py
```

Résultat : fichiers réduits dans `data/subset/`.

### Étape 4 — Lifting en RDF via RML (données structurées)

But : transformer CSV et JSON en RDF avec RMLMapper.

```powershell
# Mapping CSV -> RDF
java -jar tools/rmlmapper-8.1.0-r380-all.jar `
  -m mappings/tourpedia-csv.ttl `
  -o data/kg_csv.ttl `
  -s turtle

# Mapping JSON -> RDF
java -jar tools/rmlmapper-8.1.0-r380-all.jar `
  -m mappings/tourpedia-json.ttl `
  -o data/kg_json.ttl `
  -s turtle
```

Résultat : `data/kg_csv.ttl` et `data/kg_json.ttl`.

### Étape 5 — Fusion des graphes CSV et JSON

But : obtenir un graphe unifié.

```powershell
python -c "from rdflib import Graph; g = Graph(); g.parse('data/kg_csv.ttl', format='turtle'); g.parse('data/kg_json.ttl', format='turtle'); g.serialize('data/kg.ttl', format='turtle'); print('Merged triples:', len(g))"
```

Résultat : `data/kg.ttl`.

### Étape 6 — Filtrage des lieux incomplets

But : supprimer les lieux sans coordonnées (nécessaires pour les requêtes de proximité et la validation SHACL).

```powershell
python scripts/filter_incomplete_places.py
```

Résultat : `data/kg_filtered.ttl`.

### Étape 7 — Validation SHACL (1ère passe)

But : vérifier la conformité du graphe avant d’intégrer d’autres sources.

```powershell
python scripts/validate_shacl.py data/kg_filtered.ttl
```

Résultat attendu : validation réussie.

### Étape 8 — Extraction depuis Wikivoyage (données non structurées)

But : extraire des lieux depuis les templates MediaWiki (sections "see", "do", "eat"), normaliser et lier à Wikidata.

```powershell
python scripts/extract_wikivoyage_to_rdf.py
```

Résultat : `data/kg_wikivoyage.ttl`.

### Étape 9 — Fusion TourPedia filtré + Wikivoyage

But : intégrer données structurées (TourPedia) et non structurées (Wikivoyage).

```powershell
python -c "from rdflib import Graph; g = Graph(); g.parse('data/kg_filtered.ttl', format='turtle'); g.parse('data/kg_wikivoyage.ttl', format='turtle'); g.serialize('data/kg_final.ttl', format='turtle'); print('Final triples:', len(g))"
```

Résultat : `data/kg_final.ttl`.

### Étape 10 — Validation SHACL (2ème passe)

```powershell
python scripts/validate_shacl.py data/kg_final.ttl
```

Résultat attendu : validation réussie.

### Étape 11 — Enrichissement par avis (reviews) et alignement Schema.org

But : intégrer les avis utilisateurs comme ressources RDF distinctes.

#### 11a) Fusion des graphs de reviews

```powershell
python -c "from rdflib import Graph; g = Graph(); g.parse('data/kg_reviews_attraction.ttl', format='turtle'); g.parse('data/kg_reviews_poi.ttl', format='turtle'); g.parse('data/kg_reviews_restaurant.ttl', format='turtle'); g.serialize('data/kg_reviews_all.ttl', format='turtle'); print('Reviews triples:', len(g))"
```

Résultat : `data/kg_reviews_all.ttl`.

#### 11b) Fusion kg_final + reviews

```powershell
python -c "from rdflib import Graph; g = Graph(); g.parse('data/kg_final.ttl', format='turtle'); g.parse('data/kg_reviews_all.ttl', format='turtle'); g.serialize('data/kg_enriched.ttl', format='turtle'); print('Enriched triples:', len(g))"
```

Résultat : `data/kg_enriched.ttl`.

#### 11c) Validation SHACL du graphe enrichi

```powershell
python scripts/validate_shacl.py data/kg_enriched.ttl
```

Résultat attendu : validation réussie.

### Étape 12 — Alignement et liage vers le Web de données liées

But : lier des entités à Wikidata/DBpedia/Wikipedia pour ouvrir le KG sur le LOD.

```powershell
python scripts/link_wikidata_dbpedia.py data/kg_enriched.ttl data/kg_linked.ttl
```

Résultat : `data/kg_linked.ttl`.

### Étape 13 — Validation SHACL (3ème passe)

```powershell
python scripts/validate_shacl.py data/kg_linked.ttl
```

Résultat attendu : validation réussie.

### Étape 14 — Enrichissement SKOS (annotation thématique)

But : ajouter des liens `tg:hasTopic` entre les lieux et les concepts du thésaurus SKOS.

Commande reproductible (sans écraser l’entrée) :

```powershell
python scripts/enrich_skos.py --input data/kg_linked.ttl --topics thesaurus/topics.ttl --output data/kg_skos.ttl
```

Résultat : `data/kg_skos.ttl`.

### Étape 15 — Inférence par règles SPARQL

But : ajouter des classes inférées via règles (SPARQL CONSTRUCT).

```powershell
python scripts/apply_inference_rules.py data/kg_skos.ttl data/kg_inferred.ttl
```

Résultat : `data/kg_inferred.ttl`.

### Étape 16 — Recommandation par profils (TransE) 

But : générer des recommandations personnalisées à partir d’un graphe de recommandation dérivé du KG, en entraînant un modèle TransE sur des profils utilisateurs synthétiques (nationalité/langue + saison + budget) et des relations de type `tg:likesPlace`.

#### 16.1 Générer les profils (nationalité/langue + saison + budget)

Principe : on crée des profils discrets combinant :

- Langue / nationalité (proxy comportemental)
- Saison (proxy contexte de visite)
- Budget (proxy préférences de gamme)

Commandes (exemple) :

```powershell
# Génère les profils et les triples de recommandation à partir du KG
python scripts/build_reco_profiles.py --kg data/kg_inferred.ttl --out data/kg_reco.ttl --tsv data/reco_triples.tsv
```

Résultats :

- `data/kg_reco.ttl` : graphe dédié recommandation (entités profils + relations)
- `data/reco_triples.tsv` : triples au format entraînement (TransE)

#### 16.2 Entraîner TransE sur les triples profils → lieux

But : apprendre des embeddings (profils et lieux) pour produire des recommandations.

```powershell
python scripts/train_transe.py --triples data/reco_triples.tsv --out data/recommendations_transe.json --epochs 150
```

Résultat :

- `data/recommendations_transe.json` : top recommandations par profil

#### 16.3 Évaluer le modèle (MRR / Hits@K)

```powershell
python scripts/evaluate_transe.py --triples data/reco_triples.tsv --model data/recommendations_transe.json
```

Résultat attendu :

- MRR ≈ 60.6% (selon ton état actuel)

But : permettre à l’API de servir les recommandations.

### Étape 17 — Enrichissement NLP (NER + Sentiment DistilBERT) (optionnel)

But : exploiter le texte des reviews pour ajouter :

- des relations (NER : “ce lieu mentionne X”)
- une opinion (Sentiment : score moyen par lieu)

#### 17.1 NER sur reviews (spaCy transformers)

##### 17.1.1 Extraction brute d’entités

```powershell
python scripts/extract_entities_from_reviews.py
```

Résultat (ex.) : `data/kg_reviews_ner.ttl` (mentions brutes)

##### 17.1.2 Nettoyage anti-bruit (filtrage)

```powershell
python scripts/filter_ner_noise.py
```

Résultat :

- `data/kg_reviews_ner_clean.ttl`
- Mentions attendues : ~5,952

##### 17.1.3 Fusion NER nettoyé → KG

```powershell
# Merge
python scripts/merge_kg.py --base data/kg_inferred.ttl --add data/kg_reviews_ner_clean.ttl --out data/kg_inferred.ttl
```

#### 17.2 Sentiment analysis (DistilBERT / Transformers)

##### 17.2.1 Installer dépendances

```powershell
pip install transformers torch tqdm
```

##### 17.2.2 Analyse sentiment sur toutes les reviews textuelles

Modèle : `nlptown/bert-base-multilingual-uncased-sentiment`

Sortie : score normalisé [-1 ; +1]

```powershell
python scripts/analyze_sentiment.py --sample 43717
```

Outputs :

- `data/sentiment_stats.json`
- `data/sentiment_by_place.json`

##### 17.2.3 Intégration sentiment → KG

```powershell
# Backup avant intégration sentiment
cp data/kg_inferred.ttl data/kg_inferred.ttl.backup_before_sentiment

# Injection des propriétés tg:avgSentiment etc.
python scripts/integrate_sentiment_to_kg.py
```

## Lancement de l'application GraphRAG

### 1) Générer le cache d'embeddings (optionnel mais recommandé)

Remarque : la commande ci-dessous correspond au script présent dans `scripts/`.

```powershell
python scripts/regenerate_embeddings_cache.py
```

Résultat : `data/embeddings_cache.pkl` (le nombre d'embeddings dépend du `limit` du script).

### 2) Lancer le serveur FastAPI

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3) Ouvrir l'interface web

URL : `http://localhost:8000`

## Tests pertinents

### Test 1 — Comparaison des 2 approches GraphRAG

Interface web :

1. Aller sur l'onglet Comparaison GraphRAG
2. Taper : "Quels sont les meilleurs restaurants à Paris ?"
3. Lancer la comparaison

Résultat attendu :

- Approche 1 (SPARQL) : requête SPARQL générée + résultats structurés
- Approche 2 (Embeddings) : réponse en langage naturel + entités proches

### Test 2 — Requête SPARQL avec classes inférées

Interface web : onglet SPARQL.

Exemple : "Trouve-moi des hidden gems près de la Seine".

Résultat attendu : requête exploitant `tg:HiddenGem` + filtre géographique.

### Test 3 — Requête fédérée Wikidata

```powershell
python -c "from app.services.sparql_client import SPARQLClient; client = SPARQLClient(); results = client.query(open('queries/q16_federated_enrichment.rq', encoding='utf-8').read()); print(len(results), 'resultats')"
```

Résultat attendu : résultats via `SERVICE`.

### Test 4 — Statistiques du graphe final

```powershell
python scripts/stats_enriched.py
```

### Test 5 — Validation SHACL finale

```powershell
python scripts/validate_shacl.py data/kg_inferred.ttl
```

Résultat attendu : conformité totale.

## Résultats attendus à chaque étape

| Étape | Fichier produit | Triples | Validation SHACL |
|------:|-----------------|--------:|-----------------|
| 5 | `data/kg.ttl` | variable | - |
| 6 | `data/kg_filtered.ttl` | variable | oui |
| 9 | `data/kg_final.ttl` | ~75k | oui |
| 11 | `data/kg_enriched.ttl` | ~139k | oui |
| 12 | `data/kg_linked.ttl` | ~139k+ | oui |
| 14 | `data/kg_skos.ttl` | variable | oui |
| 15 | `data/kg_inferred.ttl` | ~141k | oui |

## Dépannage

### Erreur RMLMapper : "Input file not found"

Vérifier que les fichiers attendus existent dans `data/subset/` après l'étape 3.

### Erreur SHACL : "Conforms: False"

Lire le rapport de validation et corriger les données sources ou l'étape de transformation précédente.

### Erreur OpenRouter : "API key missing"

```powershell
$env:OPENROUTER_API_KEY="sk-or-v1-..."
```

### Cache d'embeddings manquant

Il peut être généré au premier lancement, ou via l'étape "cache d'embeddings" ci-dessus.

## Fichiers importants

| Fichier | Description |
|---------|-------------|
| `data/kg_inferred.ttl` | Graphe final (avec inférence) |
| `shacl/shapes.ttl` | Contraintes SHACL |
| `rules/r1-r4.rq` | Règles d'inférence SPARQL |
| `queries/*.rq` | Requêtes de compétence |
| `app/main.py` | API FastAPI |
| `GRAPHRAG_COMPARISON.md` | Comparaison des approches GraphRAG |

## Étapes optionnelles

Les étapes optionnelles sont intégrées directement dans la pipeline :

- Étape 16 : recommandation par profils (TransE)
- Étape 17 : enrichissement NLP (NER + Sentiment)

## Checklist de validation finale

- [ ] Environnement virtuel activé
- [ ] RMLMapper présent dans `tools/`
- [ ] Clé API OpenRouter configurée
- [ ] `data/kg_inferred.ttl` généré
- [ ] Validation SHACL réussie
- [ ] Cache d'embeddings généré (optionnel)
- [ ] Serveur lancé sans erreur
- [ ] Interface web accessible
- [ ] Test comparaison GraphRAG fonctionnel
- [ ] Requête fédérée Wikidata opérationnelle

Date de création : 2026-01-19
