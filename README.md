# Power Risk Index for Data Center Construction Planning

MOCCI -- interactive Cost and Reliability pillar explorer, built on real EIA-861
data. Availability (Capacity) and the Composite Power Risk Index are shown as
honest placeholders -- no synthetic or invented numbers for either, until
those pillars have real, validated results.

One page, one URL, with a tab per pillar (Cost / Reliability / Availability /
Composite) -- no separate page URLs to navigate between.

## What's in this folder

- `app.py` -- main entry point: password gate, header, scope banner, tabs
- `cost_pillar.py`, `reliability_pillar.py` -- each real pillar's page, as
  its own module so they stay easy to work on independently
- `availability_pillar.py`, `composite_pillar.py` -- honest "not yet
  available" placeholders
- `map_utils.py` -- shared choropleth styling (state borders, "no data" gray,
  consistent hover) used by both real pillars' maps
- `data_prep.py` -- regenerates the files in `data/` from each pillar's
  notebook outputs (run this again whenever a pillar's underlying data is
  refreshed)
- `data/` -- the static data snapshot the app actually loads: parquet files
  per pillar, plus `counties_fips.json`, a county boundary file that
  (unlike the original Cost-only app) correctly includes Connecticut's
  2022+ planning regions (09110-09190), which the original boundary file
  did not -- Connecticut was invisible on the Cost map before this fix too.
- `assets/mocci_logo.png` -- the MOCCI logo (password screen + header)
- `.streamlit/secrets.toml.example` -- template for the password secret
- `requirements.txt`

## Password protection

Gated by a single shared password, checked against `st.secrets["app_password"]`.
The real password is never stored in this folder or in source control --
only `secrets.toml.example` (a template) is included.

**Local run:** copy `.streamlit/secrets.toml.example` to
`.streamlit/secrets.toml` and put a real password in it. That file is
already in `.gitignore`.

**Streamlit Community Cloud:** no `secrets.toml` file needed in the repo.
After deploying, go to the app's **Settings -> Secrets** and paste:
```
app_password = "your real password here"
```

## Deploy to Streamlit Community Cloud

1. Create a new GitHub repository and push everything in this folder to it
   (the `data/` folder and logo included).
2. Go to https://share.streamlit.io/, connect your GitHub account.
3. Select the repository, branch `main`, main file path `app.py`, deploy.
4. Set the password in the app's Secrets before sharing the link.

## Run locally

```
pip install -r requirements.txt
streamlit run app.py
```

## Updating a pillar's data later

Each pillar's notebook is the source of truth; this app never recomputes
anything, only reshapes and displays what the notebook already validated.

1. Rerun the relevant pillar's notebook, producing fresh output files.
2. Place those fresh files alongside `data_prep.py` (see the paths at the
   top of that script -- `Industrial_Price_Panel_Long_2009_2024.xlsx` and
   `county_price_forecast_3yr_theta.csv` for Cost;
   `reliability_cri_panel_2013_2024.csv`, `county_cri_forecast_3yr.csv`,
   `county_cri_not_projected.csv` and `cri_model_metadata.json` for
   Reliability).
3. Run `python3 data_prep.py` -- it regenerates every file in `data/`.
4. Commit and push the updated `data/` files. Streamlit Community Cloud
   redeploys automatically.

## Adding the Availability pillar or the Composite index later

Follow the same pattern as Cost and Reliability: once that pillar has a
validated notebook output, extend `data_prep.py` to export it, write a new
`availability_pillar.py` (or replace the composite placeholder) following
`reliability_pillar.py` as the template, and wire it into the matching tab
in `app.py` in place of the current placeholder import.
