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

def test_libro_mayor_credb():
    uid, models = get_odoo_models()
    if not uid:
        return

    # --- PARÁMETROS DE PRUEBA ACTUALIZADOS ---
    cuenta = '252.01.03'
    nomenclatura = 'CREDB' # Volvemos a poner la nomenclatura
    regla = 'Solo_Haber' 
    fecha_fin = '2026-02-28' 

    print(f"📊 BUSCANDO EN EL LIBRO MAYOR (account.move.line)")
    print(f"▶ Cuenta: {cuenta}")
    print(f"▶ Filtro de Nomenclatura: '{nomenclatura}' (Con plan de respaldo al total)")
    print(f"▶ Regla de cálculo: {regla}")
    print(f"▶ Fechas: Todo el historial hasta el {fecha_fin}")
    print(f"▶ Estado: Solo asientos registrados (posted)")
    print("=" * 100)

    # 1. DOMINIO BASE: Sin nomenclatura (Este será nuestro plan de respaldo)
    domain_base = [
        ('date', '<=', fecha_fin), 
        ('parent_state', '=', 'posted'), 
        ('account_id.code', '=like', f"{cuenta}%")
    ]

    # 2. DOMINIO ESTRICTO: Copiamos el base y le agregamos la exigencia de la nomenclatura
    domain_estricto = list(domain_base)
    if nomenclatura and nomenclatura.strip() != "":
        domain_estricto.extend([
            '|', '|', 
            ('name', 'ilike', nomenclatura), 
            ('ref', 'ilike', nomenclatura),
            ('move_id.name', 'ilike', nomenclatura)
        ])

    try:
        # INTENTO 1: Buscamos con la nomenclatura
        lineas = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'search_read', 
            [domain_estricto], 
            {'fields': ['date', 'move_id', 'name', 'ref', 'debit', 'credit', 'partner_id'], 'order': 'date ASC'}
        )

        # VALIDACIÓN: Si Odoo nos devuelve 0 resultados, aplicamos el plan de respaldo
        if len(lineas) == 0:
            print(f"⚠️ No se encontraron movimientos con la etiqueta '{nomenclatura}'.")
            print("🔄 Ejecutando plan de respaldo: Obteniendo el total general de la cuenta...")
            
            # INTENTO 2: Buscamos con el dominio base (sin la nomenclatura)
            lineas = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'search_read', 
                [domain_base], 
                {'fields': ['date', 'move_id', 'name', 'ref', 'debit', 'credit', 'partner_id'], 'order': 'date ASC'}
            )
        else:
            print(f"✅ Se encontraron movimientos específicos para '{nomenclatura}'.")

        # --- A partir de aquí, las matemáticas son las mismas ---
        total_debe = 0.0
        total_haber = 0.0

        for l in lineas:
            total_debe += float(l.get('debit', 0.0))
            total_haber += float(l.get('credit', 0.0))

        print(f"📈 TOTAL MOVIMIENTOS OBTENIDOS: {len(lineas)}")
        print("-" * 100)
        print(f"💰 TOTAL DEBE:                    ${total_debe:,.2f}")
        print(f"💸 TOTAL HABER:                   ${total_haber:,.2f}")
        
        # Aplicamos la nueva lógica de la regla
        print("=" * 100)
        if regla == 'Solo_Debe':
            print(f"🟢 RESULTADO FINAL (REGLA '{regla}'): ${total_debe:,.2f}")
        elif regla == 'Solo_Haber':
            print(f"🟢 RESULTADO FINAL (REGLA '{regla}'): ${total_haber:,.2f}")
        else:
            print(f"⚖️ BALANCE NETO (Debe - Haber):  ${(total_debe - total_haber):,.2f}")
        print("=" * 100)

    except Exception as e:
        print(f"❌ Error al consultar Odoo: {e}")

if __name__ == '__main__':
    test_libro_mayor_credb()