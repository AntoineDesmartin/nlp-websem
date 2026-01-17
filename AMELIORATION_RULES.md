# 🔄 Amélioration des Règles d'Inférence

## 📊 Contexte

Le graphe `kg_linked.ttl` contient **deux sources de données** :
1. **TourPedia original** : `tg:polarity` (5000 lieux), `tg:numReviews` (6584 lieux)
2. **Reviews enrichies** : 10,996 reviews avec `schema:reviewRating`

## ✅ Améliorations Apportées

### **R1-R4 : Règles Améliorées**

Toutes les règles existantes ont été enrichies pour utiliser **deux sources** via `UNION` :

#### **R1: HighlyRatedPlace** (Lieux excellents)
- **Avant** : Uniquement `tg:polarity >= 7.0` et `tg:numReviews >= 20`
- **Après** : 
  - Source 1: TourPedia (polarity >= 7.0, numReviews >= 20)
  - Source 2: Reviews calculées (avgRating >= 4.0, reviewCount >= 20)
- **Impact** : Plus de lieux détectés comme "highly rated"

#### **R2: TopRestaurant** (Meilleurs restaurants)
- **Avant** : Uniquement restaurants avec `polarity >= 7.0` et `numReviews >= 30`
- **Après** :
  - Source 1: TourPedia (polarity >= 7.0, numReviews >= 30)
  - Source 2: Reviews calculées (avgRating >= 4.2, reviewCount >= 25)
- **Impact** : Détection de restaurants bien notés dans les reviews enrichies

#### **R3: PopularPlace** (Lieux populaires)
- **Avant** : Uniquement `numReviews >= 50`
- **Après** :
  - Source 1: TourPedia (numReviews >= 50)
  - Source 2: Reviews comptées (reviewCount >= 40)
- **Impact** : Popularité basée aussi sur les reviews récentes

#### **R4: HiddenGem** (Pépites cachées)
- **Avant** : `polarity >= 8.5` et `numReviews <= 5`
- **Après** :
  - Source 1: TourPedia (polarity >= 8.5, numReviews 3-15) ⚠️ Ajusté
  - Source 2: Reviews calculées (avgRating >= 4.5, reviewCount 3-15)
- **Impact** : 
  - Seuil minimum augmenté à 3 (au lieu de 0-5) pour fiabilité
  - Maximum augmenté à 15 pour plus de résultats
  - Découverte de gems basée sur reviews enrichies

---

### **R5-R7 : Nouvelles Règles**

Trois nouvelles règles exploitant spécifiquement les reviews enrichies :

#### **R5: TrendingPlace** (Lieux en tendance)
```sparql
# Nouveauté: Détecte les lieux avec beaucoup d'activité récente
Critères: >= 15 reviews, avgRating >= 3.5
```
**Utilité** : Section "Trending" dans l'application

#### **R6: MustVisitAttraction** (Attractions incontournables)
```sparql
# Combine: Type Attraction + excellentes notes + popularité
Critères: Type=Attraction, avgRating >= 4.3, reviewCount >= 30
```
**Utilité** : "Top Attractions" avec garantie qualité

#### **R7: ConsistentQuality** (Qualité constante)
```sparql
# Analyse la variance: peu de notes basses
Critères: avgRating >= 4.0, minRating >= 3.0, reviewCount >= 10
```
**Utilité** : Recommandations "safe" sans mauvaises surprises

---

## 📈 Propriétés Inférées Ajoutées

Toutes les règles ajoutent maintenant :
- `tg:inferenceReason` : Explication textuelle
- `tg:inferredRating` : Note calculée/utilisée
- `tg:inferredReviewCount` : Nombre d'avis utilisé

**Exemple de triplet inféré** :
```turtle
<place/217388> a tg:HighlyRatedPlace ;
    tg:inferenceReason "HighlyRatedPlace: avgRating=4.5, reviewCount=25 (>=4.0 & >=20) [Source: Reviews]" ;
    tg:inferredRating 4.5 ;
    tg:inferredReviewCount 25 .
```

---

## 🎯 Impact Attendu

### **Avant (règles originales)**
- ~100-200 triplets inférés
- Uniquement basé sur TourPedia
- Données parfois anciennes

### **Après (règles améliorées)**
- **~500-1000+ triplets inférés** (estimation)
- Double source (TourPedia + Reviews)
- Données plus fraîches et complètes
- 3 nouvelles catégories

---

## 🚀 Utilisation avec Corese

### **Étape 1 : Charger le graphe**
```bash
# Dans Corese GUI
Load → data/kg_linked.ttl
```

### **Étape 2 : Appliquer les règles**
```bash
# Charger toutes les règles
Load Rules → rules/r1_highly_rated_place.rq
Load Rules → rules/r2_top_restaurant.rq
Load Rules → rules/r3_popular_place.rq
Load Rules → rules/r4_hidden_gem.rq
Load Rules → rules/r5_trending_place.rq
Load Rules → rules/r6_must_visit_attraction.rq
Load Rules → rules/r7_consistent_quality.rq
```

### **Étape 3 : Exécuter l'inférence**
```bash
Inference → Run
```

### **Étape 4 : Exporter kg_inferred.ttl**
```bash
Export → Turtle → data/kg_inferred.ttl
```

---

## 🔍 Requêtes de Validation

### **Compter les inférences par type**
```sparql
PREFIX tg: <https://example.org/tourguide#>

SELECT ?type (COUNT(?place) AS ?count)
WHERE {
  ?place a ?type .
  FILTER(?type IN (
    tg:HighlyRatedPlace, 
    tg:TopRestaurant, 
    tg:PopularPlace, 
    tg:HiddenGem,
    tg:TrendingPlace,
    tg:MustVisitAttraction,
    tg:ConsistentQuality
  ))
}
GROUP BY ?type
ORDER BY DESC(?count)
```

### **Voir les raisons d'inférence**
```sparql
PREFIX tg: <https://example.org/tourguide#>

SELECT ?place ?name ?type ?reason
WHERE {
  ?place a ?type ;
         tg:name ?name ;
         tg:inferenceReason ?reason .
  FILTER(?type IN (tg:HiddenGem, tg:MustVisitAttraction))
}
ORDER BY ?type
LIMIT 20
```

---

## 📊 Tableau Récapitulatif

| Règle | Avant | Après | Nouvelles Propriétés | Source |
|-------|-------|-------|---------------------|--------|
| R1 | ✅ | ✅✅ Améliorée | +inferredRating, +inferredReviewCount | TourPedia + Reviews |
| R2 | ✅ | ✅✅ Améliorée | +inferredRating, +inferredReviewCount | TourPedia + Reviews |
| R3 | ✅ | ✅✅ Améliorée | +inferredReviewCount | TourPedia + Reviews |
| R4 | ✅ | ✅✅ Améliorée | +inferredRating, +inferredReviewCount | TourPedia + Reviews |
| R5 | ❌ | ✅ **Nouvelle** | +inferredReviewCount, +inferredAvgRating | Reviews uniquement |
| R6 | ❌ | ✅ **Nouvelle** | +inferredRating, +inferredReviewCount | Reviews uniquement |
| R7 | ❌ | ✅ **Nouvelle** | +inferredAvgRating, +inferredMinRating | Reviews uniquement |

---

## ✅ Validation du Sujet

Ces améliorations répondent aux exigences :

1. ✅ **Règles d'inférence** : 7 règles CONSTRUCT SPARQL
2. ✅ **Exploitation des reviews** : Agrégations AVG, MIN, COUNT
3. ✅ **Enrichissement du graphe** : Nouvelles classes et propriétés
4. ✅ **Recommandation intelligente** : Catégorisation automatique
5. ✅ **Traçabilité** : Propriété `tg:inferenceReason`

---

## 🎓 Conclusion

Le fichier **kg_inferred.ttl** sera le plus complet avec :
- 139,682 triples de base (kg_linked.ttl)
- +500-1000 triplets inférés
- **~140,000-140,500 triples au total**

Cela démontre une exploitation avancée du graphe de connaissances pour la recommandation ! 🚀
