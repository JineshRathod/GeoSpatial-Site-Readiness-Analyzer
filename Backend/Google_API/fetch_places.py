import requests
import folium
from folium.plugins import MarkerCluster

API_KEY = ""

lat = 23.000921
lng = 72.506410
radius = 2000  # meters

# -----------------------------
# NEW Places API endpoint
# -----------------------------
url = "https://places.googleapis.com/v1/places:searchNearby"

headers = {
    "Content-Type": "application/json",
    "X-Goog-Api-Key": API_KEY,
    "X-Goog-FieldMask": "places.displayName,places.location"
}
body = {
    "includedTypes": [
    "restaurant",
    "cafe",
    "bar",
    "bakery",
    "meal_takeaway",
    "meal_delivery",
    "food_court"
],  # change type if needed
    "maxResultCount": 200,
    "locationRestriction": {
        "circle": {
            "center": {
                "latitude": lat,
                "longitude": lng
            },
            "radius": radius
        }
    }
}

response = requests.post(url, headers=headers, json=body)
data = response.json()

# -----------------------------
# MAP
# -----------------------------
map_obj = folium.Map(
    location=[lat, lng],
    zoom_start=14,
    tiles="CartoDB positron"
)

cluster = MarkerCluster().add_to(map_obj)

# center marker
folium.Marker([lat, lng], popup="Center").add_to(map_obj)

# -----------------------------
# PLOT RESULTS
# -----------------------------
for place in data.get("places", []):
    name = place["displayName"]["text"]
    loc = place["location"]

    folium.Marker(
        [loc["latitude"], loc["longitude"]],
        popup=name
    ).add_to(cluster)

map_obj.save("fixed_map.html")

print("Done. Open fixed_map.html")