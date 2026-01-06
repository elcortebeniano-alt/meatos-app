import streamlit as st
import pandas as pd
import os
from datetime import datetime
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="El Corte Beniano | POS", 
    layout="wide", 
    page_icon="🥩",
    initial_sidebar_state="expanded"
)

# --- ESTILOS CSS (CONTRASTE ALTO + MENÚ NATIVO) ---
st.markdown("""
<style>
    /* 1. BOTONES */
    .stButton>button {
        font-weight: bold; 
        border-radius: 8px; 
        height: 3em; 
        width: 100%;
    }
    button[kind="primary"] {
        background-color: #8B0000 !important; 
        color: white !important; 
        border: none !important;
    }
    button[kind="primary"]:hover {
        background-color: #A52A2A !important; 
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }

    /* 2. TARJETAS DE DATOS (Forzamos letras negras para Modo Oscuro) */
    div[data-testid="stMetric"] {
        background-color: #f0f2f6 !important; 
        border: 1px solid #d0d0d0;
        padding: 10px;
        border-radius: 8px;
        text-align: center;
    }
    div[data-testid="stMetricLabel"] p { color: #000000 !important; }
    div[data-testid="stMetricValue"] div { color: #000000 !important; }

    /* 3. BOTÓN WHATSAPP */
    .btn-whatsapp {
        display: inline-flex; align-items: center; justify-content: center;
        background-color: #25D366; color: white !important; font-weight: bold;
        padding: 0.8rem 1.5rem; border-radius: 12px; text-decoration: none;
        border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 100%;
        font-size: 1.1rem; margin-top: 10px;
    }
    .btn-whatsapp:hover { background-color: #128C7E; color: white !important;}
</style>
""", unsafe_allow_html=True)

# --- CONEXIÓN A GOOGLE ---
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
        st.error(f"Error Google: {e}")
        return None

# Funciones Auxiliares
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
        st.error(f"Error {nombre_hoja}: {e}")
        return pd.DataFrame(columns=columnas)

def guardar_data(sheet, nombre_hoja, df):
    try:
        worksheet = sheet.worksheet(nombre_hoja)
        worksheet.clear()
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
    except Exception as e:
        st.error(f"Error guardando {nombre_hoja}: {e}")

# --- INICIO ---
if 'sheet_obj' not in st.session_state: st.session_state['sheet_obj'] = conectar_google_sheets()
sheet = st.session_state['sheet_obj']

if sheet:
    if 'finanzas' not in st.session_state: st.session_state['finanzas'] = cargar_data(sheet, "finanzas", ['Fecha', 'Detalle', 'Tipo', 'Monto', 'MetodoPago'])
    if 'productos' not in st.session_state: st.session_state['productos'] = cargar_data(sheet, "productos", ['Producto', 'Costo', 'PrecioVenta', 'Categoria', 'StockActual'])
    if 'detalles' not in st.session_state: st.session_state['detalles'] = cargar_data(sheet, "detalles", ['Fecha', 'Producto', 'Categoria', 'PesoKg', 'CostoUnit', 'PrecioVentaUnit', 'Subtotal', 'Ganancia'])
else:
    st.stop()

if 'carrito' not in st.session_state: st.session_state['carrito'] = []
if 'ultimo_ticket' not in st.session_state: st.session_state['ultimo_ticket'] = None 
if 'admin_mode' not in st.session_state: st.session_state['admin_mode'] = False
if 'reset_counter' not in st.session_state: st.session_state['reset_counter'] = 0

def limpiar_fechas(df):
    if 'Fecha' in df.columns: df['Fecha'] = df['Fecha'].astype(str).fillna("")
    return df

st.session_state['finanzas'] = limpiar_fechas(st.session_state['finanzas'])
st.session_state['detalles'] = limpiar_fechas(st.session_state['detalles'])

# --- SIDEBAR ---
with st.sidebar:
    if os.path.exists("Logo-Final.png"):
        st.image("Logo-Final.png", use_container_width=True)
    elif os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.header("🥩 EL CORTE BENIANO")
    
    st.markdown("---")
    st.write("### 👤 Panel de Acceso")
    modo_seleccionado = st.radio("Perfil", ["👨‍🍳 Vendedor", "💼 Socio (Admin)"], label_visibility="collapsed")
    
    if modo_seleccionado == "💼 Socio (Admin)":
        password = st.text_input("🔑 Contraseña", type="password")
        if password == "2026": 
            st.session_state['admin_mode'] = True
            st.success("Gerente Activo")
            if st.button("🔄 Refrescar Datos"):
                st.cache_resource.clear()
                st.rerun()
        else:
            st.session_state['admin_mode'] = False
    else:
        st.session_state['admin_mode'] = False
    
    st.markdown("---")
    st.caption("MeatOS v3.7 | Full Admin")

# --- APP ---
tab1, tab2, tab3 = None, None, None
if st.session_state['admin_mode']:
    tab1, tab2, tab3 = st.tabs(["🛒 PUNTO DE VENTA", "📦 INVENTARIO", "📊 GERENCIA"])
else:
    tab1, = st.tabs(["🛒 PUNTO DE VENTA"])

# TAB 1: CAJA
with tab1:
    st.title("Caja Registradora")
    
    # Caja Chica
    with st.expander("💸 Gastos / Movimientos de Caja"):
        c1, c2, c3, c4 = st.columns([2, 1.5, 1, 1])
        opciones_caja = ["Pago Delivery", "Hielo/Bolsas", "Apertura Caja", "Retiro Ganancias", "Otro"]
        motivo_sel = c1.selectbox("Motivo", opciones_caja, label_visibility="collapsed")
        detalle_caja = motivo_sel if motivo_sel != "Otro" else c1.text_input("Detalle:")
        monto_caja = c2.number_input("Monto Bs", min_value=0.0, step=1.0)
        tipo_caja = c3.radio("Tipo", ["Salida", "Entrada"], horizontal=True, label_visibility="collapsed")
        
        if c4.button("Registrar", key="btn_caja"):
            if monto_caja > 0:
                signo = -1 if "Salida" in tipo_caja else 1
                tipo_bd = "Egreso" if "Salida" in tipo_caja else "Ingreso"
                nuevo = pd.DataFrame([{
                    'Fecha': datetime.now().strftime("%Y-%m-%d %H:%M"),
                    'Detalle': f"[CAJA] {detalle_caja}", 'Tipo': tipo_bd, 'Monto': monto_caja * signo, 'MetodoPago': 'Efectivo'
                }])
                st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], nuevo], ignore_index=True)
                guardar_data(sheet, "finanzas", st.session_state['finanzas'])
                st.success("✅ Registrado")
                time.sleep(1)
                st.rerun()

    st.divider()

    # Venta
    col_izq, col_der = st.columns([1.2, 1.8], gap="large")

    with col_izq:
        st.subheader("🥩 Selección")
        df_seguro = st.session_state['productos'].dropna(subset=['Producto'])
        df_seguro = df_seguro[df_seguro['Producto'] != ""]
        
        if not df_seguro.empty:
            lista = sorted(df_seguro['Producto'].unique())
            prod_sel = st.selectbox("Buscar Producto...", lista)
            
            if prod_sel:
                df_filtrado = df_seguro[df_seguro['Producto'] == prod_sel]
                data = df_filtrado.iloc[0]
                
                precio_base = float(data['PrecioVenta'])
                try: stock = float(data.get('StockActual', 0.0))
                except: stock = 0.0
                
                with st.container(border=True):
                    check_precio = st.checkbox("🔓 Modificar Precio")
                    precio_final = st.number_input("Precio Venta (Bs/Kg)", value=precio_base, step=0.5) if check_precio else precio_base
                        
                    k1, k2 = st.columns(2)
                    k1.metric("Precio", f"{precio_final:.2f} Bs")
                    k2.metric("Stock Disp.", f"{stock:.3f} Kg")

                st.write("⚖️ **Peso en Gramos:**")
                key_peso = f"peso_{st.session_state['reset_counter']}" 
                gr = st.number_input("Gramos", min_value=0, value=0, step=10, key=key_peso, label_visibility="collapsed")
                kg = gr / 1000
                
                if kg > 0:
                    st.info(f"Equivale a: **{kg:.3f} Kg** | Subtotal: **{(precio_final*kg):.2f} Bs**")
                
                if st.button("AGREGAR AL CARRITO ➕", type="primary", disabled=(stock<=0.001), key="btn_add"):
                    if gr > 0 and kg <= stock:
                        st.session_state['carrito'].append({
                            "Producto": prod_sel, "Categoria": str(data.get('Categoria', 'General')), "Cantidad": kg,
                            "PrecioUnit": precio_final, "CostoUnit": float(data.get('Costo', 0.0)), "Subtotal": precio_final * kg
                        })
                        st.session_state['reset_counter'] += 1
                        st.success("Agregado")
                        time.sleep(0.2)
                        st.rerun()
                    else:
                        st.error("❌ Stock insuficiente o peso cero")
        else:
            st.warning("Inventario vacío.")

    with col_der:
        st.subheader("🛒 Carrito")
        if st.session_state['carrito']:
            df_c = pd.DataFrame(st.session_state['carrito'])
            st.dataframe(df_c, use_container_width=True, hide_index=True)
            
            total = df_c['Subtotal'].sum()
            
            st.markdown(f"""
            <div style="background-color: white; padding: 15px; border-radius: 10px; text-align: right; border: 2px solid #8B0000; margin-bottom: 20px;">
                <span style="font-size: 18px; color: black; font-weight: bold;">Total a Pagar:</span><br>
                <span style="font-size: 36px; font-weight: 800; color: #8B0000;">{total:.2f} Bs</span>
            </div>
            """, unsafe_allow_html=True)
            
            st.write("---")
            st.write("📝 **Datos del Cliente:**")
            
            c_cli, c_pay = st.columns([1, 1.5])
            celular_cliente = c_cli.text_input("📱 WhatsApp Cliente", placeholder="70712345")
            metodo = c_pay.radio("Método de Pago", ["💵 Efectivo", "📱 QR / Banco"], horizontal=True)
            
            pago_cliente = 0.0
            cambio = 0.0
            cambio_por_qr = False
            puede_cobrar = True
            
            if metodo == "💵 Efectivo":
                pago_cliente = st.number_input("Monto Recibido:", min_value=0.0, value=float(total))
                if pago_cliente >= total:
                    cambio = pago_cliente - total
                    st.info(f"💰 Vuelto: **{cambio:.2f} Bs**")
                    if cambio > 0:
                        cambio_por_qr = st.checkbox(f"🔄 Vuelto por QR")
                else:
                    st.error(f"Falta: {total - pago_cliente:.2f} Bs")
                    puede_cobrar = False
            
            col_b1, col_b2 = st.columns([1, 2])
            if col_b1.button("🗑️ Borrar", key="clean_cart"):
                st.session_state['carrito'] = []
                st.rerun()
            
            if col_b2.button("✅ COBRAR", type="primary", disabled=not puede_cobrar, key="pay_final"):
                fecha_ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                nuevos_detalles = []
                
                for item in st.session_state['carrito']:
                    indices = st.session_state['productos'].index[st.session_state['productos']['Producto'] == item['Producto']].tolist()
                    if indices:
                        idx = indices[0]
                        curr = float(st.session_state['productos'].at[idx, 'StockActual'])
                        st.session_state['productos'].at[idx, 'StockActual'] = curr - item['Cantidad']
                        ganancia = (item['PrecioUnit'] - item['CostoUnit']) * item['Cantidad']
                        nuevos_detalles.append({
                            'Fecha': fecha_ahora, 'Producto': item['Producto'], 'Categoria': item['Categoria'],
                            'PesoKg': item['Cantidad'], 'CostoUnit': item['CostoUnit'], 'PrecioVentaUnit': item['PrecioUnit'],
                            'Subtotal': item['Subtotal'], 'Ganancia': ganancia
                        })
                
                guardar_data(sheet, "productos", st.session_state['productos'])
                if nuevos_detalles:
                    st.session_state['detalles'] = pd.concat([st.session_state['detalles'], pd.DataFrame(nuevos_detalles)], ignore_index=True)
                    guardar_data(sheet, "detalles", st.session_state['detalles'])
                
                detalle_txt = ", ".join([f"{p['Producto']} ({p['Cantidad']:.3f}kg)" for p in st.session_state['carrito']])
                nuevo_ingreso = pd.DataFrame([{'Fecha': fecha_ahora, 'Detalle': f"Venta: {detalle_txt}", 'Tipo': "Ingreso", 'Monto': total, 'MetodoPago': metodo}])
                st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], nuevo_ingreso], ignore_index=True)
                
                if metodo == "💵 Efectivo" and cambio_por_qr and cambio > 0:
                    swap_in = pd.DataFrame([{'Fecha': fecha_ahora, 'Detalle': "Exc. Billete (Swap QR)", 'Tipo': "Ingreso", 'Monto': cambio, 'MetodoPago': "Efectivo"}])
                    swap_out = pd.DataFrame([{'Fecha': fecha_ahora, 'Detalle': "Devolución Cambio", 'Tipo': "Egreso", 'Monto': -cambio, 'MetodoPago': "QR"}])
                    st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], swap_in, swap_out], ignore_index=True)

                guardar_data(sheet, "finanzas", st.session_state['finanzas'])
                
                lineas = "%0A".join([f"▪️ {p['Producto']} ({p['Cantidad']:.3f}kg) - {p['Subtotal']:.2f}Bs" for p in st.session_state['carrito']])
                msg = f"*🥩 EL CORTE BENIANO*%0A📅 {fecha_ahora}%0A📋 *Su Compra:*%0A{lineas}%0A----------------%0A💰 *TOTAL: {total:.2f} Bs*%0A✅ {metodo}"
                
                link = f"https://wa.me/591{celular_cliente.strip()}?text={msg}" if celular_cliente else f"https://wa.me/?text={msg}"
                st.session_state['ultimo_ticket'] = {'link': link, 'texto': "📲 ENVIAR TICKET WHATSAPP"}
                st.session_state['carrito'] = []
                st.balloons()
                st.success("¡Cobrado!")
                time.sleep(3)
                st.rerun()
        else:
            st.info("Carrito vacío.")

    if st.session_state['ultimo_ticket']:
        st.success("✅ Venta Lista")
        st.markdown(f"""<a href="{st.session_state['ultimo_ticket']['link']}" target="_blank" class="btn-whatsapp">{st.session_state['ultimo_ticket']['texto']}</a>""", unsafe_allow_html=True)
        if st.button("Cerrar Ticket"):
            st.session_state['ultimo_ticket'] = None
            st.rerun()

    # Arqueo
    st.divider()
    st.subheader("📊 Arqueo de Caja")
    hoy = datetime.now().strftime("%Y-%m-%d")
    df_hoy = st.session_state['finanzas'][st.session_state['finanzas']['Fecha'].astype(str).str.startswith(hoy)]
    
    if not df_hoy.empty:
        v_qr = df_hoy[(df_hoy['MetodoPago'].str.contains('QR', na=False)) & (df_hoy['Tipo'] == 'Ingreso')]['Monto'].sum()
        v_efec = df_hoy[(df_hoy['MetodoPago'].str.contains('Efectivo', na=False)) & (df_hoy['Tipo'] == 'Ingreso')]['Monto'].sum()
        g_efec = df_hoy[(df_hoy['MetodoPago'].str.contains('Efectivo', na=False)) & (df_hoy['Tipo'] == 'Egreso')]['Monto'].sum()
        g_qr = df_hoy[(df_hoy['MetodoPago'].str.contains('QR', na=False)) & (df_hoy['Tipo'] == 'Egreso')]['Monto'].sum()
        
        c_a1, c_a2, c_a3 = st.columns(3)
        c_a1.metric("Ventas Total", f"{(v_qr + v_efec):.2f} Bs")
        c_a2.metric("Banco (QR)", f"{(v_qr + g_qr):.2f} Bs")
        c_a3.metric("EFECTIVO", f"{(v_efec + g_efec):.2f} Bs")
    else:
        st.caption("Sin movimientos.")

# TAB ADMIN
if st.session_state['admin_mode']:
    with tab2:
        st.header("📦 Inventario")
        with st.expander("➕ Nuevo Producto", expanded=True):
            with st.form("form_alta", clear_on_submit=True):
                c1, c2 = st.columns(2)
                nn = c1.text_input("Nombre")
                nc = c2.selectbox("Categoría", ["Res", "Pollo", "Cerdo", "Embutidos", "Otros"])
                c3, c4, c5 = st.columns(3)
                nv = c3.number_input("Precio Venta", 0.0)
                n_costo = c4.number_input("Costo", 0.0)
                ns = c5.number_input("Stock", 0.0)
                if st.form_submit_button("Guardar"):
                    if nn:
                        nuevo = pd.DataFrame([{'Producto': str(nn), 'Categoria': str(nc), 'Costo': float(n_costo), 'PrecioVenta': float(nv), 'StockActual': float(ns)}])
                        st.session_state['productos'] = pd.concat([st.session_state['productos'], nuevo], ignore_index=True)
                        guardar_data(sheet, "productos", st.session_state['productos'])
                        st.success(f"Guardado: {nn}")
                        time.sleep(1.5)
                        st.rerun()

        st.divider()
        st.subheader("📋 Tabla de Productos (Editable)")
        # num_rows="dynamic" PERMITE BORRAR FILAS
        df_edit = st.data_editor(st.session_state['productos'], num_rows="dynamic", use_container_width=True, key="inv_editor")
        if st.button("💾 Guardar Cambios Inventario"):
            st.session_state['productos'] = df_edit
            guardar_data(sheet, "productos", df_edit)
            st.success("Inventario Actualizado")
            time.sleep(1)
            st.rerun()

    with tab3:
        st.header("📊 Finanzas & Gerencia")
        
        # 1. Registrar Gastos Admin
        with st.container(border=True):
            st.subheader("📝 Registrar Movimiento Administrativo")
            col_ga1, col_ga2 = st.columns(2)
            desc_adm = col_ga1.text_input("Descripción (Ej: Sueldos, Alquiler)")
            monto_adm = col_ga2.number_input("Monto (Bs)", 0.0)
            tipo_adm = st.radio("Tipo Movimiento", ["Egreso (Gasto)", "Ingreso (Capital)"], horizontal=True)
            
            if st.button("Registrar Movimiento Admin"):
                if monto_adm > 0 and desc_adm:
                    signo = -1 if "Egreso" in tipo_adm else 1
                    tipo_bd = "Egreso" if "Egreso" in tipo_adm else "Ingreso"
                    nuevo_adm = pd.DataFrame([{
                        'Fecha': datetime.now().strftime("%Y-%m-%d %H:%M"),
                        'Detalle': f"[ADMIN] {desc_adm}", 'Tipo': tipo_bd, 'Monto': monto_adm * signo, 'MetodoPago': 'Transferencia/Otro'
                    }])
                    st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], nuevo_adm], ignore_index=True)
                    guardar_data(sheet, "finanzas", st.session_state['finanzas'])
                    st.success("Registrado")
                    time.sleep(1)
                    st.rerun()

        st.divider()
        st.subheader("📒 Libro Contable (Editable)")
        st.caption("Selecciona filas y presiona 'Supr' para borrar. Luego dale a Guardar.")
        
        # Tabla Editable para Finanzas
        df_fin_edit = st.data_editor(st.session_state['finanzas'], num_rows="dynamic", use_container_width=True, key="fin_editor")
        
        if st.button("💾 Guardar Cambios Finanzas"):
            st.session_state['finanzas'] = df_fin_edit
            guardar_data(sheet, "finanzas", df_fin_edit)
            st.success("Finanzas Actualizadas")
            time.sleep(1)
            st.rerun()
