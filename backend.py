import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import base64 # <--- NECESARIO PARA EL LOGO

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

# --- FUNCIÓN PARA CARGAR EL LOGO EN BASE64 ---
def get_image_base64(path):
    try:
        with open(path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        return f"data:image/png;base64,{encoded_string}"
    except:
        return "" # Si no hay logo, no pone nada

# --- GENERADOR DE TICKET "PREMIUM" (ESTILO IMAGEN) ---
def generar_html_ticket(carrito, total, fecha, metodo, recibo_id, direccion, telefono):
    
    # 1. Cargar Logo
    logo_b64 = get_image_base64("Logo-Final.png")
    img_tag = f'<img src="{logo_b64}" alt="Logo" style="width: 60px; height: auto;">' if logo_b64 else ""

    # 2. Generar lista de ítems con nuevo diseño
    items_html = ""
    for item in carrito:
        items_html += f"""
        <div style="margin-bottom: 8px; border-bottom: 1px solid #eee; padding-bottom: 8px;">
            <div style="font-weight: bold; font-size: 12px; color: #333;">{item['Producto']}</div>
            <div style="display: flex; justify-content: space-between; font-size: 11px; color: #666;">
                <div>{item['Cantidad']:.3f} kg x {item['PrecioUnit']:.2f} Bs</div>
                <div style="font-weight: bold; color: #333;">{item['Subtotal']:.2f} Bs</div>
            </div>
        </div>
        """

    # 3. HTML COMPLETO
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @page {{ margin: 0; size: 58mm auto; }}
            body {{
                margin: 0; padding: 8px; width: 100%;
                background-color: #fff; font-family: 'Helvetica', 'Arial', sans-serif;
                color: #333;
            }}
            .no-print {{ text-align: center; margin-bottom: 10px; }}
            button {{ background-color: #000; color: #fff; border: none; padding: 8px 15px; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 12px; }}
            
            /* Header con Logo y Título */
            .header-grid {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 15px; }}
            .logo-container {{ flex: 0 0 auto; margin-right: 10px; }}
            .biz-info {{ flex: 1; text-align: right; }}
            .biz-name {{ font-size: 14px; font-weight: bold; margin: 0; color: #8B0000; }}
            .biz-details {{ font-size: 9px; color: #666; margin: 2px 0; }}
            .receipt-id {{ font-size: 12px; font-weight: bold; margin-top: 5px; }}
            
            .section-title {{ font-size: 11px; font-weight: bold; border-bottom: 2px solid #333; padding-bottom: 4px; margin: 10px 0; }}
            
            /* Totales */
            .totals-container {{ margin-top: 15px; text-align: right; }}
            .total-line {{ font-size: 16px; font-weight: bold; margin: 5px 0; }}
            .payment-line {{ font-size: 11px; color: #666; }}
            
            .footer {{ text-align: center; margin-top: 20px; font-size: 10px; color: #666; border-top: 1px solid #eee; padding-top: 10px; }}

            @media print {{ .no-print {{ display: none; }} }}
        </style>
    </head>
    <body>
        <div class="no-print"><button onclick="window.print()">🖨️ IMPRIMIR TICKET</button></div>

        <div class="header-grid">
            <div class="logo-container">{img_tag}</div>
            <div class="biz-info">
                <p class="biz-name">EL CORTE BENIANO</p>
                <p class="biz-details">{direccion}</p>
                <p class="biz-details">Tel: {telefono}</p>
                <p class="receipt-id">{recibo_id}</p>
            </div>
        </div>
        
        <div class="section-title">Detalle de Compra ({len(carrito)} ítems)</div>
        <div>{items_html}</div>
        
        <div class="totals-container">
            <div class="total-line">Total: {total:.2f} Bs</div>
            <div class="payment-line">Pago: {metodo}</div>
        </div>
        
        <div class="footer">
            <p style="font-weight: bold; margin: 0;">¡Gracias por su compra!</p>
            <p style="margin: 2px 0;">{fecha}</p>
        </div>

        <script>
            setTimeout(function() {{ window.print(); }}, 800);
        </script>
    </body>
    </html>
    """
    return html_content
