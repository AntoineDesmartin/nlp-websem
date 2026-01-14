#!/usr/bin/env python3
from rdflib import Graph, Namespace
from rdflib.namespace import RDF
from pathlib import Path

IN_PATH = Path("data/kg.ttl")
OUT_PATH = Path("data/kg_filtered.ttl")

TG = Namespace("https://example.org/tourguide#")

def main():
    g = Graph()
    g.parse(str(IN_PATH), format="turtle")

    # Tous les Places
    places = set(g.subjects(RDF.type, TG.Place))

    # Places qui ont lat/lng
    with_lat = set(g.subjects(TG.lat, None))
    with_lng = set(g.subjects(TG.lng, None))

    # On garde uniquement les places "OK" (lat + lng)
    ok_places = with_lat & with_lng
    bad_places = places - ok_places

    print("Triples before:", len(g))
    print("Places total:", len(places))
    print("Places OK (lat+lng):", len(ok_places))
    print("Places removed (missing lat or lng):", len(bad_places))

    # Supprimer tous les triples où la place "bad" est sujet
    for s in list(bad_places):
        for t in list(g.triples((s, None, None))):
            g.remove(t)

    # (Optionnel mais utile) Supprimer les triples où la place bad est objet
    # pour éviter des références vers des noeuds supprimés
    for s in list(bad_places):
        for t in list(g.triples((None, None, s))):
            g.remove(t)

    g.serialize(destination=str(OUT_PATH), format="turtle")

    # Petit check final
    g2 = Graph()
    g2.parse(str(OUT_PATH), format="turtle")
    places2 = set(g2.subjects(RDF.type, TG.Place))
    with_lat2 = set(g2.subjects(TG.lat, None))
    with_lng2 = set(g2.subjects(TG.lng, None))

    print("Saved:", OUT_PATH)
    print("Triples after:", len(g2))
    print("Places after:", len(places2))
    print("Places still missing lat:", len(places2 - with_lat2))
    print("Places still missing lng:", len(places2 - with_lng2))

if __name__ == "__main__":
    main()
