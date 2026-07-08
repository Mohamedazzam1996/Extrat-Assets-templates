import json
import csv
import argparse

def extract_ip_port_from_interface(interface):
    return interface.get("ip", ""), interface.get("port", "")

def parse_zabbix_json(json_file):
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    hosts = data.get("zabbix_export", {}).get("hosts", [])
    rows = []
    
    for host in hosts:
        row = {
            "host": host.get("host", ""),
            "monitored_by": host.get("monitored_by", ""),
            "proxy.name": host.get("proxy", {}).get("name", ""),
        }
        
        templates = host.get("templates", [])
        row["templates"] = ",".join([t.get('name', '') for t in templates])
        
        groups = host.get("groups", [])
        row["groups"] = ";".join([f"name={g.get('name', '')}" for g in groups])
        
        interfaces = host.get("interfaces", [])
        if interfaces:
            iface = interfaces[0]
            row["ip"], row["port"] = extract_ip_port_from_interface(iface)
            row["interface_type"] = iface.get("type", "")
        else:
            row["ip"] = ""
            row["port"] = ""
            row["interface_type"] = ""
        
        tags = host.get("tags", [])
        row["tags"] = ";".join([f"tag={t.get('tag', '')}|value={t.get('value', '')}" for t in tags])
        
        rows.append(row)
    
    return rows

def load_assets_lookup(assets_file):
    lookup = {}
    try:
        with open(assets_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                asset_name = row.get("assetName", "").strip()
                if asset_name:
                    lookup[asset_name.lower()] = row
    except FileNotFoundError:
        pass
    return lookup

def merge_data(zabbix_rows, assets_lookup):
    for row in zabbix_rows:
        host_name = row.get("host", "").strip()
        host_lower = host_name.lower()
        asset_data = assets_lookup.get(host_lower, {})
        
        if asset_data:
            row.update({
                "assetId": asset_data.get("assetId", ""),
                "assetName": asset_data.get("assetName", ""),
                "assetType": asset_data.get("assetType", ""),
                "cmdbStatus": asset_data.get("cmdbStatus", ""),
                "csuId": asset_data.get("csuId", ""),
                "csuName": asset_data.get("csuName", ""),
                "customerId": asset_data.get("customerId", ""),
                "customerName": asset_data.get("customerName", ""),
                "enrichmentIssue": asset_data.get("enrichmentIssue", ""),
                "enrichmentStatus": asset_data.get("enrichmentStatus", ""),
                "l1Support": asset_data.get("l1Support", ""),
                "l1SupportName": asset_data.get("l1SupportName", ""),
                "l2Support": asset_data.get("l2Support", ""),
                "l2SupportName": asset_data.get("l2SupportName", ""),
                "monitoringAllowed": asset_data.get("monitoringAllowed", ""),
                "networkZone": asset_data.get("networkZone", ""),
                "offer": asset_data.get("offer", ""),
                "organization": asset_data.get("organization", ""),
            })
        else:
            for field in ["assetId", "assetName", "assetType", "cmdbStatus",
                         "csuId", "csuName", "customerId", "customerName",
                         "enrichmentIssue", "enrichmentStatus", "l1Support",
                         "l1SupportName", "l2Support", "l2SupportName",
                         "monitoringAllowed", "networkZone", "offer", "organization"]:
                row[field] = ""
    
    return zabbix_rows

def write_output(rows, output_file):
    fieldnames = [
        "host", "monitored_by", "proxy.name", "templates", "groups",
        "interface_type", "ip", "port", "tags",
        "assetId", "assetName", "assetType", "cmdbStatus",
        "csuId", "csuName", "customerId", "customerName",
        "enrichmentIssue", "enrichmentStatus",
        "l1Support", "l1SupportName", "l2Support", "l2SupportName",
        "monitoringAllowed", "networkZone", "offer", "organization"
    ]
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def main():
    parser = argparse.ArgumentParser(description='Convert Zabbix JSON export to CSV with CMDB merge')
    parser.add_argument('json_file', help='Input Zabbix JSON file')
    parser.add_argument('-o', '--output', required=True, help='Output CSV file')
    parser.add_argument('-a', '--assets', default='MIP-Assets.csv', help='CMDB assets CSV file (default: MIP-Assets.csv)')
    
    args = parser.parse_args()
    
    zabbix_rows = parse_zabbix_json(args.json_file)
    assets_lookup = load_assets_lookup(args.assets)
    merged_rows = merge_data(zabbix_rows, assets_lookup)
    write_output(merged_rows, args.output)
    
    print(f"WROTE {args.output}")

if __name__ == "__main__":
    main()
