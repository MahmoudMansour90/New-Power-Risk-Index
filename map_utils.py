"""
Shared choropleth-map styling for every pillar's page, so the maps look and
behave consistently app-wide (same state-border treatment, same "no data"
convention, same hover polish).
"""
import streamlit as st
import plotly.express as px

NO_DATA_COLOR = '#d9d9d9'  # distinct, visible gray -- not white/background


def build_choropleth(df, geojson, color_col, color_scale, vmin, vmax,
                      hover_data, hover_name_col, labels, colorbar_title):
    """Build a US county choropleth with visible state borders and a
    consistent "no data" gray for any county/location not present in df."""
    fig = px.choropleth(
        df, geojson=geojson, locations='FIPS', color=color_col,
        color_continuous_scale=color_scale, range_color=(vmin, vmax),
        scope='usa', hover_name=hover_name_col, hover_data=hover_data,
        labels=labels,
    )
    fig.update_traces(marker_line_width=0.3, marker_line_color='rgba(80,80,80,0.5)')
    fig.update_geos(
        showsubunits=True, subunitcolor='rgba(40,40,40,0.9)', subunitwidth=1.1,
        landcolor=NO_DATA_COLOR, showland=True,
        showcountries=False, showcoastlines=False, showlakes=False,
    )
    fig.update_layout(
        height=520, margin=dict(l=0, r=0, t=10, b=0),
        coloraxis_colorbar=dict(title=colorbar_title, thickness=16, len=0.75),
    )
    return fig


def render_map_legend_note(no_data_note):
    """Small explicit legend strip under a map: a gray swatch + an
    explanation, since Plotly's own colorbar can't show a 'no data' entry."""
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:8px; margin-top:-6px;
                    margin-bottom:10px; font-size:0.85rem; color:#555;">
            <div style="width:14px; height:14px; background:{NO_DATA_COLOR};
                        border:1px solid rgba(80,80,80,0.5); flex-shrink:0;"></div>
            <span>{no_data_note}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
