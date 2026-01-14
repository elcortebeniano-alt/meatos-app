import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import base64

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

# --- EN backend.py ---

def generar_html_ticket(carrito, total, fecha, metodo):
    """Genera HTML puro para renderizar directo en la app"""
    
    items_html = ""
    for item in carrito:
        items_html += f"""
        <tr>
            <td style="padding-top: 5px; font-weight: bold; font-size: 12px;">{item['Producto']}</td>
        </tr>
        <tr>
            <td style="padding-bottom: 5px; border-bottom: 1px dashed #ccc; font-size: 12px;">
                {item['Cantidad']:.3f} kg x {item['PrecioUnit']:.2f} = <span style="float:right;">{item['Subtotal']:.2f}</span>
            </td>
        </tr>
        """

    # HTML COMPLETO CON BOTÓN DE IMPRIMIR INTEGRADO
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: 'Courier New', monospace;
                width: 100%;
                max-width: 300px; /* Ancho típico de ticket */
                margin: 0 auto;
                background-color: #fff;
                padding: 10px;
                color: #000;
            }}
            .header {{ text-align: center; }}
            .title {{ font-size: 16px; font-weight: bold; margin: 0; }}
            .subtitle {{ font-size: 12px; margin: 0; }}
            .divider {{ border-top: 1px dashed black; margin: 5px 0; }}
            table {{ width: 100%; border-collapse: collapse; }}
            .total {{ font-size: 18px; font-weight: bold; text-align: right; margin-top: 10px; }}
            .footer {{ text-align: center; margin-top: 20px; font-size: 10px; }}
            
            /* Botón de imprimir solo visible en pantalla, no en papel */
            .no-print {{
                text-align: center;
                margin-bottom: 15px;
            }}
            button {{
                background-color: #000; color: #fff; border: none; 
                padding: 10px 20px; border-radius: 5px; font-weight: bold; cursor: pointer;
            }}
            
            @media print {{
                .no-print {{ display: none; }}
                @page {{ margin: 0; }}
                body {{ margin: 0; padding: 0; }}
            }}
        </style>
    </head>
    <body>
        <div class="no-print">
            <button onclick="window.print()">🖨️ IMPRIMIR / PDF</button>
        </div>

        <div class="header">
            <p class="title">EL CORTE BENIANO</p>
            <p class="subtitle">Carne de Primera</p>
        </div>
        
        <div class="divider"></div>
        <p style="margin: 5px 0; font-size: 12px;">Fecha: {fecha}<br>Pago: {metodo}</p>
        <div class="divider"></div>

        <table>
            {items_html}
        </table>

        <div class="divider"></div>
        <div class="total">TOTAL: {total:.2f} Bs</div>
        <div class="divider"></div>

        <div class="footer">
            <p>¡Gracias por su preferencia!</p>
            <p>***</p>
        </div>

        <script>
            setTimeout(function() {{ window.print(); }}, 500);
        </script>
    </body>
    </html>
    """
    return html_content # Devolvemos TEXTO puro, ya no Base64
    
    # Convertir a Base64 para abrirlo como link
    b64 = base64.b64encode(html_content.encode()).decode()
    href = f'data:text/html;base64,{b64}'
    return href
