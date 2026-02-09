import xmlrpc.client
import ssl
from collections import defaultdict

# --- CREDENCIALES ---
ODOO_URL = 'https://ebik.odoo.com'
ODOO_DB = 'ebik-prod-15375115'
ODOO_USER = 'sistemas@elitebike-mx.com'
ODOO_PASSWORD = 'bb36fdae62c3c113fb91de0143eba06da199672d'

def investigar_cuenta_banco():
    print("\n🕵️‍♂️ --- INVESTIGANDO CUENTA 102.01.013 (ENERO 2026) ---")
    
    try:
        context = ssl._create_unverified_context()
        common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(ODOO_URL), context=context)
        models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(ODOO_URL), context=context)
        
        uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
        
        if not uid:
            print("❌ Error de autenticación")
            return

        # --- FILTROS ---
        fecha_inicio = "2026-01-01"
        fecha_fin = "2026-01-31"
        codigo_busqueda = "102.01.013" # <--- TU CUENTA DE BANCO

        domain = [
            ('date', '>=', fecha_inicio),
            ('date', '<=', fecha_fin),
            ('parent_state', '=', 'posted'),      
            ('account_id.code', '=like', codigo_busqueda + '%') 
        ]

        print(f"📅 Rango: {fecha_inicio} al {fecha_fin}")
        print(f"🔎 Buscando movimientos en cuenta {codigo_busqueda}...")

        # [CLAVE] Agregamos 'amount_currency' y 'currency_id' para detectar Dólares
        campos = ['date', 'name', 'ref', 'debit', 'credit', 'amount_currency', 'currency_id', 'move_name']
        
        apuntes = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 
            'account.move.line', 'search_read', 
            [domain], 
            {'fields': campos}
        )

        print(f"✅ Se encontraron {len(apuntes)} movimientos.\n")

        total_debe_mxn = 0.0
        conteo_dolares = 0
        suma_dolares_original = 0.0

        print(f"{'FECHA':<12} | {'REF':<30} | {'MONEDA ORIG':<15} | {'MONTO ORIG':>15} | {'MXN (DEBE)':>15}")
        print("-" * 100)

        for a in apuntes:
            # En cuentas de Activo (Banco), el dinero que entra va al DEBE (Debit)
            monto_mxn = a['debit']
            
            # Datos de moneda original
            moneda_id = a['currency_id'][0] if a['currency_id'] else 0
            moneda_nombre = a['currency_id'][1] if a['currency_id'] else 'MXN'
            monto_original = a['amount_currency']

            # Sumamos al total en Pesos (que es lo que Odoo reporta en su balanza)
            total_debe_mxn += monto_mxn

            # Detectar si es USD (u otra moneda extranjera)
            es_extranjera = (moneda_nombre != 'MXN' and moneda_nombre != '')
            
            if es_extranjera:
                conteo_dolares += 1
                suma_dolares_original += monto_original
                # Imprimimos SOLO los que son moneda extranjera para ver si aquí está el error
                print(f"{a['date']:<12} | {str(a['move_name'])[:30]:<30} | {moneda_nombre:<15} | {monto_original:>15.2f} | {monto_mxn:>15.2f}")

        print("-" * 100)
        print(f"\n📊 RESUMEN FINAL ENERO 2026:")
        print(f"   🔹 Movimientos totales: {len(apuntes)}")
        print(f"   🔹 Movimientos en Moneda Extranjera: {conteo_dolares}")
        print(f"   💵 Suma de montos originales (USD?): {suma_dolares_original:,.2f}")
        print(f"   🇲🇽 TOTAL REAL EN PESOS (DEBE):       ${total_debe_mxn:,.2f}")
        print("-" * 100)

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    investigar_cuenta_banco()