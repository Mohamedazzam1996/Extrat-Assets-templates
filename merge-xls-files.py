import pandas as pd
from pathlib import Path

INPUT_DIR = Path(r"C:\Users\BXXT8019\Downloads")
OUTPUT_FILE = INPUT_DIR / "assets.txt"
FILES = [INPUT_DIR / f"asset-list-{i}.xls" for i in range(4, 15)]

ASSET_NAME_CANDIDATES = ["Asset Name", "asset name", "AssetName", "assetName", "Name"]

def find_asset_col(columns):
    norm = {str(c).strip().lower(): c for c in columns}
    for cand in ASSET_NAME_CANDIDATES:
        key = cand.strip().lower()
        if key in norm:
            return norm[key]
    return None

def read_file_with_fallback(file_path):
    # 1) Try true XLS engine
    try:
        return pd.read_excel(file_path, dtype=str, engine="xlrd")
    except Exception as e1:
        # 2) Fallback: many .xls are HTML tables
        try:
            tables = pd.read_html(file_path)
            if tables:
                return tables[0].astype(str)
        except Exception as e2:
            raise Exception(f"xlrd error: {e1} | html fallback error: {e2}")
    return None

all_assets = []
files_processed = 0

for file_path in FILES:
    if not file_path.exists():
        print(f"[WARN] Missing file: {file_path}")
        continue

    try:
        df = read_file_with_fallback(file_path)
        if df is None or df.empty:
            print(f"[WARN] No data in: {file_path.name}")
            continue

        col = find_asset_col(df.columns)
        if not col:
            print(f"[WARN] 'Asset Name' column not found in {file_path.name}")
            print(f"       Columns: {list(df.columns)}")
            continue

        values = df[col].fillna("").astype(str).str.strip()
        values = values[values != ""]
        all_assets.extend(values.tolist())
        files_processed += 1

        print(f"[INFO] Processed {file_path.name}: {len(values)} rows")

    except Exception as e:
        print(f"[ERROR] Failed to read {file_path.name}: {e}")

unique_assets = sorted(set(all_assets), key=lambda s: s.lower())

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    for a in unique_assets:
        f.write(a + "\n")

print("\n=== DONE ===")
print(f"[INFO] Files processed: {files_processed}")
print(f"[INFO] Total extracted rows: {len(all_assets)}")
print(f"[INFO] Unique assets written: {len(unique_assets)}")
print(f"[INFO] Output: {OUTPUT_FILE}")
