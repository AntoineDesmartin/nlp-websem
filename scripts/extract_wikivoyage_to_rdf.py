#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import json
import re
import hashlib
import unicodedata
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, XSD, OWL, RDFS

TG = Namespace("https://example.org/tourguide#")
SCHEMA = Namespace("http://schema.org/")

TEMPLATE_TYPES = {
    "see": TG.Attraction,
    "do": TG.Attraction,
    "eat": TG.Restaurant,
    "drink": TG.Restaurant,
    "buy": TG.POI,
    "sleep": TG.POI,
    "listing": TG.POI,
}

# Alignement OWL+SKOS : on associe un topic (skos:Concept) selon le type Wikivoyage.
# Ces IRIs existent dans `thesaurus/topics.ttl`.
TEMPLATE_TOPICS = {
    "see": TG.Culture,
    "do": TG.Culture,
    "eat": TG.Food,
    "drink": TG.Food,
    "buy": TG.Shopping,
    "sleep": TG.Accommodation,
    "listing": TG.Culture,
}


def normalize_price_level(raw: str) -> int | None:
    """Best-effort mapping to tg:priceLevel in [1..4]."""
    if not raw:
        return None
    s = strip_wiki_markup(raw).strip().lower()

    # common patterns: $, $$, $$$, $$$$
    dollars = re.findall(r"\$+", s)
    if dollars:
        n = max(len(d) for d in dollars)
        return max(1, min(4, n))

    # textual levels
    if any(w in s for w in ("cheap", "budget", "low")):
        return 1
    if any(w in s for w in ("moderate", "mid", "medium")):
        return 2
    if any(w in s for w in ("expensive", "high")):
        return 3
    if any(w in s for w in ("luxury", "fine", "premium")):
        return 4

    m = re.search(r"\b([1-4])\b", s)
    if m:
        return int(m.group(1))
    return None

def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:60] if s else "item"

def extract_templates(text: str, names_set: set[str]) -> list[str]:
    """
    Extract full template contents (without outer {{ }}) for template names in names_set.
    Robust-ish using brace depth parsing.
    """
    res = []
    i, n = 0, len(text)
    while i < n - 1:
        if text[i:i+2] == "{{":
            depth = 1
            j = i + 2
            while j < n - 1 and depth > 0:
                if text[j:j+2] == "{{":
                    depth += 1
                    j += 2
                    continue
                if text[j:j+2] == "}}":
                    depth -= 1
                    j += 2
                    continue
                j += 1

            if depth == 0:
                content = text[i+2 : j-2]
                name = content.split("|", 1)[0].strip().lower()
                if name in names_set:
                    res.append(content)
                i = j
                continue
        i += 1
    return res

def split_params(content: str) -> list[str]:
    """
    Split 'name|k=v|k2=v2' into parts on |, avoiding splitting inside nested {{...}}.
    """
    parts = []
    buf = []
    depth = 0
    i = 0
    while i < len(content):
        if content[i:i+2] == "{{":
            depth += 1
            buf.append("{{")
            i += 2
            continue
        if content[i:i+2] == "}}" and depth > 0:
            depth -= 1
            buf.append("}}")
            i += 2
            continue

        ch = content[i]
        if ch == "|" and depth == 0:
            parts.append("".join(buf))
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    parts.append("".join(buf))
    return parts

def parse_template(template_content: str) -> tuple[str, dict]:
    parts = split_params(template_content)
    name = parts[0].strip().lower()
    params = {}

    for p in parts[1:]:
        p = p.strip()
        if not p:
            continue
        if "=" in p:
            k, v = p.split("=", 1)
            params[k.strip().lower()] = v.strip()
        else:
            # parfois le 1er param sans clé = name
            if "name" not in params:
                params["name"] = p.strip()

    return name, params

def strip_wiki_markup(s: str) -> str:
    # enlève quelques formes courantes, sans faire un parser complet
    s = re.sub(r"\[\[([^|\]]+\|)?([^\]]+)\]\]", r"\2", s)  # [[x|y]] -> y
    s = re.sub(r"''+", "", s)  # italique/gras
    s = re.sub(r"<[^>]+>", "", s)  # tags html
    s = re.sub(r"\s+", " ", s).strip()
    return s

def mk_place_uri(name: str, lat: float, lng: float) -> URIRef:
    base = f"{name}|{lat}|{lng}"
    h = hashlib.md5(base.encode("utf-8")).hexdigest()[:10]
    return URIRef(f"https://example.org/tourguide/wikivoyage/place/{slugify(name)}-{h}")

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 scripts/extract_wikivoyage_to_rdf.py <input_json> <output_ttl>")
        sys.exit(1)

    input_json = sys.argv[1]
    output_ttl = sys.argv[2]

    data = json.load(open(input_json, "r", encoding="utf-8"))
    # format attendu type MediaWiki API: data["parse"]["wikitext"]["*"]
    wikitext = data["parse"]["wikitext"]["*"]

    templates_raw = extract_templates(wikitext, set(TEMPLATE_TYPES.keys()))
    parsed = [parse_template(t) for t in templates_raw]

    G = Graph()
    G.bind("tg", TG)
    G.bind("owl", OWL)
    G.bind("rdfs", RDFS)
    G.bind("schema", SCHEMA)

    # City: Paris (on réutilise un URI stable)
    paris = URIRef("https://example.org/tourguide/city/Paris")
    G.add((paris, RDF.type, TG.City))
    G.add((paris, TG.cityName, Literal("Paris")))

    kept = 0
    skipped = 0

    for tname, params in parsed:
        cls = TEMPLATE_TYPES.get(tname)
        if cls is None:
            skipped += 1
            continue

        name = params.get("name") or params.get("alt") or ""
        lat = params.get("lat")
        lng = params.get("long") or params.get("lon") or params.get("lng")

        # pour éviter tes violations SHACL : on garde seulement les items complets
        if not (name and lat and lng):
            skipped += 1
            continue

        try:
            lat_f = float(lat)
            lng_f = float(lng)
        except Exception:
            skipped += 1
            continue

        if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lng_f <= 180.0):
            skipped += 1
            continue

        uri = mk_place_uri(name, lat_f, lng_f)

        # placeId obligatoire dans tes SHACL -> on met un id stable "wv:..."
        place_id = f"wv:{hashlib.md5(str(uri).encode('utf-8')).hexdigest()[:12]}"

        G.add((uri, RDF.type, TG.Place))
        G.add((uri, RDF.type, cls))
        G.add((uri, TG.placeId, Literal(place_id)))
        G.add((uri, TG.name, Literal(strip_wiki_markup(name))))
        G.add((uri, TG.locatedIn, paris))
        G.add((uri, TG.lat, Literal(lat_f, datatype=XSD.decimal)))
        G.add((uri, TG.lng, Literal(lng_f, datatype=XSD.decimal)))

        # Topic SKOS (alignement OWL/SKOS/SHACL)
        topic = TEMPLATE_TOPICS.get(tname)
        if topic is not None:
            G.add((uri, TG.hasTopic, topic))

        addr = params.get("address")
        if addr:
            G.add((uri, TG.address, Literal(strip_wiki_markup(addr))))

        # wikidata=Qxxxx si présent -> owl:sameAs
        wd = (params.get("wikidata") or "").strip()
        if re.fullmatch(r"Q\d+", wd):
            G.add((uri, OWL.sameAs, URIRef(f"http://www.wikidata.org/entity/{wd}")))

        # url si présent -> schema:url (enrichissement, pas “core”)
        url = (params.get("url") or "").strip()
        if url.startswith("http://") or url.startswith("https://"):
            G.add((uri, SCHEMA.url, URIRef(url)))
            # Alignement OWL: tg:website est une DatatypeProperty (xsd:anyURI)
            G.add((uri, TG.website, Literal(url, datatype=XSD.anyURI)))

        # Champs optionnels (si présents dans le template)
        phone = (params.get("phone") or params.get("tel") or params.get("telephone") or "").strip()
        if phone:
            G.add((uri, TG.phoneNumber, Literal(strip_wiki_markup(phone), datatype=XSD.string)))

        hours = (
            params.get("hours")
            or params.get("openinghours")
            or params.get("opening_hours")
            or params.get("opening hours")
            or ""
        ).strip()
        if hours:
            G.add((uri, TG.openingHours, Literal(strip_wiki_markup(hours), datatype=XSD.string)))

        # Restaurant-specific enrichment (best-effort)
        if cls == TG.Restaurant:
            cuisine = (
                params.get("cuisine")
                or params.get("type")
                or params.get("food")
                or params.get("cuisinetype")
                or ""
            ).strip()
            if cuisine:
                G.add((uri, TG.cuisineType, Literal(strip_wiki_markup(cuisine), datatype=XSD.string)))

            price_raw = (params.get("price") or params.get("pricerange") or params.get("price range") or "").strip()
            pl = normalize_price_level(price_raw)
            if pl is not None:
                G.add((uri, TG.priceLevel, Literal(pl, datatype=XSD.integer)))

        content = params.get("content") or params.get("description") or ""
        content = strip_wiki_markup(content)
        if content:
            G.add((uri, RDFS.comment, Literal(content)))

        kept += 1

    G.serialize(output_ttl, format="turtle")
    print("Wikivoyage templates found:", len(templates_raw))
    print("Kept places (with name+lat+lng):", kept)
    print("Skipped (incomplete/invalid):", skipped)
    print("Written:", output_ttl)
    print("Triples:", len(G))

if __name__ == "__main__":
    main()
