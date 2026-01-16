# 🚀 Guide de Démarrage Rapide

## ⚡ Lancement en 3 étapes

### 1. Configurer la clé API

```powershell
$env:OPENROUTER_API_KEY="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"
```

### 2. Lancer l'application

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. Ouvrir le navigateur

👉 **http://localhost:8000**

---

## 🎯 Tester les 2 Approches

### Option A : Interface Web (Recommandé)

1. Ouvre **http://localhost:8000**
2. Clique sur l'onglet **⚖️ Comparaison GraphRAG**
3. Tape une question : *"Quels sont les meilleurs restaurants ?"*
4. Clique sur **⚖️ Comparer les 2 Approches**

➡️ Tu verras les deux résultats côte à côte !

### Option B : Tests en ligne de commande

```powershell
# Test Approche 1 (SPARQL)
python test_openrouter.py

# Test Approche 2 (Embeddings)
python test_embedding_approach.py

# Test Comparaison
python test_graphrag_comparison.py
```

---

## 📱 Onglets de l'Interface

| Onglet | Description |
|--------|-------------|
| **⚖️ Comparaison** | Compare les 2 approches sur la même question |
| **💬 SPARQL** | Approche 1 : génération de requêtes SPARQL |
| **🧠 Embeddings** | Approche 2 : réponses en langage naturel |
| **🎯 Recommandations** | Système de recommandation TransE |
| **🔍 Explorer** | Navigation dans le Knowledge Graph |
| **📊 Statistiques** | Métriques du projet |

---

## 💡 Questions Exemples

### Pour l'approche SPARQL (précision)
- "Quels sont les restaurants avec plus de 100 avis ?"
- "Trouve les attractions avec une note supérieure à 0.8"
- "Lieux liés à Wikidata"

### Pour l'approche Embeddings (naturel)
- "Recommande-moi un bon restaurant"
- "Où puis-je manger de la cuisine française ?"
- "Je cherche un endroit populaire"

### Pour la comparaison
- "Quels sont les meilleurs restaurants ?"
- "Je cherche une attraction touristique"
- "Trouve des lieux bien notés"

---

## 🎓 Résultats Attendus

### Approche 1 (SPARQL)
```
✓ Requête SPARQL générée
✓ 10 résultats structurés
✓ Format JSON avec propriétés précises
```

### Approche 2 (Embeddings)
```
✓ Réponse conversationnelle en français
✓ 5 entités par similarité
✓ Recommandations contextuelles
```

---

## 🐛 Dépannage

### Erreur : "OPENROUTER_API_KEY manquante"

```powershell
# Vérifier
$env:OPENROUTER_API_KEY

# Si vide, configurer
$env:OPENROUTER_API_KEY="sk-or-v1-..."
```

### Erreur : "Service Embeddings non disponible"

➡️ Le cache d'embeddings sera généré automatiquement à la première utilisation (~30s)

### Port 8000 déjà utilisé

```powershell
# Utiliser un autre port
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

---

## 📚 Fichiers Importants

| Fichier | Description |
|---------|-------------|
| `GRAPHRAG_COMPARISON.md` | Documentation complète de comparaison |
| `README.md` | Documentation générale du projet |
| `test_graphrag_comparison.py` | Script de test comparatif |
| `app/main.py` | API FastAPI avec les 2 endpoints |
| `app/services/openrouter_service.py` | Approche 1 (SPARQL) |
| `app/services/embedding_service.py` | Approche 2 (Embeddings) |

---

## ✅ Checklist de Validation

- [ ] Clé API OpenRouter configurée
- [ ] Serveur lancé sans erreur
- [ ] Interface web accessible
- [ ] Tab "Comparaison" fonctionne
- [ ] Approche 1 génère du SPARQL valide
- [ ] Approche 2 retourne des réponses en français
- [ ] Les deux approches donnent des résultats pertinents

---

## 🎉 C'est Prêt !

Tu as maintenant :
✅ 2 approches GraphRAG fonctionnelles
✅ Interface de comparaison interactive
✅ Tests automatisés
✅ Documentation complète

**Enjoy! 🚀**
