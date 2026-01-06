import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="El Corte Beniano | Cloud POS", 
    layout="wide", 
    page_icon="🥩",
    initial_sidebar_state="collapsed" # Arranca cerrado en móvil para ahorrar espacio
)

# --- ESTILOS CSS (CORREGIDO PARA VER EL MENÚ EN CELULAR) ---
st.markdown("""
<style>
    /* 1. FORZAR VISIBILIDAD DE LA BARRA SUPERIOR */
    header {
        visibility: visible !important;
    }
    
    [data-testid="stHeader"] {
        visibility: visible !important;
        background-color: transparent !important;
        z-index: 999999 !important; /* ¡ESTO ES LA CLAVE! Pone el menú encima de todo */
    }

    /* 2. EL BOTÓN DE ABRIR MENÚ (LA FLECHITA O HAMBURGUESA) */
    [data-testid="collapsedControl"] {
        visibility: visible !important;
        display: block !important;
        color: #8B0000 !important; /* Rojo para que lo veas bien */
    }
    
    /* También forzamos el icono del menú de hamburguesa si aparece ese */
    [data-testid="stDecoration"] {
        visibility: visible !important;
        z-index: 999999 !important;
    }

    /* 3. BAJAR EL CONTENIDO PARA QUE NO TAPE EL MENÚ */
    .block-container {
        padding-top: 5rem !important; /* Mucho espacio arriba para que no estorbe */
        padding-bottom: 1rem;
    }
    
    /* Ocultar pie de página */
    footer {visibility: hidden;}
    #MainMenu {visibility: visible;} 

    /* ESTILOS GENERALES (Botones, Tarjetas) */
    .stButton>button {font-weight: bold; border-radius: 8px; height: 3em; width: 100%;}
    button[kind="primary"] {background-color: #8B0000 !important; color: white !important; border: none !important;}
    button[kind="primary"]:hover {background-color: #A52A2A !important; box-shadow: 0 4px 8px rgba(0,0,0,0.2);}
    div[data-testid="stMetric"] {border: 1px solid #444; padding: 10px; border-radius: 8px; text-align: center;}
    
    .btn-whatsapp {
        display: inline-flex; align-items: center; justify-content: center;
        background-color: #25D366; color: white !important; font-weight: bold;
        padding: 0.8rem 1.5rem; border-radius: 12px; text-decoration: none;
        border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 100%;
        font-size: 1.1rem; transition: transform 0.1s;
    }
    .btn-whatsapp:hover { background-color: #128C7E; color: white !important; transform: scale(1.02);}
</style>
""", unsafe_allow_html=True)

# --- CONEXIÓN HÍBRIDA ---
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
            st.error("⚠️ Error Fatal: No se encontraron credenciales.")
            return None
    except Exception as e:
        st.error(f"Error conectando a Google Sheets: {e}")
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
        st.error(f"Error guardando en {nombre_hoja}: {e}")

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
        st.markdown("<h1 style='text-align: center;'>🥩 EL CORTE BENIANO</h1>", unsafe_allow_html=True)
    
    st.markdown("---")
    st.write("### 👤 Panel de Acceso")
    modo_seleccionado = st.radio("Perfil", ["👨‍🍳 Vendedor", "💼 Socio (Admin)"], label_visibility="collapsed")
    
    if modo_seleccionado == "💼 Socio (Admin)":
        st.markdown("---")
        password = st.text_input("🔑 Contraseña", type="password")
        if password == "2026": 
            st.session_state['admin_mode'] = True
            st.success("Admin Nube ☁️")
            st.markdown("---")
            if st.button("🔄 Forzar Sincronización"):
                st.cache_resource.clear()
                st.rerun()
        else:
            st.session_state['admin_mode'] = False
    else:
        st.session_state['admin_mode'] = False
    
    st.markdown("---")
    st.caption("MeatOS v3.3 | UI Rescue")

# --- TABS ---
tab1, tab2, tab3 = None, None, None
if st.session_state['admin_mode']:
    tab1, tab2, tab3 = st.tabs(["🛒 PUNTO DE VENTA", "📦 INVENTARIO", "📊 GERENCIA"])
else:
    tab1, = st.tabs(["🛒 PUNTO DE VENTA"])

# TAB 1: POS
with tab1:
    col_header, col_status = st.columns([3, 1])
    col_header.title("Caja Registradora")
    
    with st.expander("💸 Operaciones de Caja (Gastos / Apertura)", expanded=False):
        c1, c2, c3, c4 = st.columns([2, 1.5, 1, 1])
        opciones_caja = ["Pago Delivery", "Hielo/Bolsas", "Apertura Caja", "Retiro Ganancias", "Otro"]
        motivo_sel = c1.selectbox("Motivo", opciones_caja, label_visibility="collapsed")
        detalle_caja = motivo_sel if motivo_sel != "Otro" else c1.text_input("Detalle:")
        monto_caja = c2.number_input("Monto Bs", min_value=0.0, step=1.0)
        tipo_caja = c3.radio("Tipo", ["Salida", "Entrada"], horizontal=True, label_visibility="collapsed")
        
        if c4.button("Registrar", key="btn_caja_rapida"):
            if monto_caja > 0:
                signo = -1 if "Salida" in tipo_caja else 1
                tipo_bd = "Egreso" if "Salida" in tipo_caja else "Ingreso"
                nuevo = pd.DataFrame([{
                    'Fecha': datetime.now().strftime("%Y-%m-%d %H:%M"),
                    'Detalle': f"[CAJA] {detalle_caja}", 'Tipo': tipo_bd, 'Monto': monto_caja * signo, 'MetodoPago': 'Efectivo'
                }])
                st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], nuevo], ignore_index=True)
                guardar_data(sheet, "finanzas", st.session_state['finanzas'])
                st.toast(f"✅ Guardado en Nube: {monto_caja} Bs")
                time.sleep(0.5)
                st.rerun()

    st.write("") 
    col_izq, col_der = st.columns([1.2, 1.8], gap="large")

    with col_izq:
        st.markdown("### 🥩 Selección")
        df_seguro = st.session_state['productos'].dropna(subset=['Producto'])
        df_seguro = df_seguro[df_seguro['Producto'] != ""]
        
        if not df_seguro.empty:
            lista = sorted(df_seguro['Producto'].unique())
            prod_sel = st.selectbox("Buscar Producto...", lista)
            
            if prod_sel:
                df_filtrado = df_seguro[df_seguro['Producto'] == prod_sel]
                if not df_filtrado.empty:
                    data = df_filtrado.iloc[0]
                    precio_base = float(data['PrecioVenta'])
                    costo_base = float(data.get('Costo', 0.0))
                    cat_base = str(data.get('Categoria', 'General'))
                    try: stock = float(data.get('StockActual', 0.0))
                    except: stock = 0.0
                    
                    with st.container(border=True):
                        check_desc = st.checkbox("🔓 Modificar Precio")
                        if check_desc:
                            precio_final = st.number_input("Nuevo Precio (Bs/Kg)", value=precio_base, step=0.5)
                        else:
                            precio_final = precio_base
                        
                        c_info1, c_info2 = st.columns(2)
                        c_info1.metric("Precio", f"{precio_final:.2f} Bs")
                        c_info2.metric("Stock", f"{stock:.3f} Kg")
                    
                    st.write("⚖️ **Peso en Gramos:**")
                    key_dinamica = f"peso_input_{st.session_state['reset_counter']}"
                    gr = st.number_input("g", min_value=0, value=0, step=10, key=key_dinamica, label_visibility="collapsed")
                    kg = gr / 1000
                    
                    if kg > 0:
                        st.info(f"Equivale a: **{kg:.3f} Kg** | Subtotal: **{(precio_final*kg):.2f} Bs**")
                    
                    if st.button("AGREGAR AL CARRITO ➕", type="primary", disabled=(stock<=0.001), key="btn_add_cart"):
                        if gr > 0 and kg <= stock:
                            st.session_state['carrito'].append({
                                "Producto": prod_sel, "Categoria": cat_base, "Cantidad": kg,
                                "PrecioUnit": precio_final, "CostoUnit": costo_base, "Subtotal": precio_final * kg
                            })
                            st.session_state['reset_counter'] += 1
                            st.rerun()
                        else:
                            st.error("❌ Stock insuficiente")
        else:
            st.warning("Inventario vacío. Ingresa a Admin para crear productos.")

    with col_der:
        st.markdown("### 🛒 Carrito de Compra")
        if st.session_state['carrito']:
            df_c = pd.DataFrame(st.session_state['carrito'])
            st.dataframe(df_c, use_container_width=True, hide_index=True)
            total = df_c['Subtotal'].sum()
            
            st.markdown(f"""
            <div style="background-color: white; padding: 20px; border-radius: 10px; text-align: right; border: 2px solid #8B0000; margin-bottom: 20px;">
                <span style="font-size: 20px; color: black; font-weight: bold;">Total a Pagar:</span><br>
                <span style="font-size: 40px; font-weight: 800; color: #8B0000;">{total:.2f} Bs</span>
            </div>
            """, unsafe_allow_html=True)
            
            c_cli, c_pay = st.columns([1, 1.5])
            celular_cliente = c_cli.text_input("📱 WhatsApp (Sin +591)", placeholder="Ej: 70712345")
            metodo = c_pay.radio("Método de Pago", ["💵 Efectivo", "📱 QR / Banco"], horizontal=True)
            
            pago_cliente = 0.0
            cambio = 0.0
            cambio_por_qr = False
            puede_cobrar = True
            
            if metodo == "💵 Efectivo":
                pago_cliente = st.number_input("Monto Recibido (Bs):", min_value=0.0, value=float(total))
                if pago_cliente >= total:
                    cambio = pago_cliente - total
                    st.info(f"💰 Vuelto para cliente: **{cambio:.2f} Bs**")
                    if cambio > 0:
                        cambio_por_qr = st.checkbox(f"🔄 Devolver cambio ({cambio:.2f}) por QR")
                else:
                    st.error(f"⚠️ Faltan {total - pago_cliente:.2f} Bs")
                    puede_cobrar = False
            
            c_btn1, c_btn2 = st.columns([1, 2])
            if c_btn1.button("🗑️ Limpiar", key="btn_limpiar_cart"):
                st.session_state['carrito'] = []
                st.rerun()
            
            if c_btn2.button("✅ COBRAR VENTA", type="primary", disabled=not puede_cobrar, key="btn_cobrar_final"):
                fecha_ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                nuevos_detalles = []
                for item in st.session_state['carrito']:
                    indices = st.session_state['productos'].index[st.session_state['productos']['Producto'] == item['Producto']].tolist()
                    if indices:
                        idx = indices[0]
                        curr = float(st.session_state['productos'].at[idx, 'StockActual'])
                        st.session_state['productos'].at[idx, 'StockActual'] = curr - item['Cantidad']
                        ganancia_item = (item['PrecioUnit'] - item['CostoUnit']) * item['Cantidad']
                        nuevos_detalles.append({
                            'Fecha': fecha_ahora, 'Producto': item['Producto'], 'Categoria': item['Categoria'],
                            'PesoKg': item['Cantidad'], 'CostoUnit': item['CostoUnit'], 'PrecioVentaUnit': item['PrecioUnit'],
                            'Subtotal': item['Subtotal'], 'Ganancia': ganancia_item
                        })
                
                guardar_data(sheet, "productos", st.session_state['productos'])
                if nuevos_detalles:
                    st.session_state['detalles'] = pd.concat([st.session_state['detalles'], pd.DataFrame(nuevos_detalles)], ignore_index=True)
                    guardar_data(sheet, "detalles", st.session_state['detalles'])
                
                detalle_txt = ", ".join([f"{p['Producto']} ({p['Cantidad']:.3f}kg)" for p in st.session_state['carrito']])
                nuevo_venta = pd.DataFrame([{'Fecha': fecha_ahora, 'Detalle': f"Venta: {detalle_txt}", 'Tipo': "Ingreso", 'Monto': total, 'MetodoPago': metodo}])
                st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], nuevo_venta], ignore_index=True)

                if metodo == "💵 Efectivo" and cambio_por_qr and cambio > 0:
                    swap_in = pd.DataFrame([{'Fecha': fecha_ahora, 'Detalle': "Exc. Billete (Swap QR)", 'Tipo': "Ingreso", 'Monto': cambio, 'MetodoPago': "Efectivo"}])
                    swap_out = pd.DataFrame([{'Fecha': fecha_ahora, 'Detalle': "Devolución Cambio", 'Tipo': "Egreso", 'Monto': -cambio, 'MetodoPago': "QR"}])
                    st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], swap_in, swap_out], ignore_index=True)

                guardar_data(sheet, "finanzas", st.session_state['finanzas'])
                
                lineas_prod = "%0A".join([f"▪️ {p['Producto']} ({p['Cantidad']:.3f}kg) - {p['Subtotal']:.2f}Bs" for p in st.session_state['carrito']])
                msg_cambio = f" (Cambio devuelto por QR)" if cambio_por_qr else ""
                mensaje_wa = (f"*🥩 EL CORTE BENIANO*%0A📅 {fecha_ahora}%0A📋 *Su Compra:*%0A{lineas_prod}%0A----------------%0A💰 *TOTAL: {total:.2f} Bs*%0A✅ {metodo}{msg_cambio}%0A🤠 ¡Gracias por su preferencia!")
                
                base_url = "https://wa.me/"
                final_link = f"{base_url}591{celular_cliente.strip()}?text={mensaje_wa}" if celular_cliente else f"{base_url}?text={mensaje_wa}"
                st.session_state['ultimo_ticket'] = {'link': final_link, 'texto': "📲 ENVIAR TICKET WHATSAPP"}
                st.session_state['carrito'] = []
                st.balloons()
                st.rerun()
        else:
            st.info("El carrito está vacío.")

    if st.session_state['ultimo_ticket']:
        st.success("✅ ¡Venta Exitosa!")
        st.markdown(f"""<a href="{st.session_state['ultimo_ticket']['link']}" target="_blank" class="btn-whatsapp">{st.session_state['ultimo_ticket']['texto']}</a>""", unsafe_allow_html=True)
        if st.button("Cerrar Ticket"):
            st.session_state['ultimo_ticket'] = None
            st.rerun()

    st.markdown("---")
    st.subheader("📊 Arqueo de Caja (Tiempo Real)")
    hoy = datetime.now().strftime("%Y-%m-%d")
    st.session_state['finanzas']['Fecha'] = st.session_state['finanzas']['Fecha'].astype(str)
    df_hoy = st.session_state['finanzas'][st.session_state['finanzas']['Fecha'].str.startswith(hoy)]
    
    if not df_hoy.empty:
        if 'MetodoPago' not in df_hoy.columns: df_hoy['MetodoPago'] = 'Efectivo'
        v_qr = df_hoy[(df_hoy['MetodoPago'].str.contains('QR', na=False)) & (df_hoy['Tipo'] == 'Ingreso')]['Monto'].sum()
        v_efec = df_hoy[(df_hoy['MetodoPago'].str.contains('Efectivo', na=False)) & (df_hoy['Tipo'] == 'Ingreso')]['Monto'].sum()
        g_efec = df_hoy[(df_hoy['MetodoPago'].str.contains('Efectivo', na=False)) & (df_hoy['Tipo'] == 'Egreso')]['Monto'].sum()
        g_qr = df_hoy[(df_hoy['MetodoPago'].str.contains('QR', na=False)) & (df_hoy['Tipo'] == 'Egreso')]['Monto'].sum()

        k1, k2, k3 = st.columns(3)
        k1.metric("Total Movido Hoy", f"{(v_qr + v_efec + g_efec + g_qr):.2f} Bs")
        k2.metric("Banco (Neto QR)", f"{(v_qr + g_qr):.2f} Bs")
        k3.metric("EFECTIVO EN CAJA", f"{(v_efec + g_efec):.2f} Bs", delta="Contar Billetes")
    else:
        st.info("Esperando primera venta del día...")

# TAB ADMIN
if st.session_state['admin_mode']:
    with tab2:
        st.header("📦 Gestión de Inventario")
        with st.expander("🔄 Procesar Devolución / Ajuste de Stock", expanded=True):
            st.warning("⚠️ Ajuste directo en la Nube.")
            c_dev1, c_dev2, c_dev3 = st.columns(3)
            df_prods = st.session_state['productos']
            if not df_prods.empty:
                prod_dev = c_dev1.selectbox("Producto a Devolver", df_prods['Producto'].unique())
                cant_dev = c_dev2.number_input("Kilos a Reingresar", min_value=0.0, step=0.1)
                monto_dev = c_dev3.number_input("Dinero a Devolver (Bs)", min_value=0.0, step=1.0)
                if st.button("Confirmar Devolución"):
                    if cant_dev > 0:
                        idx = df_prods.index[df_prods['Producto'] == prod_dev].tolist()[0]
                        curr = float(df_prods.at[idx, 'StockActual'])
                        st.session_state['productos'].at[idx, 'StockActual'] = curr + cant_dev
                        guardar_data(sheet, "productos", st.session_state['productos'])
                        if monto_dev > 0:
                            nuevo_egreso = pd.DataFrame([{'Fecha': datetime.now().strftime("%Y-%m-%d %H:%M"), 'Detalle': f"[DEVOLUCIÓN] {prod_dev} ({cant_dev} Kg)", 'Tipo': 'Egreso', 'Monto': -monto_dev, 'MetodoPago': 'Efectivo'}])
                            st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], nuevo_egreso], ignore_index=True)
                            guardar_data(sheet, "finanzas", st.session_state['finanzas'])
                        st.success(f"✅ Nube Actualizada.")
                        time.sleep(1)
                        st.rerun()
            else:
                st.info("No hay productos.")

        st.write("---")
        with st.expander("➕ Ingresar Nuevo Producto"):
            with st.form("f_inv"):
                c1, c2 = st.columns(2)
                nn = c1.text_input("Nombre del Corte")
                nc = c2.selectbox("Categoría", ["Res", "Pollo", "Cerdo", "Embutidos", "Otros"])
                c3, c4, c5 = st.columns(3)
                nv = c3.number_input("P. Venta (Bs)", 0.0)
                n_costo = c4.number_input("P. Costo (Bs)", 0.0)
                ns = c5.number_input("Stock Inicial (Kg)", 0.0)
                if st.form_submit_button("Guardar"):
                    nuevo = pd.DataFrame([{'Producto': str(nn), 'Categoria': str(nc), 'Costo': float(n_costo), 'PrecioVenta': float(nv), 'StockActual': float(ns)}])
                    st.session_state['productos'] = pd.concat([st.session_state['productos'], nuevo], ignore_index=True)
                    guardar_data(sheet, "productos", st.session_state['productos'])
                    st.rerun()
        
        st.subheader("📋 Inventario Actual (Nube)")
        try: st.session_state['productos']['StockActual'] = pd.to_numeric(st.session_state['productos']['StockActual'], errors='coerce').fillna(0.0)
        except: pass
        df_e = st.data_editor(st.session_state['productos'], num_rows="dynamic", use_container_width=True, key="inv_adm")
        if not df_e.equals(st.session_state['productos']):
            st.session_state['productos'] = df_e
            guardar_data(sheet, "productos", df_e)

    with tab3:
        st.header("📊 Finanzas & Gerencia")
        with st.container(border=True):
            st.subheader("📝 Registrar Gasto Administrativo")
            c_adm1, c_adm2, c_adm3, c_adm4 = st.columns([2, 1, 1, 1])
            desc_adm = c_adm1.text_input("Descripción", placeholder="Ej: Sueldos, Alquiler")
            monto_adm = c_adm2.number_input("Monto (Bs)", min_value=0.0)
            tipo_adm = c_adm3.selectbox("Tipo", ["Gasto (Salida)", "Inyección Capital (Entrada)"])
            if c_adm4.button("Registrar", key="btn_gasto_admin"):
                if monto_adm > 0 and desc_adm:
                    signo = -1 if "Gasto" in tipo_adm else 1
                    tipo_bd = "Egreso" if "Gasto" in tipo_adm else "Ingreso"
                    nuevo_adm = pd.DataFrame([{'Fecha': datetime.now().strftime("%Y-%m-%d %H:%M"), 'Detalle': f"[ADMIN] {desc_adm}", 'Tipo': tipo_bd, 'Monto': monto_adm * signo, 'MetodoPago': 'Transferencia/Otro'}])
                    st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], nuevo_adm], ignore_index=True)
                    guardar_data(sheet, "finanzas", st.session_state['finanzas'])
                    st.success("Registrado en Nube")
                    time.sleep(1)
                    st.rerun()
        
        st.markdown("---")
        st.subheader("📈 Rendimiento de Productos")
        if not st.session_state['detalles'].empty:
            df_det = st.session_state['detalles'].copy()
            df_det_edit = st.data_editor(df_det, num_rows="dynamic", use_container_width=True, key="editor_detalles", column_config={"Subtotal": st.column_config.NumberColumn(format="%.2f"), "Ganancia": st.column_config.NumberColumn(format="%.2f")})
            if not df_det_edit.equals(df_det):
                st.session_state['detalles'] = df_det_edit
                guardar_data(sheet, "detalles", df_det_edit)
            st.info(f"Ganancia Estimada Acumulada: **{df_det_edit['Ganancia'].sum():,.2f} Bs**")
        else:
            st.info("Sin datos de venta.")

        st.markdown("---") 
        st.subheader("📒 Libro Contable (Dinero)")
        st.session_state['finanzas']['Fecha'] = st.session_state['finanzas']['Fecha'].astype(str)
        filtro = st.selectbox("Filtro:", ["Hoy", "Todo el Historial"])
        if filtro == "Hoy":
            df_view = st.session_state['finanzas'][st.session_state['finanzas']['Fecha'].str.startswith(datetime.now().strftime("%Y-%m-%d"))]
        else:
            df_view = st.session_state['finanzas']

        df_fin_edit = st.data_editor(df_view, num_rows="dynamic", use_container_width=True, key="fin_editor_admin", column_config={"Monto": st.column_config.NumberColumn(format="%.2f Bs")})
        if not df_fin_edit.equals(df_view):
            if filtro == "Todo el Historial":
                st.session_state['finanzas'] = df_fin_edit
                guardar_data(sheet, "finanzas", df_fin_edit)
                st.toast("🔄 Actualizando Nube...")
                time.sleep(1)
                st.rerun() 
            else:
                st.warning("Selecciona 'Todo el Historial' para editar.")

