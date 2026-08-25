---
name: add-tide-spot
description: Add a new city/surf spot to the Ventura Tides station catalog — pick the right data source (NOAA gauge, EOT20, or a tide-gauge harmonic fit), generate tides/<id>.json, rebuild index.json, verify the constants against published predictions, and propagate the dropdown to both watch-face repos. Use whenever asked to add, remove, or reposition a tide station or spot.
---

# Adding a tide spot

Each station is one `tides/<id>.json` served over GitHub Pages, holding 8 constituents
(`M2 S2 N2 K2 K1 O1 P1 Q1`, in that fixed order) that the on-device engine sums:

```
{"z":<MTL-MLLW ft>,"lat":..,"lng":..,"a":[8 amp ft],"g":[8 GMT phase deg],"toff":<min>}
```

## The invariant that must never break

**Only ever append to `WORLD`, and never renumber `GAUGE`.** WORLD ids are assigned
positionally from `9900001` in list order (`stations()` in `build_constituents.py`).
Inserting an entry mid-list, deleting one, or re-sorting the list for tidiness renumbers
every station after it — which orphans each `tides/<id>.json` and silently repoints every
watch that already has that city saved. The user sees a different city than the one they
picked.

`GAUGE` ids are **pinned explicitly** in the tuple, and the WORLD allocator skips them.
This is load-bearing: those ids were once handed out by the same running counter, so
appending a single WORLD city renumbered all three Mediterranean stations and reused
Venice's id for the new city. Do not "simplify" the pinned ids back into a counter.

After changing any list, prove no existing id moved before you build anything:

```bash
python3 - <<'EOF'
import json, importlib.util
spec = importlib.util.spec_from_file_location("b", "build_constituents.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
committed = {e["id"]: e["name"] for e in json.load(open("tides/index.json"))}
cur = {s[0]: s[1] for s in m.stations()}
moved = [(i, committed[i], cur.get(i)) for i in committed if committed[i] != cur.get(i)]
print("REPOINTED:", moved if moved else "none")
print("new ids:", [i for i in cur if i not in committed])
EOF
```

`REPOINTED: none` is the only acceptable result for an addition.

This is why `Santander, ES` and `Lacanau, FR` sit at the end of `WORLD` instead of with
the other Spanish and French entries. That is deliberate; do not "fix" it.

Display order is handled separately by `sort_catalog()`, which orders the *output*
catalog (U.S. first, then country A-Z, city A-Z) without touching IDs. If someone wants
the dropdown reordered, change the sort, never the source lists.

The `US` list is keyed by real NOAA station id, so it is safe to insert into.

## Step 1 — choose the data source

| Situation | Source | List |
|---|---|---|
| U.S. coast with a NOAA gauge | NOAA harmonic constituents | `US` |
| Open-ocean coast worldwide | EOT20 global model | `WORLD` |
| Enclosed/marginal sea (Mediterranean, Baltic, Black Sea) | Least-squares fit to gauge records | `GAUGE` |

NOAA is best where available: constituents are relative to chart datum MLLW and resolve
harbor response. EOT20 is a 1/8° altimetry model, heights relative to mean sea level
(`z=0`).

Reach for `GAUGE` when the tide is small and the basin geometry does the work — EOT20
resolves neither the Adriatic amplification toward Venice nor local harbour response, and
a few-cm error is the whole signal there. A `GAUGE` entry carries its constants inline
plus a pinned id; producing the constants is a separate least-squares job against ~1 year
of [IOC](https://www.ioc-sealevelmonitoring.org) records, not something this skill runs.

Borrowing a nearby gauge's constants is not a substitute for either. Tides change fast
across amphidromic systems: the nearest IOC gauge to Newcastle, Co. Down is Bangor at
51 km, but it sits in Belfast Lough facing the North Channel while Newcastle faces the
Irish Sea, on the far side of the Irish Sea amphidrome. Distance alone does not license a
transplant — check that the two sites share a basin and a tidal regime.

### Picking the right NOAA station

Prefer the **oceanfront** gauge over one inside an inlet, bay, or river — the watch face
is used at the beach. Ocean City, MD uses `8570280` (Ocean City Fishing Pier), not
`8570283` inside the inlet. Same reasoning as Atlantic City and the other beach entries.

Check that the station actually publishes harmonic constants:

```
https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/<id>/harcon.json?units=english
```

If `HarmonicConstituents` is empty, `us_station()` falls back to the subordinate-station
path: it resolves `tidepredoffsets.json`, borrows the reference station's constants, and
stores the mean of the high/low time offsets in `toff`. That works, but a nearby station
with its own constants is better if one exists.

## Step 2 — add the entry and build

Add one tuple to the right list in `build_constituents.py`, then build just that station.
A full regeneration is not needed and should be avoided — it re-hits NOAA 22 times and
requires the EOT20 file.

```bash
python3 build_constituents.py --only "Ocean City"   # id or label substring
python3 build_constituents.py --index-only          # rebuild tides/index.json
```

- `--only` takes a station id or a case-insensitive label substring, and errors on an
  ambiguous match rather than guessing.
- NOAA and `GAUGE` stations need no EOT20 file and no `netCDF4` install.
- `WORLD` stations need EOT20, read from `$EOT20_NC` or `~/.cache/eot20/EOT20_ocean.nc`.
  If it isn't there, run `./fetch_eot20.sh` (27 MB, a few seconds). Do not try to
  assemble it from the SEANOE original: that is the authoritative citation, but it is a
  2.3 GB zip of 17 separate per-constituent files served with no `Accept-Ranges`, so an
  interrupted download restarts from zero and in practice never finishes.
- Both modes rewrite `index.json` and print the settings dropdown block.

Every mode refuses to write `index.json` if any station in the lists has no data file on
disk, so a station that was added to a list but never built can't be advertised to the
watch face. Note this applies to `--only` too: building one station still rewrites the
whole index, so a half-finished addition elsewhere in the lists will block it.

## Step 3 — verify before committing

Constants that are wrong produce a plausible-looking tide curve, so this step is the
whole job. Do not skip it and do not substitute "the file was written".

1. **Cross-check the raw numbers.** For NOAA, compare the 8 amplitudes and phases against
   the `harcon` endpoint, and `z` against `MTL - MLLW` from `datums.json`.
2. **Reconstruct and compare.** Synthesize ~72h of tide from the new file and compare
   high/low times against NOAA's published predictions for that station (or a national
   tide table abroad).
3. **Use a control.** Run the same comparison for a station already shipped nearby, so
   you know what "good" looks like on this coast. Ocean City landed within 5 min against
   7 min for the Atlantic City control — the control is what makes 5 min meaningful.

   For an EOT20 station with no published predictions handy, compare mean spring range
   (`2*(M2+S2)`) against harbour-table MHWS−MLWS, and do the same for shipped neighbours.
   EOT20 is an open-ocean altimetry model and systematically *under*-predicts coastal
   amplification: shipped stations run at roughly 76–97% of published range (Dublin is
   the low end, being a shallow enclosed bay). A new station landing in that band is
   behaving normally; one *above* published range, or well below 76%, means the sampler
   probably picked an unrepresentative cell.

4. **Check the cell it actually sampled.** `Eot20._nearest_ocean()` walks outward for the
   first wet cell, which near a coast can be some km away and, near an amphidrome, on a
   steep gradient. Print the chosen cell, its distance, and the M2 field a few cells
   around it. At Newcastle the cell was 3.7 km out and M2 ran from 0.72 m to 1.73 m
   across a 7×7 neighbourhood — so the value is real but gradient-sensitive to about
   ±0.1 m, which is worth stating in the commit rather than implying false precision.
5. **Sanity-check M2.** The printed `M2=<x>ft` should match the region. A near-zero M2 on
   an open Atlantic coast means the EOT20 sampler grabbed a masked or inland cell.

Verify against the actual published predictions, not against the tide curve the watch
face draws — that is the same code under test.

## Step 4 — propagate the dropdown

The station list is duplicated in two watch-face repos, and nothing enforces that they
stay in sync with `index.json`:

- `../Beautiful Tides/resources/settings/settings.xml`
- `../Ventura Surf Tide/GarminTides/resources/settings/settings.xml`

In each, replace the contiguous `<listEntry .../>` block inside
`<settingConfig type="list">` with the block printed by the build. The entry count and
order must match `index.json` exactly. Confirm both:

```bash
python3 - <<'EOF'
import json, re
idx = [e["id"] for e in json.load(open("tides/index.json"))]
for p in ["../Beautiful Tides/resources/settings/settings.xml",
          "../Ventura Surf Tide/GarminTides/resources/settings/settings.xml"]:
    ids = re.findall(r'listEntry value="(\d+)"', open(p).read())
    print(f"{'OK  ' if ids == idx else 'DIFF'} {len(ids):3d} {p}")
EOF
```

Ask before editing the app repos if the user only asked about the data repo — they are
separate git repos with their own commits.

## Step 5 — commit

Commit messages in this repo explain *why*, not what: which gauge was chosen over which
alternative and on what grounds, what was verified and against what control, and any ID
or ordering consequence. Match that depth — `git log` here is the design record. State
verification results as numbers ("high/low within 5 min, control 7 min"), not as "tested".
