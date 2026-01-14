Plan de reproduction complet (pipeline KG TourGuide)
0) Prérequis

Python 3.9+ (toi tu es en 3.9) + venv

Java 11+ (pour RMLMapper)

rdflib, pyshacl, requests

Installation (exemple)
python3 -m venv .venv
source .venv/bin/activate
pip install rdflib pyshacl requests


⚠️ Sur macOS, le warning urllib3 LibreSSL est un warning, pas bloquant pour ton script (tant que les requêtes passent).

1) Télécharger les données sources (data/raw)

But : récupérer les données hétérogènes “brutes” qui serviront à construire le KG.

Inputs :

CSV Tourpedia (structuré)

JSON Tourpedia (structuré)

wikivoyage_paris_wikitext.json (non structuré)

Sortie :

fichiers dans data/raw/

✅ Check rapide :

ls -lh data/raw

2) Nettoyage du CSV (problème d’adresses)

But : corriger les champs qui cassent le parsing CSV (virgules, guillemets, retours à la ligne dans les adresses, etc.).

Script : scripts/clean_tourpedia_csv.py
Entrée : data/raw/*.csv
Sortie : un CSV nettoyé (selon ton script : soit overwrite, soit nouveau fichier)

Commande :

python3 scripts/clean_tourpedia_csv.py


✅ Contrôle :

le fichier CSV nettoyé doit s’ouvrir sans casser les colonnes

si tu veux check vite :

python - <<'PY'
import csv
path="data/raw/tourpedia_clean.csv"  # adapte au nom exact
with open(path, newline="", encoding="utf-8") as f:
    r=csv.reader(f)
    for i,row in zip(range(3), r):
        print(len(row), row[:5])
PY

3) Réduction du dataset (fichiers trop gros)

But : réduire la taille (pour garder seulement Paris ou un sous-ensemble) afin :

d’éviter des fichiers énormes

d’accélérer RMLMapper / Corese

Script : scripts/reduce_tourpedia.py
Commande :

python3 scripts/reduce_tourpedia.py


✅ Contrôle :

taille réduite (ex: quelques milliers de lignes au lieu de centaines de milliers)

wc -l data/raw/tourpedia_reduced.csv
wc -l data/raw/tourpedia_reduced.json

4) Ajouter RMLMapper dans tools/

But : exécuter les mappings RML vers RDF.

Placer :

tools/rmlmapper-8.1.0-r380-all.jar

✅ Check :

ls -lh tools/rmlmapper-8.1.0-r380-all.jar

5) Mappings RML (CSV + JSON) → RDF

But : transformer les sources structurées en RDF selon ton modèle tourguide (tg:Place, tg:Restaurant, tg:lat/lng…).

5.a Mapping CSV

Commande :

java -jar tools/rmlmapper-8.1.0-r380-all.jar \
  -m mappings/tourpedia-csv.ttl \
  -o data/kg_csv.ttl \
  -s turtle

5.b Mapping JSON

Commande :

java -jar tools/rmlmapper-8.1.0-r380-all.jar \
  -m mappings/tourpedia-json.ttl \
  -o data/kg_json.ttl \
  -s turtle


✅ Contrôle :

head -n 20 data/kg_csv.ttl
head -n 20 data/kg_json.ttl

6) Merge des 2 graphes structurés

But : obtenir un KG unique issu des données structurées.

Entrées :

data/kg_csv.ttl

data/kg_json.ttl

Sortie :

data/kg.ttl

Commande :

python - <<'PY'
from rdflib import Graph
g = Graph()
g.parse("data/kg_csv.ttl", format="turtle")
g.parse("data/kg_json.ttl", format="turtle")
g.serialize("data/kg.ttl", format="turtle")
print("Merged triples:", len(g))
PY


✅ Contrôle :

le nombre de triples doit être cohérent (non nul, et plutôt élevé)

vérifie vite qu’il y a des tg:Place

python - <<'PY'
from rdflib import Graph, Namespace
from rdflib.namespace import RDF
g=Graph(); g.parse("data/kg.ttl", format="turtle")
tg=Namespace("https://example.org/tourguide#")
print("places:", len(set(g.subjects(RDF.type, tg.Place))))
PY

7) Filtrer les Places incomplètes (missing lng/lat)

But : éviter les instances “cassées” qui gênent :

SHACL

requêtes géo / carte

exploitation application

Script : scripts/filter_incomplete_places.py
Entrée : data/kg.ttl
Sortie : data/kg_filtered.ttl

Commande :

python3 scripts/filter_incomplete_places.py


✅ Contrôle :

python - <<'PY'
from rdflib import Graph, Namespace
from rdflib.namespace import RDF
g=Graph(); g.parse("data/kg_filtered.ttl", format="turtle")
tg=Namespace("https://example.org/tourguide#")
print("triples", len(g))
print("Place", len(set(g.subjects(RDF.type, tg.Place))))
PY

8) Validation SHACL sur kg_filtered.ttl

But : vérifier que la structure attendue est respectée (types, champs obligatoires, datatypes…).

Commande :

pyshacl -a -m -s shacl/shapes.ttl -d data/kg_filtered.ttl


✅ Résultat attendu :

Conforms: True

Si Skipping shape ... no focus nodes : ce n’est pas une erreur, ça veut juste dire que la shape ne s’applique à aucune ressource dans ton graphe.

9) Extraction RDF depuis Wikivoyage (données non structurées)

But : construire un graphe RDF à partir de texte non structuré (wikitext), en extrayant :

des lieux (name)

des coordonnées (lat/lng)

des liens Wikidata QID quand disponibles

commentaires/description si tu l’as géré

Script : scripts/extract_wikivoyage_to_rdf.py
Entrée : data/raw/wikivoyage_paris_wikitext.json
Sortie : data/kg_wikivoyage.ttl

Commande :

python3 scripts/extract_wikivoyage_to_rdf.py data/raw/wikivoyage_paris_wikitext.json data/kg_wikivoyage.ttl


✅ Contrôle attendu (comme toi) :

Kept places (with name+lat+lng): ...

Triples: ...

10) Merge “structuré + non structuré” → kg_final.ttl

But : intégrer toutes les données RDF produites (structuré + non structuré) dans un KG global.

Entrées :

data/kg_filtered.ttl

data/kg_wikivoyage.ttl

Sortie :

data/kg_final.ttl

Commande :

python - <<'PY'
from rdflib import Graph
g = Graph()
g.parse("data/kg_filtered.ttl", format="turtle")
g.parse("data/kg_wikivoyage.ttl", format="turtle")
g.serialize("data/kg_final.ttl", format="turtle")
print("Final triples:", len(g))
PY

11) Validation SHACL sur kg_final.ttl

Commande :

pyshacl -a -m -s shacl/shapes.ttl -d data/kg_final.ttl


✅ Attendu :

Conforms: True

12) Alignement + liage vers Wikidata/DBpedia

But : relier tes ressources locales au Web de données liées (Linked Open Data).

Principe :

Les entités Wikivoyage ont des QIDs (dans le wikitext).

Tu mets un lien owl:sameAs vers http://www.wikidata.org/entity/Q...

Ton script interroge l’endpoint SPARQL Wikidata pour récupérer les sitelinks Wikipedia (FR/EN)

Ajout dans ton KG :

rdfs:seeAlso vers pages Wikipedia

owl:sameAs vers DBpedia / frDBpedia dérivées des URLs Wikipedia

Commande :

python3 scripts/link_wikidata_dbpedia.py data/kg_final.ttl data/kg_linked.ttl


✅ Contrôle attendu :

Found XX local resources with Wikidata links

Added rdfs:seeAlso ...

Added owl:sameAs DBpedia ...

Exemple de vérification :

grep -m 5 "wikidata.org/entity/Q" data/kg_linked.ttl
grep -m 5 "dbpedia.org/resource" data/kg_linked.ttl
grep -m 5 "rdfs:seeAlso" data/kg_linked.ttl

13) Validation SHACL sur kg_linked.ttl (fichier final)

⚠️ Dans ton message, tu as remis kg_final.ttl : ici il faut bien valider kg_linked.ttl.

Commande correcte :

pyshacl -a -m -s shacl/shapes.ttl -d data/kg_linked.ttl


✅ Attendu :

Conforms: True

👉 data/kg_linked.ttl = ton KG final exploitable

14) Requêtes SPARQL + requête fédérée dans Corese

But : implémenter les “questions de compétence” (fonctionnalités de ton app) en SPARQL, dont 1 fédérée (SERVICE).

Commande / action Corese (GUI)

Ouvrir Corese GUI

Charger data/kg_linked.ttl

(Optionnel plus tard) Charger tourguide.ttl + topics.ttl si tu veux exploiter ontologie/thésaurus

Coller tes requêtes et vérifier résultats

✅ Ce que tu as déjà fait est parfait :

Q1 top polarity

Q2 count types

Q3 top rawSubCategory

Q4 listing lat/lng

Q5 sameAs vers Wikidata/DBpedia

fédérée Wikidata avec SERVICE


15) Règles Corese + inférence → kg_inferred.ttl, puis SHACL
Ce qu’on fait

On ajoute / active des règles dans Corese (souvent dossier /rules).

On exécute l’inférence : Corese matérialise de nouveaux triples (dérivés logiquement).

On exporte le graphe inféré → data/kg_inferred.ttl

On reteste SHACL sur ce graphe :

pyshacl -a -m -s shacl/shapes.ttl -d data/kg_inferred.ttl

Pourquoi

Les règles enrichissent ton graphe automatiquement : nouvelles classifications, liens implicites, types déduits, etc.

Tu montres une brique “raisonnement” du Web sémantique (au-delà du simple stockage)

SHACL après inférence sert à vérifier que l’enrichissement n’a pas cassé la cohérence du modèle

Point important (ton ancienne question)

En général, ça ne casse pas tes anciens runs SHACL sur tes anciens fichiers :

tes anciens .ttl restent inchangés

tu lances SHACL sur un fichier donné

par contre, l’inférence peut ajouter des triples qui déclenchent des shapes supplémentaires, donc la validation peut devenir plus stricte (mais c’est normal et c’est même un bon test)

16) Link Prediction (reco) — “similaire au TP1 de Monin” avec PyKEEN

L’idée : utiliser ton KG pour faire de la recommandation via prédiction de liens (Knowledge Graph Embeddings).

16.1 Installer les libs (dans le venv)

Tu l’as fait (et c’était crucial) :

source .venv/bin/activate
pip install pykeen torch pandas tqdm

16.2 Construire un graphe “reco” à partir du KG inféré

Tu as lancé :

python3 scripts/build_reco_graph.py data/kg_inferred.ttl data/kg_reco.ttl \
  --topics data/topics.ttl \
  --triples_tsv data/reco_triples.tsv \
  --n_tourists 30 \
  --reviews_per_tourist 20 \
  --max_places 800 \
  --drop_external \
  --seed 42 \
  --like_threshold 3.5


Ce que ça fait :

Part du KG inféré

Génère un mini-scénario “touristes / reviews / topics”

Crée des triples clés pour la reco, notamment :

tg:likesPlace (c’est la relation à prédire)

tg:prefersTopic, tg:aboutPlace, tg:hasTopic, etc.

Exporte :

kg_reco.ttl (RDF)

reco_triples.tsv (format “h r t” pour PyKEEN)

Pourquoi le like_threshold 3.5 a été utile :

Au début tu avais très peu de likesPlace (99)

Après threshold 3.5 → 206 likesPlace, donc plus de signal pour entraîner un modèle

16.3 Entraîner un modèle de link prediction (TransE)

Tu as lancé :

python3 scripts/train_link_prediction.py \
  --triples_tsv data/reco_triples.tsv \
  --relation https://example.org/tourguide#likesPlace \
  --model TransE \
  --epochs 200 \
  --topk 10 \
  --out_json data/recommendations_transe.json


Ce que ça fait :

PyKEEN apprend des embeddings

Il évalue (MRR, Hits@K…)

Puis pour chaque touriste, il propose des top-K places en scorant les tails possibles pour (tourist, likesPlace, ?place).

Résultat :

data/recommendations_transe.json généré 

Jai perdu les resultats, executer de nouveau pour retrouver les resultats.



17) Prochaine etape :

Implémenter et comparer deux approches GraphRAG :

pour répondre à des questions en langage naturel en les transformant en requêtes SPARQL sur le graphe et exécutant les requêtes obtenues ;

pour répondre en langage naturel à des questions en langage naturel en calculant des embeddings.


L'application doit avoir une interface (minimale) pour communiquer avec ses utilisateurs cibles, illustrant le cas d’usage. Il est recommandé d'utiliser une interface web, mais d'autres interfaces (e.g. en ligne de commande) peuvent être acceptées. Dans tous les cas, cette partie est démonstrative, mais ne doit pas vous demander beaucoup de temps comparé au reste du projet.




