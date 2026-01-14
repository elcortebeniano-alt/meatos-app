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

def get_image_base64(path):
    try:
        with open(path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        return f"data:image/png;base64,{encoded_string}"
    except:
        return ""

# --- GENERADOR DE TICKET (CENTRADO AGRESIVO) ---
def generar_html_ticket(carrito, total, fecha, metodo, recibo_id, direccion, telefono):
    
    # Cargar Logo
    logo_b64 = get_image_base64("Logo-Final.png")
    img_tag = f'<img src="{logo_b64}" alt="Logo" style="width: 50px; height: auto;">' if logo_b64 else ""

    items_html = ""
    for item in carrito:
        items_html += f"""
        <div style="margin-bottom: 6px; border-bottom: 1px dashed #ccc; padding-bottom: 4px;">
            <div style="font-weight: bold; font-size: 11px; color: #000; text-align: left;">{item['Producto']}</div>
            <div style="display: flex; justify-content: space-between; font-size: 10px; color: #333;">
                <div>{item['Cantidad']:.3f} x {item['PrecioUnit']:.2f}</div>
                <div style="font-weight: bold;">{item['Subtotal']:.2f}</div>
            </div>
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                margin: 0;
                size: 58mm auto; 
            }}
            
            body {{
                font-family: 'Helvetica', 'Arial', sans-serif;
                margin: 0;
                padding: 0;
                background-color: #fff;
                
                /* TRUCO DEL CENTRADO AGRESIVO */
                display: flex;
                flex-direction: column;
                align-items: center; 
                width: 100%;
            }}

            /* EL TICKET EN SÍ MISMO */
            .ticket-body {{
                width: 48mm; /* Ancho fijo seguro */
                padding: 2px;
                box-sizing: border-box;
            }}

            /* Header */
            .header-container {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 10px;
                border-bottom: 2px solid #000;
                padding-bottom: 5px;
            }}
            
            .logo-box {{ flex: 0 0 50px; }}
            .info-box {{ flex: 1; text-align: right; padding-left: 5px; }}
            
            .biz-name {{ font-size: 12px; font-weight: bold; margin: 0; text-transform: uppercase; color: #000; }}
            .biz-meta {{ font-size: 9px; margin: 1px 0; display: block; color: #444; }}
            .recibo-id {{ font-size: 10px; font-weight: bold; margin-top: 2px; display: block; color: #000; }}

            .section-title {{ 
                font-size: 10px; font-weight: bold; 
                text-transform: uppercase; 
                margin: 5px 0; border-bottom: 1px solid #000; 
                text-align: left;
            }}

            .totals-box {{ 
                margin-top: 10px; 
                text-align: right; 
                border-top: 1px solid #000; 
                padding-top: 5px; 
            }}
            .total-big {{ font-size: 14px; font-weight: bold; color: #000; }}
            
            .footer {{ 
                text-align: center; margin-top: 15px; 
                font-size: 9px; color: #444;
            }}
            
            .no-print {{ text-align: center; margin-bottom: 10px; padding-top: 5px; width: 100%; }}
            button {{ background:#000; color:#fff; border:none; padding:5px 10px; border-radius:4px; font-size:10px; }}

            @media print {{ .no-print {{ display: none; }} }}
        </style>
    </head>
    <body>
        <div class="no-print"><button onclick="window.print()">🖨️ IMPRIMIR</button></div>

        <div class="ticket-body">
            
            <div class="header-container">
                <div class="logo-box">{img_tag}</div>
                <div class="info-box">
                    <span class="biz-name">El Corte Beniano</span>
                    <span class="biz-meta">{direccion}</span>
                    <span class="biz-meta">{telefono}</span>
                    <span class="recibo-id">{recibo_id}</span>
                </div>
            </div>

            <div class="section-title">DETALLE DE COMPRA</div>
            
            <div>{items_html}</div>

            <div class="totals-box">
                <div class="total-big">Total: {total:.2f} Bs</div>
                <div style="font-size: 10px;">Pago: {metodo}</div>
            </div>

            <div class="footer">
                <p style="margin:0; font-weight:bold;">¡Gracias por su compra!</p>
                <p style="margin:2px 0;">{fecha}</p>
            </div>
            
        </div>

        <script>
            setTimeout(function() {{ window.print(); }}, 800);
        </script>
    </body>
    </html>
    """
    return html_content
