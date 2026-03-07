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

def test_anticipo_proveedores():
    uid, models = get_odoo_models()
    if not uid:
        return

    # --- PARÁMETROS DE PRUEBA: ANTICIPO A PROVEEDORES ---
    cuenta = '120.01.01'
    nomenclatura = 'PANTPV'
    regla = 'Solo_Debe'
    fecha_inicio = '2026-02-01'
    fecha_fin = '2026-02-28'
    
    # 🚀 LA PALABRA QUE QUEREMOS EXCLUIR
    palabras_excluidas = [''] 

    print(f"📊 BUSCANDO EN EL LIBRO MAYOR (account.move.line)")
    print(f"▶ Cuenta: {cuenta} (Anticipo a Proveedores)")
    print(f"▶ Filtro Odoo: Contiene '{nomenclatura}'")
    print(f"▶ Regla de cálculo: {regla}")
    print(f"▶ 🚫 EXCLUYENDO palabra(s): {', '.join(palabras_excluidas)}")
    print(f"▶ Fechas: {fecha_inicio} al {fecha_fin}")
    print("=" * 100)

    # 🚀 Lógica de cuenta exacta (El escudo de seguridad que ya tienes en producción)
    operador = '=' if len(cuenta) >= 8 else '=like'
    valor_busqueda = cuenta if operador == '=' else f"{cuenta}%"

    domain = [
        ('date', '>=', fecha_inicio),
        ('date', '<=', fecha_fin),
        ('parent_state', '=', 'posted'),
        ('account_id.code', operador, valor_busqueda),
    ]

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
            {'fields': ['date', 'move_id', 'name', 'ref', 'debit', 'credit', 'partner_id', 'account_id'], 'order': 'date ASC'}
        )

        total_debe = 0.0
        total_haber = 0.0
        movimientos_validos = 0
        movimientos_excluidos = 0

        print(f"{'FECHA':<12} | {'CUENTA REAL':<12} | {'ASIENTO / REF':<35} | {'DEBE (+)':>12} | {'HABER (-)':>12}")
        print("-" * 100)

        for a in apuntes:
            # Escudo de cuenta real
            account_data = a.get('account_id')
            codigo_real = account_data[1].split(' ')[0] if account_data else ''

            if operador == '=' and codigo_real != cuenta:
                continue

            fecha = a.get('date', '')
            asiento = a['move_id'][1] if a.get('move_id') else ''
            
            # El campo "Comunicación" en Odoo es 'name'
            comunicacion = str(a.get('name', '')).upper()
            referencia = str(a.get('ref', '')).upper()
            asiento_str = str(asiento).upper()

            # --- ESCUDO DE EXCLUSIÓN ---
            # Unimos los textos por si acaso la palabra se esconde en otro lado
            texto_linea = f"{comunicacion} {referencia} {asiento_str}"
            
            debe_excluirse = False
            for palabra in palabras_excluidas:
                if palabra in texto_linea:
                    debe_excluirse = True
                    break
            
            if debe_excluirse:
                movimientos_excluidos += 1
                # Descomenta esta línea si quieres ver qué registros está ignorando:
                # print(f"🚫 EXCLUIDO: {asiento} / {comunicacion}")
                continue # Saltamos este registro y pasamos al siguiente
            # ---------------------------

            debe = float(a.get('debit', 0.0))
            haber = float(a.get('credit', 0.0))

            total_debe += debe
            total_haber += haber
            movimientos_validos += 1

            # Imprimimos lo que era el Asiento + Comunicación para que lo veas claro
            texto_impresion = f"{asiento} ({a.get('name', '')})"
            print(f"{fecha:<12} | {codigo_real:<12} | {texto_impresion[:35]:<35} | ${debe:>10,.2f} | ${haber:>10,.2f}")

        print("=" * 100)
        print(f"📉 Movimientos excluidos por la palabra '{palabras_excluidas[0]}': {movimientos_excluidos}")
        print(f"📈 TOTAL MOVIMIENTOS VALIDOS: {movimientos_validos}")
        print("-" * 100)
        print(f"💰 TOTAL DEBE:                    ${total_debe:,.2f}")
        print(f"💸 TOTAL HABER:                   ${total_haber:,.2f}")

        print("=" * 100)
        if regla == 'Solo_Debe':
            print(f"🟢 RESULTADO FINAL (REGLA '{regla}'): ${total_debe:,.2f}")
        elif regla == 'Solo_Haber':
            print(f"🟢 RESULTADO FINAL (REGLA '{regla}'): ${total_haber:,.2f}")
        print("=" * 100)

    except Exception as e:
        print(f"❌ Error al consultar Odoo: {e}")

if __name__ == '__main__':
    test_anticipo_proveedores()