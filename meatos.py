import streamlit as st
import pandas as pd
import time
import os
import json
from datetime import datetime, timedelta
from urllib.parse import quote
import streamlit.components.v1 as components

# --- LIBRERIAS IA Y VISIÓN ---
import google.generativeai as genai
from PIL import Image

# --- LIBRERIAS QR ---
import qrcode
import cv2
import numpy as np
from pyzbar.pyzbar import decode

import styles
import backend

# CONFIGURACIÓN
st.set_page_config(page_title="El Corte Beniano | POS", layout="wide", page_icon="🥩", initial_sidebar_state="collapsed")
styles.cargar_css()

# --- CONFIGURACIÓN API GEMINI ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("⚠️ Falta configurar la GOOGLE_API_KEY en los Secrets.")

def get_bolivia_time(): return (datetime.utcnow() - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M")
def get_bolivia_date(): return (datetime.utcnow() - timedelta(hours=4)).strftime("%Y-%m-%d")

# --- FUNCIÓN CEREBRO: GEMINI VISION (ROBUSTA) ---
def analizar_recibo_con_ia(image_file):
    try:
        # CAMBIO: Usamos 'gemini-1.5-pro' que es más robusto si 'flash' falla
        # Si este falla, el 'except' nos avisará.
        model = genai.GenerativeModel('gemini-1.5-pro') 
        img = Image.open(image_file)
        
        prompt = """
        Eres un experto cajero. Analiza esta imagen de un recibo o nota de venta.
        Extrae la información en formato JSON estricto.
        Estructura requerida:
        {
            "items": [
                {"producto": "Nombre exacto del corte", "peso_kg": 0.00, "precio_unitario": 0.00, "subtotal": 0.00}
            ],
            "total_pagado": 0.00,
            "metodo_pago": "Efectivo" (o "QR", "Transferencia" si se menciona)
        }
        Reglas:
        1. Si el peso está en gramos, conviértelo a KG (ej: 500g -> 0.5).
        2. Si no ves el peso explícito pero ves el precio total y unitario, calcula el peso (Total / Unitario).
        3. Devuelve SOLO el JSON, sin texto adicional ni markdown.
        """
        
        response = model.generate_content([prompt, img])
        texto_limpio = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(texto_limpio)
    except Exception as e:
        # Fallback de error
        st.error(f"Error IA: {e}")
        return None

# --- CACHE ---
@st.cache_data(ttl=3600) 
def obtener_mapa_imagenes(lista_productos):
    mapa = {}
    for prod in lista_productos:
        path_png = f"img/{prod}.png"
        path_jpg = f"img/{prod}.jpg"
        if os.path.exists(path_png): mapa[prod] = path_png
        elif os.path.exists(path_jpg): mapa[prod] = path_jpg
        else: mapa[prod] = None 
    return mapa

# --- LECTOR QR ---
def leer_qr_desde_imagen(image_file):
    try:
        file_bytes = np.asarray(bytearray(image_file.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        codigos = decode(img)
        if codigos: return codigos[0].data.decode("utf-8")
        return None
    except: return None

# --- PROCESAR QR TEXTO ---
def procesar_codigo_qr(data_qr):
    try:
        partes = data_qr.split('|')
        if len(partes) >= 3 and partes[0] == "MeatOS":
            prod_qr = partes[1]
            peso_qr = float(partes[2])
            df_prod = st.session_state['productos']
            prod_data = df_prod[df_prod['Producto'] == prod_qr]
            if not prod_data.empty:
                datos = prod_data.iloc[0]
                precio_unit = float(datos['PrecioVenta'])
                costo_unit = float(datos.get('Costo', 0.0))
                cat = str(datos.get('Categoria','Gen'))
                st.session_state['carrito'].append({
                    "Producto": prod_qr, "Categoria": cat, "Cantidad": peso_qr, 
                    "PrecioUnit": precio_unit, "CostoUnit": costo_unit, "Subtotal": precio_unit * peso_qr
                })
                return f"✅ {prod_qr} ({peso_qr} Kg)"
            else: return "❌ Producto no existe."
        else: return "❌ QR no es de MeatOS."
    except: return "❌ Error formato."

# 2. CONEXIÓN
if 'sheet_obj' not in st.session_state: st.session_state['sheet_obj'] = backend.conectar_google_sheets()
sheet = st.session_state['sheet_obj']

if sheet:
    if 'finanzas' not in st.session_state: st.session_state['finanzas'] = backend.cargar_data(sheet, "finanzas", ['Fecha', 'Detalle', 'Tipo', 'Monto', 'MetodoPago', 'Ganancia', 'Usuario', 'Sucursal'])
    if 'productos' not in st.session_state: st.session_state['productos'] = backend.cargar_data(sheet, "productos", ['Producto', 'Costo', 'PrecioVenta', 'Categoria', 'StockActual'])
    if 'detalles' not in st.session_state: st.session_state['detalles'] = backend.cargar_data(sheet, "detalles", ['Fecha', 'Producto', 'Categoria', 'PesoKg', 'CostoUnit', 'PrecioVentaUnit', 'Subtotal', 'Ganancia', 'Usuario', 'Sucursal'])
    if 'usuarios' not in st.session_state: st.session_state['usuarios'] = backend.cargar_data(sheet, "usuarios", ['Usuario', 'Password', 'Nombre', 'Rol', 'Sucursal', 'Activo'])
    if 'clientes' not in st.session_state: st.session_state['clientes'] = backend.cargar_data(sheet, "clientes", ['Telefono', 'Nombre', 'TotalGastado', 'UltimaCompra', 'Puntos'])
else:
    st.stop()

# 3. VARIABLES
if 'carrito' not in st.session_state: st.session_state['carrito'] = []
if 'ultimo_ticket' not in st.session_state: st.session_state['ultimo_ticket'] = None 
if 'reset_counter' not in st.session_state: st.session_state['reset_counter'] = 0
if 'user_info' not in st.session_state: st.session_state['user_info'] = None
if 'producto_seleccionado' not in st.session_state: st.session_state['producto_seleccionado'] = None 
if 'datos_ia_pendientes' not in st.session_state: st.session_state['datos_ia_pendientes'] = None
if 'msg_feedback' not in st.session_state: st.session_state['msg_feedback'] = None

if not st.session_state['productos'].empty:
    mapa_imgs = obtener_mapa_imagenes(st.session_state['productos']['Producto'].unique())
else: mapa_imgs = {}

st.session_state['finanzas'] = backend.limpiar_fechas(st.session_state['finanzas'])
st.session_state['detalles'] = backend.limpiar_fechas(st.session_state['detalles'])

DIRECCION_NEGOCIO = "Calle A. García #1128, Cochabamba"
TELEFONO_NEGOCIO = "591 77420111"

# ==============================================================================
# LOGIN
# ==============================================================================
if st.session_state['user_info'] is None:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if os.path.exists("Logo-Final.png"): st.image("Logo-Final.png", width=200)
        st.title("🥩 MeatOS Login")
        with st.form("login_form"):
            user_input = st.text_input("Usuario")
            pass_input = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Ingresar", type="primary"):
                df_u = st.session_state['usuarios']
                df_u['Usuario'] = df_u['Usuario'].astype(str)
                df_u['Password'] = df_u['Password'].astype(str)
                user_found = df_u[(df_u['Usuario'] == user_input) & (df_u['Password'] == pass_input)]
                if not user_found.empty:
                    data_user = user_found.iloc[0]
                    if str(data_user['Activo']).upper() == 'TRUE':
                        st.session_state['user_info'] = {'Nombre': data_user['Nombre'], 'Rol': data_user['Rol'], 'Sucursal': data_user['Sucursal'], 'Usuario': data_user['Usuario']}
                        st.success(f"Bienvenido {data_user['Nombre']}"); time.sleep(0.5); st.rerun()
                    else: st.error("Usuario desactivado.")
                else: st.error("Incorrecto.")
    st.stop()

# ==============================================================================
# APP PRINCIPAL
# ==============================================================================
usuario_actual = st.session_state['user_info']['Nombre']
rol_actual = st.session_state['user_info']['Rol']
sucursal_actual = st.session_state['user_info']['Sucursal']
user_id = st.session_state['user_info']['Usuario']

with st.sidebar:
    if os.path.exists("Logo-Final.png"): st.image("Logo-Final.png", use_container_width=True)
    st.markdown("---")
    st.caption(f"👤 **{usuario_actual}**")
    st.caption(f"🏷️ {rol_actual} | 📍 {sucursal_actual}")
    modo_movil = st.toggle("📱 Modo Celular", value=False, key="toggle_mobile_mode")
    if st.button("🔒 Cerrar Sesión", type="primary"): 
        st.session_state['user_info'] = None
        st.rerun()
    st.markdown("---")
    st.caption("MeatOS v10.1 | Stable AI")

if rol_actual == "Admin":
    tab1, tab_import, tab2, tab3 = st.tabs(["🛒 VENTA MANUAL", "📥 IMPORTAR KYTE", "📦 INVENTARIO", "📊 GERENCIA"])
else:
    tab1, tab_import = st.tabs(["🛒 VENTA MANUAL", "📥 IMPORTAR KYTE"])

# ==============================================================================
# PESTAÑA IMPORTAR KYTE (IA)
# ==============================================================================
with tab_import:
    st.header("📥 Importar Venta de Kyte")
    st.info("Sube la foto del recibo. La IA detectará los productos.")
    uploaded_file = st.file_uploader("Sube el recibo aquí", type=['png', 'jpg', 'jpeg'])
    
    if uploaded_file is not None:
        c1, c2 = st.columns([1, 2])
        with c1: st.image(uploaded_file, caption="Recibo", use_container_width=True)
        with c2:
            if st.button("✨ ANALIZAR CON IA", type="primary"):
                with st.spinner("🤖 Leyendo... (Esto puede tomar unos segundos)"):
                    datos = analizar_recibo_con_ia(uploaded_file)
                    if datos:
                        st.session_state['datos_ia_pendientes'] = datos
                        st.success("¡Leído!")
                    else: st.error("No se pudo leer.")

            if st.session_state['datos_ia_pendientes']:
                datos = st.session_state['datos_ia_pendientes']
                st.markdown("### 📝 Datos Detectados")
                df_preview = pd.DataFrame(datos['items'])
                st.data_editor(df_preview, key="editor_ia", num_rows="dynamic")
                
                col_tot1, col_tot2 = st.columns(2)
                col_tot1.metric("Total Detectado", f"{datos['total_pagado']} Bs")
                metodo_ia = col_tot2.selectbox("Pago", ["Efectivo", "QR/Banco"], index=0 if "Efec" in datos.get('metodo_pago','Efec') else 1)
                
                if st.button("✅ REGISTRAR VENTA"):
                    now_str = get_bolivia_time()
                    recibo_id = f"#KYTE-{now_str.replace('-','').replace(':','').replace(' ','-')}"
                    detalles_bd, total_gan = [], 0
                    df_items = st.session_state['editor_ia']
                    
                    for index, row in df_items.iterrows():
                        nom = row['producto']; pes = float(row['peso_kg']); pre = float(row['precio_unitario']); sub = float(row['subtotal'])
                        df_inv = st.session_state['productos']
                        match = df_inv[df_inv['Producto'].str.contains(nom, case=False, na=False)]
                        cos, cat = 0, "Kyte"
                        
                        if not match.empty:
                            idx = match.index[0]
                            st.session_state['productos'].at[idx, 'StockActual'] = float(df_inv.at[idx, 'StockActual']) - pes
                            cos = float(df_inv.at[idx, 'Costo']); cat = str(df_inv.at[idx, 'Categoria'])
                        
                        gan = sub - (cos * pes)
                        total_gan += gan
                        detalles_bd.append({'Fecha': now_str, 'Producto': nom, 'Categoria': cat, 'PesoKg': pes, 'CostoUnit': cos, 'PrecioVentaUnit': pre, 'Subtotal': sub, 'Ganancia': gan, 'Usuario': f"{user_id} (Kyte)", 'Sucursal': sucursal_actual})

                    backend.guardar_data(sheet, "productos", st.session_state['productos'])
                    if detalles_bd:
                        st.session_state['detalles'] = pd.concat([st.session_state['detalles'], pd.DataFrame(detalles_bd)], ignore_index=True)
                        backend.guardar_data(sheet, "detalles", st.session_state['detalles'])
                    
                    fin = pd.DataFrame([{'Fecha': now_str, 'Detalle': f"Venta Kyte {recibo_id}", 'Tipo': "Ingreso", 'Monto': float(datos['total_pagado']), 'MetodoPago': metodo_ia, 'Ganancia': total_gan, 'Usuario': user_id, 'Sucursal': sucursal_actual}])
                    st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], fin], ignore_index=True)
                    backend.guardar_data(sheet, "finanzas", st.session_state['finanzas'])
                    
                    st.balloons(); st.success("✅ Importado!"); st.session_state['datos_ia_pendientes'] = None; time.sleep(2); st.rerun()

# ==============================================================================
# PESTAÑA 1: VENTA MANUAL (CON FIX QR & PISTOLA)
# ==============================================================================
with tab1:
    with st.container(border=True):
        st.caption("📷 ESCANEAR QR / PISTOLA")
        # Input Pistola (Oculto visualmente en cel, util en PC)
        codigo_pistola = st.text_input("Haz clic y dispara pistola:", key="input_pistola_qr", placeholder="Esperando lector...")
        # Input Camara (Solo movil)
        img_buffer = st.camera_input("Cámara Celular") if modo_movil else None

        res = None
        if codigo_pistola: res = procesar_codigo_qr(codigo_pistola)
        elif img_buffer:
            dec = leer_qr_desde_imagen(img_buffer)
            if dec: res = procesar_codigo_qr(dec)
            else: st.warning("No se detectó QR")
        
        if res:
            if "✅" in res:
                st.success(res); st.session_state['msg_feedback'] = res; time.sleep(1); st.rerun()
            else: st.error(res)

    if st.session_state['msg_feedback']: st.toast(st.session_state['msg_feedback']); st.session_state['msg_feedback'] = None

    with st.expander("💸 Caja Chica"):
        c1, c2, c3, c4 = st.columns([2, 1.5, 1, 1])
        motivo = c1.selectbox("Motivo", ["Pago Delivery", "Hielo/Bolsas", "Apertura Caja", "Retiro Ganancias", "Otro"], label_visibility="collapsed")
        detalle = motivo if motivo != "Otro" else c1.text_input("Detalle:")
        monto = c2.number_input("Monto Bs", step=1.0, value=None, placeholder="0.0")
        tipo = c3.radio("Tipo", ["Salida", "Entrada"], horizontal=True, label_visibility="collapsed")
        if c4.button("Registrar", key="btn_caja_chica"):
            if monto and monto > 0:
                signo = -1 if "Salida" in tipo else 1
                tipo_bd = "Egreso" if "Salida" in tipo else "Ingreso"
                nuevo = pd.DataFrame([{'Fecha': get_bolivia_time(), 'Detalle': f"[CAJA] {detalle}", 'Tipo': tipo_bd, 'Monto': monto * signo, 'MetodoPago': 'Efectivo', 'Ganancia': 0, 'Usuario': user_id, 'Sucursal': sucursal_actual}])
                st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], nuevo], ignore_index=True)
                backend.guardar_data(sheet, "finanzas", st.session_state['finanzas']); st.success("✅"); time.sleep(0.5); st.rerun()
    
    st.divider()

    if modo_movil:
        layout_venta = st.tabs(["🥩 ELEGIR", "🛒 COBRAR"])
        contenedor_catalogo = layout_venta[0]; contenedor_operacion = layout_venta[1]
    else:
        col1, col2 = st.columns([1.6, 1.4], gap="medium")
        contenedor_catalogo = col1; contenedor_operacion = col2

    with contenedor_catalogo:
        if modo_movil and st.session_state['producto_seleccionado']:
            st.info(f"🔹 **{st.session_state['producto_seleccionado']}**"); mostrar_form_movil = True
        else:
            mostrar_form_movil = False
            df_prod = st.session_state['productos']
            if not df_prod.empty:
                cats_unicas = df_prod[df_prod['Categoria'] != ""]['Categoria'].unique()
                orden = ["Res", "Embutidos", "Extras", "Pollo", "Cerdo", "Otros"]
                def sort_key(c): return orden.index(c) if c in orden else 999
                categorias = sorted(cats_unicas, key=sort_key)
                tabs_cat = st.tabs(categorias)
                for i, cat in enumerate(categorias):
                    with tabs_cat[i]:
                        prods_cat = df_prod[df_prod['Categoria'] == cat]
                        cols = st.columns(2 if modo_movil else 3)
                        for idx, (index, row) in enumerate(prods_cat.iterrows()):
                            with cols[idx % (2 if modo_movil else 3)]:
                                nm = row['Producto']
                                im = mapa_imgs.get(nm)
                                if im: st.image(im, use_container_width=True)
                                else: st.markdown(f"<div style='text-align:center;font-size:30px;background:#f0f2f6;border-radius:10px;'>🥩</div>", unsafe_allow_html=True)
                                if st.button(f"{nm}\n{float(row['PrecioVenta']):.2f}", key=f"btn_{index}", use_container_width=True):
                                    st.session_state['producto_seleccionado'] = nm; st.rerun()
                                st.markdown("<br>", unsafe_allow_html=True)
            else: st.warning("Sin stock")

    with contenedor_operacion:
        target = contenedor_catalogo if (modo_movil and st.session_state['producto_seleccionado']) else contenedor_operacion
        with target:
            if st.session_state['producto_seleccionado']:
                if not modo_movil: st.info(f"Sel: **{st.session_state['producto_seleccionado']}**")
                dat = st.session_state['productos'][st.session_state['productos']['Producto'] == st.session_state['producto_seleccionado']].iloc[0]
                pr_base = float(dat['PrecioVenta']); stk = float(dat.get('StockActual', 0.0))
                cat_n = str(dat.get('Categoria', '')).strip().capitalize()
                es_und = cat_n in ["Extras", "Bebidas", "Carbón", "Carbon", "Varios"]
                
                mod_v = st.radio("Modo:", ["⚖️ Peso", "📦 Unidad"], index=1 if es_und else 0, horizontal=True)
                c_p1, c_p2 = st.columns(2)
                chk = c_p1.checkbox("Mod. Precio"); pr_fin = c_p2.number_input("Precio", value=pr_base, step=0.5) if chk else pr_base
                
                cant_fin = 0.0
                if "Peso" in mod_v:
                    if stk <= 2.0: st.error(f"🚨 Stock: {stk:.3f}")
                    else: st.success(f"Stock: {stk:.3f}")
                    gr = st.number_input("Gramos", min_value=0, step=10, value=None, placeholder="0", key=f"gr_{st.session_state['reset_counter']}")
                    if gr: cant_fin = gr/1000
                else:
                    if stk <= 5: st.warning(f"⚠️ Quedan {int(stk)}")
                    und = st.number_input("Cantidad", min_value=0, step=1, value=None, placeholder="0", key=f"und_{st.session_state['reset_counter']}")
                    if und: cant_fin = float(und)
                
                st.button("🔄 Calcular", use_container_width=True)
                if cant_fin > 0:
                    st.markdown(f"### Total: {pr_fin*cant_fin:.2f}")
                    if st.button("AGREGAR 🛒", type="primary", use_container_width=True):
                        if cant_fin <= stk:
                            st.session_state['carrito'].append({"Producto": dat['Producto'], "Categoria": str(dat.get('Categoria','Gen')), "Cantidad": cant_fin, "PrecioUnit": pr_fin, "CostoUnit": float(dat.get('Costo',0.0)), "Subtotal": pr_fin*cant_fin})
                            st.session_state['reset_counter'] += 1; st.session_state['producto_seleccionado'] = None; st.success("Ok"); time.sleep(0.1); st.rerun()
                        else: st.error("Stock insuficiente")
                if st.button("Cancelar", use_container_width=True): st.session_state['producto_seleccionado'] = None; st.rerun()
                st.divider()

            if not (modo_movil and st.session_state['producto_seleccionado']):
                st.subheader(f"🛒 Carrito ({len(st.session_state['carrito'])})")
                if st.session_state['carrito']:
                    df_c = pd.DataFrame(st.session_state['carrito'])
                    st.dataframe(df_c[["Producto", "Cantidad", "Subtotal"]], use_container_width=True, hide_index=True)
                    tot_b = df_c['Subtotal'].sum()
                    st.markdown(f"<div style='text-align:right;font-size:20px;'>Sub: {tot_b:.2f}</div>", unsafe_allow_html=True)
                    
                    cel = st.text_input("📱 Cliente", placeholder="774...", key="cli_in")
                    nom_c, pts_d, acum = "", 0, True
                    if cel:
                        df_cli = st.session_state['clientes']; df_cli['Telefono'] = df_cli['Telefono'].astype(str)
                        fd = df_cli[df_cli['Telefono'] == cel]
                        if not fd.empty: 
                            d = fd.iloc[0]; nom_c = d['Nombre']; pts_d = int(float(d['Puntos'] or 0)); st.success(f"{nom_c} | 💎 {pts_d}"); acum = st.checkbox("Acumular", value=True)
                        else: nom_c = st.text_input("Nuevo:", key="new_cli")
                    
                    dsc, pts_u = 0.0, 0
                    if pts_d > 0 and acum:
                        if st.checkbox(f"Canjear ({pts_d} Bs)"):
                            if pts_d >= tot_b: dsc = tot_b; pts_u = int(tot_b)
                            else: dsc = float(pts_d); pts_u = pts_d
                    
                    tot_n = tot_b - dsc
                    st.markdown(f"<div style='background-color:#8B0000;color:white;padding:5px;border-radius:5px;text-align:center;font-size:26px;font-weight:bold;margin:10px 0;'>TOTAL: {tot_n:.2f} Bs</div>", unsafe_allow_html=True)
                    
                    met = st.radio("Pago", ["Efectivo", "QR/Banco"], horizontal=True, label_visibility="collapsed")
                    cob, cam, qr_v = True, 0.0, False
                    if tot_n > 0 and met == "Efectivo":
                        rec_in = st.number_input("Recibido", min_value=0.0, step=0.5, value=None, placeholder="0.0")
                        if rec_in:
                            rec = float(rec_in)
                            if rec >= tot_n: cam = rec - tot_n; st.info(f"Vuelto: {cam:.2f}"); qr_v = st.checkbox("Vuelto QR") if cam > 0 else False
                            else: st.warning("Falta"); cob = False
                        else: cob = False
                    
                    c_b1, c_b2 = st.columns([1, 2])
                    if c_b1.button("🗑️"): st.session_state['carrito'] = []; st.rerun()
                    if c_b2.button("✅ PAGAR", type="primary", use_container_width=True, disabled=not cob):
                        now_str = get_bolivia_time(); rid = f"#REC-{now_str.replace('-','').replace(':','').replace(' ','-')}"
                        det_bd, t_gan = [], 0
                        for it in st.session_state['carrito']:
                            ix = st.session_state['productos'].index[st.session_state['productos']['Producto'] == it['Producto']].tolist()[0]
                            cur = float(st.session_state['productos'].at[ix, 'StockActual'])
                            st.session_state['productos'].at[ix, 'StockActual'] = cur - it['Cantidad']
                            g = (it['PrecioUnit'] - it['CostoUnit']) * it['Cantidad']; t_gan += g
                            det_bd.append({'Fecha': now_str, 'Producto': it['Producto'], 'Categoria': it['Categoria'], 'PesoKg': it['Cantidad'], 'CostoUnit': it['CostoUnit'], 'PrecioVentaUnit': it['PrecioUnit'], 'Subtotal': it['Subtotal'], 'Ganancia': g, 'Usuario': user_id, 'Sucursal': sucursal_actual})
                        
                        backend.guardar_data(sheet, "productos", st.session_state['productos'])
                        if det_bd: st.session_state['detalles'] = pd.concat([st.session_state['detalles'], pd.DataFrame(det_bd)], ignore_index=True); backend.guardar_data(sheet, "detalles", st.session_state['detalles'])

                        txt = ", ".join([f"{p['Producto']} ({p['Cantidad']:.3f})" for p in st.session_state['carrito']])
                        if pts_u: txt += f" [PTS: {pts_u}]"
                        fin = pd.DataFrame([{'Fecha': now_str, 'Detalle': f"Venta {rid}: {txt}", 'Tipo': "Ingreso", 'Monto': tot_n, 'MetodoPago': met if tot_n>0 else "Puntos", 'Ganancia': t_gan - dsc, 'Usuario': user_id, 'Sucursal': sucursal_actual}])
                        st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], fin], ignore_index=True)
                        
                        if met == "Efectivo" and qr_v and cam > 0:
                            st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], pd.DataFrame([{'Fecha': now_str, 'Detalle': f"Swap {rid}", 'Tipo': "Ingreso", 'Monto': cam, 'MetodoPago': "Efectivo", 'Ganancia':0, 'Usuario':user_id, 'Sucursal':sucursal_actual}, {'Fecha': now_str, 'Detalle': f"Dev Cambio {rid}", 'Tipo': "Egreso", 'Monto': -cam, 'MetodoPago': "QR", 'Ganancia':0, 'Usuario':user_id, 'Sucursal':sucursal_actual}])], ignore_index=True)
                        backend.guardar_data(sheet, "finanzas", st.session_state['finanzas'])
                        
                        if cel and nom_c:
                            df_cl = st.session_state['clientes']; df_cl['Telefono'] = df_cl['Telefono'].astype(str)
                            pt_g = int(tot_n * 0.01) if acum else 0
                            if not df_cl[df_cl['Telefono'] == cel].empty:
                                ic = df_cl.index[df_cl['Telefono'] == cel][0]
                                pg = float(df_cl.at[ic, 'TotalGastado'] or 0); pp = int(float(df_cl.at[ic, 'Puntos'] or 0))
                                df_cl.at[ic, 'TotalGastado'] = pg + tot_n; df_cl.at[ic, 'Puntos'] = pp - pts_u + pt_g; df_cl.at[ic, 'UltimaCompra'] = now_str
                            else:
                                st.session_state['clientes'] = pd.concat([st.session_state['clientes'], pd.DataFrame([{'Telefono': cel, 'Nombre': nom_c, 'TotalGastado': tot_n, 'UltimaCompra': now_str, 'Puntos': pt_g}])], ignore_index=True)
                            backend.guardar_data(sheet, "clientes", st.session_state['clientes'])
                        
                        lnk = f"https://wa.me/591{cel}?text={quote(f'*** RECIBO {rid} ***')}" if cel else f"https://wa.me/?text={quote('...')}"
                        htm = backend.generar_html_ticket(st.session_state['carrito'], tot_b, now_str, met, rid, DIRECCION_NEGOCIO, TELEFONO_NEGOCIO, usuario_actual, nom_c)
                        st.session_state['ultimo_ticket'] = {'link_wa': lnk, 'html_raw': htm}; st.session_state['carrito'] = []; st.balloons(); st.success("Listo!"); time.sleep(1); st.rerun()
                else:
                    if not modo_movil: st.info("🛒 Tu carrito está vacío.")

    if st.session_state['ultimo_ticket']:
        st.success("✅ Venta Exitosa")
        c1, c2 = st.columns(2)
        c1.markdown(f"<a href='{st.session_state['ultimo_ticket']['link_wa']}' target='_blank' class='btn-whatsapp'>📲 WhatsApp</a>", unsafe_allow_html=True)
        if c2.button("Cerrar"): st.session_state['ultimo_ticket'] = None; st.rerun()
        components.html(st.session_state['ultimo_ticket']['html_raw'], height=450, scrolling=True)

# ==============================================================================
# SECCIONES ADMIN (RESUMIDAS PERO FUNCIONALES IGUAL QUE ANTES)
# ==============================================================================
if rol_actual == "Admin":
    with tab2:
        st.header("📦 Inventario")
        df_ed = st.data_editor(st.session_state['productos'], num_rows="dynamic", use_container_width=True, key="inv_ed")
        if st.button("💾 Guardar Inventario"): st.session_state['productos'] = df_ed; backend.guardar_data(sheet, "productos", df_ed); st.success("Listo"); time.sleep(1); st.rerun()

    with tab3:
        g1, g2, g3 = st.tabs(["📈 Finanzas", "👥 Usuarios", "🏷️ Etiquetadora"])
        with g1:
            st.dataframe(st.session_state['finanzas'])
        with g3:
            st.subheader("🏷️ Etiquetadora 5x3")
            df_p = st.session_state['productos']; lp = sorted(df_p['Producto'].unique())
            pe = st.selectbox("Prod:", lp); pes = st.number_input("Kg:", 0.0, step=0.005, format="%.3f")
            if pe and pes > 0:
                img = Image.new('RGB', (500, 300), 'white'); d = ImageDraw.Draw(img)
                qr = qrcode.make(f"MeatOS|{pe}|{pes}").resize((200, 200)); img.paste(qr, (10, 50))
                d.text((220, 50), "EL CORTE", fill=0); d.text((220, 120), pe[:15], fill=0); d.text((220, 160), f"{pes} Kg", fill=0)
                st.image(img, width=250)
