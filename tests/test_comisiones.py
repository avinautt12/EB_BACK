import xmlrpc.client
import ssl

# --- CONFIGURACIÓN Y CREDENCIALES ---
ODOO_URL = 'https://ebik.odoo.com'
ODOO_DB = 'ebik-prod-15375115'
ODOO_USER = 'sistemas@elitebike-mx.com'
ODOO_PASSWORD = 'bb36fdae62c3c113fb91de0143eba06da199672d'

def get_odoo_models():
    print("🔄 Conectando a Odoo...")
    context = ssl._create_unverified_context()
    try:
        common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", context=context)
        models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", context=context)
        uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
        if uid:
            print("✅ Conexión exitosa a Odoo.\n")
            return uid, models
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
    return None, None

def test_comisiones_bancarias():
    uid, models = get_odoo_models()
    if not uid: return

    # --- PARÁMETROS SEGÚN TU ID 16 EN BD ---
    cuenta = '102.01.013'
    palabra_filtro = 'BANCO' # Esto es lo que pusiste en palabras_incluidas
    regla = 'Solo_Haber'
    fecha_inicio = '2026-02-01'
    fecha_fin = '2026-02-28'

    print(f"📊 PROBANDO CONCEPTO: COMISIONES BANCARIAS")
    print(f"▶ Cuenta: {cuenta}")
    print(f"▶ Palabra obligatoria (Contacto): '{palabra_filtro}'")
    print(f"▶ Regla: {regla}")
    print("=" * 100)

    # El escudo de seguridad para cuenta exacta
    domain = [
        ('date', '>=', fecha_inicio),
        ('date', '<=', fecha_fin),
        ('parent_state', '=', 'posted'),
        ('account_id.code', '=', cuenta)
    ]

    try:
        # Traemos todos los apuntes de la cuenta en el mes
        apuntes = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'search_read',
            [domain], 
            {'fields': ['date', 'name', 'ref', 'credit', 'partner_id'], 'order': 'date ASC'}
        )

        total_haber = 0.0
        print(f"{'FECHA':<12} | {'CONTACTO EN ODOO':<25} | {'REF / COMUNICACIÓN':<25} | {'HABER (-)':>12}")
        print("-" * 100)

        for a in apuntes:
            # Extraer el nombre del contacto
            contacto = a.get('partner_id')[1] if a.get('partner_id') else ""
            referencia = a.get('ref') or a.get('name') or ""
            
            # 🚨 APLICAMOS TU FILTRO DE "BANCO"
            # Buscamos en contacto, nombre o referencia
            texto_busqueda = (str(contacto) + " " + str(referencia)).upper()
            
            if palabra_filtro.upper() in texto_busqueda:
                monto = float(a.get('credit', 0.0))
                total_haber += monto
                print(f"{a.get('date'):<12} | {str(contacto)[:25]:<25} | {str(referencia)[:25]:<25} | ${monto:>10,.2f}")

        print("=" * 100)
        print(f"💰 RESULTADO FINAL PARA EL DASHBOARD: ${total_haber:,.2f}")
        print("=" * 100)
        
        # Validación con tu Excel
        esperado = 28319.30
        if round(total_haber, 2) == esperado:
            print("🎉 ¡NÚMERO EXACTO! Coincide con los $28,319.30 de tu Excel.")
        else:
            print(f"❓ El monto difiere. Excel dice ${esperado:,.2f}")

    except Exception as e:
        print(f"❌ Error al consultar Odoo: {e}")

if __name__ == '__main__':
    test_comisiones_bancarias()