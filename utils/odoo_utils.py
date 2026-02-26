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

# 1. Agregamos el parámetro columna_saldo (por defecto 'Debe')
def obtener_saldo_cuenta_odoo(codigo_cuenta, fecha_inicio, fecha_fin, es_ingreso=True, columna_saldo='Debe', excluir_txt=None):
    uid, models = get_odoo_models()
    if not uid: return 0.0

    if codigo_cuenta == 'TODAS_VENTAS':
        return _motor_flujo_global_clientes(models, uid, fecha_inicio, fecha_fin)

    usar_balanza = any(codigo_cuenta.startswith(p) for p in PREFIJOS_MODO_BALANZA)
    
    if usar_balanza:
        # Pasamos el filtro al motor
        return _motor_balanza(models, uid, codigo_cuenta, fecha_inicio, fecha_fin, columna_saldo, excluir_txt)
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
# MOTOR A: BALANZA (Gastos, Nóminas, Impuestos)
# ==============================================================================
# 2. Actualizamos el motor de balanza para hacer la resta correcta
def _motor_balanza(models, uid, codigo_cuenta, fecha_inicio, fecha_fin, columna_saldo='Debe', excluir_txt=None):
    domain = [
        ('date', '>=', fecha_inicio),
        ('date', '<=', fecha_fin),
        ('parent_state', '=', 'posted'),
        ('account_id.code', '=like', codigo_cuenta + '%'), 
    ]
    try:
        # Traemos 'name' y 'ref' para buscar las palabras prohibidas
        apuntes = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'search_read', [domain], {'fields': ['debit', 'credit', 'name', 'ref']})
        
        # Preparamos la lista de palabras a excluir (si existen)
        lista_exclusion = []
        if excluir_txt:
            # Convierte 'TRASPASO,DEVOLUCION' en ['TRASPASO', 'DEVOLUCION']
            lista_exclusion = [x.strip().upper() for x in excluir_txt.split(',')]

        neto = 0.0
        
        for a in apuntes:
            # Unimos la etiqueta y la referencia para buscar ahí
            texto_linea = (str(a['name'] or '') + ' ' + str(a['ref'] or '')).upper()
            
            # --- FILTRO DE EXCLUSIÓN ---
            # Si alguna palabra prohibida está en el texto, saltamos este movimiento
            if any(palabra in texto_linea for palabra in lista_exclusion):
                # print(f"🚫 Ignorando movimiento: {texto_linea}") # Descomentar para debug
                continue 
            
            # Cálculo normal
            if columna_saldo == 'Solo_Debe':
                val = a['debit']
            elif columna_saldo == 'Solo_Haber':
                val = a['credit']
            elif columna_saldo == 'Haber':
                val = a['credit'] - a['debit']
            else: # Debe (Default)
                val = a['debit'] - a['credit']
            
            neto += val
            
        return neto
    except Exception as e:
        print(f"Error Balanza: {e}")
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