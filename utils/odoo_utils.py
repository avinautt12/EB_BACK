import xmlrpc.client
import ssl

# --- CONFIGURACIÓN Y CREDENCIALES ---
ODOO_URL = 'https://ebik.odoo.com'
ODOO_DB = 'ebik-prod-15375115'
ODOO_USER = 'sistemas@elitebike-mx.com'
ODOO_PASSWORD = 'bb36fdae62c3c113fb91de0143eba06da199672d'

# --- CONFIGURACIÓN DE ESTRATEGIAS ---
# Aquí defines qué cuentas se calculan por BALANZA (Contable) y cuáles por FLUJO (Pagos)
# Si la cuenta empieza con alguno de estos números, usará el Motor de Balanza.
PREFIJOS_MODO_BALANZA = ['6', '5', '7'] 
# Ejemplo: 
# '6' = Gastos (Se provisionan en balanza)
# '5' = Costos
# '7' = Otros Gastos

def get_odoo_models():
    """Establece la conexión con Odoo y devuelve (uid, models)"""
    try:
        context = ssl._create_unverified_context()
        common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(ODOO_URL), context=context)
        models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(ODOO_URL), context=context)
        uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
        return uid, models
    except Exception as e:
        print(f"❌ Error conexión Odoo: {e}")
        return None, None

def obtener_saldo_cuenta_odoo(codigo_cuenta, fecha_inicio, fecha_fin, es_ingreso=True):
    """
    Función Maestra: Decide qué motor usar basándose en el código de cuenta.
    """
    uid, models = get_odoo_models()
    if not uid: return 0.0

    # 1. DECIDIR ESTRATEGIA
    # Si el código empieza con 6, 5 o 7, usamos Balanza. Si no, usamos Flujo.
    usar_balanza = any(codigo_cuenta.startswith(p) for p in PREFIJOS_MODO_BALANZA)

    if usar_balanza:
        return _motor_balanza(models, uid, codigo_cuenta, fecha_inicio, fecha_fin)
    else:
        return _motor_flujo(models, uid, codigo_cuenta, fecha_inicio, fecha_fin, es_ingreso)

# ==============================================================================
# MOTOR A: BALANZA DE COMPROBACIÓN (Apuntes Contables)
# Ideal para: Gastos (600), Costos (500), Impuestos devengados
# ==============================================================================
def _motor_balanza(models, uid, codigo_cuenta, fecha_inicio, fecha_fin):
    print(f"   📊 [Motor Balanza] Consultando cuenta {codigo_cuenta}...")
    
    # Busca todas las cuentas que empiecen con el código (ej. 601 -> 601.01, 601.05)
    domain = [
        ('date', '>=', fecha_inicio),
        ('date', '<=', fecha_fin),
        ('parent_state', '=', 'posted'),      # Solo asientos confirmados
        ('account_id.code', '=like', codigo_cuenta + '%'), # Búsqueda jerárquica
        # ('company_id', '=', 1)              # <--- DESCOMENTAR SI ES NECESARIO FILTRAR EMPRESA
    ]

    try:
        # Consultamos el detalle contable (account.move.line)
        apuntes = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 
            'account.move.line', 'search_read', 
            [domain], 
            {'fields': ['debit', 'credit']} # Traemos debe y haber
        )
        
        # Para gastos (cuentas deudoras), nos interesa el DEBE (debit)
        # Si quisieras ingresos contables, sería el HABER (credit)
        total = sum(a['debit'] - a['credit'] for a in apuntes)
        
        # Si el resultado es negativo (raro en gastos), lo devolvemos tal cual
        return total

    except Exception as e:
        print(f"   ❌ Error en Motor Balanza: {e}")
        return 0.0

# ==============================================================================
# MOTOR B: FLUJO DE EFECTIVO (Pagos Reales)
# Ideal para: Ventas cobradas, Créditos pagados, Bancos
# ==============================================================================
def _motor_flujo(models, uid, codigo_cuenta, fecha_inicio, fecha_fin, es_ingreso):
    print(f"   💸 [Motor Flujo] Consultando cuenta {codigo_cuenta}...")

    # 1. Configurar búsqueda de cuenta
    if len(codigo_cuenta) <= 4:
        operador = '=like'
        valor_busqueda = codigo_cuenta + '%'
    else:
        operador = '='
        valor_busqueda = codigo_cuenta

    # 2. Obtener IDs de las cuentas
    account_ids = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.account', 'search', 
        [[('code', operador, valor_busqueda)]]
    )
    
    if not account_ids:
        print(f"   ⚠️ Cuenta {codigo_cuenta} no encontrada en plan contable.")
        return 0.0

    # 3. Obtener Diarios vinculados (para filtrar pagos)
    journal_ids = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.journal', 'search', 
        [[('default_account_id', 'in', account_ids)]]
    )

    # 4. Configurar Filtros
    tipo_partner = 'customer' if es_ingreso else 'supplier'
    tipo_pago = 'inbound' if es_ingreso else 'outbound'

    domain = [
        ('date', '>=', fecha_inicio),
        ('date', '<=', fecha_fin),
        ('state', '=', 'posted'),
        ('partner_type', '=', tipo_partner),
        ('payment_type', '=', tipo_pago),
        # ('company_id', '=', 1) # <--- DESCOMENTAR SI ES NECESARIO FILTRAR EMPRESA
    ]
    
    if journal_ids:
            domain.append(('journal_id', 'in', journal_ids))

    try:
        pagos = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.payment', 'search_read', [domain], {'fields': ['amount']})
        total = sum(p['amount'] for p in pagos)
        return total

    except Exception as e:
        print(f"   ❌ Error en Motor Flujo: {e}")
        return 0.0