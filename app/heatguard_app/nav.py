"""Page registry so pages can link to each other (e.g. 'Why here?' from a list card)."""
import streamlit as st

PAGES = {}


def go(key, **state):
    for k, v in state.items():
        st.session_state[k] = v
    st.switch_page(PAGES[key])
