#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from pathlib import Path

import pandas as pd
import torch
from pykeen.pipeline import pipeline
from pykeen.triples import TriplesFactory


TG_PLACE_TYPE = "https://example.org/tourguide#Place"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--triples_tsv", default="data/reco_triples.tsv")
    ap.add_argument("--relation", default="https://example.org/tourguide#likesPlace")
    ap.add_argument("--model", default="TransE", help="TransE / DistMult / RESCAL / TransR ...")
    ap.add_argument("--epochs", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--topk", type=int, default=10)
    ap.add_argument("--out_json", default="data/recommendations.json")
    ap.add_argument("--batch_size", type=int, default=1024)
    ap.add_argument("--slice_size", type=int, default=4096)
    args = ap.parse_args()

    # 1) Load triples
    tf = TriplesFactory.from_path(
        args.triples_tsv,
        delimiter="\t",
    )

    # 2) Split train/valid/test
    train, test, valid = tf.split([0.8, 0.1, 0.1], random_state=args.seed)

    # 3) Pipeline PyKEEN
    # LCWA + margin loss + early stopping (compatible)
    result = pipeline(
        training=train,
        testing=test,
        validation=valid,
        model=args.model,
        training_loop="lcwa",
        loss="marginranking",
        # IMPORTANT: with LCWA, do NOT set negative_sampler
        stopper="early",
        stopper_kwargs=dict(frequency=5, patience=10, metric="mrr"),
        training_kwargs=dict(num_epochs=args.epochs, batch_size=args.batch_size),
        evaluator_kwargs=dict(filtered=True),
        random_seed=args.seed,
    )

    print("\n=== Evaluation (test) ===")
    df_metrics = result.metric_results.to_df().sort_index()
    print(df_metrics)

    model = result.model
    factory = result.training

    # 4) Identify relation id + all existing likesPlace triples
    if args.relation not in factory.relation_to_id:
        raise ValueError(
            f"Relation {args.relation} not found in triples factory relations. "
            f"Available examples: {list(factory.relation_to_id)[:10]}"
        )

    rel_id = factory.relation_to_id[args.relation]
    mapped = factory.mapped_triples

    likes_triples = mapped[mapped[:, 1] == rel_id]
    heads = sorted(set(likes_triples[:, 0].tolist()))

    # 5) Build a whitelist of valid "place" tail candidates
    # 5.a) By rdf:type triple (recommended)
    place_tail_ids_by_type = set()
    if "http://www.w3.org/1999/02/22-rdf-syntax-ns#type" in factory.relation_to_id:
        rdf_type_id = factory.relation_to_id["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"]
        if TG_PLACE_TYPE in factory.entity_to_id:
            tg_place_id = factory.entity_to_id[TG_PLACE_TYPE]
            type_triples = mapped[mapped[:, 1] == rdf_type_id]
            place_type_triples = type_triples[type_triples[:, 2] == tg_place_id]
            place_tail_ids_by_type = set(place_type_triples[:, 0].tolist())

    # 5.b) Fallback heuristic: URI contains "/place/"
    # (useful if rdf:type not present for some reason)
    place_tail_ids_by_uri = {
        eid for eid, label in factory.entity_id_to_label.items()
        if "/place/" in label
    }

    # Choose the best available filter
    if place_tail_ids_by_type:
        allowed_place_ids = place_tail_ids_by_type
        allowed_place_filter_mode = "rdf:type tg:Place"
    else:
        allowed_place_ids = place_tail_ids_by_uri
        allowed_place_filter_mode = 'URI contains "/place/"'

    if not allowed_place_ids:
        raise RuntimeError(
            "Could not detect any Place entities to recommend (allowed_place_ids is empty). "
            "Check that your reco_triples.tsv contains rdf:type tg:Place triples "
            "or that your place URIs include '/place/'."
        )

    print(f"\n[INFO] Place candidate filter mode: {allowed_place_filter_mode}")
    print(f"[INFO] Place candidates count: {len(allowed_place_ids)}")

    # 6) Recommend topK places for each tourist head
    recs = {}

    # prebuild list for speed (and stable ordering)
    allowed_place_ids_sorted = sorted(allowed_place_ids)

    for h in heads:
        # score all tails for the pair (h, rel)
        hr = torch.tensor([[h, rel_id]], dtype=torch.long, device=model.device)

        scores = (
            model.score_t(hr_batch=hr, slice_size=args.slice_size)
            .detach()
            .cpu()
            .numpy()
            .reshape(-1)
        )

        # exclude already-liked tails
        already = set(likes_triples[likes_triples[:, 0] == h][:, 2].tolist())

        # only recommend allowed place ids and not already liked
        candidates = [
            (t, float(scores[t]))
            for t in allowed_place_ids_sorted
            if t not in already
        ]
        candidates.sort(key=lambda x: x[1], reverse=True)
        top = candidates[: args.topk]

        h_label = factory.entity_id_to_label[h]
        recs[h_label] = [
            {"place": factory.entity_id_to_label[t], "score": s}
            for t, s in top
        ]

    # 7) Save JSON
    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(
            {
                "model": args.model,
                "relation": args.relation,
                "metrics_table": df_metrics.to_dict(orient="records"),
                "place_filter_mode": allowed_place_filter_mode,
                "place_candidates_count": len(allowed_place_ids),
                "recommendations": recs,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"\n[OK] wrote recommendations to {args.out_json}")


if __name__ == "__main__":
    main()
