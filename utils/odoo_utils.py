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

def obtener_saldo_cuenta_odoo(codigo_cuenta, fecha_inicio, fecha_fin, es_ingreso=True):
    uid, models, _ = get_odoo_models()
    if not uid:
        return 0.0

    # LÓGICA ESCALABLE:
    # 1. Si la clave es 'TODAS_VENTAS', traemos la cobranza global (los 15M)
    if codigo_cuenta == 'TODAS_VENTAS':
        return _motor_flujo_global_clientes(models, uid, fecha_inicio, fecha_fin)

    # 2. Si no, usamos la lógica de cuentas específica
    usar_balanza = any(codigo_cuenta.startswith(p) for p in PREFIJOS_MODO_BALANZA)
    if usar_balanza:
        return _motor_balanza(models, uid, codigo_cuenta, fecha_inicio, fecha_fin)
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
def _motor_balanza(models, uid, codigo_cuenta, fecha_inicio, fecha_fin):
    domain = [
        ('date', '>=', fecha_inicio),
        ('date', '<=', fecha_fin),
        ('parent_state', '=', 'posted'),
        ('account_id.code', '=like', codigo_cuenta + '%'), 
    ]
    try:
        # Traemos Debe y Haber
        apuntes = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'search_read', [domain], {'fields': ['debit', 'credit']})
        
        # Cálculo: Cargos (Debe) - Abonos (Haber)
        neto = sum(a['debit'] - a['credit'] for a in apuntes)
        
        # Para cuentas de Pasivo (Victor 205, Scott 201), el pago es la disminución del saldo
        # Invertimos el signo si es necesario para que el egreso sea positivo en el tablero
        if codigo_cuenta.startswith('2'):
            return abs(neto) if neto < 0 else neto
            
        return neto
    except Exception:
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