import xmlrpc.client
import ssl

# --- 1. CONFIGURACIÓN ---
ODOO_URL = 'https://ebik.odoo.com'
ODOO_DB = 'ebik-prod-15375115'
ODOO_USER = 'sistemas@elitebike-mx.com'
ODOO_PASSWORD = 'bb36fdae62c3c113fb91de0143eba06da199672d'

# 🟢 CAMBIA ESTO POR EL CLIENTE QUE QUIERES REVISAR
CLIENTE_A_BUSCAR = "ADAN ORTEGA LEON" 

# FECHAS: 1 de Julio 2025 a 30 de Junio 2026
FECHA_INICIO = '2025-07-01'
FECHA_FIN = '2026-06-30'

def conectar_odoo():
    try:
        context = ssl._create_unverified_context()
        common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common', context=context)
        uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
        models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object', context=context)
        return uid, models
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return None, None

def probar_busqueda():
    uid, models = conectar_odoo()
    if not uid: return

    print(f"\n🔵 Buscando Notas de Crédito para: {CLIENTE_A_BUSCAR}")
    print(f"📅 Rango: {FECHA_INICIO} al {FECHA_FIN}")
    print("📋 Reglas: Uso=G02, Estado=Posted, Cantidad=1, NO Garantías, NO Anticipos (APLANT)\n")

    # --- FILTROS EXACTOS (Lógica Sección C) ---
    domain = [
        ('move_id.move_type', '=', 'out_refund'),       # Es Nota de Crédito
        ('move_id.state', '=', 'posted'),               # Publicada
        ('move_id.invoice_date', '>=', FECHA_INICIO),
        ('move_id.invoice_date', '<=', FECHA_FIN),
        ('move_id.l10n_mx_edi_usage', '=', 'G02'),      # Uso: Devoluciones
        ('quantity', '=', 1),                           # <--- REGLA DE ORO: CANTIDAD 1
        ('partner_id.name', 'ilike', CLIENTE_A_BUSCAR)  # Filtro por nombre de cliente
    ]

    # Pedimos datos relevantes para ver qué encontró
    campos = ['partner_id', 'date', 'move_name', 'name', 'price_subtotal', 'product_id']
    
    lineas = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'search_read', 
        [domain], {'fields': campos})

    total_validado = 0.0
    encontrados = 0

    print(f"{'FECHA':<12} | {'FOLIO':<15} | {'PRODUCTO/DESC':<30} | {'MONTO':<10} | {'ESTADO'}")
    print("-" * 100)

    for linea in lineas:
        nombre_producto = str(linea['name'] or '').upper()
        monto = float(linea['price_subtotal'])
        folio = linea['move_name']
        fecha = linea['date']
        
        # --- FILTROS DE EXCLUSIÓN ---
        es_garantia = 'GARANTIA' in nombre_producto
        es_aplant = 'APLANT' in nombre_producto or 'ANTICIPO' in nombre_producto
        
        estado_msg = "✅ OK"
        
        if es_garantia:
            estado_msg = "❌ IGNORADO (Es Garantía)"
        elif es_aplant:
            estado_msg = "❌ IGNORADO (Es APLANT/Anticipo)"
        else:
            total_validado += monto
            encontrados += 1

        # Recortamos el nombre del producto para que quepa en la tabla
        prod_corto = (nombre_producto[:28] + '..') if len(nombre_producto) > 28 else nombre_producto
        
        print(f"{fecha:<12} | {folio:<15} | {prod_corto:<30} | ${monto:<9.2f} | {estado_msg}")

    print("-" * 100)
    print(f"\n🔢 Total de Líneas Analizadas: {len(lineas)}")
    print(f"✅ Notas Válidas Sumadas: {encontrados}")
    print(f"💰 SUMA FINAL (Solo Válidas): ${total_validado:,.2f}")

if __name__ == '__main__':
    probar_busqueda()