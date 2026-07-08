import csv
import time
import getpass
import requests
import urllib3
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ZABBIX_URL = "https://zabbix-bypassproxy.casa.uro.equant.com/api_jsonrpc.php"

# Files
INPUT_FILE = r"C:\Users\BXXT8019\OneDrive - orange.com\Bureau\assets.txt"
OUTPUT_FILE = r"C:\Users\BXXT8019\OneDrive - orange.com\Bureau\asset_templates.csv"
ASSETS_CMDB_FILE = r"C:\Users\BXXT8019\Downloads\MIP-Assets.csv"

# Request behavior
VERIFY_SSL = False   # set True + corporate CA if needed
TIMEOUT_SEC = 60
RETRIES = 3


def call(method, params, auth=None, req_id=1):
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": req_id}
    if auth:
        payload["auth"] = auth

    last_err = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = requests.post(
                ZABBIX_URL,
                json=payload,
                timeout=TIMEOUT_SEC,
                verify=VERIFY_SSL
            )
            r.raise_for_status()
            j = r.json()
            if "error" in j:
                raise Exception(j["error"])
            return j["result"]
        except Exception as e:
            last_err = e
            print(f"[WARN] {method} attempt {attempt}/{RETRIES} failed: {e}")
            time.sleep(2)

    raise Exception(f"{method} failed after {RETRIES} attempts: {last_err}")


def norm(x):
    return (x or "").strip().lower()


def fetch_hosts(auth, extra_params, req_id):
    params = {
        "output": ["hostid", "name", "host"],
        "selectInventory": ["model"],
        "selectParentTemplates": ["templateid", "name"],
        "selectTags": ["tag", "value"],
    }
    params.update(extra_params)
    return call("host.get", params, auth=auth, req_id=req_id)


def get_agent_version(auth, hostid):
    """Retrieve Zabbix agent version from host items"""
    try:
        items = call("item.get", {
            "output": ["lastvalue"],
            "hostids": hostid,
            "search": {"key_": "agent.version"},
            "sortfield": "name"
        }, auth=auth, req_id=20)

        if items and len(items) > 0:
            return items[0].get("lastvalue", "")
        return ""
    except Exception as e:
        print(f"[WARN] Could not retrieve agent version: {e}")
        return ""


def get_cmdb_id(tags):
    """Extract cmdb_id from host tags"""
    for tag in tags:
        if tag.get("tag", "").lower() == "cmdb_id":
            return tag.get("value", "")
    return ""


def get_host(auth, asset):
    a = asset.strip()
    an = norm(a)

    # 1) Exact visible name
    hosts = fetch_hosts(auth, {"filter": {"name": [a]}}, 10)
    if hosts:
        return hosts[0]

    # 2) Exact technical host
    hosts = fetch_hosts(auth, {"filter": {"host": [a]}}, 11)
    if hosts:
        return hosts[0]

    # 3) Search fallback in name
    hosts = fetch_hosts(auth, {"search": {"name": a}, "searchByAny": True}, 12)
    for h in hosts:
        if norm(h.get("name")) == an or norm(h.get("host")) == an:
            return h

    # 4) Search fallback in host
    hosts = fetch_hosts(auth, {"search": {"host": a}, "searchByAny": True}, 13)
    for h in hosts:
        if norm(h.get("name")) == an or norm(h.get("host")) == an:
            return h

    return None


def load_assets_lookup(assets_file):
    lookup = {}
    try:
        with open(assets_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                asset_name = (row.get("assetName", "") or "").strip()
                if asset_name:
                    lookup[asset_name.lower()] = row
    except FileNotFoundError:
        print(f"[WARN] CMDB file not found: {assets_file}")
    return lookup


def enrich_rows_with_cmdb(rows, assets_lookup):
    cmdb_fields = [
        "assetId", "assetName", "assetType", "cmdbStatus",
        "csuId", "csuName", "customerId", "customerName",
        "enrichmentIssue", "enrichmentStatus", "l1Support",
        "l1SupportName", "l2Support", "l2SupportName",
        "monitoringAllowed", "networkZone", "offer", "organization"
    ]

    for row in rows:
        # Match by input asset name first, fallback to matched host
        key = (row.get("asset_name") or row.get("matched_host") or "").strip().lower()
        cmdb = assets_lookup.get(key, {})

        if cmdb:
            for f in cmdb_fields:
                row[f] = cmdb.get(f, "")
        else:
            for f in cmdb_fields:
                row[f] = ""

    return rows


def main():
    # Ask credentials at runtime
    user_in = input("Zabbix username [CASAMIR]: ").strip()
    username = user_in if user_in else "CASAMIR"
    password = getpass.getpass("Zabbix password: ")

    print(f"[INFO] Logging in as: {username}")
    auth = call("user.login", {"username": username, "password": password}, req_id=1)

    # Read assets
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        assets = [line.strip() for line in f if line.strip()]

    print(f"[INFO] Loaded {len(assets)} assets from {INPUT_FILE}")

    rows = []
    for idx, asset in enumerate(assets, start=1):
        print(f"[INFO] ({idx}/{len(assets)}) Processing: {asset}")
        try:
            h = get_host(auth, asset)
            if not h:
                rows.append({
                    "asset_name": asset,
                    "matched_host": "",
                    "model": "",
                    "agent_version": "",
                    "cmdb_id": "",
                    "attached_templates": "NOT_FOUND"
                })
                continue

            hostid = h.get("hostid")
            model = (h.get("inventory") or {}).get("model", "")
            templates = [t["name"] for t in h.get("parentTemplates", [])]
            tags = h.get("tags", [])

            # Get agent version
            agent_version = get_agent_version(auth, hostid)

            # Get cmdb_id from tags
            cmdb_id = get_cmdb_id(tags)

            rows.append({
                "asset_name": asset,
                "matched_host": h.get("name") or h.get("host") or "",
                "model": model,
                "agent_version": agent_version,
                "cmdb_id": cmdb_id,
                "attached_templates": " | ".join(templates) if templates else ""
            })

        except Exception as e:
            rows.append({
                "asset_name": asset,
                "matched_host": "",
                "model": "",
                "agent_version": "",
                "cmdb_id": "",
                "attached_templates": f"ERROR: {e}"
            })

    # CMDB enrichment
    print(f"[INFO] Using CMDB file: {ASSETS_CMDB_FILE}")
    if not os.path.exists(ASSETS_CMDB_FILE):
        print(f"[WARN] CMDB file not found: {ASSETS_CMDB_FILE}")

    assets_lookup = load_assets_lookup(ASSETS_CMDB_FILE)
    rows = enrich_rows_with_cmdb(rows, assets_lookup)

    # Write CSV
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "asset_name", "matched_host", "model", "agent_version", "cmdb_id", "attached_templates",
                "assetId", "assetName", "assetType", "cmdbStatus",
                "csuId", "csuName", "customerId", "customerName",
                "enrichmentIssue", "enrichmentStatus",
                "l1Support", "l1SupportName", "l2Support", "l2SupportName",
                "monitoringAllowed", "networkZone", "offer", "organization"
            ]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"[DONE] CSV written to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
