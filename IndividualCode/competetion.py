import osmnx as ox
import warnings
warnings.filterwarnings("ignore")

BUSINESS_TAGS = {
    "restaurant"  : {"amenity": ["restaurant", "cafe", "fast_food", "food_court"]},
    "hardware"    : {"shop"   : ["hardware", "doityourself", "tools"]},
    "clothing"    : {"shop"   : ["clothes", "boutique", "fashion", "tailor"]},
    "supermarket" : {"shop"   : ["supermarket", "convenience", "grocery", "general"]},
    "pharmacy"    : {"amenity": ["pharmacy"], "shop": ["chemist", "medical"]},
    "hotel"       : {"tourism": ["hotel", "guest_house", "hostel", "motel"]},
    "bank"        : {"amenity": ["bank", "atm"]},
    "gym"         : {"leisure": ["fitness_centre", "sports_centre"], "amenity": ["gym"]},
    "school"      : {"amenity": ["school", "college", "university", "kindergarten"]},
    "hospital"    : {"amenity": ["hospital", "clinic", "doctors", "dentist"]},
    "petrol"      : {"amenity": ["fuel"]},
    "salon"       : {"shop"   : ["hairdresser", "beauty", "cosmetics"]},
    "electronics" : {"shop"   : ["electronics", "mobile_phone", "computer"]},
    "bakery"      : {"shop"   : ["bakery", "confectionery", "pastry"]},
    "jewellery"   : {"shop"   : ["jewellery", "jewelry", "goldsmith"]},
}


def safe_str(val):
    if val is None:
        return None
    if isinstance(val, list):
        return val[0] if val else None
    s = str(val)
    return None if s in ("nan", "None", "") else s


def fetch_pois_by_key(lat, lon, key, values, dist):
    """Fetch POIs for a single OSM key with multiple values."""
    all_pois = []
    for value in values:
        try:
            pois = ox.features_from_point((lat, lon), tags={key: value}, dist=dist)
            if not pois.empty:
                all_pois.append(pois)
        except Exception:
            pass  # Skip invalid tag values silently
    return all_pois


def get_competitors(lat, lon, business_type, dist=2000):
    tags = BUSINESS_TAGS.get(business_type.lower())
    if not tags:
        print(f"\n❌ Unknown business type: '{business_type}'")
        print(f"   Available types: {', '.join(BUSINESS_TAGS.keys())}")
        return None

    print(f"\nSearching for '{business_type}' competitors within {dist}m of ({lat}, {lon})...")

    import pandas as pd

    # ── Query each key→value pair separately and combine ──
    all_dfs = []
    for key, values in tags.items():
        if isinstance(values, list):
            dfs = fetch_pois_by_key(lat, lon, key, values, dist)
            all_dfs.extend(dfs)
        else:
            try:
                pois = ox.features_from_point((lat, lon), tags={key: values}, dist=dist)
                if not pois.empty:
                    all_dfs.append(pois)
            except Exception:
                pass

    if not all_dfs:
        print("No competitors found in this area.")
        return {"count": 0, "competitors": []}

    # Combine and deduplicate by OSM id
    try:
        pois = pd.concat(all_dfs)
        pois = pois[~pois.index.duplicated(keep='first')]
    except Exception as e:
        print(f"Error combining results: {e}")
        return {"count": 0, "competitors": []}

    # ── Extract all useful columns safely ──
    competitors = []
    for _, row in pois.iterrows():
        name    = safe_str(row.get("name"))
        amenity = safe_str(row.get("amenity"))
        shop    = safe_str(row.get("shop"))
        tourism = safe_str(row.get("tourism"))
        leisure = safe_str(row.get("leisure"))
        phone   = safe_str(row.get("phone")) or safe_str(row.get("contact:phone"))
        website = safe_str(row.get("website")) or safe_str(row.get("contact:website"))
        hours   = safe_str(row.get("opening_hours"))
        brand   = safe_str(row.get("brand"))
        cuisine = safe_str(row.get("cuisine"))
        addr_h  = safe_str(row.get("addr:housenumber"))
        addr_s  = safe_str(row.get("addr:street"))
        addr_c  = safe_str(row.get("addr:city"))
        rating  = safe_str(row.get("stars")) or safe_str(row.get("rating"))

        addr_parts = [p for p in [addr_h, addr_s, addr_c] if p]
        address = ", ".join(addr_parts) if addr_parts else None
        category = amenity or shop or tourism or leisure or "unknown"

        competitors.append({
            "name"    : name     or "Unnamed",
            "category": category,
            "brand"   : brand,
            "cuisine" : cuisine,
            "address" : address,
            "phone"   : phone,
            "website" : website,
            "hours"   : hours,
            "rating"  : rating,
        })

    competitors.sort(key=lambda x: (x["name"] == "Unnamed", x["name"]))

    category_count = {}
    for c in competitors:
        cat = c["category"]
        category_count[cat] = category_count.get(cat, 0) + 1

    named   = [c for c in competitors if c["name"] != "Unnamed"]
    unnamed = [c for c in competitors if c["name"] == "Unnamed"]

    print(f"\n{'='*60}")
    print(f"  COMPETITOR ANALYSIS REPORT")
    print(f"  Business Type : {business_type}")
    print(f"  Location      : ({lat}, {lon})")
    print(f"  Radius        : {dist} m")
    print(f"{'='*60}")

    print(f"\n--- Summary ---")
    print(f"  Total found    : {len(competitors)}")
    print(f"  Named          : {len(named)}")
    print(f"  Unnamed        : {len(unnamed)}  (POIs with no name tag on OSM)")

    print(f"\n--- By Category ---")
    for cat, count in sorted(category_count.items(), key=lambda x: -x[1]):
        print(f"  {cat:<25} : {count}")

    if named:
        print(f"\n--- Named Competitors ({len(named)}) ---")
        print(f"  {'#':<4} {'Name':<30} {'Category':<18} {'Extra Info'}")
        print(f"  {'─'*4} {'─'*30} {'─'*18} {'─'*20}")
        for i, c in enumerate(named, 1):
            extra_parts = []
            if c["cuisine"]: extra_parts.append(f"cuisine: {c['cuisine']}")
            if c["brand"]  : extra_parts.append(f"brand: {c['brand']}")
            if c["hours"]  : extra_parts.append(f"hours: {c['hours']}")
            extra = " | ".join(extra_parts) if extra_parts else ""
            print(f"  {i:<4} {c['name']:<30} {c['category']:<18} {extra}")

    print(f"\n--- Detailed Info (named, with contact/address) ---")
    has_detail = [c for c in named if any([c["address"], c["phone"], c["website"], c["hours"]])]
    if has_detail:
        for c in has_detail:
            print(f"\n  {c['name']}  [{c['category']}]")
            if c["address"] : print(f"    Address  : {c['address']}")
            if c["phone"]   : print(f"    Phone    : {c['phone']}")
            if c["website"] : print(f"    Website  : {c['website']}")
            if c["hours"]   : print(f"    Hours    : {c['hours']}")
            if c["cuisine"] : print(f"    Cuisine  : {c['cuisine']}")
            if c["brand"]   : print(f"    Brand    : {c['brand']}")
    else:
        print(f"  (No contact/address data available for this area on OSM)")

    total = len(competitors)
    level = (
        "Very High 🔴 — extremely saturated market" if total > 50 else
        "High 🟠      — strong competition"          if total > 20 else
        "Moderate 🟡  — some competition"            if total > 10 else
        "Low 🟢       — good opportunity"            if total > 3  else
        "Very Low ✅  — almost no competition"
    )
    print(f"\n--- Competition Level ---")
    print(f"  {level}")
    print(f"\n{'='*60}\n")

    return {
        "total_count"      : len(competitors),
        "named_count"      : len(named),
        "unnamed_count"    : len(unnamed),
        "competition_level": level,
        "category_breakdown": category_count,
        "competitors"      : competitors,
        "named_list"       : [c["name"] for c in named],
    }


if __name__ == "__main__":
    print(f"\nAvailable business types:")
    for i, btype in enumerate(BUSINESS_TAGS.keys(), 1):
        print(f"  {i}. {btype}")

    lat   = float(input("\nEnter latitude  : "))
    lon   = float(input("Enter longitude : "))
    btype = input("Enter business type : ").strip().lower()
    dist  = input("Enter radius in meters (default 2000): ").strip()
    dist  = int(dist) if dist else 2000

    result = get_competitors(lat, lon, btype, dist)