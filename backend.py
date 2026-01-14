import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def conectar_google_sheets():
    try:
        if os.path.exists("credentials.json"):
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)
            client = gspread.authorize(creds)
            return client.open("MeatOS_DB")
        elif "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
            client = gspread.authorize(creds)
            return client.open("MeatOS_DB")
        else:
            return None
    except Exception as e:
        st.error(f"Error Conexión Backend: {e}")
        return None

def cargar_data(sheet, nombre_hoja, columnas):
    try:
        worksheet = sheet.worksheet(nombre_hoja)
        data = worksheet.get_all_records()
        if not data: return pd.DataFrame(columns=columnas)
        df = pd.DataFrame(data)
        for col in columnas:
            if col not in df.columns: df[col] = "" 
        return df
    except gspread.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=nombre_hoja, rows=1000, cols=10)
        worksheet.append_row(columnas)
        return pd.DataFrame(columns=columnas)
    except Exception as e:
        st.error(f"Error leyendo {nombre_hoja}: {e}")
        return pd.DataFrame(columns=columnas)

def guardar_data(sheet, nombre_hoja, df):
    try:
        worksheet = sheet.worksheet(nombre_hoja)
        worksheet.clear()
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
    except Exception as e:
        st.error(f"Error guardando {nombre_hoja}: {e}")

def limpiar_fechas(df):
    if 'Fecha' in df.columns: df['Fecha'] = df['Fecha'].astype(str).fillna("")
    return df
