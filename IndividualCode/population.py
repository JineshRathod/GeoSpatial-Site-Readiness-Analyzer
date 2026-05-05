import rasterio
from rasterio.windows import Window

WORLDPOP_FILE = "worldpop.tif"


def get_population(lat, lon, radius_pixels=5):
    """
    Get population for a given coordinate and radius.

    Args:
        lat: Latitude
        lon: Longitude
        radius_pixels: Radius in pixels around the point (default=5)
                       Each pixel ≈ 100m in WorldPop data
    """
    try:
        with rasterio.open(WORLDPOP_FILE) as dataset:
            row, col = dataset.index(lon, lat)
            size = radius_pixels * 2
            window = Window(col - radius_pixels, row - radius_pixels, size, size)
            data = dataset.read(1, window=window)
            return float(data.sum())
    except Exception as e:
        print(f"Error: {e}")
        return 0.0


# ---------------- RUN ----------------
if __name__ == "__main__":
    lat = float(input("Enter latitude: "))
    lon = float(input("Enter longitude: "))
    radius = int(input("Enter radius in pixels (1 pixel ≈ 100m): "))

    population = get_population(lat, lon, radius_pixels=radius)
    print(f"\nEstimated Population: {population:,.0f}")