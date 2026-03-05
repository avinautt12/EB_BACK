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
            print("✅ Conexión exitosa.\n")
            return uid, models
    except Exception as e:
        print(f"❌ Error: {e}")
    return None, None

def test_pago_creditos_acumulado():
    uid, models = get_odoo_models()
    if not uid: return

    # --- PARÁMETROS: PAGO CRÉDITOS BANCARIOS (SALIDAS) ---
    cuenta = '252.01.03'
    nomenclatura = 'CREDB'
    regla = 'Acumulado_Debe' # <--- Nueva regla para el total histórico
    fecha_fin = '2026-02-28'

    print(f"📊 EJECUTANDO PRUEBA DE SALDO ACUMULADO (DEBE)")
    print(f"▶ Cuenta: {cuenta}")
    print(f"▶ Filtro buscado: '{nomenclatura}'")
    print(f"▶ Regla: {regla}")
    print(f"▶ Fecha Corte: Hasta {fecha_fin}")
    print("=" * 100)

    # 1. Dominio para búsqueda con nomenclatura (Mes actual)
    # Nota: Aquí usamos la lógica del motor balanza
    domain_estricto = [
        ('date', '<=', fecha_fin),
        ('date', '>=', '2026-02-01'),
        ('parent_state', '=', 'posted'),
        ('account_id.code', '=', cuenta),
        '|', '|',
        ('name', 'ilike', nomenclatura),
        ('ref', 'ilike', nomenclatura),
        ('move_id.name', 'ilike', nomenclatura)
    ]

    # 2. Dominio para respaldo acumulado (Sin límite de fecha inicio)
    domain_base = [
        ('date', '<=', fecha_fin),
        ('parent_state', '=', 'posted'),
        ('account_id.code', '=', cuenta)
    ]

    try:
        # Intento A: Con nomenclatura
        apuntes = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'search_read',
            [domain_estricto], {'fields': ['debit']})

        # Si no hay nada con 'CREDB', disparamos el acumulado (Igual que en el motor)
        if len(apuntes) == 0:
            print(f"⚠️ No hay movimientos '{nomenclatura}' en febrero. Obteniendo respaldo histórico...")
            apuntes = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'search_read',
                [domain_base], {'fields': ['debit', 'name', 'ref', 'date']})
            print(f"✅ Se encontraron {len(apuntes)} registros históricos.")

        total_debe_acumulado = sum(float(a.get('debit', 0.0)) for a in apuntes)

        print("-" * 100)
        # Mostramos los últimos 5 para verificar que son los correctos
        print("🔍 Últimos 5 movimientos del acumulado:")
        for a in apuntes[-5:]:
             print(f"📅 {a.get('date')} | {str(a.get('name'))[:30]:<30} | Debe: ${float(a.get('debit')):>12,.2f}")

        print("=" * 100)
        print(f"💰 TOTAL ACUMULADO (COLUMNA DEBE): ${total_debe_acumulado:,.2f}")
        print("=" * 100)
        
        # Validación con tu Excel
        esperado = 33527140.88
        if round(total_debe_acumulado, 2) == esperado:
            print("🎉 ¡NÚMERO EXACTO! Coincide con los $33,527,140.88 de tu Excel.")
        else:
            print(f"❓ El monto difiere. Odoo dice ${total_debe_acumulado:,.2f} y Excel dice ${esperado:,.2f}")

    except Exception as e:
        print(f"❌ Error en consulta: {e}")

if __name__ == '__main__':
    test_pago_creditos_acumulado()