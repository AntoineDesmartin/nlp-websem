# 🚀 Pipeline de Reproductibilité - TourGuide Paris Knowledge Graph

Ce document suit la pipeline complète du projet et détaille chaque étape avec les commandes exactes pour reproduire le KG enrichi.

---

## 📋 Prérequis

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
- **RMLMapper** : `tools/rmlmapper-8.1.0-r380-all.jar`
- **Clé API OpenRouter** (pour GraphRAG) :
```powershell
$env:OPENROUTER_API_KEY="sk-or-v1-..."
```

---

## 🏗️ Pipeline de Construction du Knowledge Graph

### Étape 1 - Import des données brutes

**But** : Rassembler toutes les données sources (CSV et JSON) dans `data/raw/` pour séparer les entrées brutes des fichiers produits.

```powershell
# Vérifier la présence des fichiers sources
ls data/raw/
```

**Fichiers attendus** :
- `tourpedia_paris_*.csv` (restaurants, attractions, POI)
- `tourpedia_paris_*.json`
- `wikivoyage_paris_wikitext.json`

---

### Étape 2 - Nettoyage des CSV (robustesse avant mapping)

**But** : Corriger les problèmes de parsing dus aux virgules dans les adresses. Sans ce nettoyage, RML générerait des triples incohérents.

```powershell
python scripts/clean_tourpedia_csv.py
```

**Résultat** : CSV nettoyés prêts pour le mapping RML.

---

### Étape 3 - Réduction des sources volumineuses

**But** : Réduire la taille des fichiers pour accélérer les traitements, en gardant les lieux les plus pertinents (plus d'avis).

```powershell
python scripts/reduce_tourpedia.py
```

**Résultat** : Fichiers réduits dans `data/subset/`.

---

### Étape 4 - Lifting en RDF via RML (données structurées)

**But** : Transformer CSV et JSON en RDF avec RMLMapper.

```powershell
# Mapping CSV → RDF
java -jar tools/rmlmapper-8.1.0-r380-all.jar `
  -m mappings/tourpedia-csv.ttl `
  -o data/kg_csv.ttl `
  -s turtle

# Mapping JSON → RDF
java -jar tools/rmlmapper-8.1.0-r380-all.jar `
  -m mappings/tourpedia-json.ttl `
  -o data/kg_json.ttl `
  -s turtle
```

**Résultat** : `kg_csv.ttl` et `kg_json.ttl` créés.

---

### Étape 5 - Fusion des graphes CSV et JSON

**But** : Rassembler toutes les données structurées dans un graphe unifié.

```powershell
python -c "from rdflib import Graph; g = Graph(); g.parse('data/kg_csv.ttl', format='turtle'); g.parse('data/kg_json.ttl', format='turtle'); g.serialize('data/kg.ttl', format='turtle'); print(f'Merged triples: {len(g)}')"
```

**Résultat** : `data/kg.ttl` créé.

---

### Étape 6 - Filtrage des lieux incomplets

**But** : Supprimer les lieux sans coordonnées (nécessaires pour les requêtes de proximité et validation SHACL).

```powershell
python scripts/filter_incomplete_places.py
```

**Résultat** : `data/kg_filtered.ttl` créé.

---

### Étape 7 - Validation SHACL (1ère passe)

**But** : Garantir que les données sont conformes au modèle avant d'intégrer d'autres sources.

```powershell
python scripts/validate_shacl.py data/kg_filtered.ttl
```

**Résultat attendu** : ✅ Validation réussie

---

### Étape 8 - Extraction depuis Wikivoyage (données non structurées)

**But** : Extraire des lieux depuis les templates MediaWiki (sections "see", "do", "eat"), normaliser et typer avec OWL/SKOS.

```powershell
python scripts/extract_wikivoyage_to_rdf.py
```

**Résultat** : `data/kg_wikivoyage.ttl` créé avec liens Wikidata (`owl:sameAs`).

---

### Étape 9 - Fusion TourPedia filtré + Wikivoyage

**But** : Intégrer les données structurées et non structurées.

```powershell
python -c "from rdflib import Graph; g = Graph(); g.parse('data/kg_filtered.ttl', format='turtle'); g.parse('data/kg_wikivoyage.ttl', format='turtle'); g.serialize('data/kg_final.ttl', format='turtle'); print(f'Final triples: {len(g)}')"
```

**Résultat** : `data/kg_final.ttl` créé (≈75,940 triples).

---

### Étape 10 - Validation SHACL (2ème passe)

**But** : Vérifier que l'intégration de Wikivoyage n'a pas introduit d'erreurs.

```powershell
python scripts/validate_shacl.py data/kg_final.ttl
```

**Résultat attendu** : ✅ Validation réussie

---

### Étape 11 - Enrichissement par avis (reviews) et alignement Schema.org

**But** : Intégrer les avis utilisateurs comme ressources RDF distinctes (Schema.org).

#### 11a) Merge des reviews attraction + POI + restaurants

```powershell
python -c "from rdflib import Graph; g = Graph(); g.parse('data/kg_reviews_attraction.ttl', format='turtle'); g.parse('data/kg_reviews_poi.ttl', format='turtle'); g.parse('data/kg_reviews_restaurant.ttl', format='turtle'); g.serialize('data/kg_reviews_all.ttl', format='turtle'); print(f'Reviews triples: {len(g)}')"
```

**Résultat** : `data/kg_reviews_all.ttl` (≈63,662 triples).

#### 11b) Merge kg_final + reviews → kg_enriched

```powershell
python -c "from rdflib import Graph; g = Graph(); g.parse('data/kg_final.ttl', format='turtle'); g.parse('data/kg_reviews_all.ttl', format='turtle'); g.serialize('data/kg_enriched.ttl', format='turtle'); print(f'Enriched triples: {len(g)}')"
```

**Résultat** : `data/kg_enriched.ttl` (≈139,602 triples).

#### 11c) Validation SHACL du graphe enrichi

```powershell
python scripts/validate_shacl.py data/kg_enriched.ttl
```

**Résultat attendu** : ✅ Validation réussie

---

### Étape 12 - Alignement et liage vers le Web de données liées

**But** : Aligner les entités avec Wikidata/DBpedia/Wikipedia pour ouvrir le graphe sur le LOD.

```powershell
python scripts/link_wikidata_dbpedia.py data/kg_enriched.ttl data/kg_linked.ttl
```

**Résultat** : `data/kg_linked.ttl` avec liens `owl:sameAs` (Wikidata, DBpedia) et `rdfs:seeAlso` (Wikipedia).

---

### Étape 13 - Validation SHACL (3ème passe)

**But** : S'assurer que l'ajout de liens LOD n'a pas cassé la structure.

```powershell
python scripts/validate_shacl.py data/kg_linked.ttl
```

**Résultat attendu** : ✅ Validation réussie

---

### Étape 14 - Inférence par règles SPARQL

**But** : Ajouter une couche d'intelligence sémantique automatique (classes inférées).

```powershell
python scripts/apply_inference_rules.py data/kg_linked.ttl data/kg_inferred.ttl
```

**Classes inférées** :
- `tg:HighlyRatedPlace` : note ≥7.0 ET ≥20 avis (ou ≥4.0 ET ≥20 reviews)
- `tg:TopRestaurant` : note ≥7.0 ET ≥30 avis (ou ≥4.2 ET ≥25 reviews)
- `tg:PopularPlace` : ≥50 avis (ou ≥40 reviews)
- `tg:HiddenGem` : note ≥8.5 ET 3-15 avis (ou ≥4.5 ET 3-15 reviews)

**Résultat** : `data/kg_inferred.ttl` (≈140,975 triples) avec `tg:inferenceReason`.

---

## 🎯 Lancement de l'Application GraphRAG

### 1. Générer le cache d'embeddings (optionnel mais recommandé)

```powershell
python scripts/regenerate_embeddings.py
```

**Résultat** : `data/embeddings_cache.pkl` (422 embeddings, 3.7 MB).

---

### 2. Lancer le serveur FastAPI

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

### 3. Ouvrir l'interface web

👉 **http://localhost:8000**

---

## ✅ Tests Pertinents

### Test 1 : Comparaison des 2 approches GraphRAG

**Interface Web** :
1. Aller sur l'onglet **⚖️ Comparaison GraphRAG**
2. Taper : *"Quels sont les meilleurs restaurants à Paris ?"*
3. Cliquer sur **⚖️ Comparer les 2 Approches**

**Résultat attendu** :
- **Approche 1 (SPARQL)** : Requête SPARQL générée + 10 résultats structurés
- **Approche 2 (Embeddings)** : Réponse en langage naturel + 5 entités par similarité

---

### Test 2 : Requête SPARQL avec classes inférées

**Interface Web** :
1. Onglet **💬 SPARQL**
2. Taper : *"Trouve-moi des hidden gems près de la Seine"*

**Résultat attendu** : Requête exploitant la classe `tg:HiddenGem` + filtrage géographique.

---

### Test 3 : Requête fédérée Wikidata

**Ligne de commande** :
```powershell
python -c "from app.services.sparql_client import SPARQLClient; client = SPARQLClient(); results = client.query(open('queries/q16_federated_enrichment.rq').read()); print(len(results), 'résultats')"
```

**Résultat attendu** : Enrichissement avec labels Wikidata via `SERVICE`.

---

### Test 4 : Statistiques du graphe final

```powershell
python scripts/stats_enriched.py
```

**Résultat attendu** :
- Nombre total de triples : ≈140,975
- Places : ≈1,447
- Reviews : ≈10,996
- Classes inférées : 376 instances (HighlyRatedPlace, TopRestaurant, PopularPlace, HiddenGem)

---

### Test 5 : Validation complète SHACL

```powershell
python scripts/validate_shacl.py data/kg_inferred.ttl
```

**Résultat attendu** : ✅ Toutes les contraintes respectées.

---

## 📊 Résultats Attendus à Chaque Étape

| Étape | Fichier Produit | Triples | Validation SHACL |
|-------|----------------|---------|------------------|
| 5 | `kg.ttl` | Variable | - |
| 6 | `kg_filtered.ttl` | Variable | ✅ |
| 9 | `kg_final.ttl` | ≈75,940 | ✅ |
| 11 | `kg_enriched.ttl` | ≈139,602 | ✅ |
| 12 | `kg_linked.ttl` | ≈139,602+ | ✅ |
| 14 | `kg_inferred.ttl` | ≈140,975 | ✅ |

---

## 🐛 Dépannage

### Erreur RMLMapper : "Input file not found"
➡️ Vérifier que les fichiers sont dans `data/subset/` après l'étape 3.

### Erreur SHACL : "Conforms: False"
➡️ Vérifier les logs de validation et corriger les données sources.

### Erreur OpenRouter : "API key missing"
```powershell
$env:OPENROUTER_API_KEY="sk-or-v1-..."
```

### Cache d'embeddings manquant
➡️ Il sera généré automatiquement au premier lancement (≈30s).

---

## 📚 Fichiers Importants

| Fichier | Description |
|---------|-------------|
| `data/kg_inferred.ttl` | **Graphe final** avec inférence |
| `shacl/shapes.ttl` | Contraintes SHACL |
| `rules/r1-r4.rq` | Règles d'inférence SPARQL |
| `queries/*.rq` | Requêtes de compétence |
| `app/main.py` | API FastAPI |
| `GRAPHRAG_COMPARISON.md` | Documentation GraphRAG |

---

## ✅ Checklist de Validation Finale

- [ ] Environnement virtuel activé
- [ ] RMLMapper présent dans `tools/`
- [ ] Clé API OpenRouter configurée
- [ ] `kg_inferred.ttl` généré (≈140,975 triples)
- [ ] Validation SHACL réussie
- [ ] Cache d'embeddings généré
- [ ] Serveur lancé sans erreur
- [ ] Interface web accessible
- [ ] Test comparaison GraphRAG fonctionnel
- [ ] Requête fédérée Wikidata opérationnelle

---

**Date de création** : 2026-01-19  
**Graphe final** : `data/kg_inferred.ttl` (≈140,975 triples) ✅  
**Approches GraphRAG** : 2 (SPARQL + Embeddings) ✅
