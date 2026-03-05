import xmlrpc.client
import ssl
import time

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

def test_libro_mayor_devoluciones():
    uid, models = get_odoo_models()
    if not uid:
        return

    # --- PARÁMETROS DE PRUEBA: OTROS INGRESOS (DEVOLUCIONES) ---
    cuenta = '102.01.013'
    nomenclatura = 'PSAN52'         # Filtro 1: El código del proyecto
    palabra_extra = 'DEVOLUC'       # Filtro 2: Lo que debe decir en la comunicación
    regla = 'Solo_Debe'
    fecha_inicio = '2026-02-01'
    fecha_fin = '2026-02-28'

    print(f"📊 BUSCANDO EN EL LIBRO MAYOR (account.move.line)")
    print(f"▶ Cuenta: {cuenta}")
    print(f"▶ Filtro Odoo (Proyecto): Contiene '{nomenclatura}'")
    print(f"▶ Filtro Python (Concepto): DEBE contener la palabra '{palabra_extra}'")
    print(f"▶ Regla de cálculo: {regla}")
    print(f"▶ Fechas: {fecha_inicio} al {fecha_fin}")
    print("=" * 100)

    # 1. Buscamos en Odoo todo lo de la cuenta y la fecha
    domain = [
        ('date', '>=', fecha_inicio),
        ('date', '<=', fecha_fin),
        ('parent_state', '=', 'posted'),
        ('account_id.code', '=like', f"{cuenta}%")
    ]

    # Le decimos a Odoo que nos traiga todo lo que tenga 'PSAN52'
    if nomenclatura:
        domain.extend([
            '|', '|', 
            ('name', 'ilike', nomenclatura), 
            ('ref', 'ilike', nomenclatura),
            ('move_id.name', 'ilike', nomenclatura)
        ])

    try:
        apuntes = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'search_read', 
            [domain], 
            {'fields': ['date', 'move_id', 'name', 'ref', 'debit', 'credit', 'partner_id'], 'order': 'date ASC'}
        )

        total_debe = 0.0
        total_haber = 0.0
        movimientos_validos = 0

        print(f"{'FECHA':<12} | {'ASIENTO / REF':<35} | {'DEBE (+)':>12} | {'HABER (-)':>12}")
        print("-" * 100)

        for a in apuntes:
            # Unimos el nombre del asiento y la referencia (comunicación) para buscar ahí
            texto_linea = (str(a.get('name', '')) + ' ' + str(a.get('ref', ''))).upper()
            
            # --- NUEVO FILTRO EN PYTHON ---
            # Si la palabra 'DEVOLUC' NO está en el texto de la línea, la ignoramos y pasamos a la siguiente
            if palabra_extra not in texto_linea:
                continue 
            
            # Si pasó el filtro, extraemos los datos
            fecha = a.get('date', '')
            asiento = a['move_id'][1] if a.get('move_id') else str(a.get('name', ''))
            comunicacion = str(a.get('ref', ''))
            
            # Etiqueta visual para la consola
            info_visual = f"{asiento[:15]}... {comunicacion[:15]}"
            
            debe = float(a.get('debit', 0.0))
            haber = float(a.get('credit', 0.0))

            total_debe += debe
            total_haber += haber
            movimientos_validos += 1

            # Imprimimos los que SÍ pasaron el filtro para que los compares con tu Excel
            print(f"{fecha:<12} | {info_visual:<35} | ${debe:>10,.2f} | ${haber:>10,.2f}")

        print("=" * 100)
        print(f"📈 TOTAL MOVIMIENTOS QUE CUMPLEN AMBAS REGLAS: {movimientos_validos}")
        print("-" * 100)
        print(f"💰 TOTAL DEBE:                    ${total_debe:,.2f}")
        print(f"💸 TOTAL HABER:                   ${total_haber:,.2f}")
        
        print("=" * 100)
        if regla == 'Solo_Debe':
            print(f"🟢 RESULTADO FINAL (REGLA '{regla}'): ${total_debe:,.2f}")
        print("=" * 100)

    except Exception as e:
        print(f"❌ Error al consultar Odoo: {e}")

if __name__ == '__main__':
    test_libro_mayor_devoluciones()