# clean_tourpedia_csv.py
import csv
import re
from pathlib import Path

EXPECTED_HEADER = [
    "address", "category", "id", "lat", "lng", "location", "name",
    "originalId", "polarity", "subCategory", "details", "reviews"
]
N = len(EXPECTED_HEADER)
DIGITS = re.compile(r"^\d+$")

RAW_FILES = [
    ("data/raw/paris-attraction.csv", "data/clean/paris-attraction.clean.csv"),
    ("data/raw/paris-poi.csv",        "data/clean/paris-poi.clean.csv"),
    ("data/raw/paris-restaurant.csv", "data/clean/paris-restaurant.clean.csv"),
]

def is_alt_restaurant_row(row: list[str]) -> bool:
    """
    Format alternatif observé dans ton paris-restaurant.csv :
    83360,Alcar,"25 Rue de Buci, Paris, France",restaurant,Paris,48.853738,2.336777,details,reviews
    => 9 champs, ordre différent, sans originalId/polarity/subCategory
    """
    return (
        len(row) == 9
        and DIGITS.match(row[0].strip()) is not None
        and row[3].strip().lower() == "restaurant"
    )

def convert_alt_restaurant_row(row: list[str]) -> list[str]:
    _id, name, address, category, location, lat, lng, details, reviews = row
    return [
        address, category, _id, lat, lng, location, name,
        "", "", "",  # originalId, polarity, subCategory manquants
        details, reviews
    ]

def fix_to_12_columns(row: list[str]) -> list[str]:
    """
    Ramène n'importe quelle ligne à exactement 12 colonnes.
    - Si trop de colonnes : on recolle le surplus dans 'address' (col 0), car c'est là que les virgules cassent le CSV.
    - Si pas assez : on complète avec "".
    """
    if len(row) == N:
        return row

    if is_alt_restaurant_row(row):
        return convert_alt_restaurant_row(row)

    if len(row) > N:
        extra = len(row) - N
        # On absorbe (extra) champs dans l'adresse
        address = ",".join(row[: 1 + extra])
        fixed = [address] + row[1 + extra :]
        return (fixed + [""] * N)[:N]

    # len(row) < N
    return (row + [""] * N)[:N]

def clean_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)

    # newline='' recommandé pour le module csv (évite des soucis de parsing) :contentReference[oaicite:1]{index=1}
    with src.open(newline="", encoding="utf-8") as f_in, dst.open("w", newline="", encoding="utf-8") as f_out:
        reader = csv.reader(f_in)
        _header = next(reader, None)
        if _header is None:
            raise RuntimeError(f"Fichier vide: {src}")

        writer = csv.writer(f_out, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(EXPECTED_HEADER)

        for row in reader:
            row = [c.strip() for c in row]
            row = fix_to_12_columns(row)
            writer.writerow(row)

def main():
    for src, dst in RAW_FILES:
        clean_file(Path(src), Path(dst))
    print("OK -> fichiers nettoyés dans data/clean/*.clean.csv")

if __name__ == "__main__":
    main()
