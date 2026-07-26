# garmintides-data

Tidal harmonic constituents for the [Ventura Tides](https://github.com/freethebikes/GarminTides) Garmin watch face, served via GitHub Pages.

Each `tides/<id>.json` holds the 8 principal constituents (M2 S2 N2 K2 K1 O1 P1 Q1) for on-device offline tide prediction. U.S. cities: NOAA. Mediterranean cities: least-squares fit to [ISPRA/IOC](https://www.ioc-sealevelmonitoring.org) gauge records, since the Mediterranean tide is too small for a global model to resolve. Rest: EOT20 (CC BY 4.0).
