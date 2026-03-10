import os
import json
import math
import argparse
import pandas as pd
import requests

MAPBOX_TOKEN = os.environ.get("MAPBOX_TOKEN", "pk.eyJ1Ijoic2xhdnV0aWNoIiwiYSI6ImNtaTUwNG1oZDFheG4ybHF3OGh4NGU1b2EifQ.b18lhmFrzTMD1Ds38NThrw")

def project(lat, lon, angle_deg, dist_m):
    R  = 6378137.0
    br = math.radians(angle_deg)
    φ1 = math.radians(lat)
    λ1 = math.radians(lon)
    d  = dist_m / R
    φ2 = math.asin(math.sin(φ1)*math.cos(d) + math.cos(φ1)*math.sin(d)*math.cos(br))
    λ2 = λ1 + math.atan2(math.sin(br)*math.sin(d)*math.cos(φ1), math.cos(d)-math.sin(φ1)*math.sin(φ2))
    return math.degrees(φ2), math.degrees(λ2)

def bearing_deg(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0

def match_mapbox(lat1, lon1, lat2, lon2, token):
    coords = f"{lon1},{lat1};{lon2},{lat2}"
    url = f"https://api.mapbox.com/matching/v5/mapbox/driving/{coords}"
    r = requests.get(url, params={
        "access_token": token,
        "overview":     "false",
        "tidy":         "false",
    }, timeout=8)
    data = r.json()

    if data.get("code") != "Ok":
        raise RuntimeError(f"Mapbox error: {data.get('message', data.get('code'))}")

    tracepoints = data.get("tracepoints", [])
    # second tracepoint = projected point on road
    if len(tracepoints) < 2 or tracepoints[1] is None:
        return None

    loc = tracepoints[1]["location"]  # [lon, lat]
    return loc[1], loc[0]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv_file", required=True)
    parser.add_argument("--angle",    type=float, required=True)
    parser.add_argument("--token",    default=MAPBOX_TOKEN)
    parser.add_argument("--dist",     type=int,   default=30)
    args = parser.parse_args()

    try:
        df = pd.read_csv(args.csv_file)
        if df.empty:
            raise ValueError("CSV is empty")

        lat = float(df['lat'].iloc[-1])
        lon = float(df['lon'].iloc[-1])

        proj_lat, proj_lon = project(lat, lon, args.angle, args.dist)
        result = match_mapbox(lat, lon, proj_lat, proj_lon, args.token)

        if result:
            angle_on_road = bearing_deg(lat, lon, result[0], result[1])
            print(json.dumps({
                "status": "success",
                "lat":    round(result[0], 7),
                "lon":    round(result[1], 7),
                "angle":  round(angle_on_road, 2)
            }))
        else:
            print(json.dumps({"status": "not_found"}))

    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    main()