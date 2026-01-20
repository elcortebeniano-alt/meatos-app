import streamlit as st
import pandas as pd
import time
import os
import json
from datetime import datetime, timedelta
import streamlit.components.v1 as components

# LIBRERIAS
import google.generativeai as genai
from PIL import Image
import qrcode
import cv2
import numpy as np
from pyzbar.pyzbar import decode
import styles
import backend

st.set_page_config(page_title="El Corte Beniano | POS", layout="wide", page_icon="🥩", initial_sidebar_state="collapsed")
styles.cargar_css()

# --- DIAGNÓSTICO DE VERSIÓN ---
try:
    lib_version = genai.__version__
except:
    lib_version = "Error"

# --- CONFIGURACIÓN API ---
api_msg = "Desconocido"
if "GOOGLE_API_KEY" in st.secrets:
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        api_msg = "✅ Configurada"
    except Exception as e:
        api_msg = f"❌ Error: {e}"
else:
    api_msg = "⚠️ Faltan Secrets"

def get_bolivia_time(): return (datetime.utcnow() - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M")

@st.cache_data(ttl=3600) 
def obtener_mapa_imagenes(lista_productos):
    mapa = {}
    for prod in lista_productos:
        p1, p2 = f"img/{prod}.png", f"img/{prod}.jpg"
        if os.path.exists(p1): mapa[prod] = p1
        elif os.path.exists(p2): mapa[prod] = p2
        else: mapa[prod] = None 
    return mapa

# --- CEREBRO IA (LISTA AMPLIADA) ---
def analizar_recibo_con_ia(image_file):
    img = Image.open(image_file)
    prompt = """
    Extrae items en JSON: {"items":[{"producto":"", "peso_kg":0.0, "precio_unitario":0.0, "subtotal":0.0}], "total_pagado":0.0, "metodo_pago":"Efectivo"}
    """
    
    # LISTA DE INTENTOS (Del más nuevo al más compatible)
    # Agregamos 'gemini-pro-vision' (v1.0) que es muy estable
    modelos = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro-vision']
    
    errores = []
    
    for m_name in modelos:
        try:
            model = genai.GenerativeModel(m_name)
            response = model.generate_content([prompt, img])
            return json.loads(response.text.replace("```json", "").replace("```", "").strip())
        except Exception as e:
            errores.append(f"{m_name}: {str(e)}")
            continue
            
    st.error(f"❌ Fallaron todos. Versión Lib: {lib_version}. Detalles: {errores}")
    return None

# --- LECTOR QR ---
def leer_qr_desde_imagen(image_file):
    try:
        file_bytes = np.asarray(bytearray(image_file.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        codigos = decode(img)
        if codigos: return codigos[0].data.decode("utf-8")
        return None
    except: return None

def procesar_codigo_qr(data_qr):
    try:
        partes = data_qr.split('|')
        if len(partes) >= 3 and partes[0] == "MeatOS":
            prod, peso = partes[1], float(partes[2])
            df = st.session_state['productos']
            match = df[df['Producto'] == prod]
            if not match.empty:
                d = match.iloc[0]
                st.session_state['carrito'].append({
                    "Producto": prod, "Categoria": str(d.get('Categoria','Gen')), 
                    "Cantidad": peso, "PrecioUnit": float(d['PrecioVenta']), 
                    "CostoUnit": float(d.get('Costo',0)), "Subtotal": float(d['PrecioVenta'])*peso
                })
                return f"✅ {prod} ({peso} Kg)"
            return "❌ No existe"
        return "❌ Formato inválido"
    except: return "❌ Error"

# CONEXIÓN
if 'sheet_obj' not in st.session_state: st.session_state['sheet_obj'] = backend.conectar_google_sheets()
sheet = st.session_state['sheet_obj']
if not sheet: st.stop()

# CARGA
for k, cols in {'finanzas':['Fecha','Detalle','Tipo','Monto','MetodoPago','Ganancia','Usuario','Sucursal'], 
                'productos':['Producto','Costo','PrecioVenta','Categoria','StockActual'], 
                'detalles':['Fecha','Producto','Categoria','PesoKg','CostoUnit','PrecioVentaUnit','Subtotal','Ganancia','Usuario','Sucursal'],
                'usuarios':['Usuario','Password','Nombre','Rol','Sucursal','Activo'],
                'clientes':['Telefono','Nombre','TotalGastado','UltimaCompra','Puntos']}.items():
    if k not in st.session_state: st.session_state[k] = backend.cargar_data(sheet, k, cols)

for k in ['carrito','ultimo_ticket','user_info','producto_seleccionado','datos_ia_pendientes','msg_feedback']:
    if k not in st.session_state: st.session_state[k] = None
if 'reset_counter' not in st.session_state: st.session_state['reset_counter'] = 0
if st.session_state['carrito'] is None: st.session_state['carrito'] = []

if not st.session_state['productos'].empty:
    mapa_imgs = obtener_mapa_imagenes(st.session_state['productos']['Producto'].unique())
else: mapa_imgs = {}

st.session_state['finanzas'] = backend.limpiar_fechas(st.session_state['finanzas'])
st.session_state['detalles'] = backend.limpiar_fechas(st.session_state['detalles'])

DIRECCION_NEGOCIO = "Calle A. García #1128, Cochabamba"
TELEFONO_NEGOCIO = "591 77420111"

# LOGIN
if st.session_state['user_info'] is None:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if os.path.exists("Logo-Final.png"): st.image("Logo-Final.png", width=200)
        st.title("🥩 MeatOS Login")
        st.caption(f"🔧 Lib: v{lib_version}")
        with st.form("login_form"):
            u = st.text_input("Usuario"); p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Ingresar", type="primary"):
                df = st.session_state['usuarios']
                found = df[(df['Usuario'].astype(str) == u) & (df['Password'].astype(str) == p)]
                if not found.empty and str(found.iloc[0]['Activo']).upper() == 'TRUE':
                    st.session_state['user_info'] = found.iloc[0].to_dict()
                    st.rerun()
                else: st.error("Incorrecto")
    st.stop()

# APP
user = st.session_state['user_info']
with st.sidebar:
    if os.path.exists("Logo-Final.png"): st.image("Logo-Final.png", use_container_width=True)
    st.caption(f"👤 {user['Nombre']} | {user['Rol']}")
    
    st.markdown("---")
    st.caption(f"🤖 IA: v{lib_version}")
    
    # --- BOTÓN REVELADOR DE MODELOS ---
    if st.button("🔍 Ver Modelos Disponibles"):
        try:
            mods = genai.list_models()
            found = [m.name for m in mods if 'generateContent' in m.supported_generation_methods]
            st.success(f"Disponibles: {found}")
        except Exception as e:
            st.error(f"Error listando: {e}")
            
    modo_movil = st.toggle("📱 Modo Celular", False)
    if st.button("🔒 Salir"): st.session_state['user_info'] = None; st.rerun()

if user['Rol'] == "Admin": tabs = st.tabs(["🛒 VENTA", "📥 IMPORTAR KYTE", "📦 INV", "📊 GERENCIA"])
else: tabs = st.tabs(["🛒 VENTA", "📥 IMPORTAR KYTE"])

# --- IMPORTAR ---
with tabs[1]:
    st.header("📥 Importar Kyte")
    up = st.file_uploader("Recibo", type=['png','jpg','jpeg'])
    if up:
        st.image(up, width=300)
        if st.button("✨ ANALIZAR", type="primary"):
            with st.spinner("🤖 Consultando..."):
                d = analizar_recibo_con_ia(up)
                if d: st.session_state['datos_ia_pendientes'] = d; st.success("¡Leído!")
        
        if st.session_state['datos_ia_pendientes']:
            datos = st.session_state['datos_ia_pendientes']
            st.data_editor(pd.DataFrame(datos['items']), key="ed_ia", num_rows="dynamic")
            c1, c2 = st.columns(2)
            c1.metric("Total", f"{datos['total_pagado']} Bs")
            met = c2.selectbox("Pago", ["Efectivo", "QR/Banco"], index=0 if "Efec" in datos.get('metodo_pago','') else 1)
            
            if st.button("✅ GUARDAR VENTA"):
                now = get_bolivia_time(); rid = f"#KYTE-{now.replace(':','').replace(' ','-')}"
                det_bd, tot_g = [], 0
                for i, r in st.session_state['ed_ia'].iterrows():
                    match = st.session_state['productos'][st.session_state['productos']['Producto'].str.contains(r['producto'], case=False, na=False)]
                    cost, cat, idx = 0, "Kyte", -1
                    if not match.empty:
                        idx = match.index[0]; cost = float(st.session_state['productos'].at[idx, 'Costo'])
                        cat = str(st.session_state['productos'].at[idx, 'Categoria'])
                        st.session_state['productos'].at[idx, 'StockActual'] = float(st.session_state['productos'].at[idx, 'StockActual']) - float(r['peso_kg'])
                    
                    g = float(r['subtotal']) - (cost * float(r['peso_kg'])); tot_g += g
                    det_bd.append({'Fecha': now, 'Producto': r['producto'], 'Categoria': cat, 'PesoKg': r['peso_kg'], 'CostoUnit': cost, 'PrecioVentaUnit': r['precio_unitario'], 'Subtotal': r['subtotal'], 'Ganancia': g, 'Usuario': f"{user['Usuario']} (Kyte)", 'Sucursal': user['Sucursal']})

                backend.guardar_data(sheet, "productos", st.session_state['productos'])
                if det_bd: st.session_state['detalles'] = pd.concat([st.session_state['detalles'], pd.DataFrame(det_bd)], ignore_index=True); backend.guardar_data(sheet, "detalles", st.session_state['detalles'])
                fin = pd.DataFrame([{'Fecha': now, 'Detalle': f"Venta Kyte {rid}", 'Tipo': "Ingreso", 'Monto': float(datos['total_pagado']), 'MetodoPago': met, 'Ganancia': tot_g, 'Usuario': user['Usuario'], 'Sucursal': user['Sucursal']}])
                st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], fin], ignore_index=True)
                backend.guardar_data(sheet, "finanzas", st.session_state['finanzas'])
                st.success("Guardado!"); st.session_state['datos_ia_pendientes'] = None; time.sleep(2); st.rerun()

# --- VENTA ---
with tabs[0]:
    with st.container(border=True):
        st.caption("📷 ESCANEAR")
        pistola = st.text_input("Pistola:", key="pist")
        cam = st.camera_input("Cam") if modo_movil else None
        res = procesar_codigo_qr(pistola) if pistola else (procesar_codigo_qr(leer_qr_desde_imagen(cam)) if cam and leer_qr_desde_imagen(cam) else None)
        if res: 
            if "✅" in res: st.success(res); time.sleep(1); st.rerun()
            else: st.error(res)
    
    if modo_movil: l_tabs = st.tabs(["CATALOGO", "CARRITO"]); cont_cat = l_tabs[0]; cont_op = l_tabs[1]
    else: c1, c2 = st.columns([1.6, 1.4]); cont_cat = c1; cont_op = c2
    
    with cont_cat:
        df = st.session_state['productos']
        if not df.empty:
            cats = sorted(df['Categoria'].astype(str).unique()); tabs_c = st.tabs(cats)
            for i, c in enumerate(cats):
                with tabs_c[i]:
                    cols = st.columns(2 if modo_movil else 3)
                    for ix, (idx, r) in enumerate(df[df['Categoria']==c].iterrows()):
                        with cols[ix % (2 if modo_movil else 3)]:
                            im = mapa_imgs.get(r['Producto'])
                            if im: st.image(im, use_container_width=True)
                            else: st.markdown("<div style='text-align:center;'>🥩</div>", unsafe_allow_html=True)
                            if st.button(f"{r['Producto']}\n{r['PrecioVenta']}", key=f"b_{idx}"): st.session_state['producto_seleccionado'] = r['Producto']; st.rerun()

    with cont_op:
        if st.session_state['producto_seleccionado']:
            dat = st.session_state['productos'][st.session_state['productos']['Producto'] == st.session_state['producto_seleccionado']].iloc[0]
            st.info(f"Sel: {dat['Producto']}")
            mod = st.radio("Modo", ["Peso", "Und"], horizontal=True)
            cant = st.number_input("Cant/Gr", 0.0)
            cant_f = cant/1000 if mod=="Peso" else cant
            if st.button("Agregar"): 
                st.session_state['carrito'].append({"Producto":dat['Producto'], "Cantidad":cant_f, "PrecioUnit":float(dat['PrecioVenta']), "Subtotal":cant_f*float(dat['PrecioVenta']), "CostoUnit": float(dat.get('Costo',0)), "Categoria":str(dat.get('Categoria','Gen'))})
                st.session_state['producto_seleccionado']=None; st.rerun()
            if st.button("Cancelar"): st.session_state['producto_seleccionado']=None; st.rerun()
        
        if st.session_state['carrito']:
            st.dataframe(pd.DataFrame(st.session_state['carrito']))
            if st.button("Cobrar"): 
                st.session_state['carrito']=[]; st.success("Vendido"); st.rerun()

if user['Rol'] == "Admin":
    with tabs[2]: st.data_editor(st.session_state['productos'], key="inv")
    with tabs[3]: 
        st.dataframe(st.session_state['finanzas'])
        pe = st.selectbox("P:", st.session_state['productos']['Producto'].unique())
        pes = st.number_input("Kg:", 0.0)
        if pe and pes:
            im = Image.new('RGB', (500,300), 'white'); d = ImageDraw.Draw(im)
            im.paste(qrcode.make(f"MeatOS|{pe}|{pes}").resize((200,200)), (10,50))
            d.text((220,50), "EL CORTE", fill=0); d.text((220,100), f"{pe}\n{pes}kg", fill=0)
            st.image(im, width=250)
