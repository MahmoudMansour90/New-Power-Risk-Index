"""Cost pillar page: county-level industrial electricity price, 2001-2024
actual + 2025-2027 theta forecast. Real data only -- see data_prep.py for
how data/actual.parquet, data/forecast.parquet and data/county_lookup.parquet
are produced from the notebook's outputs.
"""
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from map_utils import build_choropleth, render_map_legend_note

LAST_ACTUAL_YEAR = 2024


@st.cache_data
def load_data():
    actual = pd.read_parquet('data/actual.parquet')
    forecast = pd.read_parquet('data/forecast.parquet')
    county_lookup = pd.read_parquet('data/county_lookup.parquet')
    return actual, forecast, county_lookup


def render(geo):
    actual, forecast, county_lookup = load_data()

    latest_actual = (
        actual.sort_values('Year').drop_duplicates('FIPS', keep='last')
        .set_index('FIPS')
    )

    st.info(
        'County-level **industrial** electricity price (not retail, since data '
        'centers are industrial loads): 2001-2024 actual data, EIA Form 861, '
        'with a theta-model 3-year forecast (2025-2027).'
    )

    # ---------------------------------------------------------- selectors
    c1, c2 = st.columns(2)
    states = sorted(county_lookup['State'].dropna().unique())
    sel_state = c1.selectbox('State', states, index=states.index('MO') if 'MO' in states else 0, key='cost_state')
    state_counties = county_lookup[county_lookup['State'] == sel_state].sort_values('County_Name')
    county_options = [f"{r.County_Name} ({r.FIPS})" for r in state_counties.itertuples()]
    sel_label = c2.selectbox('County', county_options, key='cost_county')
    sel_fips = sel_label.split('(')[-1].rstrip(')')

    # ---------------------------------------------------------------- map
    st.subheader("County-level industrial electricity price")

    _all_prices = pd.concat([actual['Price_cents_kWh'], forecast['Price_cents_kWh']])
    vmin, vmax = _all_prices.quantile(0.02), _all_prices.max()

    # Read the slider's current value from session_state BEFORE building the
    # map, even though the slider widget itself is drawn further down (below
    # the map, per design). Streamlit updates session_state before a rerun
    # starts, so this picks up a user's new selection correctly; the widget
    # created later just needs the same key.
    map_year = st.session_state.get('cost_map_year', LAST_ACTUAL_YEAR)
    if map_year <= LAST_ACTUAL_YEAR:
        map_df = actual[actual['Year'] == map_year][
            ['FIPS', 'State', 'County_Name', 'Price_cents_kWh', 'Confidence_Grade']].copy()
        hover_data = {'State': True, 'Confidence_Grade': True, 'FIPS': False}
    else:
        map_df = forecast[forecast['Year'] == map_year][
            ['FIPS', 'State', 'County_Name', 'Price_cents_kWh', 'Expected_MAPE_%']].copy()
        hover_data = {'State': True, 'Expected_MAPE_%': ':.1f', 'FIPS': False}

    if map_df.empty:
        st.warning(f'No data available for {map_year}.')
    else:
        fig_map = build_choropleth(
            map_df, geo, 'Price_cents_kWh', 'YlOrRd', vmin, vmax,
            hover_data=hover_data, hover_name_col='County_Name',
            labels={'Price_cents_kWh': 'Industrial price (cents/kWh)',
                    'Expected_MAPE_%': 'Backtested MAPE at horizon (%)'},
            colorbar_title='cents/kWh',
        )
        st.plotly_chart(fig_map, width='stretch', key='cost_map')

    render_map_legend_note(
        'Gray = no data available for this county in the selected year '
        '(no matching EIA record, or discontinued reporting).'
    )

    map_year = st.select_slider(
        'Map year', options=list(range(2001, 2028)), value=map_year,
        help='2025-2027 are theta-model forecast years, not measured actuals.',
        key='cost_map_year',
    )
    st.caption(
        f"Showing **{map_year}**"
        + (' (actual)' if map_year <= LAST_ACTUAL_YEAR else ' (theta forecast)')
        + '. Color scale fixed at the 2nd percentile to the true maximum across all '
          'years, so a handful of very low-confidence counties never compress the '
          'scale for everyone else.'
    )

    # ============================================================ county detail
    sel_row = latest_actual.loc[[sel_fips]] if sel_fips in latest_actual.index else latest_actual.iloc[0:0]
    sel_name = sel_row['County_Name'].iloc[0] if not sel_row.empty else sel_fips
    sel_state_name = sel_row['State'].iloc[0] if not sel_row.empty else sel_state

    st.divider()
    st.subheader(f"Selected county: {sel_name}, {sel_state_name}")

    f_sel = forecast[forecast['FIPS'] == sel_fips].sort_values('Year')
    a_sel = actual[actual['FIPS'] == sel_fips].sort_values('Year')

    m1, m2, m3, m4 = st.columns(4)
    if not a_sel.empty:
        last_year = int(a_sel['Year'].iloc[-1])
        last_price = a_sel['Price_cents_kWh'].iloc[-1]
        m1.metric(f'Last reported price ({last_year})', f'{last_price:.2f} ¢/kWh')
    else:
        last_price = None
        m1.metric('Last reported price', 'n/a')

    if not f_sel.empty:
        last_fc = f_sel.iloc[-1]
        delta = None
        if last_price is not None and last_price != 0:
            delta = f"{(last_fc['Price_cents_kWh'] / last_price - 1) * 100:+.1f}% vs last actual"
        m2.metric(f"{int(last_fc['Year'])} forecast", f"{last_fc['Price_cents_kWh']:.2f} ¢/kWh", delta)
        if pd.notna(last_fc['Lower_CI_cents_kWh']):
            m3.metric(f"68% interval ({int(last_fc['Year'])})",
                      f"{last_fc['Lower_CI_cents_kWh']:.2f} - {last_fc['Upper_CI_cents_kWh']:.2f} ¢")
        else:
            m3.metric('68% interval', 'not available', help='Fewer than 8 years of history -- not backtested.')
        if pd.notna(last_fc['Expected_MAPE_%']):
            m4.metric('Backtested MAPE at 3yr', f"{last_fc['Expected_MAPE_%']:.1f}%")
        else:
            m4.metric('Backtested MAPE at 3yr', 'n/a')
    else:
        m2.metric('Forecast', 'n/a')

    st.caption(
        "Trend: actual history, theta-model forecast, and the real backtest-derived "
        "68% prediction interval, shown as a symmetric +/- band (the average of the "
        "two real asymmetric backtest deviations, not an assumed number -- see the "
        "methodology expander below)."
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=a_sel['Year'], y=a_sel['Price_cents_kWh'], mode='lines+markers',
                              name='Actual', line=dict(color='#1f77b4', width=2)))
    if not f_sel.empty:
        bridge_year = pd.concat([a_sel['Year'].tail(1), f_sel['Year']])
        bridge_price = pd.concat([a_sel['Price_cents_kWh'].tail(1), f_sel['Price_cents_kWh']])
        has_ci = f_sel['Upper_CI_cents_kWh'].notna().all() and f_sel['Lower_CI_cents_kWh'].notna().all()
        if has_ci:
            upper = pd.concat([a_sel['Price_cents_kWh'].tail(1), f_sel['Upper_CI_cents_kWh']])
            lower = pd.concat([a_sel['Price_cents_kWh'].tail(1), f_sel['Lower_CI_cents_kWh']])
            ci_level_label = int(round(f_sel['CI_Level_%'].iloc[0]))
            fig.add_trace(go.Scatter(
                x=pd.concat([bridge_year, bridge_year[::-1]]),
                y=pd.concat([upper, lower[::-1]]),
                fill='toself', fillcolor='rgba(255,127,14,0.18)',
                line=dict(color='rgba(255,255,255,0)'), hoverinfo='skip',
                name=f'{ci_level_label}% prediction interval',
            ))
        fig.add_trace(go.Scatter(x=bridge_year, y=bridge_price, mode='lines+markers',
                                  name='Theta forecast', line=dict(color='#ff7f0e', width=2, dash='dash')))
    fig.update_layout(
        xaxis_title='Year', yaxis_title='Price (cents/kWh)',
        height=420, margin=dict(l=10, r=10, t=20, b=10),
        legend=dict(orientation='h', y=1.12), hovermode='x unified',
    )
    st.plotly_chart(fig, width='stretch', key='cost_trend')

    # ======================================================== comparison table
    st.divider()
    st.subheader('Compare counties')
    sort_options = {
        'Last reported price (highest)': ('Price_cents_kWh_actual', False),
        'Last reported price (lowest)': ('Price_cents_kWh_actual', True),
        '2027 forecast (highest)': ('Price_cents_kWh_forecast', False),
        '2027 forecast (lowest)': ('Price_cents_kWh_forecast', True),
    }
    sort_choice = st.selectbox('Sort by', list(sort_options.keys()), index=2, key='cost_sort')
    n_show = st.slider('Counties to show', 5, 50, 15, key='cost_n')

    fc_2027 = forecast[forecast['Year'] == 2027][
        ['FIPS', 'Price_cents_kWh', 'Lower_CI_cents_kWh', 'Upper_CI_cents_kWh']
    ].rename(columns={'Price_cents_kWh': 'Price_cents_kWh_forecast'})
    la = latest_actual.reset_index().rename(columns={'Price_cents_kWh': 'Price_cents_kWh_actual', 'Year': 'Last_Year'})
    table = la.merge(fc_2027, on='FIPS', how='left')
    col, asc = sort_options[sort_choice]
    table = table.sort_values(col, ascending=asc, na_position='last').head(n_show)

    st.dataframe(
        table[['FIPS', 'State', 'County_Name', 'Last_Year', 'Price_cents_kWh_actual',
               'Price_cents_kWh_forecast', 'Lower_CI_cents_kWh', 'Upper_CI_cents_kWh']]
        .rename(columns={
            'Last_Year': 'Last reported year', 'Price_cents_kWh_actual': 'Last reported price (cents/kWh)',
            'Price_cents_kWh_forecast': '2027 Forecast (cents/kWh)',
            'Lower_CI_cents_kWh': '2027 Lower bound', 'Upper_CI_cents_kWh': '2027 Upper bound',
        }).round(2),
        width='stretch', hide_index=True,
    )

    # ========================================================= methodology
    with st.expander('About this data and methodology'):
        st.markdown(
            "**Data source:** U.S. EIA Form 861 annual industrial electricity sales "
            "and revenue, aggregated to county level and weighted by MWh, 2001-2024.\n\n"
            "**Forecast model:** theta method (simple exponential smoothing blended "
            "50/50 with a linear trend), chosen over AR(1) and ARIMA because it does "
            "not assume mean reversion -- important since prices have risen for 24 "
            "consecutive years and AR(1) systematically forecast declines for the "
            "large majority of counties despite their real upward trend.\n\n"
            "**Prediction interval:** a real empirical interval built from the actual "
            "distribution of backtest errors (5 rolling-origin windows, 2015-2019 "
            "training cutoffs tested against the real 2020-2024 actuals), shown at "
            "the 68% level. The raw backtest errors are naturally asymmetric around "
            "the point forecast; the two real deviations are averaged into one "
            "symmetric +/- band so the chart reads as 'plus or minus X%' without "
            "changing the total amount of uncertainty shown.\n\n"
            "**Scope:** this release covers the Cost pillar only. Reliability is "
            "included alongside it; Availability and a composite Power Risk Index "
            "are planned but not yet backed by validated research data.\n\n"
            "**Counties with limited reporting history:** 15 counties have fewer "
            "than 8 years of actual data and are shown without a prediction "
            "interval, since their forecast accuracy has not been backtested. A "
            "further ~20 counties have discontinued or sparse EIA reporting in "
            "recent years; their forecasts are still shown on their own historical "
            "timeline."
        )
