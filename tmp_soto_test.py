from utils.odoo_utils import get_odoo_models, ODOO_DB, ODOO_PASSWORD

uid, models, err = get_odoo_models()
if not uid:
    print("Error Odoo:", err)
    exit(1)

# 1. Buscar partner con ref GC395
partners = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD,
    'res.partner', 'search_read',
    [[['ref', '=', 'GC395']]],
    {'fields': ['id', 'name', 'ref'], 'limit': 5})
print("Partner GC395:", partners)

if not partners:
    partners2 = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD,
        'res.partner', 'search_read',
        [[['name', 'ilike', 'SOTO ACOSTA']]],
        {'fields': ['id', 'name', 'ref'], 'limit': 10})
    print("Por nombre 'SOTO ACOSTA':", partners2)

    partners3 = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD,
        'res.partner', 'search_read',
        [[['name', 'ilike', 'SOTO']]],
        {'fields': ['id', 'name', 'ref'], 'limit': 10})
    print("Por nombre 'SOTO':", partners3)
else:
    pid = partners[0]['id']
    # Sale orders (incluyendo draft para ver todo)
    orders_all = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD,
        'sale.order', 'search_read',
        [[['partner_id', '=', pid]]],
        {'fields': ['name', 'state', 'date_order'], 'limit': 20})
    print(f"Todas las ordenes de {partners[0]['name']} (id={pid}): {len(orders_all)}")
    for o in orders_all:
        print(f"  {o['name']}  state={o['state']}  fecha={o['date_order']}")
