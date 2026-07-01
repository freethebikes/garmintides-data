#!/usr/bin/env python3
"""Build per-city tidal-constituent files served via GitHub Pages for the
Ventura Tides watch face. Each file tides/<id>.json is tiny and holds the 8
principal constituents the on-device engine sums:

  {"z":<MTL-MLLW ft>,"lat":..,"lng":..,"a":[8 amp ft],"g":[8 GMT phase deg],"toff":<min>}

U.S. cities use NOAA harmonic constituents (chart-datum MLLW, precise in
harbors). The rest use the EOT20 global ocean-tide model (CC BY 4.0; heights
relative to mean sea level, z=0). Constituent order is fixed: M2 S2 N2 K2 K1 O1
P1 Q1.

Run:  python3 build_constituents.py /path/to/EOT20_ocean.nc
Outputs tides/*.json and prints the watch settings.xml dropdown entries.
"""
import sys, os, json, math, urllib.request
import numpy as np
import netCDF4

ORDER = ["M2","S2","N2","K2","K1","O1","P1","Q1"]
MD = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations"
OUT = os.path.join(os.path.dirname(__file__), "tides")

# U.S. NOAA stations: (label, id, lat, lng)
US = [
    ("San Diego, CA","9410170",32.7156,-117.1767),("La Jolla, CA","9410230",32.8669,-117.2571),
    ("Los Angeles, CA","9410660",33.72,-118.272),("Santa Barbara, CA","9411340",34.4046,-119.6925),
    ("Ventura, CA","9411189",34.2667,-119.283),("Monterey, CA","9413450",36.6089,-121.8914),
    ("San Francisco, CA","9414290",37.8063,-122.4659),("Seattle, WA","9447130",47.6026,-122.3393),
    ("Honolulu, HI","1612340",21.3033,-157.8645),("Hilo, HI","1617760",19.7303,-155.0556),
    ("Galveston, TX","8771510",29.2853,-94.7894),("Grand Isle, LA","8761724",29.2633,-89.9567),
    ("Tampa, FL","8726607",27.8578,-82.5528),("Key West, FL","8724580",24.5557,-81.8079),
    ("Miami, FL","8723214",25.7314,-80.1618),("Charleston, SC","8665530",32.7808,-79.9236),
    ("Norfolk, VA","8638610",36.9428,-76.3286),("Atlantic City, NJ","8534720",39.3567,-74.4181),
    ("New York, NY","8518750",40.7006,-74.0142),("Boston, MA","8443970",42.3539,-71.0503),
]
# World cities via EOT20: (label, lat, lng). IDs assigned 9900001+.
WORLD = [
    ("Tofino, Canada",49.153,-125.907),("Vancouver, Canada",49.29,-123.13),("Halifax, Canada",44.65,-63.57),
    ("Cabo San Lucas, MX",22.877,-109.912),("Puerto Escondido, MX",15.855,-97.072),("Sayulita, MX",20.87,-105.44),
    ("Cancun, MX",21.16,-86.85),("Mazatlan, MX",23.25,-106.41),("Ensenada, MX",31.86,-116.63),
    ("Tamarindo, CR",10.30,-85.84),("Bocas del Toro, PA",9.34,-82.24),("Nassau, Bahamas",25.08,-77.34),
    ("Rio de Janeiro, BR",-22.989,-43.189),("Florianopolis, BR",-27.596,-48.423),("Salvador, BR",-12.97,-38.51),
    ("Recife, BR",-8.06,-34.87),("Lima (Callao), PE",-12.066,-77.173),("Mancora, PE",-4.10,-81.05),
    ("Valparaiso, CL",-33.032,-71.631),("Punta del Este, UY",-34.96,-54.95),("Mar del Plata, AR",-38.00,-57.55),
    ("Lisbon, PT",38.689,-9.421),("Porto, PT",41.15,-8.68),("Ericeira, PT",38.96,-9.42),("Nazare, PT",39.60,-9.07),
    ("Biarritz, FR",43.482,-1.574),("Hossegor, FR",43.66,-1.44),("Brest, FR",48.39,-4.49),
    ("San Sebastian, ES",43.32,-1.98),("A Coruna, ES",43.37,-8.40),("Las Palmas, ES",28.138,-15.430),
    ("Tenerife, ES",28.41,-16.55),("Newquay, UK",50.417,-5.103),("Brighton, UK",50.82,-0.14),
    ("Thurso, UK",58.59,-3.52),("Bundoran, IE",54.48,-8.28),("Lahinch, IE",52.93,-9.35),("Dublin, IE",53.35,-6.24),
    ("Scheveningen, NL",52.10,4.27),("Sylt, DE",54.90,8.31),("Bergen, NO",60.39,5.32),
    ("Taghazout, MA",30.543,-9.710),("Casablanca, MA",33.59,-7.62),("Dakar, SN",14.69,-17.45),
    ("Cape Town, ZA",-33.911,18.401),("Jeffreys Bay, ZA",-34.049,24.931),("Durban, ZA",-29.871,31.048),
    ("Swakopmund, NA",-22.68,14.53),("Lagos, NG",6.42,3.42),("Mombasa, KE",-4.04,39.67),
    ("Zanzibar, TZ",-6.16,39.19),("Mauritius",-20.16,57.50),
    ("Dubai, AE",25.23,55.27),("Muscat, OM",23.61,58.59),
    ("Mumbai, IN",18.94,72.82),("Goa, IN",15.55,73.75),("Chennai, IN",13.05,80.28),("Colombo, LK",6.93,79.84),
    ("Male, MV",4.18,73.51),("Phuket, TH",7.89,98.30),("Da Nang, VN",16.07,108.22),("Singapore",1.26,103.82),
    ("Bali (Kuta), ID",-8.723,115.168),("Uluwatu, ID",-8.83,115.09),("Lombok, ID",-8.89,116.28),
    ("Siargao, PH",9.85,126.16),
    ("Tokyo, JP",35.31,140.30),("Osaka, JP",34.65,135.43),("Okinawa, JP",26.34,127.80),
    ("Busan, KR",35.10,129.04),("Jeju, KR",33.24,126.56),("Hong Kong",22.21,114.26),("Taipei, TW",24.87,121.84),
    ("Gold Coast, AU",-28.002,153.434),("Byron Bay, AU",-28.64,153.61),("Sydney, AU",-33.951,151.272),
    ("Newcastle, AU",-32.93,151.78),("Torquay (Bells), AU",-38.36,144.29),("Noosa, AU",-26.38,153.09),
    ("Margaret River, AU",-33.955,114.991),("Perth (Trigg), AU",-31.87,115.75),("Adelaide, AU",-35.0,138.48),
    ("Cairns, AU",-16.92,145.78),("Darwin, AU",-12.46,130.84),
    ("Raglan, NZ",-37.799,174.821),("Gisborne, NZ",-38.67,178.02),("Piha, NZ",-36.95,174.47),("Dunedin, NZ",-45.88,170.50),
    ("Fiji (Cloudbreak)",-17.85,177.19),("Teahupoo, Tahiti",-17.85,-149.27),("Samoa",-13.83,-171.74),
    ("Santander, ES",43.461,-3.804),
    ("Lacanau, FR",44.998,-1.198),
]

def fetch(url):
    with urllib.request.urlopen(url) as r:
        return json.load(r)

def write(sid, obj):
    with open(os.path.join(OUT, sid + ".json"), "w") as f:
        json.dump(obj, f, separators=(",", ":"))

def us_station(sid, lat, lng):
    hc = fetch(f"{MD}/{sid}/harcon.json?units=english").get("HarmonicConstituents", [])
    if hc:
        amp = {c["name"]: c["amplitude"] for c in hc}
        pha = {c["name"]: c["phase_GMT"] for c in hc}
        z = 0.0
        try:
            d = fetch(f"{MD}/{sid}/datums.json?units=english")
            v = {x["name"]: x["value"] for x in d.get("datums", [])}
            if "MTL" in v and "MLLW" in v: z = round(v["MTL"] - v["MLLW"], 3)
        except Exception: pass
        return {"z": z, "lat": lat, "lng": lng, "toff": 0,
                "a": [round(amp.get(n, 0.0), 3) for n in ORDER],
                "g": [round(pha.get(n, 0.0), 1) for n in ORDER]}
    off = fetch(f"{MD}/{sid}/tidepredoffsets.json")
    ref = off["refStationId"]
    toff = round((off.get("timeOffsetHighTide", 0) + off.get("timeOffsetLowTide", 0)) / 2.0)
    base = us_station(ref, lat, lng)
    base["toff"] = toff; base["lat"] = lat; base["lng"] = lng
    return base

def main(ncpath):
    os.makedirs(OUT, exist_ok=True)
    ds = netCDF4.Dataset(ncpath)
    names = ds.variables["constituents"].constituent_order.upper().split()
    lon = ds.variables["lon"][:]; lat = ds.variables["lat"][:]
    hRe = ds.variables["hRe"]; hIm = ds.variables["hIm"]
    cidx = {n: names.index(n) for n in ORDER}
    m2 = cidx["M2"]

    def nearest_ocean(la, lo):
        if lo < 0 and lon.max() > 180: lo += 360
        j = int(np.argmin(np.abs(lon - lo))); i = int(np.argmin(np.abs(lat - la)))
        for r in range(0, 12):
            for di in range(-r, r + 1):
                for dj in range(-r, r + 1):
                    ii, jj = i + di, j + dj
                    if 0 <= ii < len(lat) and 0 <= jj < len(lon):
                        re = hRe[m2, ii, jj]; im = hIm[m2, ii, jj]
                        if np.ma.is_masked(re) or np.ma.is_masked(im): continue
                        if abs(float(re)) + abs(float(im)) > 1e-6: return ii, jj
        return None

    catalog = []  # (id, label)
    for label, sid, la, lng in US:
        write(sid, us_station(sid, la, lng)); catalog.append((sid, label))
        print(f"US   {label:22s} {sid}")
    wid = 9900001
    for label, la, lo in WORLD:
        cell = nearest_ocean(la, lo)
        if cell is None:
            print(f"SKIP {label} (no ocean cell / out of EOT20 coverage)"); continue
        i, j = cell
        a = []; g = []
        for n in ORDER:
            re = float(hRe[cidx[n], i, j]); im = float(hIm[cidx[n], i, j])
            a.append(round(math.hypot(re, im) * 3.280839895, 3))
            g.append(round(math.degrees(math.atan2(im, re)) % 360.0, 1))
        sid = str(wid); wid += 1
        write(sid, {"z": 0.0, "lat": la, "lng": lo, "toff": 0, "a": a, "g": g})
        catalog.append((sid, label))
        print(f"W    {label:22s} {sid}  M2={a[0]}ft")

    json.dump([{"id": c[0], "name": c[1]} for c in catalog],
              open(os.path.join(OUT, "index.json"), "w"), separators=(",", ":"))
    print(f"\n{len(catalog)} cities -> {OUT}")
    print("\n--- settings.xml dropdown (paste into app) ---")
    for sid, label in catalog:
        print(f'            <listEntry value="{sid}">{label}</listEntry>')

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/eot20/EOT20_ocean.nc")
