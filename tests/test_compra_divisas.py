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

def test_compra_divisas():
    uid, models = get_odoo_models()
    if not uid:
        return

    # --- PARÁMETROS DE PRUEBA: COMPRA DE DIVISAS ---
    cuenta = '102.01.013'
    nomenclatura = 'COMP/'         
    regla = 'Haber'  # <--- Usamos Haber para respetar el mes de febrero
    fecha_inicio = '2026-02-01'
    fecha_fin = '2026-02-28'

    print(f"📊 BUSCANDO EN EL LIBRO MAYOR (account.move.line)")
    print(f"▶ Cuenta: {cuenta}")
    print(f"▶ Filtro de Nomenclatura: Contiene '{nomenclatura}'")
    print(f"▶ Regla de cálculo: {regla}")
    print(f"▶ Fechas: {fecha_inicio} al {fecha_fin}")
    print("=" * 100)

    # Dominio estricto de fechas y cuenta
    domain = [
        ('date', '>=', fecha_inicio),
        ('date', '<=', fecha_fin),
        ('parent_state', '=', 'posted'),
        ('account_id.code', '=like', f"{cuenta}%")
    ]

    # Filtro por nomenclatura 'COMP'
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

        print(f"{'FECHA':<12} | {'ASIENTO PÓLIZA':<35} | {'DEBE (+)':>12} | {'HABER (-)':>12}")
        print("-" * 100)

        for a in apuntes:
            fecha = a.get('date', '')
            asiento = a['move_id'][1] if a.get('move_id') else str(a.get('name', ''))
            
            debe = float(a.get('debit', 0.0))
            haber = float(a.get('credit', 0.0))

            total_debe += debe
            total_haber += haber

            print(f"{fecha:<12} | {asiento[:35]:<35} | ${debe:>10,.2f} | ${haber:>10,.2f}")

        print("=" * 100)
        print(f"📈 TOTAL MOVIMIENTOS ENCONTRADOS: {len(apuntes)}")
        print("-" * 100)
        print(f"💰 TOTAL DEBE:                    ${total_debe:,.2f}")
        print(f"💸 TOTAL HABER:                   ${total_haber:,.2f}")
        
        print("=" * 100)
        # Aplicamos lógica de la regla
        if regla == 'Haber':
            print(f"🟢 RESULTADO FINAL (REGLA '{regla}'): ${(total_haber - total_debe):,.2f}")
        elif regla == 'Solo_Haber':
            print(f"🟢 RESULTADO FINAL (REGLA '{regla}'): ${total_haber:,.2f}")
        print("=" * 100)

    except Exception as e:
        print(f"❌ Error al consultar Odoo: {e}")

if __name__ == '__main__':
    test_compra_divisas()