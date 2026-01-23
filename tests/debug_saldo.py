import xmlrpc.client
import ssl

# --- CREDENCIALES ---
URL = 'https://ebik.odoo.com'
DB = 'ebik-prod-15375115'
USER = 'sistemas@elitebike-mx.com'
PASS = 'bb36fdae62c3c113fb91de0143eba06da199672d'

# DATOS A BUSCAR (Los mismos que fallaron en el botón)
CODIGO = '102.01.013'
FECHA_INI = '2026-01-01'
FECHA_FIN = '2026-01-31'

print(f"🕵️ INICIANDO DIAGNÓSTICO PARA: {CODIGO} ({FECHA_INI} - {FECHA_FIN})")

try:
    context = ssl._create_unverified_context()
    common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(URL), context=context)
    models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(URL), context=context)
    
    uid = common.authenticate(DB, USER, PASS, {})
    if not uid:
        print("❌ Error de Login.")
        exit()
    print("✅ Login correcto.")

    # PASO 1: VERIFICAR LA CUENTA
    account_ids = models.execute_kw(DB, uid, PASS, 'account.account', 'search', [[('code', '=', CODIGO)]])
    
    if not account_ids:
        print(f"❌ LA CUENTA {CODIGO} NO EXISTE EN ODOO (Búsqueda exacta falló).")
        # Intento de búsqueda flexible
        print("   Intentando búsqueda flexible...")
        account_ids = models.execute_kw(DB, uid, PASS, 'account.account', 'search', [[('code', 'like', CODIGO)]])
        if account_ids:
             print(f"   ⚠️ Encontré cuentas parecidas: {account_ids}")
        exit()
    
    account_id = account_ids[0]
    print(f"✅ Cuenta encontrada. ID Interno Odoo: {account_id}")

    # PASO 2: BUSCAR MOVIMIENTOS SIN FILTRO DE ESTADO
    # Quitamos lo de 'posted' para ver si los movimientos existen pero están en borrador o cancelados
    domain_crudo = [
        ('account_id', '=', account_id),
        ('date', '>=', FECHA_INI),
        ('date', '<=', FECHA_FIN)
    ]
    
    count_total = models.execute_kw(DB, uid, PASS, 'account.move.line', 'search_count', [domain_crudo])
    print(f"📊 Total de movimientos en fechas (Borrador + Publicados): {count_total}")

    if count_total == 0:
        print("❌ NO HAY MOVIMIENTOS EN ESAS FECHAS. Revisa si la fecha en Odoo es correcta.")
    else:
        # PASO 3: BUSCAR SOLO PUBLICADOS (POSTED)
        # Aquí suele estar el problema. A veces el campo no es 'parent_state', sino 'move_id.state'
        domain_posted = domain_crudo + [('parent_state', '=', 'posted')]
        
        try:
            lines = models.execute_kw(DB, uid, PASS, 'account.move.line', 'search_read', 
                [domain_posted], 
                {'fields': ['date', 'name', 'debit', 'credit', 'parent_state']}
            )
            
            print(f"✅ Movimientos PUBLICADOS encontrados: {len(lines)}")
            
            saldo = 0.0
            print("-" * 60)
            for l in lines:
                monto = l['debit'] - l['credit']
                saldo += monto
                print(f"   📅 {l['date']} | {l['name']} | Estado: {l.get('parent_state', '?')} | Monto: ${monto:,.2f}")
            print("-" * 60)
            print(f"💰 SALDO FINAL CALCULADO: ${saldo:,.2f}")

        except Exception as e_field:
            print(f"⚠️ Error al filtrar por 'parent_state'. Tal vez tu Odoo es una versión antigua.")
            print(f"   Error técnico: {e_field}")

except Exception as e:
    print(f"❌ Error General: {e}")