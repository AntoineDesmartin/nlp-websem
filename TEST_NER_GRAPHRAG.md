# 🧪 GUIDE DE TEST : NER + GraphRAG

**App déjà lancée sur :** http://localhost:8005

---

## ✅ ÉTAPE 1 : Tester les Requêtes NER (Vérifier que ça Fonctionne)

**Onglet :** "Inférence & Requêtes"  
**Section :** 🔍 Analyses NER

### 1.1 Top Lieux Mentionnés

**Clique sur** : `Top Lieux Mentionnés`

**Résultat Attendu :**
```
✅ 20 résultats
1. Paris (2,352 mentions)
2. Café d'Orleans - Paris (467 mentions)
3. H.A.N.D (Have A Nice Day) (439 mentions)
4. Our (249 mentions)
5. Vinci Park Services (171 mentions)
...
```

✅ **Si tu vois ça** → NER fonctionne !

### 1.2 Co-visitation

**Clique sur** : `Co-visitation`

**Résultat Attendu :**
```
✅ 19 résultats
• Place A ↔ Place B : 25 fois mentionnés ensemble
• Place C ↔ Place D : 18 fois mentionnés ensemble
...
```

✅ **Cela montre** : Quels lieux les gens visitent ensemble

### 1.3 Itinéraires Découverts

**Clique sur** : `Itinéraires Découverts`

**Résultat Attendu :**
```
✅ 20 résultats
📍 LieuA → LieuB → LieuC → LieuD
   5 lieux | Review: 220622_r10
...
```

✅ **Cela montre** : Parcours mentionnés dans les reviews

---

## 🤖 ÉTAPE 2 : Tester GraphRAG Approche 1 (SPARQL) avec NER

**Onglet :** "Approche 1 (SPARQL)"

### Test 2.1 : Utilisation Directe de NER

**Question à poser :**
```
Quels lieux sont mentionnés dans les reviews ?
```

**Ce qui devrait se passer :**
1. GPT-4o-mini génère automatiquement un SPARQL avec `schema:mentions`
2. Requête exécutée sur le KG
3. Résultats affichés

**SPARQL Généré (exemple) :**
```sparql
PREFIX schema: <http://schema.org/>
PREFIX tg: <https://example.org/tourguide#>

SELECT ?place ?placeName (COUNT(?review) as ?mentions)
WHERE {
  ?review schema:mentions ?place .
  ?place tg:name ?placeName .
}
GROUP BY ?place ?placeName
ORDER BY DESC(?mentions)
LIMIT 20
```

✅ **Preuve que NER est utilisé** : La requête contient `schema:mentions`

### Test 2.2 : Co-visitation Intelligente

**Question à poser :**
```
Quels lieux sont souvent visités ensemble selon les avis ?
```

**SPARQL Attendu :**
```sparql
SELECT ?place1 ?place2 (COUNT(*) as ?times)
WHERE {
  ?review schema:mentions ?place1 ;
          schema:mentions ?place2 .
  FILTER(?place1 != ?place2)
}
GROUP BY ?place1 ?place2
ORDER BY DESC(?times)
```

✅ **Preuve** : Utilise les relations NER pour découvrir des patterns

### Test 2.3 : Popularité Basée Reviews

**Question à poser :**
```
Trouve les lieux les plus populaires basé sur les mentions
```

✅ **Résultat** : Classement par nombre de `schema:mentions`

---

## 🧠 ÉTAPE 3 : Tester GraphRAG Approche 2 (Embeddings) avec NER

**Onglet :** "Approche 2 (Embeddings)"

### Test 3.1 : Recommandation Générale

**Question à poser :**
```
Recommande-moi des lieux populaires à Paris
```

**Ce qui se passe :**
1. Embeddings trouvent lieux similaires à "populaires"
2. L'IA génère une réponse en langage naturel
3. Liste les lieux avec leurs infos

**Résultat Attendu :**
```
💬 Voici des lieux populaires à Paris :

1. Tour Eiffel - Monument emblématique
2. Louvre - Musée d'art célèbre
3. Notre-Dame - Cathédrale historique
...

Entités Utilisées (Embeddings):
• Tour Eiffel (Note: 9.2/10)
• Louvre (Note: 9.5/10)
...
```

✅ **Avec NER** : Les lieux retournés sont dans le même KG que les mentions NER

### Test 3.2 : Contexte de Visite

**Question à poser :**
```
Où aller après avoir visité le Louvre ?
```

**Résultat Attendu :**
- L'IA recommande lieux proches du Louvre
- **Avec NER**, elle pourrait mentionner lieux co-visités si enrichi

### Test 3.3 : Recherche Thématique

**Question à poser :**
```
Quels sont les meilleurs restaurants mentionnés par les touristes ?
```

**Résultat Attendu :**
- Restaurants bien notés
- Contexte des reviews (si enrichi avec NER)

---

## 🔍 ÉTAPE 4 : Comparaison Directe (PREUVE VISUELLE)

**Onglet :** "Comparaison"

### Test 4.1 : Question Identique aux 2 Approches

**Question à poser :**
```
Quels lieux sont mentionnés ensemble dans les reviews ?
```

**Résultat Attendu :**

**📊 Approche 1 (SPARQL)** :
```sql
SELECT ?place1 ?place2 (COUNT(*) as ?co)
WHERE {
  ?review schema:mentions ?place1 ;
          schema:mentions ?place2 .
}
...
```
→ Liste précise de co-visitations avec compteurs

**🧠 Approche 2 (Embeddings)** :
```
Les lieux souvent associés incluent :
- Tour Eiffel et Trocadéro
- Louvre et Tuileries
...
```
→ Réponse conversationnelle avec contexte sémantique

✅ **Différence Visible** : SPARQL est précis, Embeddings est contextuel

---

## 📊 ÉTAPE 5 : Vérification Technique (API)

### Test API Direct

```bash
# Test 1 : Stats NER
curl http://localhost:8005/api/ner/stats | jq

# Résultat attendu :
{
  "status": "available",
  "stats": {
    "total_reviews_processed": 43717,
    "entities_matched_to_kg": 8641,
    "top_matched_places": [
      ["Paris", 2352],
      ["Café d'Orleans - Paris", 467]
    ]
  }
}

# Test 2 : Requête NER top mentions
curl http://localhost:8005/api/predefined-query/ner_top_mentions | jq '.count'
# Résultat : 20

# Test 3 : Co-visitation
curl http://localhost:8005/api/predefined-query/ner_covisitation | jq '.results[:3]'
```

---

## ✅ CHECKLIST DE VALIDATION

### NER Fonctionne ✓
- [ ] Boutons NER apparaissent dans UI
- [ ] "Top Lieux Mentionnés" → Paris en #1
- [ ] "Co-visitation" → Affiche paires avec compteurs
- [ ] "Itinéraires" → Affiche parcours 3+ lieux

### GraphRAG Approche 1 Utilise NER ✓
- [ ] Question "lieux mentionnés" → SPARQL avec `schema:mentions`
- [ ] Question "co-visitation" → Jointure sur mentions
- [ ] Résultats basés sur extractions NER

### GraphRAG Approche 2 Contexte NER ✓
- [ ] Recommandations incluent lieux du KG enrichi
- [ ] Réponses contextuelles pertinentes
- [ ] Lieux mentionnés sont dans le même graphe

### Comparaison Fonctionne ✓
- [ ] Question identique aux 2 approches
- [ ] App 1 : SPARQL précis
- [ ] App 2 : Réponse conversationnelle
- [ ] Différence claire visible

---

## 🎯 QUESTIONS RECOMMANDÉES POUR DÉMONSTRATION

### Pour Montrer NER au Jury

**App 1 :**
1. `Quels lieux sont les plus mentionnés dans les reviews ?`
2. `Trouve les paires de lieux souvent visités ensemble`
3. `Quels parcours touristiques sont mentionnés ?`

**App 2 :**
1. `Recommande-moi un itinéraire à partir du Louvre`
2. `Quels restaurants sont populaires selon les avis ?`
3. `Où aller après la Tour Eiffel ?`

**Comparaison :**
1. `Quels sont les lieux les plus populaires ?`
   → Montre la différence SPARQL vs Embeddings

---

## 🐛 TROUBLESHOOTING

### Si "Sans nom" apparaît encore :
→ **Recharge la page** (F5 ou Cmd+R)  
→ Le fix JavaScript est chargé

### Si aucun résultat NER :
```bash
# Vérifier triplets NER dans KG
grep -c "schema1:mentions" data/kg_inferred.ttl
# Devrait afficher : 7167
```

### Si GraphRAG ne génère pas SPARQL avec NER :
→ Reformule la question pour mentionner "reviews", "mentions", "avis"  
→ Exemple : "lieux **mentionnés** dans reviews"

---

## 🎓 POUR LA SOUTENANCE

**Ce que tu peux dire :**

> "Nous avons implémenté du NER avec spaCy (transformers) sur 43,000 reviews. Regardez : *[cliquer Top Lieux Mentionnés]* Paris est mentionné 2,352 fois. Maintenant testons GraphRAG : *[poser question App 1]* Le système génère automatiquement du SPARQL utilisant ces relations NER. *[montrer SPARQL]* Vous voyez `schema:mentions` ? C'est le NER qui alimente ça."

**Démo Live (2 min) :**
1. Clique "Top Lieux Mentionnés" → Montre résultats
2. Onglet "Approche 1" → Pose "Quels lieux sont mentionnés ?"
3. Montre le SPARQL généré avec `schema:mentions`
4. Onglet "Com comparaison" → Compare les 2 approches
5. **BOOM** → Jury impressed 🎉

---

**🚀 Prêt à tester ! Ouvre http://localhost:8005 et suis ce guide !**
