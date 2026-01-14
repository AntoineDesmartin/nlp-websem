#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import random
from datetime import date, timedelta
from pathlib import Path

from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD, SKOS


TG = Namespace("https://example.org/tourguide#")
TOURIST_NS = Namespace("https://example.org/tourguide/tourist/")
REVIEW_NS = Namespace("https://example.org/tourguide/review/")


def is_external_uri(u: URIRef) -> bool:
    s = str(u)
    return (
        s.startswith("http://dbpedia.org/")
        or s.startswith("http://fr.dbpedia.org/")
        or s.startswith("https://en.wikipedia.org/")
        or s.startswith("https://fr.wikipedia.org/")
        or s.startswith("http://www.wikidata.org/")
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kg_in", help="ex: data/kg_inferred.ttl (ou kg_linked.ttl)")
    ap.add_argument("kg_out", help="ex: data/kg_reco.ttl")
    ap.add_argument("--topics", default="data/topics.ttl", help="thesaurus topics (SKOS)")
    ap.add_argument("--triples_tsv", default="data/reco_triples.tsv", help="TSV for PyKEEN (h\\tr\\tt)")
    ap.add_argument("--n_tourists", type=int, default=30)
    ap.add_argument("--reviews_per_tourist", type=int, default=20)
    ap.add_argument("--like_threshold", type=float, default=4.0, help="rating >= threshold => likesPlace")
    ap.add_argument("--max_places", type=int, default=800, help="limit places to keep training small")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--drop_external", action="store_true", help="drop owl:sameAs / seeAlso / external URIs")
    args = ap.parse_args()

    random.seed(args.seed)

    kg = Graph()
    kg.parse(args.kg_in, format="turtle")

    topics_g = Graph()
    topics_path = Path(args.topics)
    if topics_path.exists():
        topics_g.parse(str(topics_path), format="turtle")

    # --- collect places
    places = list(set(kg.subjects(RDF.type, TG.Place)))
    if not places:
        raise SystemExit("No tg:Place found. Did you pass the right KG?")
    random.shuffle(places)
    places = places[: args.max_places]

    # --- collect topics (SKOS concepts)
    topics = list(set(topics_g.subjects(RDF.type, SKOS.Concept)))
    if not topics:
        # fallback: use TG:Food TG:Museum TG:Culture if present in your namespace
        topics = [TG.Food, TG.Museum, TG.Culture]

    # --- define likesPlace property in the output KG (minimal OWL)
    kg.add((TG.likesPlace, RDF.type, OWL.ObjectProperty))
    kg.add((TG.likesPlace, RDFS.domain, TG.Tourist))
    kg.add((TG.likesPlace, RDFS.range, TG.Place))

    # --- helper: get place polarity/numReviews to create plausible ratings
    def get_decimal(s, p):
        for o in kg.objects(s, p):
            try:
                return float(o)
            except Exception:
                pass
        return None

    # --- assign each place a "topic" (simple heuristic)
    def place_topic(place: URIRef) -> URIRef:
        # restaurant -> Food, attraction -> Culture, else -> Museum (fallback)
        if (place, RDF.type, TG.Restaurant) in kg:
            return TG.Food
        if (place, RDF.type, TG.Attraction) in kg:
            return TG.Culture
        return TG.Museum

    # --- create tourists + reviews
    today = date.today()
    for i in range(1, args.n_tourists + 1):
        t = TOURIST_NS[str(i)]
        kg.add((t, RDF.type, TG.Tourist))
        kg.add((t, TG.name, Literal(f"Tourist {i}", datatype=XSD.string)))

        pref = random.choice(topics)
        kg.add((t, TG.prefersTopic, pref))

        # pick candidate places biased by preferred topic
        candidates = [p for p in places if place_topic(p) == pref]
        if len(candidates) < args.reviews_per_tourist:
            # fallback to any places
            candidates = places[:]
        random.shuffle(candidates)
        candidates = candidates[: args.reviews_per_tourist]

        for j, p in enumerate(candidates, start=1):
            rid = f"{i}_{j}"
            r = REVIEW_NS[rid]
            kg.add((r, RDF.type, TG.Review))
            kg.add((r, TG.authoredBy, t))
            kg.add((r, TG.aboutPlace, p))
            kg.add((t, TG.wroteReview, r))
            kg.add((p, TG.hasReview, r))

            pol = get_decimal(p, TG.polarity)
            nrev = get_decimal(p, TG.numReviews)

            # rating in [1..5], correlated with polarity (your polarity looks like 0..10)
            base = 3.0
            if pol is not None:
                base = 1.0 + (pol / 10.0) * 4.0  # map 0..10 -> 1..5
            noise = random.uniform(-0.8, 0.8)
            rating = max(1.0, min(5.0, base + noise))
            kg.add((r, TG.rating, Literal(round(rating, 2), datatype=XSD.decimal)))

            # small text (optional)
            txt = f"Review on place. polarity={pol}, numReviews={nrev}"
            kg.add((r, TG.reviewText, Literal(txt, datatype=XSD.string)))

            d = today - timedelta(days=random.randint(0, 365))
            kg.add((r, TG.reviewDate, Literal(str(d), datatype=XSD.date)))

            # likesPlace
            if rating >= args.like_threshold:
                kg.add((t, TG.likesPlace, p))

            # also add hasTopic to help the model
            kg.add((p, TG.hasTopic, place_topic(p)))

    # --- optionally drop noisy external links for training
    if args.drop_external:
        to_remove = []
        for s, p, o in kg:
            if p in (OWL.sameAs, RDFS.seeAlso):
                to_remove.append((s, p, o))
            elif isinstance(s, URIRef) and is_external_uri(s):
                to_remove.append((s, p, o))
            elif isinstance(o, URIRef) and is_external_uri(o):
                to_remove.append((s, p, o))
        for t in to_remove:
            kg.remove(t)

    # --- write KG
    kg.serialize(args.kg_out, format="turtle")
    print(f"[OK] wrote {args.kg_out} with {len(kg)} triples")

    # --- build TSV for PyKEEN: keep ONLY entity-entity triples + rdf:type
    keep_preds = {
        RDF.type,
        TG.likesPlace,
        TG.prefersTopic,
        TG.hasTopic,
        TG.locatedIn,
        TG.wroteReview,
        TG.aboutPlace,
        TG.hasReview,
        TG.authoredBy,
    }

    lines = []
    for s, p, o in kg:
        if p not in keep_preds:
            continue
        if not isinstance(s, URIRef):
            continue
        if p == RDF.type:
            if isinstance(o, URIRef):
                lines.append((str(s), str(p), str(o)))
            continue
        if isinstance(o, URIRef):
            lines.append((str(s), str(p), str(o)))

    tsv_path = Path(args.triples_tsv)
    tsv_path.parent.mkdir(parents=True, exist_ok=True)
    with tsv_path.open("w", encoding="utf-8") as f:
        for h, r, t in lines:
            f.write(f"{h}\t{r}\t{t}\n")
    print(f"[OK] wrote {args.triples_tsv} with {len(lines)} triples for PyKEEN")


if __name__ == "__main__":
    main()
