import xmlrpc.client
import ssl
import time
import logging

# --- CONFIGURACIÓN Y CREDENCIALES ---
ODOO_URL = 'https://ebik.odoo.com'
ODOO_DB = 'ebik-prod-15375115'
ODOO_USER = 'sistemas@elitebike-mx.com'
ODOO_PASSWORD = 'bb36fdae62c3c113fb91de0143eba06da199672d'

PREFIJOS_MODO_BALANZA = ['6', '5', '7', '2'] 

def get_odoo_models(retries: int = 3, delay: float = 1.0):
    """Attempt to connect and authenticate to Odoo XML-RPC.

    Retries a few times in case of transient network/errors. Returns (uid, models)
    or (None, None) on failure. Uses logging instead of print so server logs capture failures.
    """
    context = ssl._create_unverified_context()
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", context=context)
            models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", context=context)
            uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
            if uid:
                return uid, models, None
            else:
                logging.warning("Odoo authenticate returned falsy uid on attempt %d", attempt)
                last_exc = RuntimeError("Odoo authentication failed (falsy uid)")
        except Exception as e:
            last_exc = e
            logging.exception("Error conexión Odoo (attempt %d): %s", attempt, e)

        # backoff before next attempt
        time.sleep(delay * attempt)

    tb = None
    try:
        import traceback as _tb
        tb = _tb.format_exception(type(last_exc), last_exc, last_exc.__traceback__)
        tb = ''.join(tb)
    except Exception:
        tb = str(last_exc)
    logging.error("Could not connect to Odoo after %d attempts: %s", retries, last_exc)
    return None, None, tb

def obtener_saldo_cuenta_odoo(codigo_cuenta, fecha_inicio, fecha_fin, es_ingreso=True, columna_saldo='Debe', excluir_txt=None, incluir_txt=None, palabras_incluidas=None):
    uid, models, _ = get_odoo_models()
    
    if not uid: return 0.0

    if codigo_cuenta == 'TODAS_VENTAS':
        return _motor_flujo_global_clientes(models, uid, fecha_inicio, fecha_fin)

    # 🚨 LA MAGIA CORREGIDA: 
    # Forzamos el uso de balanza si:
    # 1. Tiene filtros de texto (como tu CREDB)
    # 2. La regla es un acumulado (como tu Acumulado_Debe)
    # 3. La cuenta empieza con los prefijos configurados (como el '2' de tu crédito)
    
    reglas_especiales = ['Acumulado_Haber', 'Acumulado_Debe', 'Solo_Haber', 'Solo_Debe', 'Haber']
    forzar_balanza = bool(incluir_txt or excluir_txt or palabras_incluidas or columna_saldo in reglas_especiales)
    usar_balanza = forzar_balanza or any(codigo_cuenta.startswith(p) for p in PREFIJOS_MODO_BALANZA)
    
    if usar_balanza:
        return _motor_balanza(models, uid, codigo_cuenta, fecha_inicio, fecha_fin, columna_saldo, excluir_txt, incluir_txt, palabras_incluidas)
    else:
        return _motor_flujo(models, uid, codigo_cuenta, fecha_inicio, fecha_fin, es_ingreso)

# ==============================================================================
# MOTOR GLOBAL: PARA TRAER TODA LA COBRANZA SIN IMPORTAR EL BANCO (ESCALABLE)
# ==============================================================================
def _motor_flujo_global_clientes(models, uid, fecha_inicio, fecha_fin):
    print(f"🌍 [Motor Global] Trayendo todos los pagos de clientes...")
    domain = [
        ('date', '>=', fecha_inicio),
        ('date', '<=', fecha_fin),
        ('state', '=', 'posted'),
        ('payment_type', '=', 'inbound'),
        ('partner_type', '=', 'customer')
    ]
    try:
        pagos = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.payment', 'search_read', [domain], {'fields': ['amount']})
        return sum(p['amount'] for p in pagos)
    except Exception as e:
        print(f"❌ Error Motor Global: {e}")
        return 0.0

# ==============================================================================
# MOTOR A: BALANZA (Gastos, Nóminas, Impuestos, Proveedores)
# ==============================================================================
def _motor_balanza(models, uid, codigo_cuenta, fecha_inicio, fecha_fin, columna_saldo='Debe', excluir_txt=None, incluir_txt=None, palabras_incluidas=None):
    
    # BLINDAJE EXTRA: Quitamos espacios accidentales
    codigo_cuenta = str(codigo_cuenta).strip()

    # 🚀 LÓGICA INTELIGENTE DE CUENTAS
    operador = '=' if len(codigo_cuenta) >= 8 else '=like'
    valor_busqueda = codigo_cuenta if operador == '=' else f"{codigo_cuenta}%"

    # 1. DOMINIO BASE
    domain_base = [
        ('date', '<=', fecha_fin),
        ('parent_state', '=', 'posted'),
        ('account_id.code', operador, valor_busqueda), 
    ]

    # 🚨 LA MAGIA: Liberamos las fechas si es un acumulado (Debe o Haber)
    # Esto permite que 'Acumulado_Haber' y 'Acumulado_Debe' traigan el histórico completo
    reglas_acumuladas = ['Acumulado_Haber', 'Acumulado_Debe']
    if columna_saldo not in reglas_acumuladas:
        domain_base.append(('date', '>=', fecha_inicio))

    # 2. DOMINIO ESTRICTO (Con Nomenclatura para Odoo)
    domain_estricto = list(domain_base)
    nomenclatura = None
    
    if incluir_txt and str(incluir_txt).strip():
        nomenclatura = str(incluir_txt).strip()
        domain_estricto.extend([
            '|', '|', 
            ('name', 'ilike', nomenclatura), 
            ('ref', 'ilike', nomenclatura),
            ('move_id.name', 'ilike', nomenclatura)
        ])

    try:
        # AÑADIMOS 'partner_id' (Contacto) y 'account_id' a la lista de campos solicitados
        apuntes = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'search_read', [domain_estricto], {'fields': ['debit', 'credit', 'name', 'ref', 'partner_id', 'account_id']})
        
        # VALIDACIÓN (FALLBACK SEGURO) - Aplicamos el respaldo histórico si es una regla acumulada
        if len(apuntes) == 0 and nomenclatura and columna_saldo in reglas_acumuladas:
            print(f"⚠️ Sin resultados para '{nomenclatura}' en cuenta {codigo_cuenta}. Ejecutando respaldo acumulado...")
            apuntes = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'search_read', [domain_base], {'fields': ['debit', 'credit', 'name', 'ref', 'partner_id', 'account_id']})

        # Preparamos listas de Python
        lista_exclusion = [x.strip().upper() for x in str(excluir_txt).split(',')] if excluir_txt else []
        lista_inclusion = [x.strip().upper() for x in str(palabras_incluidas).split(',')] if palabras_incluidas else []

        neto = 0.0
        
        for a in apuntes:
            # 🛑 ESCUDO FINAL DE SEGURIDAD 🛑
            account_data = a.get('account_id')
            account_name = account_data[1] if account_data else ''
            codigo_real = account_name.split(' ')[0] if account_name else ''

            if operador == '=' and codigo_real != codigo_cuenta:
                continue

            # EXTRAEMOS EL CONTACTO DE ODOO
            contacto = str(a.get('partner_id')[1]) if a.get('partner_id') else ''
            
            # UNIMOS TODO: Asiento + Referencia + Contacto
            texto_linea = (str(a['name'] or '') + ' ' + str(a['ref'] or '') + ' ' + contacto).upper()
            
            # --- FILTROS DE EXCLUSIÓN E INCLUSIÓN ---
            if any(palabra in texto_linea for palabra in lista_exclusion):
                continue 
            if lista_inclusion and not any(palabra in texto_linea for palabra in lista_inclusion):
                continue
            
            # 🧮 CÁLCULO DE COLUMNAS ACTUALIZADO 🧮
            if columna_saldo in ['Solo_Debe', 'Acumulado_Debe']: # <--- Ambas reglas suman puro Debe
                val = a['debit']
            elif columna_saldo in ['Solo_Haber', 'Acumulado_Haber']: # <--- Ambas reglas suman puro Haber
                val = a['credit']
            elif columna_saldo == 'Haber':
                val = a['credit'] - a['debit']
            else: # Debe (Default)
                val = a['debit'] - a['credit']
            
            neto += val
            
        return neto
    
    except Exception as e:
        print(f"❌ Error Balanza (Cuenta {codigo_cuenta}): {e}")
        return 0.0
   
# ==============================================================================
# MOTOR B: FLUJO ESPECÍFICO (Bancos o Proveedores por Diario)
# ==============================================================================
def _motor_flujo(models, uid, codigo_cuenta, fecha_inicio, fecha_fin, es_ingreso):
    print(f"💸 [Motor Flujo] Cuenta específica {codigo_cuenta}...")
    
    # Buscamos la cuenta
    operador = '=like' if len(codigo_cuenta) <= 4 else '='
    account_ids = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.account', 'search', [[('code', operador, codigo_cuenta + ('%' if operador == '=like' else ''))]])
    
    if not account_ids: return 0.0

    # Buscamos sus diarios (Para que sea específico y no mezcle)
    journal_ids = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.journal', 'search', [[('default_account_id', 'in', account_ids)]])

    tipo_pago = 'inbound' if es_ingreso else 'outbound'
    domain = [
        ('date', '>=', fecha_inicio),
        ('date', '<=', fecha_fin),
        ('state', '=', 'posted'),
        ('payment_type', '=', tipo_pago),
    ]
    
    # AQUÍ ESTÁ LA ESCALABILIDAD: Si pediste una cuenta, filtramos por su diario obligatoriamente
    if journal_ids:
        domain.append(('journal_id', 'in', journal_ids))
    else:
        # Si no tiene diario, es un gasto o pasivo, usamos balanza
        return _motor_balanza(models, uid, codigo_cuenta, fecha_inicio, fecha_fin)

    try:
        pagos = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.payment', 'search_read', [domain], {'fields': ['amount']})
        return sum(p['amount'] for p in pagos)
    except Exception as e:
        return 0.0