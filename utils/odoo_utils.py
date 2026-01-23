import xmlrpc.client
import ssl

# --- CREDENCIALES ---
ODOO_URL = 'https://ebik.odoo.com'
ODOO_DB = 'ebik-prod-15375115'
ODOO_USER = 'sistemas@elitebike-mx.com'
ODOO_PASSWORD = 'bb36fdae62c3c113fb91de0143eba06da199672d'

def obtener_saldo_cuenta_odoo(codigo_cuenta, fecha_inicio, fecha_fin):
    """
    Busca pagos en el modelo 'account.payment' replicando los filtros de la vista 'Pagos del Cliente'.
    Filtros aplicados:
      1. Rango de Fechas
      2. Diario: Santander 752 (obtenido vía código de cuenta)
      3. Estado: PUBLICADO (posted) <--- TU REQUISITO CLAVE
      4. Tipo Partner: Cliente (customer)
      5. Tipo Pago: Entrada (inbound)
    """
    try:
        context = ssl._create_unverified_context()
        common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(ODOO_URL), context=context)
        models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(ODOO_URL), context=context)
        
        uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})

        if not uid:
            print("❌ Error de autenticación Odoo")
            return 0.0

        # 1. Encontrar el Diario correcto (Santander 752) usando el código de cuenta
        account_ids = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD,
            'account.account', 'search',
            [[('code', '=', codigo_cuenta)]]
        )
        
        if not account_ids:
            print(f"⚠️ No encontré la cuenta contable {codigo_cuenta}.")
            return 0.0

        # Buscamos qué diario usa esta cuenta por defecto
        journal_ids = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD,
            'account.journal', 'search',
            [[('default_account_id', 'in', account_ids)]]
        )

        print(f"   🔎 Diario encontrado para la cuenta {codigo_cuenta}: {journal_ids}")

        # 2. APLICAR FILTROS EXACTOS DE TU PANTALLA
        domain = [
            ('date', '>=', fecha_inicio),
            ('date', '<=', fecha_fin),
            ('journal_id', 'in', journal_ids),      # Solo en Santander 752
            ('state', '=', 'posted'),               # <--- ¡AQUÍ ESTÁ! Solo Publicados
            ('partner_type', '=', 'customer'),      # Solo Clientes (Ventas)
            ('payment_type', '=', 'inbound')        # Solo Dinero que entra
        ]
        
        # 3. Descargar los pagos
        # Traemos 'amount' (monto) y 'name' (referencia)
        pagos = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD,
            'account.payment', 'search_read',
            [domain],
            {'fields': ['amount', 'name', 'date', 'ref']}
        )

        print(f"   ✅ Se encontraron {len(pagos)} Pagos de Clientes PUBLICADOS.")

        # 4. Sumar el total
        total_ventas = 0.0
        for p in pagos:
            total_ventas += p['amount']

        return total_ventas

    except Exception as e:
        print(f"❌ Error conectando a Odoo: {e}")
        return 0.0