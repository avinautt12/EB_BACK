import xmlrpc.client
import ssl

# --- TUS CREDENCIALES ---
url = 'https://ebik.odoo.com'
db = 'ebik-prod-15375115'
username = 'sistemas@elitebike-mx.com'
password = 'bb36fdae62c3c113fb91de0143eba06da199672d'

# Tomamos un pago real de tu captura de pantalla
REFERENCIA_PAGO = 'PSAN52/2026/00234' 

print(f"--- RASTREANDO LA RUTA DEL DINERO PARA: {REFERENCIA_PAGO} ---")

try:
    context = ssl._create_unverified_context()
    models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url), context=context)
    common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url), context=context)
    uid = common.authenticate(db, username, password, {})

    if not uid:
        print("❌ Error de login")
        exit()

    # 1. Buscamos el Asiento Contable (Account Move) por su nombre/referencia
    move_ids = models.execute_kw(db, uid, password, 
        'account.move', 'search', 
        [[('name', '=', REFERENCIA_PAGO)]]
    )

    if not move_ids:
        print(f"❌ No encontré el movimiento '{REFERENCIA_PAGO}'. Revisa espacios o guiones.")
        exit()

    # 2. Leemos las líneas del asiento (Débitos y Créditos)
    lines = models.execute_kw(db, uid, password,
        'account.move.line', 'search_read',
        [[('move_id', '=', move_ids[0])]],
        {'fields': ['name', 'account_id', 'debit', 'credit']}
    )

    print(f"\nEl pago '{REFERENCIA_PAGO}' movió dinero en estas cuentas:\n")
    print(f"{'CÓDIGO':<15} | {'NOMBRE CUENTA':<40} | {'DÉBITO':<12} | {'CRÉDITO'}")
    print("-" * 90)

    cuenta_ganadora = ""

    for line in lines:
        # account_id viene como [ID, "Codigo Nombre"]
        cuenta_texto = line['account_id'][1]
        codigo = cuenta_texto.split(' ')[0] # Sacamos solo el número
        
        debit = line['debit']
        credit = line['credit']
        
        print(f"{codigo:<15} | {cuenta_texto[0:40]:<40} | ${debit:<11,.2f} | ${credit:,.2f}")
        
        # Lógica: Buscamos la cuenta donde entró el dinero (Débito > 0) 
        # y que NO sea la de Clientes (que suele ser 105 o 120)
        if debit > 0 and not codigo.startswith('105') and not codigo.startswith('401'):
            cuenta_ganadora = codigo

    print("-" * 90)
    if cuenta_ganadora:
        print(f"\n👉 CONCLUSIÓN: El dinero entró a la cuenta: {cuenta_ganadora}")
        print(f"   (Usa este código en tu base de datos MySQL)")
    else:
        print("\n⚠️ No pude determinar automáticamente la cuenta de destino.")

except Exception as e:
    print(f"Error: {e}")