import streamlit as st

def cargar_css():
    st.markdown("""
    <style>
        /* CONFIGURACIÓN GENERAL */
        .block-container { padding-top: 2rem; }
        
        /* BOTONES */
        .stButton>button { font-weight: bold; border-radius: 8px; height: 3em; width: 100%; }
        button[kind="primary"] { background-color: #8B0000 !important; color: white !important; border: none !important; }
        button[kind="primary"]:hover { background-color: #A52A2A !important; box-shadow: 0 4px 8px rgba(0,0,0,0.2); }

        /* TARJETAS KPI (Forzando letras negras) */
        div[data-testid="stMetric"] { background-color: #f0f2f6 !important; border: 1px solid #d0d0d0; padding: 10px; border-radius: 8px; text-align: center; }
        div[data-testid="stMetricLabel"] p { color: #000000 !important; }
        div[data-testid="stMetricValue"] div { color: #000000 !important; }

        /* WHATSAPP BUTTON */
        .btn-whatsapp { display: inline-flex; align-items: center; justify-content: center; background-color: #25D366; color: white !important; font-weight: bold; padding: 0.8rem 1.5rem; border-radius: 12px; text-decoration: none; border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 100%; font-size: 1.1rem; margin-top: 10px; }
        .btn-whatsapp:hover { background-color: #128C7E; color: white !important; }
    </style>
    """, unsafe_allow_html=True)
