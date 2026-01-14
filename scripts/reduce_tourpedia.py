# reduce_tourpedia.py
import csv
import json
from pathlib import Path

# ---- Réglages : change les tailles ici ----
N_ATTRACTIONS = 1500
N_POI = 1500
N_RESTAURANTS = 2000

# Fichiers INPUT (clean) -> OUTPUT (subset)
CSV_TASKS = [
    ("data/clean/paris-attraction.clean.csv", "data/subset/paris-attraction.subset.csv", N_ATTRACTIONS),
    ("data/clean/paris-poi.clean.csv",        "data/subset/paris-poi.subset.csv",        N_POI),
    ("data/clean/paris-restaurant.clean.csv", "data/subset/paris-restaurant.subset.csv", N_RESTAURANTS),
]

JSON_TASKS = [
    ("data/raw/places_paris_attraction.json",  "data/subset/places_paris_attraction.subset.json"),
    ("data/raw/places_paris_poi.json",         "data/subset/places_paris_poi.subset.json"),
    ("data/raw/places_paris_restaurant.json",  "data/subset/places_paris_restaurant.subset.json"),
]

def read_json_by_id(path: str) -> dict[str, dict]:
    arr = json.load(open(path, encoding="utf-8"))
    # JSON = liste d'objets, chacun a "id"
    return {str(o.get("id")): o for o in arr if "id" in o}

def write_csv_subset(src_csv: str, dst_csv: str, ids_keep: set[str]) -> None:
    Path(dst_csv).parent.mkdir(parents=True, exist_ok=True)
    with open(src_csv, newline="", encoding="utf-8") as f_in, open(dst_csv, "w", newline="", encoding="utf-8") as f_out:
        r = csv.DictReader(f_in)
        w = csv.DictWriter(f_out, fieldnames=r.fieldnames)
        w.writeheader()
        for row in r:
            if str(row.get("id", "")).strip() in ids_keep:
                w.writerow(row)

def main():
    Path("data/subset").mkdir(parents=True, exist_ok=True)

    # 1) Charger JSON (pour pouvoir trier par numReviews)
    json_attraction = read_json_by_id("data/raw/places_paris_attraction.json")
    json_poi        = read_json_by_id("data/raw/places_paris_poi.json")
    json_restaurant = read_json_by_id("data/raw/places_paris_restaurant.json")

    # 2) Choisir IDs à garder = top N par numReviews (fallback 0 si absent)
    def top_ids(jmap: dict[str, dict], n: int) -> set[str]:
        items = sorted(
            jmap.items(),
            key=lambda kv: int(kv[1].get("numReviews") or 0),
            reverse=True
        )
        return set([k for k, _ in items[:n]])

    keep_attraction = top_ids(json_attraction, N_ATTRACTIONS)
    keep_poi        = top_ids(json_poi,        N_POI)
    keep_restaurant = top_ids(json_restaurant, N_RESTAURANTS)

    # 3) Écrire CSV subset (cohérent avec JSON)
    write_csv_subset("data/clean/paris-attraction.clean.csv", "data/subset/paris-attraction.subset.csv", keep_attraction)
    write_csv_subset("data/clean/paris-poi.clean.csv",        "data/subset/paris-poi.subset.csv",        keep_poi)
    write_csv_subset("data/clean/paris-restaurant.clean.csv", "data/subset/paris-restaurant.subset.csv", keep_restaurant)

    # 4) Écrire JSON subset (juste les objets gardés)
    def write_json_subset(jmap: dict[str, dict], ids_keep: set[str], out_path: str):
        arr = [jmap[i] for i in ids_keep if i in jmap]
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(arr, f, ensure_ascii=False, indent=2)

    write_json_subset(json_attraction, keep_attraction, "data/subset/places_paris_attraction.subset.json")
    write_json_subset(json_poi,        keep_poi,        "data/subset/places_paris_poi.subset.json")
    write_json_subset(json_restaurant, keep_restaurant, "data/subset/places_paris_restaurant.subset.json")

    print("OK -> data/subset/*.subset.(csv|json)")
    print("Sizes:",
          "attraction", len(keep_attraction),
          "poi", len(keep_poi),
          "restaurant", len(keep_restaurant))

if __name__ == "__main__":
    main()
