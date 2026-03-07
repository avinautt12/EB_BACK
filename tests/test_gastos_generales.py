import xmlrpc.client
import ssl

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
            print("✅ Conexión exitosa.\n")
            return uid, models
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
    return None, None

def test_gastos_generales():
    uid, models = get_odoo_models()
    if not uid: return

    # --- PARÁMETROS DE LA CUENTA ---
    cuenta = '102.01.013'
    fecha_inicio = '2026-02-01'
    fecha_fin = '2026-02-28'

    # --- TUS REGLAS DE FILTRADO AVANZADO ---
    # Ponemos también versiones con acento por si el contador lo escribió así
    frases_incluidas = [
        ''
    ]
    
    frases_excluidas = [
        'INVERSION', 'INVERSIÓN', 'ANTICIPO', 'DEVOLUCION', 'DEVOLUCIÓN', 'NOMINA', 'SATPP', 'COMP/', 'IMPORTACIONES'
    ]

    print(f"📊 PROBANDO CONCEPTO: GASTOS GENERALES")
    print(f"▶ Cuenta: {cuenta}")
    print(f"▶ Buscará: {', '.join(frases_incluidas[:4])}...")
    print(f"▶ Ignorará: {', '.join(frases_excluidas)}")
    print("-" * 110)

    # 1. Traemos TODOS los movimientos de la cuenta en febrero
    domain = [
        ('date', '>=', fecha_inicio),
        ('date', '<=', fecha_fin),
        ('parent_state', '=', 'posted'),
        ('account_id.code', '=', cuenta)
    ]

    try:
        # Solicitamos todos los campos necesarios, incluyendo el nombre del Asiento (move_id)
        apuntes = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'search_read',
            [domain], 
            {'fields': ['date', 'name', 'ref', 'credit', 'debit', 'move_id'], 'order': 'date ASC'}
        )

        total_haber = 0.0
        conteo = 0
        
        print(f"{'FECHA':<12} | {'COMUNICACIÓN / REF (Fragmento)':<45} | {'HABER (-)':>12}")
        print("-" * 110)

        for a in apuntes:
            # Extraemos la referencia del encabezado del asiento
            asiento_nombre = a['move_id'][1] if a.get('move_id') else ""
            
            # UNIMOS TODO y lo convertimos a MAYÚSCULAS para que no importe cómo lo escribieron
            texto_busqueda = (str(a.get('name') or '') + " " + 
                              str(a.get('ref') or '') + " " + 
                              str(asiento_nombre)).upper()
            
            # --- LÓGICA DE FILTRADO ---
            # 1. Verificamos si tiene ALGUNA de las frases válidas
            es_valido = any(frase in texto_busqueda for frase in frases_incluidas)
            
            # 2. Si es válido, verificamos que NO tenga las palabras prohibidas
            if es_valido:
                tiene_prohibida = any(mala in texto_busqueda for mala in frases_excluidas)
                if tiene_prohibida:
                    es_valido = False # Lo descartamos
            
            # Si pasó la prueba, lo sumamos (usamos crédito porque es salida de dinero del banco)
            if es_valido:
                monto = float(a.get('credit', 0.0))
                
                # Solo imprimimos si realmente salió dinero
                if monto > 0:
                    total_haber += monto
                    conteo += 1
                    
                    # Cortamos el texto para que se vea bonito en la consola
                    texto_limpio = texto_busqueda.replace('\n', ' ')
                    print(f"✅ {a.get('date')} | {texto_limpio[:45]:<45} | ${monto:>10,.2f}")

        print("-" * 110)
        print(f"📈 Movimientos encontrados que cumplen las reglas: {conteo}")
        print(f"💰 TOTAL DE GASTOS GENERALES (HABER): ${total_haber:,.2f}")
        print("=" * 110)

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    test_gastos_generales()