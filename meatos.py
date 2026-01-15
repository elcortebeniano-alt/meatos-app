import streamlit as st
import pandas as pd
import time
import os
from datetime import datetime, timedelta
from urllib.parse import quote
import streamlit.components.v1 as components

# --- IMPORTACIÓN DE MÓDULOS PROPIOS ---
import styles
import backend

# CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="El Corte Beniano | POS", layout="wide", page_icon="🥩", initial_sidebar_state="collapsed")

# 1. CARGAR DISEÑO
styles.cargar_css()

# --- FUNCIONES DE HORA ---
def get_bolivia_time(): return (datetime.utcnow() - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M")
def get_bolivia_date(): return (datetime.utcnow() - timedelta(hours=4)).strftime("%Y-%m-%d")

# 2. CONEXIÓN Y CARGA INICIAL
if 'sheet_obj' not in st.session_state: st.session_state['sheet_obj'] = backend.conectar_google_sheets()
sheet = st.session_state['sheet_obj']

if sheet:
    # CARGAR TABLAS
    if 'finanzas' not in st.session_state: st.session_state['finanzas'] = backend.cargar_data(sheet, "finanzas", ['Fecha', 'Detalle', 'Tipo', 'Monto', 'MetodoPago', 'Ganancia', 'Usuario', 'Sucursal'])
    if 'productos' not in st.session_state: st.session_state['productos'] = backend.cargar_data(sheet, "productos", ['Producto', 'Costo', 'PrecioVenta', 'Categoria', 'StockActual'])
    if 'detalles' not in st.session_state: st.session_state['detalles'] = backend.cargar_data(sheet, "detalles", ['Fecha', 'Producto', 'Categoria', 'PesoKg', 'CostoUnit', 'PrecioVentaUnit', 'Subtotal', 'Ganancia', 'Usuario', 'Sucursal'])
    if 'usuarios' not in st.session_state: st.session_state['usuarios'] = backend.cargar_data(sheet, "usuarios", ['Usuario', 'Password', 'Nombre', 'Rol', 'Sucursal', 'Activo'])
else:
    st.stop()

# 3. VARIABLES DE ESTADO
if 'carrito' not in st.session_state: st.session_state['carrito'] = []
if 'ultimo_ticket' not in st.session_state: st.session_state['ultimo_ticket'] = None 
if 'reset_counter' not in st.session_state: st.session_state['reset_counter'] = 0
if 'user_info' not in st.session_state: st.session_state['user_info'] = None

# LIMPIEZA
st.session_state['finanzas'] = backend.limpiar_fechas(st.session_state['finanzas'])
st.session_state['detalles'] = backend.limpiar_fechas(st.session_state['detalles'])

# DATOS NEGOCIO
DIRECCION_NEGOCIO = "Calle A. García #1128, Cochabamba"
TELEFONO_NEGOCIO = "591 77420111"

# ==============================================================================
# 🔐 SISTEMA DE LOGIN
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
            submitted = st.form_submit_button("Ingresar", type="primary")
            
            if submitted:
                df_u = st.session_state['usuarios']
                df_u['Usuario'] = df_u['Usuario'].astype(str)
                df_u['Password'] = df_u['Password'].astype(str)
                
                user_found = df_u[(df_u['Usuario'] == user_input) & (df_u['Password'] == pass_input)]
                
                if not user_found.empty:
                    data_user = user_found.iloc[0]
                    if str(data_user['Activo']).upper() == 'TRUE':
                        st.session_state['user_info'] = {
                            'Nombre': data_user['Nombre'],
                            'Rol': data_user['Rol'],
                            'Sucursal': data_user['Sucursal'],
                            'Usuario': data_user['Usuario']
                        }
                        st.success(f"Bienvenido {data_user['Nombre']}")
                        time.sleep(0.5); st.rerun()
                    else:
                        st.error("Usuario desactivado.")
                else:
                    st.error("Usuario o contraseña incorrectos.")
    st.stop()

# ==============================================================================
# 🚀 APLICACIÓN PRINCIPAL
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
    
    if st.button("🔒 Cerrar Sesión", type="primary"):
        st.session_state['user_info'] = None
        st.rerun()
    st.markdown("---")
    st.caption("MeatOS v5.3 | Stock Alert")

if rol_actual == "Admin":
    tab1, tab2, tab3 = st.tabs(["🛒 PUNTO DE VENTA", "📦 INVENTARIO", "📊 GERENCIA"])
else:
    tab1, = st.tabs(["🛒 PUNTO DE VENTA"])

# ==============================================================================
# PESTAÑA 1: VENTA
# ==============================================================================
with tab1:
    st.title(f"Caja - {sucursal_actual}")
    
    with st.expander("💸 Gastos / Movimientos de Caja"):
        c1, c2, c3, c4 = st.columns([2, 1.5, 1, 1])
        opciones = ["Pago Delivery", "Hielo/Bolsas", "Apertura Caja", "Retiro Ganancias", "Otro"]
        motivo = c1.selectbox("Motivo", opciones, label_visibility="collapsed", key="sel_motivo_caja")
        detalle = motivo if motivo != "Otro" else c1.text_input("Detalle:", key="input_detalle_caja")
        monto = c2.number_input("Monto Bs", 0.0, step=1.0, key="input_monto_caja")
        tipo = c3.radio("Tipo", ["Salida", "Entrada"], horizontal=True, label_visibility="collapsed", key="radio_tipo_caja")
        
        if c4.button("Registrar", key="btn_caja"):
            if monto > 0:
                signo = -1 if "Salida" in tipo else 1
                tipo_bd = "Egreso" if "Salida" in tipo else "Ingreso"
                nuevo = pd.DataFrame([{
                    'Fecha': get_bolivia_time(), 'Detalle': f"[CAJA] {detalle}", 'Tipo': tipo_bd, 
                    'Monto': monto * signo, 'MetodoPago': 'Efectivo', 'Ganancia': 0,
                    'Usuario': user_id, 'Sucursal': sucursal_actual
                }])
                st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], nuevo], ignore_index=True)
                backend.guardar_data(sheet, "finanzas", st.session_state['finanzas'])
                st.success("✅ Registrado"); time.sleep(1); st.rerun()

    st.divider()
    col_izq, col_der = st.columns([1.2, 1.8], gap="large")

    with col_izq:
        st.subheader("🥩 Selección")
        df_prod = st.session_state['productos']
        if not df_prod.empty:
            lista = sorted(df_prod[df_prod['Producto'] != ""]['Producto'].unique())
            prod_sel = st.selectbox("Buscar Producto...", lista, key="sel_producto_venta")
            if prod_sel:
                data = df_prod[df_prod['Producto'] == prod_sel].iloc[0]
                precio_base = float(data['PrecioVenta'])
                stock_actual = float(data.get('StockActual',0.0)) # Convertir a float para comparar

                with st.container(border=True):
                    check = st.checkbox("🔓 Modificar Precio", key="check_precio_manual")
                    precio_final = st.number_input("Precio Venta", value=precio_base, step=0.5, key="input_precio_final") if check else precio_base
                    
                    # --- SEMÁFORO DE STOCK (VISUAL) ---
                    c_stock1, c_stock2 = st.columns([1, 2])
                    c_stock1.metric("Stock Disp.", f"{stock_actual:.3f} Kg")
                    
                    with c_stock2:
                        if stock_actual <= 2.0:
                            st.error(f"🚨 **CRÍTICO**: Queda muy poco.")
                        elif stock_actual <= 10.0:
                            st.warning(f"⚠️ **BAJO**: Reponer pronto.")
                        else:
                            st.success(f"✅ **OK**: Stock saludable.")
                
                gr = st.number_input("Gramos", 0, step=10, key=f"peso_{st.session_state['reset_counter']}", label_visibility="collapsed")
                kg = gr / 1000
                if kg > 0: st.info(f"Total: **{(precio_final*kg):.2f} Bs** ({kg:.3f} Kg)")
                
                if st.button("AGREGAR ➕", type="primary", key="btn_add_carrito"):
                    if gr > 0 and kg <= stock_actual:
                        st.session_state['carrito'].append({
                            "Producto": prod_sel, "Categoria": str(data.get('Categoria','Gen')), "Cantidad": kg,
                            "PrecioUnit": precio_final, "CostoUnit": float(data.get('Costo',0.0)), "Subtotal": precio_final*kg
                        })
                        st.session_state['reset_counter'] += 1
                        st.success("Agregado"); time.sleep(0.2); st.rerun()
                    else: st.error("❌ Stock insuficiente")
        else: st.warning("Sin productos.")

    with col_der:
        st.subheader("🛒 Carrito")
        if st.session_state['carrito']:
            df_c = pd.DataFrame(st.session_state['carrito'])
            st.dataframe(df_c[["Producto", "Cantidad", "PrecioUnit", "Subtotal"]], use_container_width=True, hide_index=True)
            total = df_c['Subtotal'].sum()
            total_ganancia = sum([(r['PrecioUnit'] - r['CostoUnit']) * r['Cantidad'] for r in st.session_state['carrito']])
            
            st.markdown(f"<div style='background-color:white;padding:15px;border-radius:10px;text-align:right;border:2px solid #8B0000;margin-bottom:20px;'><span style='font-size:36px;font-weight:800;color:#8B0000;'>{total:.2f} Bs</span></div>", unsafe_allow_html=True)
            
            st.write("---")
            c1, c2 = st.columns([1, 1.5])
            cel = c1.text_input("📱 WhatsApp", placeholder="70712345", key="input_celular")
            metodo = c2.radio("Pago", ["💵 Efectivo", "📱 QR / Banco"], horizontal=True, key="radio_metodo_pago")
            
            pago, cambio, qr_vuelto, cobrar = 0.0, 0.0, False, True
            if metodo == "💵 Efectivo":
                pago = st.number_input("Recibido:", 0.0, step=0.5, key="input_pago_cliente")
                if pago >= total:
                    cambio = pago - total
                    st.info(f"💰 Vuelto: **{cambio:.2f} Bs**")
                    if cambio > 0: qr_vuelto = st.checkbox("🔄 Vuelto por QR", key="check_vuelto_qr")
                else: 
                    if pago > 0: st.error(f"Falta: {total-pago:.2f}"); cobrar = False
                    else: st.warning("Ingrese monto"); cobrar = False
            
            b1, b2 = st.columns([1, 2])
            if b1.button("🗑️", key="btn_borrar_carrito"): st.session_state['carrito'] = []; st.rerun()
            if b2.button("✅ COBRAR", type="primary", disabled=not cobrar, key="btn_cobrar_final"):
                now_str = get_bolivia_time()
                recibo_id = f"#REC-{now_str.replace('-','').replace(':','').replace(' ','-')}"
                detalles = []
                for item in st.session_state['carrito']:
                    idx = st.session_state['productos'].index[st.session_state['productos']['Producto'] == item['Producto']].tolist()[0]
                    curr = float(st.session_state['productos'].at[idx, 'StockActual'])
                    st.session_state['productos'].at[idx, 'StockActual'] = curr - item['Cantidad']
                    gan = (item['PrecioUnit'] - item['CostoUnit']) * item['Cantidad']
                    detalles.append({
                        'Fecha': now_str, 'Producto': item['Producto'], 'Categoria': item['Categoria'], 
                        'PesoKg': item['Cantidad'], 'CostoUnit': item['CostoUnit'], 
                        'PrecioVentaUnit': item['PrecioUnit'], 'Subtotal': item['Subtotal'], 'Ganancia': gan,
                        'Usuario': user_id, 'Sucursal': sucursal_actual
                    })
                
                backend.guardar_data(sheet, "productos", st.session_state['productos'])
                if detalles:
                    st.session_state['detalles'] = pd.concat([st.session_state['detalles'], pd.DataFrame(detalles)], ignore_index=True)
                    backend.guardar_data(sheet, "detalles", st.session_state['detalles'])
                
                txt = ", ".join([f"{p['Producto']} ({p['Cantidad']:.3f}kg)" for p in st.session_state['carrito']])
                fin = pd.DataFrame([{
                    'Fecha': now_str, 'Detalle': f"Venta {recibo_id}: {txt}", 'Tipo': "Ingreso", 
                    'Monto': total, 'MetodoPago': metodo, 'Ganancia': total_ganancia,
                    'Usuario': user_id, 'Sucursal': sucursal_actual
                }])
                st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], fin], ignore_index=True)
                
                if metodo == "💵 Efectivo" and qr_vuelto and cambio > 0:
                    swap = pd.DataFrame([
                        {'Fecha': now_str, 'Detalle': f"Exc. Billete (Swap) {recibo_id}", 'Tipo': "Ingreso", 'Monto': cambio, 'MetodoPago': "Efectivo", 'Ganancia': 0, 'Usuario': user_id, 'Sucursal': sucursal_actual},
                        {'Fecha': now_str, 'Detalle': f"Devolución Cambio {recibo_id}", 'Tipo': "Egreso", 'Monto': -cambio, 'MetodoPago': "QR", 'Ganancia': 0, 'Usuario': user_id, 'Sucursal': sucursal_actual}
                    ])
                    st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], swap], ignore_index=True)
                
                backend.guardar_data(sheet, "finanzas", st.session_state['finanzas'])
                
                lineas_txt = "\n".join([f"> {p['Producto']} ({p['Cantidad']:.3f}kg) - {p['Subtotal']:.2f}Bs" for p in st.session_state['carrito']])
                msg_txt = f"*** EL CORTE BENIANO ***\nRecibo: {recibo_id}\nAtiende: {usuario_actual}\nFecha: {now_str}\n{lineas_txt}\n----------------\nTOTAL: {total:.2f} Bs\nPago: {metodo}"
                msg_encoded = quote(msg_txt)
                link_wa = f"https://wa.me/591{cel.strip()}?text={msg_encoded}" if cel else f"https://wa.me/?text={msg_encoded}"
                
                html_raw = backend.generar_html_ticket(st.session_state['carrito'], total, now_str, metodo, recibo_id, DIRECCION_NEGOCIO, TELEFONO_NEGOCIO, usuario_actual)
                st.session_state['ultimo_ticket'] = {'link_wa': link_wa, 'html_raw': html_raw}
                st.session_state['carrito'] = []
                st.balloons(); st.success("¡Cobrado!"); time.sleep(1); st.rerun()
        else:
            st.info("Carrito vacío.")

    if st.session_state['ultimo_ticket']:
        st.success("✅ Venta Exitosa")
        c_t1, c_t2 = st.columns([1, 1])
        with c_t1:
            st.markdown(f"<a href='{st.session_state['ultimo_ticket']['link_wa']}' target='_blank' class='btn-whatsapp'>📲 ENVIAR WHATSAPP</a>", unsafe_allow_html=True)
            if st.button("❌ CERRAR / NUEVA VENTA", key="btn_cerrar_ticket"): 
                st.session_state['ultimo_ticket'] = None; st.rerun()
        with c_t2:
            st.caption("Vista Previa:"); components.html(st.session_state['ultimo_ticket']['html_raw'], height=450, scrolling=True)

    st.divider()
    st.subheader("📊 Arqueo (Hoy)")
    hoy = get_bolivia_date()
    df_hoy = st.session_state['finanzas'][st.session_state['finanzas']['Fecha'].astype(str).str.startswith(hoy)]
    if not df_hoy.empty:
        v_qr = df_hoy[df_hoy['MetodoPago'].str.contains('QR', na=False) & (df_hoy['Tipo'] == 'Ingreso')]['Monto'].sum()
        v_efec = df_hoy[df_hoy['MetodoPago'].str.contains('Efectivo', na=False) & (df_hoy['Tipo'] == 'Ingreso')]['Monto'].sum()
        c1, c2 = st.columns(2)
        c1.metric("Ventas Totales", f"{(v_qr + v_efec):.2f} Bs")
        c2.metric("EFECTIVO CAJA", f"{v_efec:.2f} Bs")

# ==============================================================================
# SECCIONES DE ADMIN
# ==============================================================================
if rol_actual == "Admin":
    with tab2:
        st.header("📦 Inventario")
        
        # --- NUEVO: PANEL DE ALERTAS DE STOCK ---
        df_inv = st.session_state['productos'].copy()
        df_inv['StockActual'] = pd.to_numeric(df_inv['StockActual'], errors='coerce').fillna(0.0)
        
        # Filtrar productos críticos (< 5 kg) y bajos (< 15 kg)
        criticos = df_inv[df_inv['StockActual'] <= 5.0]
        bajos = df_inv[(df_inv['StockActual'] > 5.0) & (df_inv['StockActual'] <= 15.0)]
        
        if not criticos.empty or not bajos.empty:
            st.markdown("### 🚨 Alertas de Reposición")
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                if not criticos.empty:
                    st.error(f"🛑 **{len(criticos)} Productos Críticos** (Menos de 5kg)")
                    st.dataframe(criticos[['Producto', 'StockActual']], use_container_width=True, hide_index=True)
            with col_a2:
                if not bajos.empty:
                    st.warning(f"⚠️ **{len(bajos)} Productos Bajos** (Menos de 15kg)")
                    st.dataframe(bajos[['Producto', 'StockActual']], use_container_width=True, hide_index=True)
            st.divider()
        else:
            st.success("✅ Todo el inventario está en niveles saludables.")
            st.divider()

        with st.expander("➕ Nuevo Producto"):
            with st.form("alta", clear_on_submit=True):
                c1, c2 = st.columns(2); n = c1.text_input("Nombre"); c = c2.selectbox("Cat", ["Res", "Pollo", "Cerdo", "Embutidos", "Otros"])
                c3, c4, c5 = st.columns(3); pv = c3.number_input("P. Venta", 0.0); pc = c4.number_input("Costo", 0.0); s = c5.number_input("Stock", 0.0)
                if st.form_submit_button("Guardar") and n:
                    nuevo = pd.DataFrame([{'Producto': n, 'Categoria': c, 'Costo': pc, 'PrecioVenta': pv, 'StockActual': s}])
                    st.session_state['productos'] = pd.concat([st.session_state['productos'], nuevo], ignore_index=True)
                    backend.guardar_data(sheet, "productos", st.session_state['productos'])
                    st.success("Guardado"); time.sleep(1); st.rerun()
        st.divider()
        df_ed = st.data_editor(st.session_state['productos'], num_rows="dynamic", use_container_width=True, key="inv_ed")
        if st.button("💾 Guardar Cambios Inventario", key="btn_save_inv"):
            st.session_state['productos'] = df_ed; backend.guardar_data(sheet, "productos", df_ed); st.success("Listo"); time.sleep(1); st.rerun()

    with tab3:
        st.header("📊 Gerencia & Reportes")
        g_tab1, g_tab2 = st.tabs(["📈 FINANZAS", "👥 USUARIOS"])
        
        with g_tab1:
            df_f = st.session_state['finanzas']
            if not df_f.empty and 'Ganancia' in df_f.columns:
                df_f['Fecha_dt'] = pd.to_datetime(df_f['Fecha'], format="%Y-%m-%d %H:%M", errors='coerce')
                df_f['Ganancia'] = pd.to_numeric(df_f['Ganancia'], errors='coerce').fillna(0.0)
                
                with st.container(border=True):
                    c_filtro1, c_filtro2 = st.columns([2, 1])
                    with c_filtro1:
                        today = datetime.utcnow() - timedelta(hours=4)
                        start_month = today.replace(day=1)
                        rango_fechas = st.date_input("Rango de Fechas:", value=(start_month, today), max_value=today, format="DD/MM/YYYY", key="filtro_gerencia")
                    with c_filtro2: st.write(""); st.info("Selecciona 'Inicio' y 'Fin'.")
                
                if isinstance(rango_fechas, tuple) and len(rango_fechas) == 2:
                    inicio, fin = rango_fechas
                    mask = (df_f['Fecha_dt'].dt.date >= inicio) & (df_f['Fecha_dt'].dt.date <= fin)
                    df_filtrado = df_f.loc[mask]
                    st.success(f"Mostrando: **{inicio.strftime('%d/%m/%Y')}** al **{fin.strftime('%d/%m/%Y')}**")
                else: df_filtrado = df_f; st.warning("Mostrando histórico total.")
                
                ganancia_periodo = df_filtrado['Ganancia'].sum()
                efectivo_periodo = df_filtrado[df_filtrado['MetodoPago'].str.contains('Efectivo', na=False, case=False)]['Monto'].sum()
                banco_periodo = df_filtrado[df_filtrado['MetodoPago'].str.contains('QR', na=False, case=False) | df_f['MetodoPago'].str.contains('Banco', na=False, case=False)]['Monto'].sum()
                total_periodo = df_filtrado['Monto'].sum()

                st.subheader("Resultados del Periodo")
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("💰 GANANCIA", f"{ganancia_periodo:.2f} Bs")
                k2.metric("💵 EFECTIVO", f"{efectivo_periodo:.2f} Bs")
                k3.metric("📱 BANCO/QR", f"{banco_periodo:.2f} Bs")
                k4.metric("∑ TOTAL", f"{total_periodo:.2f} Bs", border=True)
                st.divider()

                c_table, c_export = st.columns([3, 1])
                with c_table:
                    st.subheader("📒 Detalle")
                    df_editor = st.data_editor(df_filtrado, num_rows="dynamic", use_container_width=True, key="fin_ed_final", column_config={"Fecha_dt": None})
                
                with c_export:
                    st.subheader("📂 Descargas")
                    df_dl = df_editor.drop(columns=['Fecha_dt'], errors='ignore')
                    csv_filtrado = df_dl.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                    st.download_button("📥 Descargar Reporte", data=csv_filtrado, file_name="Reporte.csv", mime='text/csv', type="primary", key="btn_dl_1")
                    st.caption("Seguridad:")
                    csv_total = df_f.drop(columns=['Fecha_dt'], errors='ignore').to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                    st.download_button("📦 Backup Total", data=csv_total, file_name=f"BACKUP_{today.strftime('%Y%m%d')}.csv", mime='text/csv', key="btn_dl_2")

                if st.button("💾 Guardar Cambios Tabla", key="btn_save_fin_final"):
                    indices_originales = df_filtrado.index
                    st.session_state['finanzas'] = st.session_state['finanzas'].drop(indices_originales)
                    to_add = df_editor.drop(columns=['Fecha_dt'], errors='ignore')
                    st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], to_add]).sort_index()
                    backend.guardar_data(sheet, "finanzas", st.session_state['finanzas'])
                    st.success("Base de datos actualizada."); time.sleep(1.5); st.rerun()

                st.divider()
                with st.container(border=True):
                    st.subheader("📝 Registrar Gasto/Ingreso Admin")
                    c1, c2 = st.columns(2)
                    desc = c1.text_input("Descripción", key="input_desc_admin_final") 
                    mont = c2.number_input("Monto", 0.0, key="input_monto_admin_final")
                    tipo = st.radio("Tipo", ["Egreso", "Ingreso"], horizontal=True, key="radio_tipo_admin_final")
                    if st.button("Registrar Movimiento", key="btn_reg_admin_final") and mont > 0:
                        s = -1 if tipo == "Egreso" else 1
                        n = pd.DataFrame([{
                            'Fecha': get_bolivia_time(), 'Detalle': f"[ADMIN] {desc}", 'Tipo': tipo, 
                            'Monto': mont*s, 'MetodoPago': 'Otro', 'Ganancia': 0,
                            'Usuario': user_id, 'Sucursal': sucursal_actual
                        }])
                        st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], n], ignore_index=True)
                        backend.guardar_data(sheet, "finanzas", st.session_state['finanzas'])
                        st.success("Registrado"); time.sleep(1); st.rerun()
            else:
                st.info("Sin datos.")

        with g_tab2:
            st.subheader("Gestión de Equipo")
            with st.expander("➕ Crear Nuevo Usuario"):
                with st.form("new_user"):
                    u_user = st.text_input("Usuario (Login)")
                    u_pass = st.text_input("Contraseña")
                    u_name = st.text_input("Nombre Completo")
                    u_rol = st.selectbox("Rol", ["Vendedor", "Admin"])
                    u_suc = st.text_input("Sucursal", value="Matriz")
                    if st.form_submit_button("Crear Usuario"):
                        if u_user and u_pass:
                            new_u = pd.DataFrame([{'Usuario': u_user, 'Password': u_pass, 'Nombre': u_name, 'Rol': u_rol, 'Sucursal': u_suc, 'Activo': 'TRUE'}])
                            st.session_state['usuarios'] = pd.concat([st.session_state['usuarios'], new_u], ignore_index=True)
                            backend.guardar_data(sheet, "usuarios", st.session_state['usuarios'])
                            st.success("Usuario Creado"); time.sleep(1); st.rerun()
                        else: st.error("Faltan datos")
            st.divider()
            st.write("Editar Usuarios:")
            df_users_ed = st.data_editor(st.session_state['usuarios'], num_rows="dynamic", use_container_width=True, key="users_editor")
            if st.button("💾 Guardar Usuarios", key="btn_save_users"):
                st.session_state['usuarios'] = df_users_ed
                backend.guardar_data(sheet, "usuarios", st.session_state['usuarios'])
                st.success("Usuarios Actualizados"); time.sleep(1); st.rerun()
