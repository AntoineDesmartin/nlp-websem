#!/usr/bin/env python3
import sys
import time
import re
import requests
import urllib3
from urllib.parse import quote, unquote
from typing import Optional, List, Dict

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDFS

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
QID_RE = re.compile(r"/(Q\d+)$")


def chunked(lst: List[str], n: int):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def qid_from_wd_uri(u: str) -> Optional[str]:
    """
    Accepts:
      http://www.wikidata.org/entity/Q123
      https://www.wikidata.org/entity/Q123
    """
    m = QID_RE.search(u)
    if m:
        return m.group(1)
    return None


def dbpedia_from_wikipedia_url(wiki_url: str) -> Optional[URIRef]:
    # ex: https://en.wikipedia.org/wiki/Eiffel_Tower -> http://dbpedia.org/resource/Eiffel_Tower
    if "/wiki/" not in wiki_url:
        return None

    base, title = wiki_url.split("/wiki/", 1)
    title = title.strip()
    if not title:
        return None

    # éviter double-encoding (%2527 etc.)
    title = unquote(title)

    # garder certains caractères lisibles (dont virgule)
    safe_chars = "(),._-'"  # + virgule incluse
    title_enc = quote(title, safe=safe_chars + ",")

    if base.startswith("https://en.wikipedia.org"):
        return URIRef("http://dbpedia.org/resource/" + title_enc)
    if base.startswith("https://fr.wikipedia.org"):
        return URIRef("http://fr.dbpedia.org/resource/" + title_enc)

    return None


def fetch_wikipedia_sitelinks(qids: List[str]) -> Dict[str, Dict[str, str]]:
    """
    Returns:
      {
        "Q123": {"en": "https://en.wikipedia.org/wiki/...", "fr": "https://fr.wikipedia.org/wiki/..."},
        ...
      }
    """
    values = " ".join(f"wd:{qid}" for qid in qids)
    query = f"""
    PREFIX wd: <http://www.wikidata.org/entity/>
    PREFIX schema: <http://schema.org/>

    SELECT ?item ?enwiki ?frwiki WHERE {{
      VALUES ?item {{ {values} }}

      OPTIONAL {{
        ?enwiki schema:about ?item ;
               schema:isPartOf <https://en.wikipedia.org/> .
      }}
      OPTIONAL {{
        ?frwiki schema:about ?item ;
               schema:isPartOf <https://fr.wikipedia.org/> .
      }}
    }}
    """

    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "tourguide-project/1.0 (Wikidata->DBpedia linking)"
    }

    r = requests.get(WIKIDATA_SPARQL, params={"query": query}, headers=headers, timeout=60, verify=False)
    r.raise_for_status()
    data = r.json()

    out: Dict[str, Dict[str, str]] = {}
    for b in data["results"]["bindings"]:
        item_uri = b["item"]["value"]  # http://www.wikidata.org/entity/Qxxx
        qid = item_uri.rsplit("/", 1)[-1]
        out.setdefault(qid, {})
        if "enwiki" in b:
            out[qid]["en"] = b["enwiki"]["value"]
        if "frwiki" in b:
            out[qid]["fr"] = b["frwiki"]["value"]
    return out


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 scripts/link_wikidata_dbpedia.py data/kg_final.ttl data/kg_linked.ttl")
        sys.exit(1)

    in_path, out_path = sys.argv[1], sys.argv[2]

    g = Graph()
    g.parse(in_path, format="turtle")

    # 1) local -> QID via owl:sameAs Wikidata
    local_to_qid: Dict[URIRef, str] = {}
    for s, o in g.subject_objects(OWL.sameAs):
        if isinstance(o, URIRef):
            qid = qid_from_wd_uri(str(o))
            if qid:
                local_to_qid[s] = qid

    if not local_to_qid:
        print("No Wikidata owl:sameAs found in input graph. Nothing to link.")
        g.serialize(out_path, format="turtle")
        sys.exit(0)

    qids = sorted(set(local_to_qid.values()))
    print(f"Found {len(local_to_qid)} local resources with Wikidata links ({len(qids)} unique QIDs).")

    # 2) Wikidata query by batches
    qid_to_wikis: Dict[str, Dict[str, str]] = {}
    for batch in chunked(qids, 200):
        part = fetch_wikipedia_sitelinks(batch)
        qid_to_wikis.update(part)
        time.sleep(0.2)

    # 3) add links
    added_dbpedia = 0
    added_wikipedia = 0

    for local, qid in local_to_qid.items():
        wikis = qid_to_wikis.get(qid, {})

        for lang in ("en", "fr"):
            url = wikis.get(lang)
            if url:
                triple = (local, RDFS.seeAlso, URIRef(url))
                if triple not in g:
                    g.add(triple)
                    added_wikipedia += 1

                dbp = dbpedia_from_wikipedia_url(url)
                if dbp:
                    triple2 = (local, OWL.sameAs, dbp)
                    if triple2 not in g:
                        g.add(triple2)
                        added_dbpedia += 1

    g.serialize(out_path, format="turtle")
    print(f"Written: {out_path}")
    print(f"Added rdfs:seeAlso Wikipedia links: {added_wikipedia}")
    print(f"Added owl:sameAs DBpedia links: {added_dbpedia}")


if __name__ == "__main__":
    main()
