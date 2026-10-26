"""Reliability pillar page: County Reliability Index (CRI), 2013-2024
history + 2025-2027 projection. Real data only -- see data_prep.py and the
MOCCI_Reliability_Export handoff note for how these files were produced and
validated. The app never recomputes anything the notebook already computed.
"""
import json
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from map_utils import build_choropleth, render_map_legend_note

LAST_OBSERVED_YEAR = 2024


@st.cache_data
def load_data():
    panel = pd.read_parquet('data/reliability_panel.parquet')
    forecast = pd.read_parquet('data/reliability_forecast.parquet')
    not_projected = pd.read_parquet('data/reliability_not_projected.parquet')
    county_lookup = pd.read_parquet('data/reliability_county_lookup.parquet')
    with open('data/reliability_metadata.json') as f:
        meta = json.load(f)
    return panel, forecast, not_projected, county_lookup, meta


def render(geo):
    panel, forecast, not_projected, county_lookup, meta = load_data()
    not_projected_fips = set(not_projected['FIPS'])

    latest_panel = panel.sort_values('Year').drop_duplicates('FIPS', keep='last').set_index('FIPS')

    st.info(
        'County Reliability Index (CRI): a 0-100 constructed index from EIA Form 861 '
        'SAIDI/SAIFI outage data, county-level, 2013-2024, with a 3-year projection '
        '(2025-2027). **Higher CRI = worse reliability.**'
    )

    # ---------------------------------------------------------- selectors
    c1, c2 = st.columns(2)
    states = sorted(county_lookup['State'].dropna().unique())
    sel_state = c1.selectbox('State', states, index=states.index('MO') if 'MO' in states else 0, key='rel_state')
    state_counties = county_lookup[county_lookup['State'] == sel_state].sort_values('County_Name')
    county_options = [f"{r.County_Name.title()} ({r.FIPS})" for r in state_counties.itertuples()]
    sel_label = c2.selectbox('County', county_options, key='rel_county')
    sel_fips = sel_label.split('(')[-1].rstrip(')')

    # ---------------------------------------------------------------- map
    st.subheader("County Reliability Index (CRI)")

    vmin, vmax = 0, 100  # fixed per the handoff note -- same scale every year

    map_year = st.session_state.get('rel_map_year', LAST_OBSERVED_YEAR)
    if map_year <= LAST_OBSERVED_YEAR:
        map_df = panel[panel['Year'] == map_year][
            ['FIPS', 'State', 'County_Name', 'CRI', 'CRI_Tier', 'Confidence_Grade']].dropna(subset=['CRI']).copy()
        hover_data = {'State': True, 'CRI_Tier': True, 'Confidence_Grade': True, 'FIPS': False}
        color_col = 'CRI'
    else:
        map_df = forecast[forecast['Year'] == map_year][
            ['FIPS', 'State', 'County_Name', 'Projected_CRI', 'Projected_Tier', 'P_High_or_VeryHigh']].copy()
        hover_data = {'State': True, 'Projected_Tier': True, 'P_High_or_VeryHigh': ':.0%', 'FIPS': False}
        color_col = 'Projected_CRI'

    if map_df.empty:
        st.warning(f'No data available for {map_year}.')
    else:
        fig_map = build_choropleth(
            map_df, geo, color_col, 'OrRd', vmin, vmax,
            hover_data=hover_data, hover_name_col='County_Name',
            labels={'CRI': 'CRI (0-100)', 'Projected_CRI': 'Projected CRI (0-100)',
                    'P_High_or_VeryHigh': 'P(High or Very High)'},
            colorbar_title='CRI',
        )
        st.plotly_chart(fig_map, width='stretch', key='rel_map')

    render_map_legend_note(
        'Gray = no data available for this county in the selected year '
        '(insufficient history, or no projection -- see "About this data" below).'
    )

    map_year = st.select_slider(
        'Map year', options=list(range(2013, 2028)), value=map_year,
        help='2025-2027 are projected years, not measured actuals.',
        key='rel_map_year',
    )
    st.caption(
        f"Showing **{map_year}**"
        + (' (observed)' if map_year <= LAST_OBSERVED_YEAR else ' (Projected)')
        + '. Color scale fixed at 0-100 in every year, so colors mean the same '
          'thing regardless of which year is selected.'
    )

    # ============================================================ county detail
    sel_row = latest_panel.loc[[sel_fips]] if sel_fips in latest_panel.index else latest_panel.iloc[0:0]
    sel_name = sel_row['County_Name'].iloc[0].title() if not sel_row.empty else sel_fips
    sel_state_name = sel_row['State'].iloc[0] if not sel_row.empty else sel_state

    st.divider()
    st.subheader(f"Selected county: {sel_name}, {sel_state_name}")

    p_sel = panel[panel['FIPS'] == sel_fips].sort_values('Year')
    f_sel = forecast[forecast['FIPS'] == sel_fips].sort_values('Year')
    is_not_projected = sel_fips in not_projected_fips

    m1, m2, m3, m4 = st.columns(4)
    p_sel_valid = p_sel.dropna(subset=['CRI'])
    if not p_sel_valid.empty:
        last_year = int(p_sel_valid['Year'].iloc[-1])
        last_cri = p_sel_valid['CRI'].iloc[-1]
        last_tier = p_sel_valid['CRI_Tier'].iloc[-1]
        m1.metric(f'Last observed CRI ({last_year})', f'{last_cri:.1f}', last_tier)
    else:
        m1.metric('Last observed CRI', 'n/a')

    if is_not_projected:
        reason = not_projected.loc[not_projected['FIPS'] == sel_fips, 'Reason'].iloc[0]
        m2.metric('2027 projection', 'No projection')
        st.caption(f"No projection for this county: {reason}. Shown as 'no projection', never a placeholder value.")
    elif not f_sel.empty:
        last_fc = f_sel.iloc[-1]
        m2.metric(f"{int(last_fc['Year'])} projected CRI", f"{last_fc['Projected_CRI']:.1f}", last_fc['Projected_Tier'])
        m3.metric('68% interval', f"{last_fc['CRI_Low_68']:.1f} - {last_fc['CRI_High_68']:.1f}")
        m4.metric('P(High or Very High)', f"{last_fc['P_High_or_VeryHigh']:.0%}")
        if last_fc['History_Flag'] != 'OK':
            st.caption(f"Note: {last_fc['History_Flag']}")
    else:
        m2.metric('Projection', 'n/a')

    st.caption(
        "CRI trend: solid = observed, dashed = Projected, shaded = the real "
        "68% empirical prediction interval (CRI_Low_68/CRI_High_68 -- see the "
        "methodology expander below)."
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=p_sel['Year'], y=p_sel['CRI'], mode='lines+markers',
                              name='Observed CRI', line=dict(color='#1f77b4', width=2),
                              connectgaps=False))
    if not f_sel.empty:
        bridge_year = pd.concat([p_sel_valid['Year'].tail(1), f_sel['Year']])
        bridge_cri = pd.concat([p_sel_valid['CRI'].tail(1), f_sel['Projected_CRI']])
        has_ci = f_sel['CRI_Low_68'].notna().all() and f_sel['CRI_High_68'].notna().all()
        if has_ci and not p_sel_valid.empty:
            upper = pd.concat([p_sel_valid['CRI'].tail(1), f_sel['CRI_High_68']])
            lower = pd.concat([p_sel_valid['CRI'].tail(1), f_sel['CRI_Low_68']])
            fig.add_trace(go.Scatter(
                x=pd.concat([bridge_year, bridge_year[::-1]]),
                y=pd.concat([upper, lower[::-1]]),
                fill='toself', fillcolor='rgba(227,74,51,0.18)',
                line=dict(color='rgba(255,255,255,0)'), hoverinfo='skip',
                name='68% prediction interval',
            ))
        if not p_sel_valid.empty:
            fig.add_trace(go.Scatter(x=bridge_year, y=bridge_cri, mode='lines+markers',
                                      name='Projected CRI', line=dict(color='#e34a33', width=2, dash='dash')))
    fig.update_layout(
        xaxis_title='Year', yaxis_title='CRI (0-100, higher = worse)',
        height=420, margin=dict(l=10, r=10, t=20, b=10),
        legend=dict(orientation='h', y=1.12), hovermode='x unified',
        yaxis_range=[0, 100],
    )
    st.plotly_chart(fig, width='stretch', key='rel_trend')

    # SAIDI/SAIFI history only -- explicitly not projected, per handoff note
    with st.expander('SAIDI / SAIFI history (not projected)'):
        saidi_saifi = p_sel[['Year', 'SAIDI_min_per_customer', 'SAIFI_interruptions_per_customer']].dropna(how='all', subset=['SAIDI_min_per_customer', 'SAIFI_interruptions_per_customer'])
        if saidi_saifi.empty:
            st.caption('No SAIDI/SAIFI history available for this county.')
        else:
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=saidi_saifi['Year'], y=saidi_saifi['SAIDI_min_per_customer'],
                                       name='SAIDI (min/customer)', mode='lines+markers', yaxis='y1'))
            fig2.add_trace(go.Scatter(x=saidi_saifi['Year'], y=saidi_saifi['SAIFI_interruptions_per_customer'],
                                       name='SAIFI (interruptions/customer)', mode='lines+markers', yaxis='y2'))
            fig2.update_layout(
                height=320, margin=dict(l=10, r=10, t=20, b=10),
                yaxis=dict(title='SAIDI (min/customer)'),
                yaxis2=dict(title='SAIFI', overlaying='y', side='right'),
                legend=dict(orientation='h', y=1.15),
            )
            st.plotly_chart(fig2, width='stretch', key='rel_saidi_saifi')
            st.caption('History only -- SAIDI/SAIFI are not projected; only the constructed CRI is.')

    # ======================================================== comparison table
    st.divider()
    st.subheader('Compare counties')
    sort_options = {
        'Last observed CRI (worst first)': ('CRI', False),
        'Last observed CRI (best first)': ('CRI', True),
        '2027 projected CRI (worst first)': ('Projected_CRI', False),
        '2027 projected CRI (best first)': ('Projected_CRI', True),
    }
    sort_choice = st.selectbox('Sort by', list(sort_options.keys()), index=2, key='rel_sort')
    n_show = st.slider('Counties to show', 5, 50, 15, key='rel_n')

    fc_2027 = forecast[forecast['Year'] == 2027][
        ['FIPS', 'Projected_CRI', 'CRI_Low_68', 'CRI_High_68', 'Projected_Tier']
    ]
    la = latest_panel.reset_index().rename(columns={'Year': 'Last_Year'})
    table = la.merge(fc_2027, on='FIPS', how='left')
    col, asc = sort_options[sort_choice]
    table = table.sort_values(col, ascending=asc, na_position='last').head(n_show)
    table['County_Name'] = table['County_Name'].str.title()

    st.dataframe(
        table[['FIPS', 'State', 'County_Name', 'Last_Year', 'CRI', 'CRI_Tier',
               'Projected_CRI', 'Projected_Tier', 'CRI_Low_68', 'CRI_High_68']]
        .rename(columns={
            'Last_Year': 'Last observed year', 'CRI': 'Last observed CRI', 'CRI_Tier': 'Tier',
            'Projected_CRI': '2027 Projected CRI', 'Projected_Tier': '2027 Tier',
            'CRI_Low_68': '2027 Lower bound', 'CRI_High_68': '2027 Upper bound',
        }).round(1),
        width='stretch', hide_index=True,
    )

    # ========================================================= methodology
    with st.expander('About this data and methodology'):
        st.markdown(f"**Method:** {meta['method']}\n\n"
                    f"**National trend:** {meta['national_trend_cri_pts_per_year']} CRI points/yr "
                    f"(90% bootstrap CI {meta['national_trend_90ci_state_bootstrap'][0]}-"
                    f"{meta['national_trend_90ci_state_bootstrap'][1]}).\n\n"
                    f"**Band:** {meta['band_app']}.")
        st.markdown("**Disclosures:**")
        for d in meta['disclosures']:
            st.markdown(f"- {d}")
        st.caption(
            "Scope: this page covers the Reliability pillar only. Availability and "
            "a composite Power Risk Index are planned but not yet backed by "
            "validated research data -- no placeholder or synthetic values are "
            "shown for them."
        )
