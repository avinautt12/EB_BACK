from utils.odoo_utils import get_odoo_models, ODOO_DB, ODOO_PASSWORD

uid, models, odoo_err = get_odoo_models()
print('UID', uid)
print('ODOO_ERR:', odoo_err)
cliente='JUAN MANUEL RUACHO RANGEL'
if not uid:
    print('No uid')
    raise SystemExit(1)
partners = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'res.partner', 'search_read', [[['name', 'ilike', cliente]]], {'fields': ['id','name','ref']})
print('partners count', len(partners))
if partners:
    partner_ids=[p['id'] for p in partners]
    orders = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'sale.order', 'search_read', [[['partner_id','in',partner_ids]]], {'fields': ['id','name','date_order','partner_id','order_line','amount_total']})
    print('orders count', len(orders))
    all_line_ids=[]
    for o in orders:
        all_line_ids.extend(o.get('order_line') or [])
    print('all_line_ids len', len(all_line_ids))
    if all_line_ids:
        all_lines = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'sale.order.line', 'search_read', [[['id','in', all_line_ids]]], {'fields':['id','order_id','product_id','name','product_uom_qty','qty_delivered','price_unit']})
        print('all_lines', len(all_lines))
    pf = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'stock.picking', 'fields_get', [], {})
    print('picking fields count', len(pf) if isinstance(pf, dict) else type(pf))
    if orders:
        name=orders[0].get('name')
        print('first order', name)
        pickings = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'stock.picking', 'search_read', [[['origin','=',name]]], {'fields':['name','state','picking_type_id','scheduled_date','move_ids','move_line_ids']})
        print('pickings', len(pickings))
        if pickings:
            p=pickings[0]
            print('p keys', list(p.keys()))
            mid = p.get('move_ids') or []
            print('move_ids len', len(mid))
            if mid:
                # Determinar campos disponibles antes de leer stock.move
                try:
                    move_fields = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'stock.move', 'fields_get', [], {})
                    move_keys = set(move_fields.keys()) if isinstance(move_fields, dict) else set()
                except Exception:
                    move_keys = set()

                m_fields = ['product_id', 'product_uom_qty', 'state']
                if 'quantity_done' in move_keys:
                    m_fields.append('quantity_done')
                elif 'qty_done' in move_keys:
                    m_fields.append('qty_done')

                try:
                    mrows = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'stock.move', 'search_read', [[['id','in',mid]]], {'fields': m_fields})
                    print('move rows', len(mrows))
                except Exception as ex:
                    print('stock.move read failed:', ex)
print('done')
