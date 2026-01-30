import xmlrpc.client
import ssl
from collections import defaultdict

# --- CREDENCIALES ---
ODOO_URL = 'https://ebik.odoo.com'
ODOO_DB = 'ebik-prod-15375115'
ODOO_USER = 'sistemas@elitebike-mx.com'
ODOO_PASSWORD = 'bb36fdae62c3c113fb91de0143eba06da199672d'

def investigar_desglose_601():
    print("\n🕵️‍♂️ --- INVESTIGANDO CUENTAS 601 (ENERO 2026) ---")
    
    try:
        context = ssl._create_unverified_context()
        common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(ODOO_URL), context=context)
        models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(ODOO_URL), context=context)
        
        uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
        
        if not uid:
            print("❌ Error de autenticación")
            return

        # --- FILTROS EXACTOS DE TU MOTOR BALANZA ---
        fecha_inicio = "2026-01-01"
        fecha_fin = "2026-01-31"
        codigo_busqueda = "601"

        domain = [
            ('date', '>=', fecha_inicio),
            ('date', '<=', fecha_fin),
            ('parent_state', '=', 'posted'),      # Solo confirmados
            ('account_id.code', '=like', codigo_busqueda + '%') # Que empiece con 601
        ]

        print(f"📅 Rango: {fecha_inicio} al {fecha_fin}")
        print(f"🔎 Buscando en account.move.line (Apuntes Contables)...")

        # Traemos más campos para ver el detalle
        campos = ['date', 'name', 'ref', 'debit', 'account_id', 'move_name']
        
        apuntes = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 
            'account.move.line', 'search_read', 
            [domain], 
            {'fields': campos}
        )

        print(f"✅ Se encontraron {len(apuntes)} movimientos.\n")

        # --- AGRUPAR POR CUENTA ---
        cuentas = defaultdict(list)
        total_general = 0

        for a in apuntes:
            # account_id viene como [id, "Nombre Cuenta"]
            nombre_cuenta = a['account_id'][1] 
            cuentas[nombre_cuenta].append(a)
            total_general += a['debit']

        # --- IMPRIMIR REPORTE ---
        print(f"{'CUENTA CONTABLE':<50} | {'MONTO (DEBE)':>15}")
        print("-" * 70)

        lista_cuentas_ordenada = sorted(cuentas.keys())

        for cuenta in lista_cuentas_ordenada:
            movimientos = cuentas[cuenta]
            total_cuenta = sum(m['debit'] for m in movimientos)
            
            print(f"{cuenta:<50} | ${total_cuenta:,.2f}")
            
            # SI QUIERES VER EL DETALLE DE CADA CUENTA, DESCOMENTA ESTAS 3 LINEAS:
            # for m in movimientos:
            #     ref = m['name'] or m['ref'] or 'Sin ref'
            #     print(f"    - {m['date']} | {ref[:40]:<40} | ${m['debit']:,.2f}")

        print("-" * 70)
        print(f"{'TOTAL GENERAL (Lo que ve el sistema)':<50} | ${total_general:,.2f}")
        print("-" * 70)

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    investigar_desglose_601()