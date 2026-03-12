import xmlrpc.client
import ssl

# --- CONFIGURACIÓN Y CREDENCIALES ---
ODOO_URL = 'https://ebik.odoo.com'
ODOO_DB = 'ebik-prod-15375115'
ODOO_USER = 'sistemas@elitebike-mx.com'
ODOO_PASSWORD = 'bb36fdae62c3c113fb91de0143eba06da199672d'

# 👇 EL BLINDAJE: Fijamos el ID de la empresa Elite Bike
ODOO_COMPANY_ID = 1 

def get_odoo_models():
    context = ssl._create_unverified_context()
    try:
        common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", context=context)
        models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", context=context)
        uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
        return uid, models
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return None, None

def test_balance_perfecto():
    uid, models = get_odoo_models()
    if not uid:
        return

    cuentas_a_probar = ['102.01.014', '102.01.015', '102.01.018', '102.01.07', '102.01.08', '102.01.09']
    fecha_fin = '2026-01-31'
    
    print(f"\n📊 OBTENIENDO BALANCE HISTÓRICO AL {fecha_fin} (SOLO ELITE BIKE)")
    print("=" * 65)

    gran_total_bancos = 0.0

    for cuenta in cuentas_a_probar:
        # 🚀 EL SECRETO 1: Usamos '%'. Así si Odoo tiene sub-cuentas (102.01.07.1), las suma todas.
        valor_busqueda = f"{cuenta}%"

        # 🚀 EL SECRETO 2 y 3: Sin fecha de inicio y filtrando por empresa.
        domain = [
            ('company_id', '=', ODOO_COMPANY_ID), # <--- AQUÍ PROTEGEMOS LA CONSULTA
            ('date', '<=', fecha_fin), 
            ('parent_state', '=', 'posted'),
            ('account_id.code', '=like', valor_busqueda),
        ]

        try:
            # Agrupamos por 'parent_state' para que Odoo nos devuelva 1 solo renglón con la sumatoria total
            resultado = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'read_group',
                [domain],
                {'fields': ['balance'], 'groupby': ['parent_state']} 
            )

            if resultado:
                balance_cuenta = resultado[0].get('balance', 0.0)
            else:
                balance_cuenta = 0.0
                
            gran_total_bancos += balance_cuenta

            print(f"🏦 Cuenta {cuenta: <10} -> Balance: ${balance_cuenta:>12,.2f}")

        except Exception as e:
            print(f"❌ Error al consultar la cuenta {cuenta}: {e}")

    print("-" * 65)
    print(f"🏆 TOTAL EXACTO DEL REPORTE:     ${gran_total_bancos:>12,.2f}")
    print("=" * 65 + "\n")

if __name__ == '__main__':
    test_balance_perfecto()