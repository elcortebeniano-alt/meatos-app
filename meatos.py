if b2.button("✅ COBRAR", type="primary", disabled=not cobrar):
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                detalles = []
                for item in st.session_state['carrito']:
                    idx = st.session_state['productos'].index[st.session_state['productos']['Producto'] == item['Producto']].tolist()[0]
                    curr = float(st.session_state['productos'].at[idx, 'StockActual'])
                    st.session_state['productos'].at[idx, 'StockActual'] = curr - item['Cantidad']
                    gan = (item['PrecioUnit'] - item['CostoUnit']) * item['Cantidad']
                    detalles.append({'Fecha': now, 'Producto': item['Producto'], 'Categoria': item['Categoria'], 'PesoKg': item['Cantidad'], 'CostoUnit': item['CostoUnit'], 'PrecioVentaUnit': item['PrecioUnit'], 'Subtotal': item['Subtotal'], 'Ganancia': gan})
                
                backend.guardar_data(sheet, "productos", st.session_state['productos'])
                if detalles:
                    st.session_state['detalles'] = pd.concat([st.session_state['detalles'], pd.DataFrame(detalles)], ignore_index=True)
                    backend.guardar_data(sheet, "detalles", st.session_state['detalles'])
                
                txt = ", ".join([f"{p['Producto']} ({p['Cantidad']:.3f}kg)" for p in st.session_state['carrito']])
                fin = pd.DataFrame([{'Fecha': now, 'Detalle': f"Venta: {txt}", 'Tipo': "Ingreso", 'Monto': total, 'MetodoPago': metodo, 'Ganancia': total_ganancia}])
                st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], fin], ignore_index=True)
                
                if metodo == "💵 Efectivo" and qr_vuelto and cambio > 0:
                    swap = pd.DataFrame([
                        {'Fecha': now, 'Detalle': "Exc. Billete (Swap)", 'Tipo': "Ingreso", 'Monto': cambio, 'MetodoPago': "Efectivo", 'Ganancia': 0},
                        {'Fecha': now, 'Detalle': "Devolución Cambio", 'Tipo': "Egreso", 'Monto': -cambio, 'MetodoPago': "QR", 'Ganancia': 0}
                    ])
                    st.session_state['finanzas'] = pd.concat([st.session_state['finanzas'], swap], ignore_index=True)
                
                backend.guardar_data(sheet, "finanzas", st.session_state['finanzas'])
                
                # --- GENERACIÓN DE TICKETS ---
                # 1. Link WhatsApp
                lineas = "%0A".join([f"> {p['Producto']} ({p['Cantidad']:.3f}kg) - {p['Subtotal']:.2f}Bs" for p in st.session_state['carrito']])
                msg = f"*** EL CORTE BENIANO ***%0AFecha: {now}%0A{lineas}%0A----------------%0ATOTAL: {total:.2f} Bs%0APago: {metodo}"
                link_wa = f"https://wa.me/591{cel.strip()}?text={msg}" if cel else f"https://wa.me/?text={msg}"
                
                # 2. Link Ticket HTML (Universal)
                link_html = backend.generar_html_ticket(st.session_state['carrito'], total, now, metodo)

                st.session_state['ultimo_ticket'] = {'link_wa': link_wa, 'link_html': link_html}
                st.session_state['carrito'] = []
                st.balloons(); st.success("¡Cobrado!"); time.sleep(1); st.rerun()

    if st.session_state['ultimo_ticket']:
        st.success("✅ Venta OK")
        
        c_t1, c_t2 = st.columns(2)
        # WhatsApp
        c_t1.markdown(f"<a href='{st.session_state['ultimo_ticket']['link_wa']}' target='_blank' class='btn-whatsapp'>📲 ENVIAR WHATSAPP</a>", unsafe_allow_html=True)
        
        # Botón Imprimir HTML (Abre nueva pestaña)
        html_btn = f"""
        <a href="{st.session_state['ultimo_ticket']['link_html']}" target="_blank" 
           style="display: inline-flex; align-items: center; justify-content: center; background-color: #333; color: white; font-weight: bold; padding: 0.8rem 1.5rem; border-radius: 12px; text-decoration: none; width: 100%; font-size: 1.1rem; margin-top: 10px;">
           🖨️ VER TICKET
        </a>
        """
        c_t2.markdown(html_btn, unsafe_allow_html=True)

        if st.button("Cerrar Ticket"): st.session_state['ultimo_ticket'] = None; st.rerun()
