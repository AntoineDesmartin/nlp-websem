1) Telecharger les datas dans data/raw



2) Ajouter dans scripts/clean_tourpedia_csv.py pour clean le csv car probleme avec les adresses
```
python3 scripts/clean_tourpedia_csv.py 
```
3) Ajouter dans scripts/reduce_tourpedia.py pour reduce car fichiers trop gros
```
python3 scripts/reduce_tourpedia.py 
```
4) Ajouter dans tools/ le rml mapper : rmlmapper-8.1.0-r380-all

5) Ajouter les mappings pour json et csv et executer ces deux commandes :

```
java -jar tools/rmlmapper-8.1.0-r380-all.jar \
  -m mappings/tourpedia-csv.ttl \
  -o data/kg_csv.ttl \
  -s turtle
```

```
java -jar tools/rmlmapper-8.1.0-r380-all.jar \
  -m mappings/tourpedia-json.ttl \
  -o data/kg_json.ttl \
  -s turtle
```

6) Merge les deux kg_json et kg_csv

```
python - <<'PY'
from rdflib import Graph
g = Graph()
g.parse("data/kg_csv.ttl", format="turtle")
g.parse("data/kg_json.ttl", format="turtle")
g.serialize("data/kg.ttl", format="turtle")
print("Merged triples:", len(g))
PY
```

7) Supprimer les Places sans lgn car gene

```
python3 scripts/filter_incomplete_places.py 
```

8) Lancer les shapes sur kg_filtered.ttl

```
pyshacl -a -m -s shacl/shapes.ttl -d data/kg_filtered.ttl
```

9) Ajouter extract_wikivoyage_to_rdf.py

```
python3 scripts/extract_wikivoyage_to_rdf.py
```

10) Merge le kg_wikivoyage et kg_filtered

```
python - <<'PY'
from rdflib import Graph
g = Graph()
g.parse("data/kg_filtered.ttl", format="turtle")
g.parse("data/kg_wikivoyage.ttl", format="turtle")
g.serialize("data/kg_final.ttl", format="turtle")
print("Final triples:", len(g))
PY
```


11) Lancer de nouveau les shapes sur kg_final.ttl

```
pyshacl -a -m -s shacl/shapes.ttl -d data/kg_final.ttl
```

12) Ajouter link_wikidata_dbpedia.py
```
python3 scripts/link_wikidata_dbpedia.py data/kg_final.ttl data/kg_linked.ttl     
```

Alignement et liage vers le Web de données liées.
Les entités extraites de Wikivoyage contiennent des identifiants Wikidata (QID) présents dans le wikitext. Nous avons modélisé ces correspondances via owl:sameAs vers http://www.wikidata.org/entity/Q…. Ensuite, un script a interrogé l’endpoint SPARQL de Wikidata pour récupérer les sitelinks Wikipedia (FR/EN) et a enrichi le graphe avec rdfs:seeAlso vers les pages Wikipedia correspondantes. Enfin, ces URLs ont été transformées en URIs DBpedia/frDBpedia afin d’ajouter des liens owl:sameAs vers DBpedia. Au total, 27 ressources locales ont été liées à Wikidata, et 40 liens vers Wikipedia ainsi que 40 liens vers DBpedia ont été ajoutés.



13) Lancer de nouveau les shapes sur kg_linked.ttls

```
pyshacl -a -m -s shacl/shapes.ttl -d data/kg_linked.ttl
```

kg_linked est le fichier final


14) Ecrire requete sparkl dans /queries et federated et tester sur corese.

15) Insert des regles et faire de l'inferences avec  /rules sur corese, telecharger le kg_inferred et tester shacl dessus.

```
pyshacl -a -m -s shacl/shapes.ttl -d data/kg_inferred.ttl
```
16) Linked prediction --> similaire au tp1 de monin

```
pip install pykeen torch pandas tqdm
```





- on ajoute scripts/build_reco_graph.py qui construire un graphe reco puis on le lance tel que 

```
python3 scripts/build_reco_graph.py data/kg_inferred.ttl data/kg_reco.ttl \
  --topics data/topics.ttl \
  --triples_tsv data/reco_triples.tsv \
  --n_tourists 30 \
  --reviews_per_tourist 20 \
  --max_places 800 \
  --drop_external \
  --seed 42 \
  --like_threshold 3.5
```

- on ajoute scripts/build_reco_graph.py et on entraîne TransE (link prediction)

```
python3 -m venv .venv

source .venv/bin/activate

python -m pip install --upgrade pip
pip install pyshacl
```


