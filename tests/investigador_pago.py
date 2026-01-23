import xmlrpc.client
import ssl

# --- CREDENCIALES ---
URL = 'https://ebik.odoo.com'
DB = 'ebik-prod-15375115'
USER = 'sistemas@elitebike-mx.com'
PASS = 'bb36fdae62c3c113fb91de0143eba06da199672d'

# PAGO A INVESTIGAR (Uno que sabemos que existe)
REF_PAGO = 'PSAN52/2026/00234' 

print(f"--- INVESTIGANDO A FONDO EL PAGO: {REF_PAGO} ---")

try:
    context = ssl._create_unverified_context()
    models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(URL), context=context)
    common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(URL), context=context)
    uid = common.authenticate(DB, USER, PASS, {})

    if not uid:
        print("❌ Error de login")
        exit()

    # 1. Buscar el asiento por nombre
    move_ids = models.execute_kw(DB, uid, PASS, 'account.move', 'search', [[('name', '=', REF_PAGO)]])
    
    if not move_ids:
        print("❌ No encontré el pago. ¿Seguro que la referencia está bien escrita?")
        exit()

    # 2. Leer las líneas (Apuntes contables) de ese asiento
    lines = models.execute_kw(DB, uid, PASS, 'account.move.line', 'search_read',
        [[('move_id', '=', move_ids[0])]],
        {'fields': ['account_id', 'date', 'debit', 'credit', 'name']}
    )

    print(f"\n✅ El pago existe y tiene {len(lines)} líneas contables.")
    print("-" * 80)
    print(f"{'ID CUENTA':<10} | {'CÓDIGO CUENTA':<15} | {'FECHA REAL':<12} | {'MONTO (DÉBITO)'}")
    print("-" * 80)

    id_cuenta_correcta = 0

    for l in lines:
        # account_id viene como [874, "102.01.013 00000752"]
        id_acc = l['account_id'][0]
        nombre_acc = l['account_id'][1]
        codigo = nombre_acc.split(' ')[0]
        
        if l['debit'] > 0: # Esta es la línea donde entró el dinero
            id_cuenta_correcta = id_acc
            print(f"👉 {id_acc:<8} | {codigo:<15} | {l['date']:<12} | ${l['debit']:,.2f}")
        else:
            print(f"   {id_acc:<8} | {codigo:<15} | {l['date']:<12} | ${l['debit']:,.2f}")

    print("-" * 80)
    
    # 3. COMPARACIÓN CON EL ID QUE ESTÁBAMOS USANDO (874)
    print(f"\n🔎 ANÁLISIS:")
    if id_cuenta_correcta == 874:
        print("   El ID de la cuenta COINCIDE (874). El problema podría ser la FECHA.")
        print(f"   Fecha en el pago: {lines[0]['date']}")
    else:
        print(f"   🚨 ¡ALERTA! El ID de la cuenta es DIFERENTE.")
        print(f"   El script anterior buscaba en ID 874.")
        print(f"   Pero el dinero realmente está en ID {id_cuenta_correcta}.")
        print("   (Esto pasa cuando hay cuentas duplicadas o multi-compañía)")

except Exception as e:
    print(f"Error: {e}")