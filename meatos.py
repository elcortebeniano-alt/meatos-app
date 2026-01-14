import streamlit as st
import pandas as pd
import time
import os
from datetime import datetime, timedelta # <--- IMPORTANTE: Agregamos timedelta
import streamlit.components.v1 as components

# --- IMPORTACIÓN DE MÓDULOS PROPIOS ---
import styles
import backend

# CONFIGURACIÓN
st.set_page_config(page_title="El Corte Beniano | POS", layout="wide", page_icon="🥩", initial_sidebar_state="expanded")

# 1. CARGAR DISEÑO
styles.cargar_css()

# --- FUNCIÓN MAESTRA DE HORA BOLIVIANA (UTC - 4) ---
def get_bolivia_time():
    # Toma la hora universal y resta 4 horas
    return (datetime.utcnow() - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M")

def get_bolivia_date():
    return (datetime.utcnow() - timedelta(hours=4)).strftime("%Y-%m-%d")

# 2. CONEXIÓN DATOS
if 'sheet_obj' not in st.session_state: st.session_state['sheet_obj'] = backend.conectar_google_sheets()
sheet = st.session_state['sheet_obj']

if sheet:
    if 'finanzas' not in st.session_state: st.session_state['finanzas'] = backend.cargar_data(sheet, "finanzas", ['Fecha', 'Detalle', 'Tipo', 'Monto', 'MetodoPago', 'Ganancia'])
    if 'productos' not in st.session_state: st.session_state['productos'] = backend.cargar_data(sheet, "productos", ['Producto', 'Costo', 'PrecioVenta', 'Categoria', 'StockActual'])
    if 'detalles' not in st.session_state: st.session_state['detalles'] = backend.cargar_data(sheet, "detalles", ['Fecha', 'Producto', 'Categoria', 'PesoKg', 'CostoUnit', 'PrecioVentaUnit', 'Subtotal', 'Ganancia'])
else:
    st.stop()

# 3. VARIABLES DE ESTADO
if 'carrito' not in st.session_state: st.session_state['carrito'] = []
if 'ultimo_ticket' not in st.session_state: st.session_state['ultimo_ticket'] = None 
if 'admin_mode' not in st.session_state: st.session_state['admin_mode'] = False
if 'reset_counter' not in st.session_state: st.session_state['reset_counter'] = 0

st.session_state['finanzas'] = backend.limpiar_fechas(st.session_state['finanzas'])
st.session_state['detalles'] = backend.limpiar_fechas(st.session_state['detalles'])

# --- DATOS DEL NEGOCIO ---
DIRECCION_NEGOCIO = "Calle A. García #1128, Cochabamba"
TELEFONO_NEGOCIO = "591 77420111"

# --- SIDEBAR ---
with st.sidebar:
    if os.path.exists("Logo-Final.png"): st.image("Logo-Final.png", use_container_width=True)
    else: st.header("🥩 EL CORTE BENIANO")
    st.markdown("---")
    modo = st.radio("Perfil", ["👨‍🍳 Vendedor", "💼 Socio (Admin)"], label_visibility="collapsed")
    if modo == "💼 Socio (Admin)":
        if st.text_input("Contraseña", type="password") == "2026":
            st.session_state['admin_mode'] = True
            st.success("Gerente Activo")
            if st.button("🔄 Refrescar"): st.cache_resource.clear(); st.rerun()
        else: st.session_state['admin_mode'] = False
    else: st.session_state['admin_mode'] = False
    st.caption("MeatOS v4.4 | Hora Bolivia")

# --- NAVEGACIÓN ---
tab1, tab2, tab3 = None, None, None
if st.session_state['admin_mode']:
    tab1, tab2, tab3 = st.tabs(["🛒 PUNTO DE VENTA", "📦 INVENTARIO", "📊 GERENCIA"])
else:
    tab1, = st.tabs(["🛒 PUNTO DE VENTA"])

# === PESTAÑA 1: VENTA ===
with tab1:
    st.title("Caja Registradora")
    
    # CAJA CHICA
    with st.expander("💸 Gastos / Movimientos de Caja"):
        c1, c2, c3, c4 = st.columns([2, 1.5, 1, 1])
        opciones = ["Pago Delivery", "Hielo/Bolsas", "Apertura Caja", "Retiro Ganancias", "Otro"]
        motivo = c1.selectbox("Motivo", opciones, label_visibility="collapsed")
        detalle = motivo if motivo != "Otro" else c1.text_input("Detalle:")
        monto = c2.number_input("Monto Bs", 0.0, step=1.0)
        tipo = c3.radio("Tipo", ["Salida", "Entrada"], horizontal=True, label_visibility="collapsed")
        
        if c4.button("Registrar", key="btn_caja"):
            if monto > 0:
                signo = -1 if "Salida" in tipo else 1
                tipo_bd = "Egreso" if "Salida" in tipo else "Ingreso"
                # AQUI USAMOS LA HORA BOLIVIANA
                nuevo = pd.DataFrame([{'Fecha': get_bolivia_time(), 'Detalle': f"[CAJA] {detalle}", 'Tipo': tipo_bd, 'Monto': monto * signo, 'MetodoPago': 'Efectivo', 'Ganancia': 0}])
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
            prod_sel = st.selectbox("Buscar Producto...", lista)
            if prod_sel:
                data = df_prod[df_prod['Producto'] == prod_sel].iloc[0]
                precio_base = float(data['PrecioVenta'])
                with st.container(border=True):
                    check = st.checkbox("🔓 Modificar Precio")
                    precio_final = st.number_input("Precio Venta", value=precio_base, step=0.5) if check else precio_base
                    st.metric("Stock Disp.", f"{float(data.get('StockActual',0.0)):.3f} Kg")
                
                st.write("⚖️ **Peso (g):**")
                gr = st.number_input("Gramos", 0, step=10, key=f"peso_{st.session_state['reset_counter']}", label_visibility="collapsed")
                kg = gr / 1000
                if kg > 0: st.info(f"Total: **{(precio_final*kg):.2f} Bs** ({kg:.3f} Kg)")
                
                if st.button("AGREGAR ➕", type="primary"):
                    if gr > 0 and kg <= float(data.get('StockActual',0.0)):
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
            cel = c1.text_input("📱 WhatsApp", placeholder="70712345")
            metodo = c2.radio("Pago", ["💵 Efectivo", "📱 QR / Banco"], horizontal=True)
            
            pago, cambio, qr_vuelto, cobrar = 0.0, 0.0, False, True
            if metodo == "💵 Efectivo":
                pago = st.number_input("Recibido:", 0.0, step=0.5)
                if pago >= total:
                    cambio = pago - total
                    st.info(f"💰 Vuelto: **{cambio:.2f} Bs**")
                    if cambio > 0: qr_vuelto = st.checkbox("🔄 Vuelto por QR")
                else: 
                    if pago > 0: st.error(f"Falta: {total-pago:.2f}"); cobrar = False
                    else: st.warning("Ingrese monto"); cobrar = False
            
            b1, b2 = st.columns([1, 2])
            if b1.button("🗑️"): st.session_state['carrito'] = []; st.rerun()
            if b2.button("✅ COBRAR", type="primary", disabled=not cobrar):
                # AQUI USAMOS LA HORA BOLIVIANA
                now_str = get_bolivia_time()
                # ID Único basado en hora Bolivia
                recibo_id = f"#REC-{now_str.replace('-','').replace(':','').replace(' ','-')}"

                detalles = []
                for item in st.session_state['carrito']:
                    idx = st.session_state['productos'].index[st.session_state['productos']['Producto'] == item['Producto']].tolist()[0]
                    curr = float(st.session_state['productos'].at[idx, 'StockActual'])
                    st.session_state['productos'].at[idx, 'StockActual'] = curr - item['Cantidad']
                    gan = (item['PrecioUnit'] - item['CostoUnit']) * item['Cantidad']
                    detalles.append({'Fecha': now_str, 'Producto': item['Producto'], 'Categoria': item['Categoria'], 'PesoKg': item['Cantidad'], 'CostoUnit': item['CostoUnit'], 'PrecioVentaUnit': item['PrecioUnit'], 'Subtotal': item['Subtotal'], 'Ganancia': gan})
                
                backend.guardar_data(sheet, "productos", st.session_state['productos'])
                if detalles:
                    st.session_state['detalles'] = pd.concat([st.session_state['detalles'], pd.DataFrame(detalles)], ignore_index=True)
                    backend.guardar_data(sheet, "detalles", st.session_state['detalles'])
                
                txt = ", ".join([f"{p['Producto']} ({p['Cantidad']:.3f}kg)" for p in st.session_state['carrito']])
                fin = pd.DataFrame([{'Fecha': now_str, 'Detalle': f"Venta {recibo_id}: {txt}", 'Tipo': "Ingreso", 'Monto': total, 'MetodoPago': metodo, 'Ganancia': total_ganancia}])
                st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], fin], ignore_index=True)
                
                if metodo == "💵 Efectivo" and qr_vuelto and cambio > 0:
                    swap = pd.DataFrame([
                        {'Fecha': now_str, 'Detalle': f"Exc. Billete (Swap) {recibo_id}", 'Tipo': "Ingreso", 'Monto': cambio, 'MetodoPago': "Efectivo", 'Ganancia': 0},
                        {'Fecha': now_str, 'Detalle': f"Devolución Cambio {recibo_id}", 'Tipo': "Egreso", 'Monto': -cambio, 'MetodoPago': "QR", 'Ganancia': 0}
                    ])
                    st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], swap], ignore_index=True)
                
                backend.guardar_data(sheet, "finanzas", st.session_state['finanzas'])
                
                # --- GENERAR TICKETS ---
                lineas = "%0A".join([f"> {p['Producto']} ({p['Cantidad']:.3f}kg) - {p['Subtotal']:.2f}Bs" for p in st.session_state['carrito']])
                msg = f"*** EL CORTE BENIANO ***%0ARecibo: {recibo_id}%0AFecha: {now_str}%0A{lineas}%0A----------------%0ATOTAL: {total:.2f} Bs%0APago: {metodo}"
                link_wa = f"https://wa.me/591{cel.strip()}?text={msg}" if cel else f"https://wa.me/?text={msg}"
                
                html_raw = backend.generar_html_ticket(st.session_state['carrito'], total, now_str, metodo, recibo_id, DIRECCION_NEGOCIO, TELEFONO_NEGOCIO)

                st.session_state['ultimo_ticket'] = {'link_wa': link_wa, 'html_raw': html_raw}
                st.session_state['carrito'] = []
                st.balloons(); st.success("¡Cobrado!"); time.sleep(1); st.rerun()

        else:
            st.info("Carrito vacío.")

    # --- MOSTRAR TICKET ---
    if st.session_state['ultimo_ticket']:
        st.success("✅ Venta Exitosa")
        c_t1, c_t2 = st.columns([1, 1])
        with c_t1:
            st.markdown(f"<a href='{st.session_state['ultimo_ticket']['link_wa']}' target='_blank' class='btn-whatsapp'>📲 ENVIAR WHATSAPP</a>", unsafe_allow_html=True)
            st.write("")
            if st.button("❌ CERRAR / NUEVA VENTA"): 
                st.session_state['ultimo_ticket'] = None
                st.rerun()
        with c_t2:
            st.caption("Vista Previa:")
            components.html(st.session_state['ultimo_ticket']['html_raw'], height=450, scrolling=True)

    st.divider()
    st.subheader("📊 Arqueo (Hoy)")
    # AQUI USAMOS LA FECHA BOLIVIANA
    hoy = get_bolivia_date()
    df_hoy = st.session_state['finanzas'][st.session_state['finanzas']['Fecha'].astype(str).str.startswith(hoy)]
    if not df_hoy.empty:
        v_qr = df_hoy[df_hoy['MetodoPago'].str.contains('QR', na=False) & (df_hoy['Tipo'] == 'Ingreso')]['Monto'].sum()
        v_efec = df_hoy[df_hoy['MetodoPago'].str.contains('Efectivo', na=False) & (df_hoy['Tipo'] == 'Ingreso')]['Monto'].sum()
        c1, c2 = st.columns(2)
        c1.metric("Ventas Totales", f"{(v_qr + v_efec):.2f} Bs")
        c2.metric("EFECTIVO CAJA", f"{v_efec:.2f} Bs")

# === ADMIN ===
if st.session_state['admin_mode']:
    with tab2:
        st.header("📦 Inventario")
        with st.expander("➕ Nuevo Producto", expanded=True):
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
        if st.button("💾 Guardar Cambios"):
            st.session_state['productos'] = df_ed; backend.guardar_data(sheet, "productos", df_ed); st.success("Listo"); time.sleep(1); st.rerun()

    with tab3:
        st.header("📊 Gerencia")
        df_f = st.session_state['finanzas']
        if not df_f.empty and 'Ganancia' in df_f.columns:
            df_f['Fecha_dt'] = pd.to_datetime(df_f['Fecha'], format="%Y-%m-%d %H:%M", errors='coerce')
            df_f['Ganancia'] = pd.to_numeric(df_f['Ganancia'], errors='coerce').fillna(0.0)
            
            # FECHA BOLIVIA PARA CALCULOS
            now = datetime.utcnow() - timedelta(hours=4)
            
            g_hoy = df_f[df_f['Fecha_dt'].dt.date == now.date()]['Ganancia'].sum()
            g_mes = df_f[(df_f['Fecha_dt'].dt.month == now.month) & (df_f['Fecha_dt'].dt.year == now.year)]['Ganancia'].sum()
            c1, c2, c3 = st.columns(3)
            c1.metric("Ganancia HOY", f"{g_hoy:.2f} Bs")
            c2.metric("Ganancia MES", f"{g_mes:.2f} Bs")
            efec = df_f[df_f['MetodoPago'].str.contains('Efectivo', na=False)]['Monto'].sum()
            c3.metric("CAJA EFECTIVO", f"{efec:.2f} Bs")
        
        st.divider()
        with st.container(border=True):
            st.subheader("📝 Movimiento Admin")
            c1, c2 = st.columns(2); desc = c1.text_input("Desc"); mont = c2.number_input("Monto", 0.0)
            tipo = st.radio("Tipo", ["Egreso", "Ingreso"], horizontal=True)
            if st.button("Registrar") and mont > 0:
                s = -1 if tipo == "Egreso" else 1
                # AQUI USAMOS LA HORA BOLIVIANA
                n = pd.DataFrame([{'Fecha': get_bolivia_time(), 'Detalle': f"[ADMIN] {desc}", 'Tipo': tipo, 'Monto': mont*s, 'MetodoPago': 'Otro', 'Ganancia': 0}])
                st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], n], ignore_index=True)
                backend.guardar_data(sheet, "finanzas", st.session_state['finanzas'])
                st.success("Listo"); time.sleep(1); st.rerun()
        st.divider()
        df_fin_ed = st.data_editor(st.session_state['finanzas'], num_rows="dynamic", use_container_width=True, key="fin_ed")
        if st.button("💾 Guardar Finanzas"):
            st.session_state['finanzas'] = df_fin_ed; backend.guardar_data(sheet, "finanzas", df_fin_ed); st.success("Listo"); time.sleep(1); st.rerun()
