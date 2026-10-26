"""
data_prep.py -- Power Risk Index for Data Center Construction Planning
=======================================================================
Converts each pillar's notebook-computed outputs into the compact
parquet/JSON snapshot the Streamlit app actually loads. The notebooks
compute everything; this script and the app never recompute anything,
only reshape/export. Re-run this after any pillar's notebook produces
new validated outputs, then push the updated data/ files.

Inputs (place alongside this script, same names the source notebooks
export):
  Cost pillar:
    Industrial_Price_Panel_Long_2009_2024.xlsx
    county_price_forecast_3yr_theta.csv
  Reliability pillar (from the MOCCI_Reliability_Export handoff):
    reliability_cri_panel_2013_2024.csv
    county_cri_forecast_3yr.csv
    county_cri_not_projected.csv
    cri_model_metadata.json

Outputs -> data/:
  actual.parquet, forecast.parquet, county_lookup.parquet            (Cost)
  reliability_panel.parquet, reliability_forecast.parquet,
  reliability_not_projected.parquet, reliability_county_lookup.parquet,
  reliability_metadata.json                                          (Reliability)
  counties_fips.json  (shared county boundary file -- NOT regenerated
                        here; built once from a TIGER/Line-derived source
                        that includes the 2022+ Connecticut planning
                        regions, see build_assets/ for how it was made)
"""
import json
import shutil
import pandas as pd

OUT_DIR = 'data'

# ============================================================== COST PILLAR
PANEL_LONG_PATH = 'Industrial_Price_Panel_Long_2009_2024.xlsx'
FORECAST_CSV_PATH = 'county_price_forecast_3yr_theta.csv'

panel_long = pd.read_excel(PANEL_LONG_PATH)
panel_long['FIPS'] = panel_long['FIPS'].astype(str).str.extract(r'(\d+)')[0].str.zfill(5)

forecast_df = pd.read_csv(FORECAST_CSV_PATH, dtype={'FIPS': str})
forecast_df['FIPS'] = forecast_df['FIPS'].str.zfill(5)

actual = panel_long.rename(columns={'Ind_Price_cents_kWh': 'Price_cents_kWh'})[
    ['FIPS', 'State', 'County_Name', 'Year', 'Price_cents_kWh', 'Confidence_Grade', 'Total_MWh']
].copy()

forecast = forecast_df.rename(
    columns={'Forecast_Year': 'Year', 'Forecast_Price_cents_kWh': 'Price_cents_kWh'}
)[['FIPS', 'State', 'County_Name', 'Year', 'Years_Ahead', 'Price_cents_kWh',
   'Lower_CI_cents_kWh', 'Upper_CI_cents_kWh', 'CI_Level_%',
   'Expected_MAPE_%', 'Error_Band_Source']].copy()

cost_county_lookup = (
    pd.concat([actual[['FIPS', 'State', 'County_Name']], forecast[['FIPS', 'State', 'County_Name']]])
    .drop_duplicates('FIPS').sort_values(['State', 'County_Name']).reset_index(drop=True)
)

actual.to_parquet(f'{OUT_DIR}/actual.parquet', index=False)
forecast.to_parquet(f'{OUT_DIR}/forecast.parquet', index=False)
cost_county_lookup.to_parquet(f'{OUT_DIR}/county_lookup.parquet', index=False)

print(f"[Cost] actual.parquet: {len(actual):,} rows, {actual['FIPS'].nunique():,} counties")
print(f"[Cost] forecast.parquet: {len(forecast):,} rows")
print(f"[Cost] county_lookup.parquet: {len(cost_county_lookup):,} counties")

# ======================================================= RELIABILITY PILLAR
REL_PANEL_PATH = 'reliability_cri_panel_2013_2024.csv'
REL_FORECAST_PATH = 'county_cri_forecast_3yr.csv'
REL_NOT_PROJECTED_PATH = 'county_cri_not_projected.csv'
REL_METADATA_PATH = 'cri_model_metadata.json'

rel_panel = pd.read_csv(REL_PANEL_PATH, dtype={'FIPS': str})
rel_panel['FIPS'] = rel_panel['FIPS'].str.zfill(5)

rel_forecast = pd.read_csv(REL_FORECAST_PATH, dtype={'FIPS': str})
rel_forecast['FIPS'] = rel_forecast['FIPS'].str.zfill(5)

rel_not_projected = pd.read_csv(REL_NOT_PROJECTED_PATH, dtype={'FIPS': str})
rel_not_projected['FIPS'] = rel_not_projected['FIPS'].str.zfill(5)

rel_county_lookup = (
    pd.concat([
        rel_panel[['FIPS', 'State', 'County_Name']],
        rel_forecast[['FIPS', 'State', 'County_Name']],
        rel_not_projected[['FIPS', 'State', 'County_Name']],
    ])
    .drop_duplicates('FIPS').sort_values(['State', 'County_Name']).reset_index(drop=True)
)

rel_panel.to_parquet(f'{OUT_DIR}/reliability_panel.parquet', index=False)
rel_forecast.to_parquet(f'{OUT_DIR}/reliability_forecast.parquet', index=False)
rel_not_projected.to_parquet(f'{OUT_DIR}/reliability_not_projected.parquet', index=False)
rel_county_lookup.to_parquet(f'{OUT_DIR}/reliability_county_lookup.parquet', index=False)
shutil.copy(REL_METADATA_PATH, f'{OUT_DIR}/reliability_metadata.json')

print(f"\n[Reliability] reliability_panel.parquet: {len(rel_panel):,} rows, "
      f"{rel_panel['FIPS'].nunique():,} counties")
print(f"[Reliability] reliability_forecast.parquet: {len(rel_forecast):,} rows")
print(f"[Reliability] reliability_not_projected.parquet: {len(rel_not_projected):,} rows")
print(f"[Reliability] reliability_county_lookup.parquet: {len(rel_county_lookup):,} counties")

# ============================================================ SHARED FILES
print(f"\ncounties_fips.json left as-is in {OUT_DIR}/ "
      f"(shared county boundary file; not regenerated by this script)")

with open(f'{OUT_DIR}/counties_fips.json') as f:
    n_geo = len(json.load(f)['features'])
print(f"  ({n_geo:,} boundary features)")
