from utils.odoo_utils import get_odoo_models, ODOO_DB, ODOO_PASSWORD

uid, models, odoo_err = get_odoo_models()
print('UID:', uid)

# fields_get for stock.picking
try:
    fg = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'stock.picking', 'fields_get', [], {})
    print('stock.picking fields_get keys count:', len(fg.keys()))
    sample = list(fg.keys())[:50]
    print('sample keys:', sample)
except Exception as e:
    print('ERROR fields_get stock.picking:', repr(e))

# find partners
partners = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'res.partner', 'search_read', [[['name','ilike','BIKES MART']]], {'fields':['id','name'], 'limit': 10})
print('partners found:', partners[:5])
if not partners:
    partners = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'res.partner', 'search_read', [[['name','ilike','BIKES']]], {'fields':['id','name'], 'limit': 10})
    print('fallback partners:', partners[:5])

partner_ids = [p['id'] for p in partners]
print('partner_ids sample:', partner_ids[:5])

# fetch orders
orders = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'sale.order', 'search_read', [[['partner_id','in', partner_ids]]], {'fields':['id','name'], 'limit': 10})
print('orders sample:', orders[:5])
if not orders:
    print('No orders found for partner_ids; exiting')
    raise SystemExit

order_name = orders[0]['name']
print('order_name:', order_name)

# Try several field sets on stock.picking
field_sets = [
    ['name','state','move_ids','scheduled_date'],
    ['name','state','move_line_ids','scheduled_date'],
    ['name','state','move_lines','scheduled_date'],
    ['name','state','move_ids','move_line_ids','scheduled_date'],
]

for fs in field_sets:
    try:
        print('\nTrying fields:', fs)
        res = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'stock.picking', 'search_read', [[['origin','=', order_name]]], {'fields': fs})
        print('Result count:', len(res))
        if res:
            print('First picking keys:', list(res[0].keys()))
    except Exception as e:
        print('ERROR for fields', fs, ':', repr(e))

# Also check sale.order fields_get
try:
    fg_so = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'sale.order', 'fields_get', [], {})
    print('\nsale.order fields sample:', list(fg_so.keys())[:50])
except Exception as e:
    print('ERROR fields_get sale.order:', repr(e))

print('\nDone')
