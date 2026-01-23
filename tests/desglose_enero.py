import xmlrpc.client
import ssl

# --- CREDENCIALES ---
URL = 'https://ebik.odoo.com'
DB = 'ebik-prod-15375115'
USER = 'sistemas@elitebike-mx.com'
PASS = 'bb36fdae62c3c113fb91de0143eba06da199672d'

# CONFIGURACIÓN
CODIGO = '102.01.013'
FECHA_INI = '2026-01-01'
FECHA_FIN = '2026-01-31'

print(f"--- AUDITANDO LOS $8 MILLONES DE LA CUENTA {CODIGO} ---")

try:
    context = ssl._create_unverified_context()
    common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(URL), context=context)
    models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(URL), context=context)
    
    uid = common.authenticate(DB, USER, PASS, {})

    # 1. Buscar TODOS los IDs de la cuenta (Duplicados incluidos)
    account_ids = models.execute_kw(DB, uid, PASS, 'account.account', 'search', [[('code', '=', CODIGO)]])
    
    # 2. Traer el detalle de movimientos
    domain = [
        ('account_id', 'in', account_ids),
        ('date', '>=', FECHA_INI),
        ('date', '<=', FECHA_FIN),
        ('parent_state', '=', 'posted') 
    ]
    
    # Pedimos nombre, fecha y montos
    lines = models.execute_kw(DB, uid, PASS, 'account.move.line', 'search_read',
        [domain],
        {'fields': ['date', 'name', 'debit', 'credit', 'ref', 'partner_id']}
    )

    print(f"\nSe encontraron {len(lines)} movimientos.\n")
    
    print(f"{'FECHA':<12} | {'REFERENCIA':<20} | {'MONTO NETO'}")
    print("-" * 60)

    suma_total = 0.0
    
    # Mostramos los primeros 20 para no saturar, pero sumamos TODOS
    for i, l in enumerate(lines):
        monto = l['debit'] - l['credit']
        suma_total += monto
        
        # Imprimimos solo si el monto es relevante (ej: > $10,000) o los primeros 20
        if i < 20 or abs(monto) > 100000: 
            print(f"{l['date']:<12} | {l['name']:<20} | ${monto:,.2f}")

    print("-" * 60)
    print(f"💰 GRAN TOTAL SUMADO: ${suma_total:,.2f}")
    print("-" * 60)

except Exception as e:
    print(f"Error: {e}")