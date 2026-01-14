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

# --- GENERADOR DE TICKET HTML (CALIBRADO PARA 58mm/57mm) ---
def generar_html_ticket(carrito, total, fecha, metodo):
    """Genera HTML ajustado para evitar cortes en los márgenes"""
    
    items_html = ""
    for item in carrito:
        items_html += f"""
        <tr>
            <td colspan="2" style="padding-top: 3px; font-weight: bold; font-size: 11px;">{item['Producto']}</td>
        </tr>
        <tr>
            <td style="padding-bottom: 3px; border-bottom: 1px dashed #000; font-size: 11px;">
                {item['Cantidad']:.3f} x {item['PrecioUnit']:.2f}
            </td>
            <td style="padding-bottom: 3px; border-bottom: 1px dashed #000; font-size: 11px; text-align: right;">
                {item['Subtotal']:.2f}
            </td>
        </tr>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: 'Courier New', monospace;
                /* AJUSTE CLAVE: Usamos 48mm para asegurar que entre en el papel de 57mm */
                width: 48mm; 
                margin: 0;
                background-color: #fff;
                padding: 0;
                color: #000;
            }}
            .container {{
                padding: 2px; /* Margen mínimo de seguridad */
            }}
            .header {{ text-align: center; }}
            .title {{ font-size: 14px; font-weight: bold; margin: 0; }}
            .subtitle {{ font-size: 11px; margin: 0; }}
            .divider {{ border-top: 1px dashed black; margin: 5px 0; }}
            table {{ width: 100%; border-collapse: collapse; }}
            .total {{ font-size: 16px; font-weight: bold; text-align: right; margin-top: 5px; }}
            .footer {{ text-align: center; margin-top: 10px; font-size: 10px; }}
            
            .no-print {{ text-align: center; margin-bottom: 10px; padding-top: 10px; }}
            button {{ background-color: #000; color: #fff; border: none; padding: 5px 10px; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 12px; }}
            
            @media print {{
                .no-print {{ display: none; }}
                @page {{ margin: 0; size: auto; }}
                body {{ margin: 0; }}
            }}
        </style>
    </head>
    <body>
        <div class="no-print">
            <button onclick="window.print()">🖨️ IMPRIMIR</button>
        </div>

        <div class="container">
            <div class="header">
                <p class="title">EL CORTE BENIANO</p>
                <p class="subtitle">Carne de Primera</p>
            </div>
            <div class="divider"></div>
            <p style="margin: 2px 0; font-size: 11px;">Fecha: {fecha}<br>Pago: {metodo}</p>
            <div class="divider"></div>
            
            <table>{items_html}</table>
            
            <div class="divider"></div>
            <div class="total">TOTAL: {total:.2f} Bs</div>
            <div class="divider"></div>
            
            <div class="footer"><p>¡Gracias por su compra!</p></div>
        </div>

        <script>
            setTimeout(function() {{ window.print(); }}, 800);
        </script>
    </body>
    </html>
    """
    return html_content
