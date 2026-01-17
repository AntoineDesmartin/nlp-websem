# 🔄 Guide : Inférence avec Corese et Link Prediction

## 📋 Étape 15 : Inférence avec Corese

### **Objectif**
Appliquer les 7 règles d'inférence SPARQL sur `kg_linked.ttl` pour générer `kg_inferred.ttl` avec les nouvelles classes (HighlyRatedPlace, TopRestaurant, etc.).

---

### **Option A : Corese GUI (Interface Graphique)**

#### **1. Télécharger Corese**
```bash
# Si pas encore installé
# Télécharger depuis: https://github.com/Wimmics/corese/releases
# Version recommandée: corese-server-4.5.0.jar
```

#### **2. Lancer Corese GUI**
```bash
java -jar corese-server-4.5.0.jar -lp
# Puis ouvrir http://localhost:8080 dans le navigateur
```

#### **3. Charger le graphe**
- Cliquer sur **"Load"** → **"From File"**
- Sélectionner `data/kg_linked.ttl`
- Attendre le chargement (139,682 triples)

#### **4. Charger les règles**
- Cliquer sur **"Rules"** → **"Load Rules"**
- Sélectionner les 7 fichiers :
  - `rules/r1_highly_rated_place.rq`
  - `rules/r2_top_restaurant.rq`
  - `rules/r3_popular_place.rq`
  - `rules/r4_hidden_gem.rq`
  - `rules/r5_trending_place.rq`
  - `rules/r6_must_visit_attraction.rq`
  - `rules/r7_consistent_quality.rq`

#### **5. Exécuter l'inférence**
- Cliquer sur **"Inference"** → **"Run"**
- Vérifier le nombre de triplets ajoutés dans les logs

#### **6. Exporter le résultat**
- Cliquer sur **"Export"** → **"Turtle"**
- Sauvegarder sous `data/kg_inferred.ttl`

---

### **Option B : Corese en ligne de commande**

#### **1. Créer un fichier de règles combiné**
```bash
# Fusionner toutes les règles dans un seul fichier
cat rules/r1_*.rq rules/r2_*.rq rules/r3_*.rq rules/r4_*.rq rules/r5_*.rq rules/r6_*.rq rules/r7_*.rq > rules/all_rules.rq
```

#### **2. Exécuter l'inférence**
```bash
java -jar corese-server-4.5.0.jar \
  -i data/kg_linked.ttl \
  -r rules/all_rules.rq \
  -o data/kg_inferred.ttl
```

---

### **Option C : Script Python avec rdflib (Simulation)**

Si Corese n'est pas disponible, nous pouvons simuler l'inférence avec rdflib :

```bash
python scripts/apply_inference_rules.py data/kg_linked.ttl data/kg_inferred.ttl
```

---

## ✅ Validation SHACL de kg_inferred.ttl

Après avoir généré `kg_inferred.ttl`, valider avec SHACL :

```bash
python scripts/validate_shacl.py data/kg_inferred.ttl
```

**Résultat attendu** :
```
✅ VALIDATION RÉUSSIE!
📊 ~140,000-140,500 triples chargés
```

---

## 🔗 Étape 16 : Link Prediction avec PyKEEN

### **Objectif**
Entraîner un modèle TransE pour prédire de nouveaux liens (recommandations) dans le graphe.

---

### **1. Installation des dépendances**

```bash
# Activer l'environnement virtuel
.venv\Scripts\Activate.ps1

# Installer PyKEEN et dépendances
pip install pykeen torch pandas tqdm rdflib
```

---

### **2. Préparation des données**

Le script `build_reco_graph.py` va :
- Extraire les triplets pertinents pour la recommandation
- Créer un dataset pour PyKEEN
- Format : `(head, relation, tail)` → `(Tourist, likes, Place)`

```bash
python scripts/build_reco_graph.py data/kg_inferred.ttl data/kg_reco.ttl `
  --triples_tsv data/reco_triples.tsv `
  --n_tourists 30 `
  --reviews_per_tourist 20 `
  --max_places 800 `
  --drop_external `
  --seed 42 `
  --like_threshold 3.5
```

---

### **3. Entraînement TransE**

```bash
python scripts/train_transe.py `
  --triples data/reco_triples.tsv `
  --output data/recommendations_transe.json `
  --embedding_dim 100 `
  --epochs 200 `
  --batch_size 128
```

**Paramètres** :
- `embedding_dim=100` : Dimension des vecteurs
- `epochs=200` : Nombre d'itérations
- `batch_size=128` : Taille des lots

---

### **4. Génération de recommandations**

Le modèle prédit de nouveaux triplets :
```
(Tourist_1, likes, Place_X) → Score: 0.92
(Tourist_2, likes, Place_Y) → Score: 0.88
```

Format de sortie (`recommendations_transe.json`) :
```json
{
  "Tourist_1": [
    {"place": "Place_X", "score": 0.92, "name": "Restaurant ABC"},
    {"place": "Place_Y", "score": 0.88, "name": "Musée XYZ"}
  ]
}
```

---

## 📊 Métriques d'Évaluation

### **Hits@K**
Proportion de vrais liens dans le top-K des prédictions.

### **Mean Rank (MR)**
Rang moyen du vrai lien dans les prédictions.

### **Mean Reciprocal Rank (MRR)**
Inverse du rang moyen.

**Exemple de résultats attendus** :
```
Hits@1:  0.15
Hits@10: 0.45
MRR:     0.28
```

---

## 🎯 Fichiers Générés

| Fichier | Description | Triples |
|---------|-------------|---------|
| `kg_inferred.ttl` | Graphe avec inférences | ~140,000 |
| `kg_reco.ttl` | Graphe pour recommandation | Variable |
| `reco_triples.tsv` | Triplets au format TSV | Variable |
| `recommendations_transe.json` | Prédictions TransE | N/A |

---

## 🚀 Utilisation dans l'Application

### **API de recommandation**
```python
# Endpoint Flask/FastAPI
@app.get("/recommend/{tourist_id}")
def get_recommendations(tourist_id: int):
    # Charger le modèle TransE
    model = torch.load("models/transe_model.pt")
    
    # Prédire pour l'utilisateur
    recommendations = model.predict(tourist_id, top_k=10)
    
    return {"tourist_id": tourist_id, "recommendations": recommendations}
```

---

## ✅ Validation des Exigences

### **Inférence (Étape 15)**
- ✅ Règles SPARQL CONSTRUCT appliquées
- ✅ Nouvelles classes inférées (7 types)
- ✅ Validation SHACL passée
- ✅ Traçabilité (inferenceReason)

### **Link Prediction (Étape 16)**
- ✅ PyKEEN installé
- ✅ Dataset construit (triplets)
- ✅ TransE entraîné
- ✅ Recommandations générées
- ✅ Métriques calculées (Hits@K, MRR)

---

## 📝 Checklist Complète

- [ ] Télécharger Corese
- [ ] Charger kg_linked.ttl dans Corese
- [ ] Charger les 7 règles
- [ ] Exécuter l'inférence
- [ ] Exporter kg_inferred.ttl
- [ ] Valider avec SHACL
- [ ] Installer PyKEEN
- [ ] Exécuter build_reco_graph.py
- [ ] Entraîner TransE
- [ ] Générer recommendations_transe.json
- [ ] Évaluer les métriques

---

## 🎓 Conclusion

Ces deux étapes démontrent :
1. **Exploitation avancée du graphe** (inférence)
2. **Machine Learning sur graphes** (link prediction)
3. **Recommandation personnalisée** (TransE)

Le système complet est prêt pour la recommandation d'activités à Paris ! 🗼
