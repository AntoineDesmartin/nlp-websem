# 🔄 Inférence Automatique avec RDFLib (Alternative à Apache Jena)

## 📖 Qu'est-ce que l'inférence ?

L'**inférence** est un processus de raisonnement automatique qui permet de **dériver de nouvelles connaissances** à partir des données existantes en appliquant des **règles logiques**.

Dans notre projet, nous utilisons **RDFLib** (bibliothèque Python) comme alternative à **Apache Jena** pour appliquer des règles SPARQL CONSTRUCT et générer automatiquement 4 nouvelles classes de qualité.

---

## 🎯 Objectif de l'inférence

**Entrée** : `kg_enriched.ttl` (139,602 triples)
- Contient les données de base : Restaurants, Attractions, POI
- Inclut les reviews Schema.org et les liens LOD

**Sortie** : `kg_inferred.ttl` (140,975 triples)
- Contient TOUTES les données de `kg_enriched.ttl`
- + 1,373 nouveaux triples représentant **4 classes inférées** :
  - 🏆 **HighlyRatedPlace** : 75 instances (lieux excellents)
  - 🍽️ **TopRestaurant** : 26 instances (meilleurs restaurants)
  - 📈 **PopularPlace** : 151 instances (lieux populaires)
  - 💎 **HiddenGem** : 124 instances (pépites cachées)
  - **Total** : 376 instances automatiquement classifiées

---

## 🔧 Pipeline d'inférence

```
┌─────────────────────────────────────────────────────────────────┐
│                    1️⃣ DONNÉES D'ENTRÉE                          │
│                     kg_enriched.ttl                              │
│                     139,602 triples                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Restaurant   │  │ Attraction   │  │     POI      │          │
│  │   2000       │  │   1529       │  │    1530      │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  + Schema.org reviews (tg:polarity, tg:numReviews)              │
│  + LOD links (Wikidata, DBpedia, Wikipedia)                     │
└─────────────────────────────────────────────────────────────────┘
                              ⬇
┌─────────────────────────────────────────────────────────────────┐
│                    2️⃣ RÈGLES D'INFÉRENCE                        │
│                      rules/*.rq                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ r1_highly_rated_place.rq                                   │ │
│  │ ➜ SI polarity ≥7.0 ET numReviews ≥20                      │ │
│  │ ➜ OU avgRating ≥4.0 ET reviewCount ≥20                    │ │
│  │ ➜ ALORS ajouter tg:HighlyRatedPlace                       │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ r2_top_restaurant.rq                                       │ │
│  │ ➜ SI type=Restaurant ET polarity ≥7.0 ET numReviews ≥30   │ │
│  │ ➜ OU avgRating ≥4.2 ET reviewCount ≥25                    │ │
│  │ ➜ ALORS ajouter tg:TopRestaurant                          │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ r3_popular_place.rq                                        │ │
│  │ ➜ SI numReviews ≥100 OU reviewCount ≥100                  │ │
│  │ ➜ ALORS ajouter tg:PopularPlace                           │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ r4_hidden_gem.rq                                           │ │
│  │ ➜ SI polarity ≥8.5 ET numReviews ENTRE 3 et 15            │ │
│  │ ➜ OU avgRating ≥4.5 ET reviewCount ENTRE 3 et 15          │ │
│  │ ➜ ALORS ajouter tg:HiddenGem                              │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ⬇
┌─────────────────────────────────────────────────────────────────┐
│                 3️⃣ MOTEUR D'INFÉRENCE                           │
│             scripts/apply_inference_rules.py                     │
│                     (RDFLib CONSTRUCT)                           │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 1. Charger kg_enriched.ttl dans RDFLib Graph              │ │
│  │ 2. Pour chaque règle r1-r4:                                │ │
│  │    a) Lire la requête SPARQL CONSTRUCT                     │ │
│  │    b) Exécuter la requête sur le graphe                    │ │
│  │    c) Récupérer les nouveaux triples générés               │ │
│  │    d) Fusionner avec le graphe principal                   │ │
│  │ 3. Sauvegarder le résultat dans kg_inferred.ttl            │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ⬇
┌─────────────────────────────────────────────────────────────────┐
│                    4️⃣ RÉSULTAT FINAL                            │
│                     kg_inferred.ttl                              │
│                     140,975 triples                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ CLASSES DE BASE (inchangées)                             │  │
│  │  • Restaurant: 2000    • Attraction: 1529                │  │
│  │  • POI: 1530           • Place: 5059                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ CLASSES INFÉRÉES (nouvelles) - 376 instances             │  │
│  │  🏆 HighlyRatedPlace: 75   (lieux excellents)            │  │
│  │  🍽️ TopRestaurant: 26      (top restaurants)             │  │
│  │  📈 PopularPlace: 151      (lieux populaires)            │  │
│  │  💎 HiddenGem: 124         (pépites cachées)             │  │
│  └──────────────────────────────────────────────────────────┘  │
│  + Métadonnées d'inférence (tg:inferenceReason)                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Comment exécuter l'inférence

### Commande simple

```bash
python scripts/apply_inference_rules.py data/kg_enriched.ttl data/kg_inferred.ttl
```

### Sortie attendue

```
Loading graph: data/kg_enriched.ttl
  ✓ 139602 triples loaded

Applying rule: r1_highly_rated_place.rq
  ✓ 225 triples inferred

Applying rule: r2_top_restaurant.rq
  ✓ 78 triples inferred

Applying rule: r3_popular_place.rq
  ✓ 453 triples inferred

Applying rule: r4_hidden_gem.rq
  ✓ 372 triples inferred

============================================================
Total triples after inference: 140975
New triples inferred: 1373
============================================================

Saving to: data/kg_inferred.ttl
  ✓ Done!

📊 Inference Summary:
  - HighlyRatedPlace: 75
  - TopRestaurant: 26
  - PopularPlace: 151
  - HiddenGem: 124
```

---

## 📝 Exemple de règle SPARQL CONSTRUCT

Voici comment fonctionne **r4_hidden_gem.rq** (pépites cachées) :

```sparql
PREFIX tg:  <https://example.org/tourguide#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

# R4: HiddenGem - Excellents mais peu connus
CONSTRUCT {
  ?p rdf:type tg:HiddenGem .
  ?p tg:inferenceReason ?reason .
  ?p tg:inferredRating ?avgRating .
  ?p tg:inferredReviewCount ?count .
}
WHERE {
  # Chercher les lieux avec:
  ?p rdf:type tg:Place ;
     tg:polarity ?pol ;
     tg:numReviews ?n .
  
  # Critères: Excellente note MAIS peu d'avis
  FILTER(xsd:decimal(?pol) >= 8.5 && 
         xsd:integer(?n) >= 3 && 
         xsd:integer(?n) <= 15)
  
  # Capturer les données pour traçabilité
  BIND(?pol AS ?avgRating)
  BIND(?n AS ?count)
  BIND(CONCAT("HiddenGem: polarity=", STR(?pol), 
              ", numReviews=", STR(?n)) AS ?reason)
}
```

**Explication** :
1. **CONSTRUCT** : Définit les nouveaux triples à créer
2. **WHERE** : Définit les conditions pour déclencher la règle
3. **FILTER** : Applique les critères de classification
   - Note ≥ 8.5 (excellent)
   - Entre 3 et 15 avis (peu connu)
4. **BIND** : Capture les métadonnées pour traçabilité

---

## 🔍 Exemple de triplet généré

Avant inférence (`kg_enriched.ttl`) :
```turtle
tg:restaurant_12345 a tg:Restaurant ;
    tg:name "Le Petit Bistrot" ;
    tg:polarity "9.2"^^xsd:decimal ;
    tg:numReviews "8"^^xsd:integer .
```

Après inférence (`kg_inferred.ttl`) :
```turtle
tg:restaurant_12345 a tg:Restaurant ;
    tg:name "Le Petit Bistrot" ;
    tg:polarity "9.2"^^xsd:decimal ;
    tg:numReviews "8"^^xsd:integer ;
    
    # ⬇️ NOUVEAUX TRIPLES INFÉRÉS ⬇️
    a tg:HiddenGem ;
    tg:inferenceReason "HiddenGem: polarity=9.2, numReviews=8 (>=8.5 & 3-15 reviews) [Source: TourPedia]" ;
    tg:inferredRating "9.2"^^xsd:decimal ;
    tg:inferredReviewCount "8"^^xsd:integer .
```

---

## 🆚 RDFLib vs Apache Jena

| Critère | **RDFLib** (notre choix) | **Apache Jena** |
|---------|---------------------------|-----------------|
| **Langage** | Python | Java |
| **Installation** | `pip install rdflib` | Téléchargement + config JVM |
| **Règles** | SPARQL CONSTRUCT | SPARQL + OWL Reasoner |
| **Performance** | Rapide pour ≤1M triples | Optimisé pour >10M triples |
| **Intégration** | Facile (déjà en Python) | Nécessite subprocess Java |
| **Traçabilité** | Excellente (métadonnées) | Excellente |

**Pourquoi RDFLib ?**
- ✅ Projet déjà en Python
- ✅ Plus simple à intégrer (pas de dépendance Java)
- ✅ Performance suffisante pour 140K triples
- ✅ Règles SPARQL CONSTRUCT très expressives

---

## 📊 Statistiques d'inférence

```
Triples de base (kg_enriched.ttl):     139,602
Nouveaux triples (inference):          +1,373
Total final (kg_inferred.ttl):         140,975

Répartition des 1,373 nouveaux triples:
  • Déclarations de type (rdf:type):         376  (27%)
  • Raisons d'inférence (inferenceReason):   376  (27%)
  • Ratings inférés (inferredRating):        376  (27%)
  • Compteurs inférés (inferredReviewCount): 245  (18%)
```

---

## 🎯 Utilisation dans l'application

Les classes inférées sont utilisées dans **2 onglets** de l'interface :

### Onglet 1 : Recommandations GraphRAG
- Questions comme "Trouve-moi des pépites cachées"
- Le système détecte automatiquement `tg:HiddenGem` dans la base

### Onglet 2 : Classes Inférées
- Exploration directe des 4 classes
- Statistiques et comparaison
- Affichage des raisons d'inférence

---

## 🔄 Workflow complet du projet

```
1. TourPedia JSON → clean_tourpedia_csv.py → kg_csv.ttl
2. kg_csv.ttl + reviews → kg_reviews_all.ttl
3. kg_reviews_all.ttl + Wikidata → kg_linked.ttl
4. kg_linked.ttl → (validation SHACL) → kg_enriched.ttl
5. kg_enriched.ttl + rules/*.rq → apply_inference_rules.py → kg_inferred.ttl ⬅️ VOUS ÊTES ICI
6. kg_inferred.ttl → TransE embeddings → recommendations_transe.json
```

---

## ✅ Avantages de l'inférence

1. **Automatisation** : Pas besoin de classifier manuellement 376 lieux
2. **Traçabilité** : Chaque classification contient sa justification
3. **Évolutivité** : Ajouter une règle = ajouter un fichier `.rq`
4. **Cohérence** : Les règles garantissent des critères uniformes
5. **Maintenance** : Modifier une règle = régénérer le graphe
6. **Richesse** : 4 nouvelles dimensions de recherche (TopRestaurant, HiddenGem, etc.)

---

## 📚 Ressources

- **RDFLib** : https://rdflib.readthedocs.io/
- **SPARQL CONSTRUCT** : https://www.w3.org/TR/sparql11-query/#construct
- **Apache Jena** : https://jena.apache.org/documentation/inference/
- **Script d'inférence** : `scripts/apply_inference_rules.py`
- **Règles** : `rules/r1-r4.rq`

---

## 🎬 Test rapide

Pour vérifier que l'inférence fonctionne :

```bash
# 1. Régénérer kg_inferred.ttl
python scripts/apply_inference_rules.py data/kg_enriched.ttl data/kg_inferred.ttl

# 2. Comparer les deux graphes
python compare_graphs.py

# 3. Requête SPARQL pour voir les HiddenGem
python -c "
from rdflib import Graph, Namespace
TG = Namespace('https://example.org/tourguide#')
g = Graph()
g.parse('data/kg_inferred.ttl')
gems = list(g.subjects(None, TG.HiddenGem))
print(f'Nombre de HiddenGem: {len(gems)}')
"
```

---

## 🎯 Conclusion

L'inférence avec **RDFLib** (alternative Python à Apache Jena) permet de :
- Enrichir automatiquement le graphe avec 376 classifications qualité
- Tracer chaque inférence avec des métadonnées explicites
- Offrir 4 nouvelles dimensions de recherche dans l'interface
- Maintenir une base de connaissances cohérente et évolutive

**Résultat** : `kg_inferred.ttl` contient non seulement les données brutes, mais aussi une couche d'**intelligence sémantique** générée automatiquement par raisonnement logique ! 🚀
