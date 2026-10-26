"""Power Risk Index for Data Center Construction Planning -- main app.

Single page, one URL. Password-gated. Four pillars as tabs: Cost and
Reliability are real, tested, validated pillars; Availability and the
Composite index are honest placeholders (no synthetic data) until their
own pillars are built out.
"""
import json
import streamlit as st

st.set_page_config(
    page_title='Power Risk Index for Data Center Construction Planning',
    page_icon='⚡', layout='wide',
)


def check_password():
    """Simple shared-password gate. The real password lives only in
    st.secrets (never in source control) -- see .streamlit/secrets.toml.example."""
    if st.session_state.get('authenticated'):
        return True

    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.image('assets/mocci_logo.png', width=140)
        st.markdown("#### Power Risk Index for Data Center Construction Planning")
        st.caption('Missouri Consortium for Construction Innovation (MOCCI)')
        pw = st.text_input('Password', type='password', key='pw_input')
        if st.button('Enter', width='stretch'):
            real_pw = st.secrets.get('app_password')
            if real_pw is None:
                st.error('App password is not configured yet (set app_password in Secrets).')
            elif pw == real_pw:
                st.session_state['authenticated'] = True
                st.rerun()
            else:
                st.error('Incorrect password.')
    return False


if not check_password():
    st.stop()


@st.cache_data
def load_geojson():
    with open('data/counties_fips.json') as f:
        return json.load(f)


geo = load_geojson()

h1, h2 = st.columns([1, 9])
with h1:
    st.image('assets/mocci_logo.png', width=90)
with h2:
    st.title('Power Risk Index for Data Center Construction Planning')
    st.caption('Missouri Consortium for Construction Innovation (MOCCI)')

st.info(
    '**Scope:** this release includes the **Cost** and **Reliability** pillars, '
    'both built on real, validated data and tested forecasts. The **Availability** '
    '(Capacity) pillar and the **Composite Power Risk Index** are planned but not '
    'yet included -- no placeholder or synthetic values are shown for them.'
)

tab_cost, tab_reliability, tab_availability, tab_composite = st.tabs(
    ['Cost', 'Reliability', 'Availability', 'Composite']
)

with tab_cost:
    import cost_pillar
    cost_pillar.render(geo)

with tab_reliability:
    import reliability_pillar
    reliability_pillar.render(geo)

with tab_availability:
    import availability_pillar
    availability_pillar.render()

with tab_composite:
    import composite_pillar
    composite_pillar.render()
