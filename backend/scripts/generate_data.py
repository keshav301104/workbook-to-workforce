"""Generate the simulated business data used by the 10 workflows.

Every file is deterministic (fixed seed) and deliberately contains the edge
cases the Excel decision rules talk about, so the behaviour is testable:

* inventory.csv            stock exactly AT threshold (must NOT be flagged), zero stock,
                           missing max_stock (fallback reorder formula)
* products.csv / vendor_prices.csv
                           SKU format drift (TS-1001 vs ts1001), a price gap of exactly
                           10% (must NOT be flagged), unmatched SKUs on both sides
* vendor_upload_sample.*   messy headers, missing SKU / name, whitespace-only names,
                           blank rows, non-numeric prices, duplicate SKUs
* orders.csv / shipments.csv
                           shipped, delivered, processing (no shipment yet), cancelled,
                           multiple orders for one email
* catalog.csv              exact SKU duplicates, look-alike products, near-misses that
                           differ only by size (must not be a high-confidence duplicate)
* keywords.csv             case/whitespace duplicates, all four intents
* employees.csv            right skills but on leave, right skills but overloaded
* execution_logs.csv       30 days of step-level history for WF010

Run:  python scripts/generate_data.py
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
rng = random.Random(42)


def save(df: pd.DataFrame, name: str) -> None:
    df.to_csv(DATA / name, index=False)
    print(f"  wrote data/{name:<28} {len(df):>4} rows")


# --------------------------------------------------------------------------- products
products = [
    # sku, name, brand, category, collection, launch, material, color, size, audience, price, cost, features
    ("TS-1001", "Classic Linen Shirt", "Halden", "Shirts", "Summer 2026", "2026-04-01", "Linen", "White", "M", "Men 25-45", 59.00, 21.50, "Relaxed fit; mother-of-pearl buttons"),
    ("TS-1002", "Oxford Button-Down Shirt", "Halden", "Shirts", "Core", "2025-01-10", "Cotton", "Light Blue", "L", "Men 25-45", 64.00, 24.00, "Button-down collar; chest pocket"),
    ("TS-1003", "Linen Overshirt", "Halden", "Shirts", "Autumn 2026", "2026-09-15", "Linen", "Sage Green", "M", "Men 25-40", 89.00, 31.00, "Two flap pockets; boxy fit"),
    ("KN-2001", "Merino Crew Sweater", "Halden", "Knitwear", "Autumn 2026", "2026-09-15", "Merino Wool", "Charcoal", "M", "Men & Women 25-50", 119.00, 42.00, "Ribbed cuffs; machine washable"),
    ("KN-2002", "Cable Knit Cardigan", "Halden", "Knitwear", "Autumn 2026", "2026-09-15", None, "Oat", "S", "Women 25-45", 139.00, 55.00, "Horn buttons"),
    ("OW-3001", "Waxed Field Jacket", "Halden", "Outerwear", "Autumn 2026", "2026-09-15", "Waxed Cotton", "Olive", "L", "Men 30-55", 249.00, 96.00, "Corduroy collar; storm flap"),
    ("OW-3002", "Quilted Liner Vest", "Halden", "Outerwear", "Autumn 2026", "2026-09-15", "Recycled Polyester", None, "M", None, 129.00, 44.00, "Packable"),
    ("TR-4001", "Relaxed Chino Trousers", "Halden", "Trousers", "Core", "2025-01-10", "Cotton Twill", "Stone", "32", "Men 25-45", 79.00, 27.00, "Garment dyed"),
    ("TR-4002", "Pleated Wool Trousers", "Halden", "Trousers", "Autumn 2026", "2026-09-15", "Wool", "Navy", "32", "Men 30-55", 149.00, 58.00, "Single pleat; side adjusters"),
    ("AC-5001", "Leather Belt", "Halden", "Accessories", "Core", "2025-01-10", "Full-grain Leather", "Brown", "90", "Men & Women", 49.00, 15.00, "Solid brass buckle"),
    ("AC-5002", "Wool Beanie", "Halden", "Accessories", "Autumn 2026", "2026-09-15", "Lambswool", "Rust", "One Size", "Men & Women", 35.00, 9.50, "Fold-over cuff"),
    ("AC-5003", "Canvas Tote Bag", "Halden", "Accessories", "Summer 2026", "2026-04-01", "Organic Cotton Canvas", "Natural", "One Size", "Men & Women", 39.00, 11.00, "Inner zip pocket"),
    ("HM-6001", "Linen Duvet Cover", "Halden Home", "Home", "Core", "2025-03-01", "Linen", "Clay", "Queen", "Homeowners", 189.00, 70.00, "Coconut buttons"),
    ("HM-6002", "Stoneware Mug Set", "Halden Home", "Home", "Core", "2025-03-01", "Stoneware", "Speckled White", "Set of 4", "Homeowners", 45.00, 14.00, "Dishwasher safe"),
    ("HM-6003", "Wool Throw Blanket", "Halden Home", "Home", "Autumn 2026", "2026-09-15", "Wool", "Forest", "130x180", "Homeowners", 129.00, 47.00, "Fringed edges"),
]
pcols = ["sku", "product_name", "brand", "category", "collection", "launch_date", "material", "color",
         "size", "target_audience", "internal_price", "unit_cost", "features"]
save(pd.DataFrame(products, columns=pcols), "products.csv")

# --------------------------------------------------------------------------- inventory
inv = [
    # sku, name, category, current, minimum, max
    ("TS-1001", "Classic Linen Shirt", "Shirts", 12, 25, 120),
    ("TS-1002", "Oxford Button-Down Shirt", "Shirts", 64, 30, 150),
    ("TS-1003", "Linen Overshirt", "Shirts", 0, 20, 100),          # out of stock
    ("KN-2001", "Merino Crew Sweater", "Knitwear", 18, 18, 90),     # exactly AT threshold -> not flagged
    ("KN-2002", "Cable Knit Cardigan", "Knitwear", 7, 15, None),    # no max -> fallback formula
    ("OW-3001", "Waxed Field Jacket", "Outerwear", 22, 10, 60),
    ("OW-3002", "Quilted Liner Vest", "Outerwear", 9, 12, 50),
    ("TR-4001", "Relaxed Chino Trousers", "Trousers", 140, 40, 200),
    ("TR-4002", "Pleated Wool Trousers", "Trousers", 17, 15, 70),
    ("AC-5001", "Leather Belt", "Accessories", 33, 20, 100),
    ("AC-5002", "Wool Beanie", "Accessories", 4, 30, 150),
    ("AC-5003", "Canvas Tote Bag", "Accessories", 51, 25, 120),
    ("HM-6001", "Linen Duvet Cover", "Home", 6, 8, 40),
    ("HM-6002", "Stoneware Mug Set", "Home", 75, 20, 120),
    ("HM-6003", "Wool Throw Blanket", "Home", 11, 10, 45),
]
inv_df = pd.DataFrame(inv, columns=["sku", "product_name", "category", "current_stock", "minimum_stock", "max_stock"])
inv_df["max_stock"] = inv_df["max_stock"].astype("Int64")
inv_df["warehouse"] = ["Miami-1", "Miami-1", "Miami-1", "Atlanta-2", "Atlanta-2", "Miami-1", "Atlanta-2",
                       "Miami-1", "Atlanta-2", "Miami-1", "Atlanta-2", "Miami-1", "Atlanta-2", "Miami-1", "Atlanta-2"]
inv_df["last_counted"] = "2026-10-07"
save(inv_df, "inventory.csv")

# --------------------------------------------------------------------------- vendor prices
vendor = [
    ("ts1001", "Northshore Textiles", 61.95),      # +5.0%
    ("TS-1002", "Northshore Textiles", 70.40),     # +10.0% exactly -> NOT flagged ("exceeds")
    ("ts-1003", "Northshore Textiles", 98.50),     # +10.67% -> flagged
    ("KN2001", "Highland Knits", 101.15),          # -15.0% -> flagged
    ("KN-2002", "Highland Knits", 141.00),         # +1.4%
    ("ow 3001", "Fieldcraft Supply", 311.25),      # +25.0% -> flagged
    ("OW-3002", "Fieldcraft Supply", 125.00),      # -3.1%
    ("TR-4001", "Fieldcraft Supply", 79.00),       # 0%
    ("TR-4002", "Highland Knits", 133.00),         # -10.74% -> flagged
    ("AC-5001", "Brass & Hide Co.", 52.00),        # +6.1%
    ("AC-5002", "Highland Knits", 31.50),          # -10.0% exactly -> NOT flagged
    ("HM-6001", "Casa Linen", 204.00),             # +7.9%
    ("HM-6002", "Casa Linen", 39.00),              # -13.3% -> flagged
    ("XX-9001", "Casa Linen", 22.00),              # vendor SKU with no internal product
    # AC-5003 and HM-6003 intentionally have no vendor price
]
save(pd.DataFrame(vendor, columns=["vendor_sku", "vendor_name", "vendor_price"]).assign(currency="USD"),
     "vendor_prices.csv")

# --------------------------------------------------------------------------- messy vendor upload (WF003)
messy = pd.DataFrame(
    [
        ["NS-701", "  Garment-Dyed Tee ", "18.50", "120", "Bone", "Tops"],
        ["NS-702", "Heavyweight Hoodie", "42", "60", "Black", "Tops"],
        [None, "Ribbed Tank Top", "12.00", "80", "White", "Tops"],            # missing SKU
        ["NS-704", "", "25.00", "40", "Navy", "Tops"],                         # missing name
        ["NS-705", "   ", "31.00", "35", "Grey", "Tops"],                      # whitespace-only name
        [None, None, None, None, None, None],                                  # blank row
        ["NS-706", "Fleece Joggers", "N/A", "50", "Heather", "Bottoms"],      # non-numeric price (warning)
        ["NS-707", "Utility Cargo Pants", "48.00", "", "Khaki", "Bottoms"],   # missing qty (warning)
        ["NS-702", "Heavyweight Hoodie", "42", "60", "Black", "Tops"],        # duplicate SKU (warning)
        [" ns-708 ", "Corduroy Cap", "22.00", "90", "Rust", "Accessories"],   # SKU needs trimming/uppercasing
        ["NS-709", "Waffle Knit Henley", "$29.99", "70", "Oat", "Tops"],      # price with currency symbol
        [None, "", "15.00", "10", "Red", "Tops"],                              # missing both
    ],
    columns=["Item Code", " Product Title", "Unit Cost ($)", "Qty Available", "Colour", "Dept."],
)
with pd.ExcelWriter(DATA / "vendor_upload_sample.xlsx") as xw:
    messy.to_excel(xw, index=False, sheet_name="Vendor Feed")
messy.to_csv(DATA / "vendor_upload_sample.csv", index=False)
print(f"  wrote data/vendor_upload_sample.xlsx/.csv {len(messy):>4} rows")

# --------------------------------------------------------------------------- orders + shipments (WF005)
orders = [
    ("ORD-1001", "maya.patel@example.com", "Maya Patel", "2026-10-01", "Shipped", "Classic Linen Shirt x1; Leather Belt x1", 108.00),
    ("ORD-1002", "liam.chen@example.com", "Liam Chen", "2026-09-24", "Delivered", "Waxed Field Jacket x1", 249.00),
    ("ORD-1003", "sofia.reyes@example.com", "Sofia Reyes", "2026-10-06", "Processing", "Merino Crew Sweater x2", 238.00),
    ("ORD-1004", "noah.kim@example.com", "Noah Kim", "2026-09-28", "Cancelled", "Wool Beanie x3", 105.00),
    ("ORD-1005", "maya.patel@example.com", "Maya Patel", "2026-10-05", "Packed", "Stoneware Mug Set x1", 45.00),
    ("ORD-1006", "ava.johnson@example.com", "Ava Johnson", "2026-10-03", "Shipped", "Linen Duvet Cover x1; Wool Throw Blanket x1", 318.00),
]
save(pd.DataFrame(orders, columns=["order_id", "customer_email", "customer_name", "order_date", "order_status",
                                   "items", "order_total"]), "orders.csv")
ships = [
    ("ORD-1001", "UPS", "1Z999AA10123456784", "In transit", "Jacksonville, FL", "2026-10-09", "2026-10-07 08:42"),
    ("ORD-1002", "FedEx", "784512369874", "Delivered", "Orlando, FL", "2026-09-27", "2026-09-27 14:10"),
    ("ORD-1005", "USPS", None, "Label created", "Miami, FL", "2026-10-10", "2026-10-06 17:05"),
    ("ORD-1006", "UPS", "1Z999AA10198765432", "Out for delivery", "Tampa, FL", "2026-10-07", "2026-10-07 07:15"),
]
save(pd.DataFrame(ships, columns=["order_id", "carrier", "tracking_number", "shipment_status", "last_location",
                                  "estimated_delivery", "last_update"]), "shipments.csv")

# --------------------------------------------------------------------------- catalog with duplicates (WF006)
catalog = [
    ("TS-1001", "Classic Linen Shirt", "Halden", "Shirts", "White", "M", 59.00, "Main store"),
    ("ts-1001 ", "Classic Linen Shirt - White", "Halden", "Shirts", "White", "M", 59.00, "Marketplace import"),   # exact SKU (after trim/case)
    ("TS-1002", "Oxford Button-Down Shirt", "Halden", "Shirts", "Light Blue", "L", 64.00, "Main store"),
    ("MK-88213", "Oxford Button Down Shirt Light Blue", "Halden", "Shirts", "Light Blue", "L", 64.00, "Marketplace import"),  # possible
    ("TS-1003", "Linen Overshirt", "Halden", "Shirts", "Sage Green", "M", 89.00, "Main store"),
    ("KN-2001", "Merino Crew Sweater", "Halden", "Knitwear", "Charcoal", "M", 119.00, "Main store"),
    ("KN-2001-L", "Merino Crew Sweater", "Halden", "Knitwear", "Charcoal", "L", 119.00, "Main store"),  # size variant: NOT high
    ("KN-2001", "Merino Crewneck Sweater Charcoal", "Halden", "Knitwear", "Charcoal", "M", 115.00, "Wholesale feed"),  # exact SKU
    ("KN-2002", "Cable Knit Cardigan", "Halden", "Knitwear", "Oat", "S", 139.00, "Main store"),
    ("OW-3001", "Waxed Field Jacket", "Halden", "Outerwear", "Olive", "L", 249.00, "Main store"),
    ("WH-55120", "Field Jacket, Waxed - Olive", "Halden", "Outerwear", "Olive", "L", 239.00, "Wholesale feed"),  # possible
    ("OW-3002", "Quilted Liner Vest", "Halden", "Outerwear", "Black", "M", 129.00, "Main store"),
    ("TR-4001", "Relaxed Chino Trousers", "Halden", "Trousers", "Stone", "32", 79.00, "Main store"),
    ("TR-4001B", "Relaxed Chino Trousers", "Halden", "Trousers", "Navy", "32", 79.00, "Main store"),  # color variant: NOT high
    ("AC-5001", "Leather Belt", "Halden", "Accessories", "Brown", "90", 49.00, "Main store"),
    ("AC-5002", "Wool Beanie", "Halden", "Accessories", "Rust", "One Size", 35.00, "Main store"),
    ("MK-90021", "Lambswool Beanie Rust", "Halden", "Accessories", "Rust", "One Size", 35.00, "Marketplace import"),  # possible
    ("HM-6001", "Linen Duvet Cover", "Halden Home", "Home", "Clay", "Queen", 189.00, "Main store"),
    ("HM-6002", "Stoneware Mug Set", "Halden Home", "Home", "Speckled White", "Set of 4", 45.00, "Main store"),
    ("HM-6003", "Wool Throw Blanket", "Halden Home", "Home", "Forest", "130x180", 129.00, "Main store"),
    ("AC-5003", "Canvas Tote Bag", "Halden", "Accessories", "Natural", "One Size", 39.00, "Main store"),
]
save(pd.DataFrame(catalog, columns=["sku", "product_name", "brand", "category", "color", "size", "price", "source"]),
     "catalog.csv")

# --------------------------------------------------------------------------- keywords + site taxonomy (WF008)
kw = [
    ("linen shirt", 14800, 42), ("Linen Shirt ", 14800, 42), ("linen  shirt", 14800, 42),
    ("buy linen shirt online", 2400, 35), ("how to wash linen shirts", 6600, 18), ("best linen shirts 2026", 3900, 51),
    ("linen vs cotton shirt", 2900, 22), ("halden login", 880, 5), ("halden store miami", 590, 8),
    ("merino wool sweater", 9900, 47), ("merino sweater sale", 1900, 38), ("is merino wool itchy", 4400, 12),
    ("waxed jacket", 8100, 45), ("how to rewax a waxed jacket", 2400, 15), ("best waxed jacket for rain", 1300, 33),
    ("waxed field jacket olive", 720, 24), ("wool throw blanket", 5400, 40), ("order wool throw blanket", 320, 21),
    ("chino trousers men", 6600, 44), ("chinos vs trousers", 1600, 19), ("halden returns policy", 480, 6),
    ("leather belt brown", 4400, 39), ("cheap leather belt", 2900, 41), ("stoneware mug set", 3600, 30),
    ("stoneware vs ceramic mugs", 1900, 17), ("linen duvet cover queen", 2400, 36), ("halden discount code", 1300, 9),
]
save(pd.DataFrame(kw, columns=["keyword", "search_volume", "difficulty"]), "keywords.csv")
cats = [
    ("Shirts", "/collections/shirts", "shirt;linen shirt;oxford;button-down;overshirt"),
    ("Knitwear", "/collections/knitwear", "sweater;merino;cardigan;knit;jumper"),
    ("Outerwear", "/collections/outerwear", "jacket;waxed;vest;coat;outerwear"),
    ("Trousers", "/collections/trousers", "trousers;chino;chinos;pants"),
    ("Accessories", "/collections/accessories", "belt;beanie;tote;bag;accessory"),
    ("Home", "/collections/home", "duvet;mug;blanket;throw;stoneware;bedding"),
    ("Account", "/account/login", "login;sign in;account;my orders;password"),
    ("Brand & Support", "/pages/help", "returns;store;stores;discount;contact;help"),
]
save(pd.DataFrame(cats, columns=["category", "page_url", "terms"]), "categories.csv")

# --------------------------------------------------------------------------- employees (WF009)
emps = [
    ("E-101", "Arjun Mehta", "Developer", "python;fastapi;postgresql;docker", 28, 40, "available", "Senior"),
    ("E-102", "Priya Nair", "Developer", "react;typescript;css;stripe", 36, 40, "available", "Mid"),      # right skills, nearly full
    ("E-103", "Daniel Ortiz", "Developer", "react;typescript;node.js;stripe;graphql", 18, 40, "available", "Senior"),
    ("E-104", "Hannah Weiss", "Developer", "react;typescript;stripe;css", 10, 40, "on_leave", "Senior"),  # best skills, on leave
    ("E-105", "Kenji Sato", "Developer", "python;machine learning;langgraph;aws", 22, 40, "available", "Senior"),
    ("E-106", "Fatima Zahra", "Developer", "node.js;postgresql;redis;aws", 39, 40, "available", "Mid"),
    ("E-107", "Lucas Brown", "Designer", "figma;ui design;css", 15, 40, "available", "Mid"),
    ("E-108", "Chloe Martin", "Marketer", "seo;content;email marketing", 20, 32, "available", "Mid"),
    ("E-109", "Omar Haddad", "Developer", "shopify;liquid;javascript;css", 30, 40, "available", "Junior"),
    ("E-110", "Grace Liu", "Data Analyst", "sql;python;tableau", 25, 40, "available", "Mid"),
]
save(pd.DataFrame(emps, columns=["employee_id", "name", "role", "skills", "current_workload_hours",
                                 "weekly_capacity_hours", "status", "seniority"]), "employees.csv")

# --------------------------------------------------------------------------- execution logs (WF010)
# step names mirror the Excel step text, so seeded history and live runs aggregate together.
xl = pd.read_excel(ROOT / "workflows" / "AI_Agent_Workflow_Assessment_1.xlsx", sheet_name="Workflows")
profiles = {  # workflow -> (runs, failure prob, base ms per step, slow step index, slow factor, error pool)
    "WF001": (46, 0.02, 120, 1, 1.5, ["Inventory file not found"]),
    "WF002": (31, 0.06, 140, 1, 2.0, ["SKU column missing in vendor price list"]),
    "WF003": (28, 0.14, 260, 0, 9.0, ["Unsupported file encoding", "Header row not detected", "Unsupported file encoding"]),
    "WF004": (39, 0.05, 900, 1, 3.0, ["LLM timeout after 30s"]),
    "WF005": (52, 0.19, 180, 1, 6.0, ["Order API timeout (504)", "Order API timeout (504)", "Shipment API rate limited (429)"]),
    "WF006": (17, 0.00, 300, 4, 4.0, []),
    "WF007": (22, 0.09, 2100, 3, 2.2, ["LLM returned invalid JSON"]),
    "WF008": (19, 0.05, 700, 2, 4.5, ["LLM returned an unknown intent label"]),
    "WF009": (24, 0.04, 150, 3, 1.4, ["Employee directory unavailable"]),
    "WF010": (12, 0.00, 110, 0, 1.2, []),
}
rows = []
end = datetime(2026, 10, 6, 23, 0)
for _, r in xl.iterrows():
    wid, wname = r["Workflow_ID"], r["Workflow_Name"]
    steps = [s.strip()[0].upper() + s.strip()[1:] for s in str(r["Steps"]).split("→")]
    n, pfail, base, slow_idx, slow_f, errors = profiles[wid]
    for i in range(n):
        run_id = f"seed-{wid.lower()}-{i:03d}"
        ts = end - timedelta(minutes=rng.randint(0, 30 * 24 * 60))
        failed = rng.random() < pfail
        fail_at = rng.randrange(len(steps)) if failed else None
        if failed and wid in ("WF005",):
            fail_at = 1  # order lookup step
        if failed and wid == "WF003":
            fail_at = 0
        step_rows, total = [], 0
        for si, sname in enumerate(steps):
            if fail_at is not None and si > fail_at:
                break
            ms = int(base * rng.uniform(0.6, 1.4) * (slow_f if si == slow_idx else 1.0))
            total += ms
            st = "failed" if si == fail_at else "ok"
            step_rows.append([si + 1, sname, st, ms, (rng.choice(errors) if st == "failed" else "")])
        for sr in step_rows:
            rows.append([run_id, ts.strftime("%Y-%m-%d %H:%M:%S"), wid, wname, "failed" if failed else "success",
                         total, f"s{sr[0]}", sr[1], sr[2], sr[3], sr[4], "seed"])
logs = pd.DataFrame(rows, columns=["run_id", "timestamp", "workflow_id", "workflow_name", "run_status",
                                   "run_duration_ms", "step_id", "step_name", "step_status", "step_duration_ms",
                                   "error_message", "source"])
save(logs.sort_values(["timestamp", "run_id", "step_id"]), "execution_logs.csv")
print("done.")