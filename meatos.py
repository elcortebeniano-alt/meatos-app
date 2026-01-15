import streamlit as st
import pandas as pd
import time
import os
from datetime import datetime, timedelta
from urllib.parse import quote
import streamlit.components.v1 as components

import styles
import backend

# CONFIGURACIÓN INICIAL (Optimizada para evitar recargas innecesarias)
st.set_page_config(page_title="El Corte Beniano | POS", layout="wide", page_icon="🥩", initial_sidebar_state="collapsed")
styles.cargar_css()

def get_bolivia_time(): return (datetime.utcnow() - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M")
def get_bolivia_date(): return (datetime.utcnow() - timedelta(hours=4)).strftime("%Y-%m-%d")

# --- CACHE DE IMÁGENES (Vital para que no salga "In the Oven" por memoria) ---
@st.cache_data(ttl=3600) # Cache por 1 hora
def obtener_mapa_imagenes(lista_productos):
    mapa = {}
    for prod in lista_productos:
        path_png = f"img/{prod}.png"
        path_jpg = f"img/{prod}.jpg"
        if os.path.exists(path_png): mapa[prod] = path_png
        elif os.path.exists(path_jpg): mapa[prod] = path_jpg
        else: mapa[prod] = None 
    return mapa

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

if not st.session_state['productos'].empty:
    mapa_imgs = obtener_mapa_imagenes(st.session_state['productos']['Producto'].unique())
else:
    mapa_imgs = {}

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
    
    # --- INTERRUPTOR MODO CELULAR ---
    modo_movil = st.toggle("📱 Modo Celular", value=False, key="toggle_mobile_mode")
    
    if st.button("🔒 Cerrar Sesión", type="primary"): 
        st.session_state['user_info'] = None
        st.rerun()
    st.markdown("---")
    st.caption("MeatOS v7.5 | Auto-Cat & Stability")

if rol_actual == "Admin":
    tab1, tab2, tab3 = st.tabs(["🛒 PUNTO DE VENTA", "📦 INVENTARIO", "📊 GERENCIA"])
else:
    tab1, = st.tabs(["🛒 PUNTO DE VENTA"])

# ==============================================================================
# PESTAÑA 1: VENTA (DUAL MODE)
# ==============================================================================
with tab1:
    with st.expander("💸 Caja Chica / Gastos Menores"):
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
                backend.guardar_data(sheet, "finanzas", st.session_state['finanzas'])
                st.success("✅"); time.sleep(0.5); st.rerun()
    
    st.divider()

    if modo_movil:
        layout_venta = st.tabs(["🥩 1. ELEGIR PRODUCTOS", "🛒 2. VER CARRITO Y PAGAR"])
        contenedor_catalogo = layout_venta[0]
        contenedor_operacion = layout_venta[1]
    else:
        col1, col2 = st.columns([1.6, 1.4], gap="medium")
        contenedor_catalogo = col1
        contenedor_operacion = col2

    # >>> CONTENEDOR 1: CATALOGO <<<
    with contenedor_catalogo:
        if modo_movil and st.session_state['producto_seleccionado']:
            st.info(f"🔹 **{st.session_state['producto_seleccionado']}**")
            mostrar_form_movil = True
        else:
            mostrar_form_movil = False
            st.subheader("🥩 Catálogo")
            df_prod = st.session_state['productos']
            
            if not df_prod.empty:
                # Ordenamiento VIP: Res > Embutidos > Extras
                categorias_unicas = df_prod[df_prod['Categoria'] != ""]['Categoria'].unique()
                orden_prioridad = ["Res", "Embutidos", "Extras", "Pollo", "Cerdo", "Otros"]
                def sort_key(cat):
                    if cat in orden_prioridad: return orden_prioridad.index(cat)
                    return 999 
                
                categorias = sorted(categorias_unicas, key=sort_key)
                tabs_cat = st.tabs(categorias)
                
                for i, cat in enumerate(categorias):
                    with tabs_cat[i]:
                        prods_cat = df_prod[df_prod['Categoria'] == cat]
                        cols_num = 2 if modo_movil else 3 
                        cols = st.columns(cols_num)
                        for idx, (index, row) in enumerate(prods_cat.iterrows()):
                            with cols[idx % cols_num]:
                                nombre_prod = row['Producto']
                                img_path = mapa_imgs.get(nombre_prod)
                                if img_path: st.image(img_path, use_container_width=True)
                                else: st.markdown(f"<div style='text-align:center;font-size:30px;background:#f0f2f6;border-radius:10px;padding:5px;'>🥩</div>", unsafe_allow_html=True)
                                
                                if st.button(f"{nombre_prod}\n{float(row['PrecioVenta']):.2f}", key=f"btn_prod_{index}", use_container_width=True):
                                    st.session_state['producto_seleccionado'] = nombre_prod
                                    st.rerun()
                                st.markdown("<br>", unsafe_allow_html=True)
            else:
                st.warning("Sin productos.")

    # >>> CONTENEDOR 2: OPERACION <<<
    target_container = contenedor_catalogo if (modo_movil and st.session_state['producto_seleccionado']) else contenedor_operacion
    
    with target_container:
        # 1. ZONA DE PESAJE
        if st.session_state['producto_seleccionado']:
            if not modo_movil: st.info(f"🔹 Seleccionado: **{st.session_state['producto_seleccionado']}**")
            
            df_prod = st.session_state['productos']
            data_sel = df_prod[df_prod['Producto'] == st.session_state['producto_seleccionado']].iloc[0]
            precio_base = float(data_sel['PrecioVenta'])
            stock_actual = float(data_sel.get('StockActual', 0.0))
            
            # --- LÓGICA INTELIGENTE DE UNIDAD/PESO ---
            cat_normalizada = str(data_sel.get('Categoria', '')).strip().capitalize() # Normalizamos
            
            # Lista de Categorías que SIEMPRE son Unidad
            cats_unidad = ["Extras", "Bebidas", "Carbón", "Carbon", "Varios"]
            
            if cat_normalizada in cats_unidad:
                index_modo = 1 # Unidad
            else:
                index_modo = 0 # Peso (Default para Res, Embutidos, etc)

            modo_venta = st.radio("Modo:", ["⚖️ Peso (g)", "📦 Unidad"], index=index_modo, horizontal=True)
            
            c_p1, c_p2 = st.columns(2)
            check_precio = c_p1.checkbox("Mod. Precio")
            precio_final = c_p2.number_input("Precio", value=precio_base, step=0.5) if check_precio else precio_base
            
            cantidad_final = 0.0
            if "Peso" in modo_venta:
                if stock_actual <= 2.0: st.error(f"🚨 Crítico: {stock_actual:.3f} Kg")
                else: st.success(f"✅ Stock: {stock_actual:.3f} Kg")
                
                gr_input = st.number_input("⚖️ PESO (Gramos)", min_value=0, step=10, value=None, placeholder="Escribe gramos...", key=f"peso_input_{st.session_state['reset_counter']}")
                if gr_input:
                    cantidad_final = gr_input / 1000
                    st.caption(f"= {cantidad_final:.3f} Kg")
            else:
                if stock_actual <= 5.0: st.warning(f"⚠️ Quedan {int(stock_actual)}")
                und_input = st.number_input("📦 CANTIDAD", min_value=0, step=1, value=None, placeholder="Escribe cantidad...", key=f"und_{st.session_state['reset_counter']}")
                if und_input:
                    cantidad_final = float(und_input)

            # --- BOTÓN PARA CALCULAR ---
            # Este botón no hace nada lógico, solo recarga la página (rerun)
            # Al recargar, Streamlit lee los inputs que acabas de escribir y actualiza el "Total" abajo.
            st.button("🔄 Calcular Precio", use_container_width=True) 

            if cantidad_final > 0:
                st.markdown(f"### Total: {precio_final*cantidad_final:.2f} Bs")
                if st.button("AGREGAR AL CARRITO 🛒", type="primary", use_container_width=True):
                    if cantidad_final <= stock_actual:
                        st.session_state['carrito'].append({
                            "Producto": data_sel['Producto'], "Categoria": str(data_sel.get('Categoria','Gen')), 
                            "Cantidad": cantidad_final, "PrecioUnit": precio_final, "CostoUnit": float(data_sel.get('Costo',0.0)), 
                            "Subtotal": precio_final*cantidad_final
                        })
                        st.session_state['reset_counter'] += 1
                        st.session_state['producto_seleccionado'] = None
                        st.success("Agregado"); time.sleep(0.1); st.rerun()
                    else: st.error("Stock Insuficiente")
            
            if st.button("Cancelar", use_container_width=True):
                st.session_state['producto_seleccionado'] = None; st.rerun()
            st.divider()

        # 2. CARRITO
        if not (modo_movil and st.session_state['producto_seleccionado']):
            st.subheader(f"🛒 Carrito ({len(st.session_state['carrito'])})")
            if st.session_state['carrito']:
                df_c = pd.DataFrame(st.session_state['carrito'])
                st.dataframe(df_c[["Producto", "Cantidad", "Subtotal"]], use_container_width=True, hide_index=True)
                
                total_bruto = df_c['Subtotal'].sum()
                st.markdown(f"<div style='text-align:right;font-size:20px;'>Subtotal: {total_bruto:.2f}</div>", unsafe_allow_html=True)
                
                cel = st.text_input("📱 Cliente", placeholder="774...", key="input_cel_touch")
                nombre_cliente = ""
                puntos_disp = 0
                acumular = True
                
                if cel:
                    df_cli = st.session_state['clientes']
                    df_cli['Telefono'] = df_cli['Telefono'].astype(str)
                    found = df_cli[df_cli['Telefono'] == cel]
                    if not found.empty:
                        d = found.iloc[0]
                        nombre_cliente = d['Nombre']
                        puntos_disp = int(float(d['Puntos'])) if d['Puntos'] else 0
                        st.success(f"{nombre_cliente} | 💎 {puntos_disp}")
                        acumular = st.checkbox("Acumular", value=True)
                    else:
                        nombre_cliente = st.text_input("Nuevo:", key="new_cli_touch")
                
                desc_pts = 0.0
                pts_usados = 0
                if puntos_disp > 0 and acumular:
                    if st.checkbox(f"Canjear ({puntos_disp} Bs)"):
                        if puntos_disp >= total_bruto:
                            desc_pts = total_bruto; pts_usados = int(total_bruto)
                        else:
                            desc_pts = float(puntos_disp); pts_usados = puntos_disp
                
                total_neto = total_bruto - desc_pts
                st.markdown(f"<div style='background-color:#8B0000;color:white;padding:5px;border-radius:5px;text-align:center;font-size:26px;font-weight:bold;margin:10px 0;'>TOTAL: {total_neto:.2f} Bs</div>", unsafe_allow_html=True)
                
                metodo = st.radio("Pago", ["Efectivo", "QR/Banco"], horizontal=True, label_visibility="collapsed")
                cobrar = True
                cambio = 0.0
                qr_vuelto = False
                
                if total_neto > 0 and metodo == "Efectivo":
                    recibido_input = st.number_input("Recibido", min_value=0.0, step=0.5, value=None, placeholder="0.0")
                    if recibido_input:
                        recibido = float(recibido_input)
                        if recibido >= total_neto:
                            cambio = recibido - total_neto
                            st.info(f"Vuelto: {cambio:.2f}")
                            if cambio > 0: qr_vuelto = st.checkbox("Vuelto QR")
                        else: st.warning("Falta"); cobrar = False
                    else: cobrar = False
                
                c_btn1, c_btn2 = st.columns([1, 2])
                if c_btn1.button("🗑️"): st.session_state['carrito'] = []; st.rerun()
                if c_btn2.button("✅ PAGAR", type="primary", use_container_width=True, disabled=not cobrar):
                    now_str = get_bolivia_time()
                    recibo_id = f"#REC-{now_str.replace('-','').replace(':','').replace(' ','-')}"
                    detalles, total_gan = [], 0
                    for item in st.session_state['carrito']:
                        idx = st.session_state['productos'].index[st.session_state['productos']['Producto'] == item['Producto']].tolist()[0]
                        curr = float(st.session_state['productos'].at[idx, 'StockActual'])
                        st.session_state['productos'].at[idx, 'StockActual'] = curr - item['Cantidad']
                        g = (item['PrecioUnit'] - item['CostoUnit']) * item['Cantidad']
                        total_gan += g
                        detalles.append({'Fecha': now_str, 'Producto': item['Producto'], 'Categoria': item['Categoria'], 'PesoKg': item['Cantidad'], 'CostoUnit': item['CostoUnit'], 'PrecioVentaUnit': item['PrecioUnit'], 'Subtotal': item['Subtotal'], 'Ganancia': g, 'Usuario': user_id, 'Sucursal': sucursal_actual})
                    
                    backend.guardar_data(sheet, "productos", st.session_state['productos'])
                    if detalles: st.session_state['detalles'] = pd.concat([st.session_state['detalles'], pd.DataFrame(detalles)], ignore_index=True); backend.guardar_data(sheet, "detalles", st.session_state['detalles'])

                    txt = ", ".join([f"{p['Producto']} ({p['Cantidad']:.3f})" for p in st.session_state['carrito']])
                    if pts_usados: txt += f" [PTS: {pts_usados}]"
                    fin = pd.DataFrame([{'Fecha': now_str, 'Detalle': f"Venta {recibo_id}: {txt}", 'Tipo': "Ingreso", 'Monto': total_neto, 'MetodoPago': metodo if total_neto>0 else "Puntos", 'Ganancia': total_gan - desc_pts, 'Usuario': user_id, 'Sucursal': sucursal_actual}])
                    st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], fin], ignore_index=True)
                    
                    if metodo == "Efectivo" and qr_vuelto and cambio > 0:
                        st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], pd.DataFrame([{'Fecha': now_str, 'Detalle': f"Swap {recibo_id}", 'Tipo': "Ingreso", 'Monto': cambio, 'MetodoPago': "Efectivo", 'Ganancia':0, 'Usuario':user_id, 'Sucursal':sucursal_actual}, {'Fecha': now_str, 'Detalle': f"Dev Cambio {recibo_id}", 'Tipo': "Egreso", 'Monto': -cambio, 'MetodoPago': "QR", 'Ganancia':0, 'Usuario':user_id, 'Sucursal':sucursal_actual}])], ignore_index=True)
                    backend.guardar_data(sheet, "finanzas", st.session_state['finanzas'])
                    
                    if cel and nombre_cliente:
                        df_cli = st.session_state['clientes']
                        df_cli['Telefono'] = df_cli['Telefono'].astype(str)
                        pts_ganados = int(total_neto * 0.01) if acumular else 0
                        if not df_cli[df_cli['Telefono'] == cel].empty:
                            idx = df_cli.index[df_cli['Telefono'] == cel][0]
                            prev_g = float(df_cli.at[idx, 'TotalGastado'] or 0)
                            prev_p = int(float(df_cli.at[idx, 'Puntos'] or 0))
                            df_cli.at[idx, 'TotalGastado'] = prev_g + total_neto
                            df_cli.at[idx, 'Puntos'] = prev_p - pts_usados + pts_ganados
                            df_cli.at[idx, 'UltimaCompra'] = now_str
                        else:
                            st.session_state['clientes'] = pd.concat([st.session_state['clientes'], pd.DataFrame([{'Telefono': cel, 'Nombre': nombre_cliente, 'TotalGastado': total_neto, 'UltimaCompra': now_str, 'Puntos': pts_ganados}])], ignore_index=True)
                        backend.guardar_data(sheet, "clientes", st.session_state['clientes'])
                    
                    lineas = "\n".join([f"> {p['Producto']} ({p['Cantidad']:.3f}) - {p['Subtotal']:.2f}" for p in st.session_state['carrito']])
                    msg = f"*** EL CORTE BENIANO ***\nRecibo: {recibo_id}\nCliente: {nombre_cliente}\nTotal: {total_neto:.2f}\n{lineas}"
                    link = f"https://wa.me/591{cel}?text={quote(msg)}" if cel else f"https://wa.me/?text={quote(msg)}"
                    html = backend.generar_html_ticket(st.session_state['carrito'], total_bruto, now_str, metodo, recibo_id, DIRECCION_NEGOCIO, TELEFONO_NEGOCIO, usuario_actual, nombre_cliente)
                    st.session_state['ultimo_ticket'] = {'link_wa': link, 'html_raw': html}
                    st.session_state['carrito'] = []
                    st.balloons(); st.success("Listo!"); time.sleep(1); st.rerun()
            else:
                if not modo_movil:
                    st.info("🛒 Tu carrito está vacío.")

    if st.session_state['ultimo_ticket']:
        st.success("✅ Venta Exitosa")
        c1, c2 = st.columns(2)
        c1.markdown(f"<a href='{st.session_state['ultimo_ticket']['link_wa']}' target='_blank' class='btn-whatsapp'>📲 WhatsApp</a>", unsafe_allow_html=True)
        if c2.button("Cerrar"): st.session_state['ultimo_ticket'] = None; st.rerun()
        components.html(st.session_state['ultimo_ticket']['html_raw'], height=450, scrolling=True)

# ==============================================================================
# SECCIONES ADMIN (INVENTARIO Y GERENCIA - MANTENIDAS)
# ==============================================================================
if rol_actual == "Admin":
    with tab2:
        st.header("📦 Inventario")
        df_inv = st.session_state['productos'].copy()
        df_inv['StockActual'] = pd.to_numeric(df_inv['StockActual'], errors='coerce').fillna(0.0)
        criticos = df_inv[df_inv['StockActual'] <= 5.0]
        if not criticos.empty: st.error(f"🛑 **{len(criticos)} Críticos**"); st.dataframe(criticos[['Producto', 'StockActual']], use_container_width=True, hide_index=True)
        
        with st.expander("➕ Nuevo Producto"):
            with st.form("alta", clear_on_submit=True):
                c1, c2 = st.columns(2); n = c1.text_input("Nombre"); c = c2.selectbox("Cat", ["Res", "Pollo", "Cerdo", "Embutidos", "Extras", "Otros"])
                c3, c4, c5 = st.columns(3); pv = c3.number_input("P. Venta", 0.0); pc = c4.number_input("Costo", 0.0); s = c5.number_input("Stock", 0.0)
                if st.form_submit_button("Guardar") and n:
                    nuevo = pd.DataFrame([{'Producto': n, 'Categoria': c, 'Costo': pc, 'PrecioVenta': pv, 'StockActual': s}])
                    st.session_state['productos'] = pd.concat([st.session_state['productos'], nuevo], ignore_index=True)
                    backend.guardar_data(sheet, "productos", st.session_state['productos']); st.success("Guardado"); time.sleep(1); st.rerun()
        df_ed = st.data_editor(st.session_state['productos'], num_rows="dynamic", use_container_width=True, key="inv_ed")
        if st.button("💾 Guardar Inventario"): st.session_state['productos'] = df_ed; backend.guardar_data(sheet, "productos", df_ed); st.success("Listo"); time.sleep(1); st.rerun()

    with tab3:
        st.header("📊 Gerencia")
        g1, g2 = st.tabs(["📈 Finanzas", "👥 Usuarios"])
        with g1:
            df_f = st.session_state['finanzas']
            if not df_f.empty:
                df_f['Monto'] = pd.to_numeric(df_f['Monto'], errors='coerce').fillna(0.0)
                df_f['Ganancia'] = pd.to_numeric(df_f['Ganancia'], errors='coerce').fillna(0.0)
                ingresos = df_f[df_f['Tipo'] == 'Ingreso']['Monto'].sum()
                util_bruta = df_f[df_f['Ganancia'] > 0]['Ganancia'].sum()
                gastos = df_f[(df_f['Tipo'] == 'Egreso') & (df_f['Detalle'].str.contains('ADMIN', na=False))]['Monto'].sum()
                saldo_efectivo = df_f[df_f['MetodoPago'].str.contains('Efectivo', na=False, case=False)]['Monto'].sum()
                saldo_qr = df_f[df_f['MetodoPago'].str.contains('QR', na=False, case=False) | df_f['MetodoPago'].str.contains('Banco', na=False, case=False)]['Monto'].sum()
                
                k1, k2, k3 = st.columns(3)
                k1.metric("Utilidad Bruta", f"{util_bruta:.2f}")
                k2.metric("Gastos Fijos", f"{gastos:.2f}")
                k3.metric("Neta Real", f"{util_bruta+gastos:.2f}")
                t1, t2, t3 = st.columns(3)
                t1.metric("En Caja", f"{saldo_efectivo:.2f}")
                t2.metric("En Banco", f"{saldo_qr:.2f}")
                t3.metric("Flujo Total", f"{ingresos:.2f}")
                
                df_editor = st.data_editor(df_f, num_rows="dynamic", key="fin_main")
                if st.button("💾 Guardar Finanzas"): 
                    st.session_state['finanzas'] = df_editor
                    backend.guardar_data(sheet, "finanzas", df_editor); st.success("Ok"); time.sleep(1); st.rerun()
                
                with st.expander("Registrar Gasto"):
                    c1, c2, c3 = st.columns(3)
                    d = c1.text_input("Detalle"); m = c2.number_input("Monto", value=None, placeholder="0"); o = c3.selectbox("Origen", ["Efectivo", "QR"])
                    if st.button("Registrar", key="btn_gasto_admin"):
                        if m and m > 0:
                            n = pd.DataFrame([{'Fecha': get_bolivia_time(), 'Detalle': f"[ADMIN] {d}", 'Tipo': "Egreso", 'Monto': -m, 'MetodoPago': o, 'Ganancia': -m, 'Usuario': user_id, 'Sucursal': sucursal_actual}])
                            st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], n], ignore_index=True)
                            backend.guardar_data(sheet, "finanzas", st.session_state['finanzas']); st.rerun()
        with g2:
             st.write("Gestión de Usuarios")
             with st.expander("➕ Usuario"):
                with st.form("new_u"):
                    u, p, n, r, s = st.text_input("User"), st.text_input("Pass"), st.text_input("Nombre"), st.selectbox("Rol", ["Vendedor", "Admin"]), st.text_input("Sucursal", "Matriz")
                    if st.form_submit_button("Crear"):
                        nuevo = pd.DataFrame([{'Usuario': u, 'Password': p, 'Nombre': n, 'Rol': r, 'Sucursal': s, 'Activo': 'TRUE'}])
                        st.session_state['usuarios'] = pd.concat([st.session_state['usuarios'], nuevo], ignore_index=True)
                        backend.guardar_data(sheet, "usuarios", st.session_state['usuarios']); st.success("Creado"); time.sleep(1); st.rerun()
             df_u_ed = st.data_editor(st.session_state['usuarios'], num_rows="dynamic")
             if st.button("Guardar Users"): st.session_state['usuarios'] = df_u_ed; backend.guardar_data(sheet, "usuarios", st.session_state['usuarios']); st.rerun()
