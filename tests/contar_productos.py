import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.odoo_utils import get_odoo_models, ODOO_DB, ODOO_PASSWORD, ODOO_URL

print(f"Conectando a {ODOO_URL} / {ODOO_DB}")

uid, models, err = get_odoo_models()
if err or not uid:
    print(f"Error conectando a Odoo: {err}")
    sys.exit(1)

print(f"uid={uid}")

domain_move = [
    ['move_type', '=', 'out_invoice'],
    ['state',     '=', 'posted'],
    ['invoice_date', '>=', '2026-01-01'],
    ['invoice_date', '<=', '2026-04-16'],
]
move_ids_all = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move', 'search', [domain_move], {'limit': 0})
print(f"Facturas posted (todas): {len(move_ids_all)}")

domain_cobradas = domain_move + [['payment_state', 'in', ['paid', 'partial']]]
move_ids_cobradas = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move', 'search', [domain_cobradas], {'limit': 0})
print(f"Facturas cobradas (paid/partial): {len(move_ids_cobradas)}")

domain_cobradas_co1 = domain_cobradas + [['company_id', '=', 1]]
move_ids_co1 = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move', 'search', [domain_cobradas_co1], {'limit': 0})
print(f"Facturas cobradas company_id=1: {len(move_ids_co1)}")

domain_todas_co1 = domain_move + [['company_id', '=', 1]]
move_ids_todas_co1 = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move', 'search', [domain_todas_co1], {'limit': 0})
print(f"Facturas posted (todas) company_id=1: {len(move_ids_todas_co1)}")

if not move_ids_all:
    sys.exit(0)

def contar_lineas(move_ids, etiqueta, filtrar_monto=True):
    if not move_ids:
        print(f"\n[{etiqueta}] No hay facturas")
        return
    lineas = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD,
        'account.move.line', 'search_read',
        [[['move_id','in',move_ids],['display_type','=','product'],['quantity','>',0]]],
        {'fields': ['name','product_id','quantity','price_subtotal'], 'limit': 0})
    
    lineas_noflete = [l for l in lineas if 'FLETE' not in (l.get('name') or '').upper()]
    if filtrar_monto:
        lineas_filtradas = [l for l in lineas_noflete if float(l.get('price_subtotal') or 0) > 0]
    else:
        lineas_filtradas = lineas_noflete

    pids = set(l['product_id'][0] for l in lineas_filtradas if l.get('product_id'))
    nombres = set((l.get('name') or '').split('\n')[0].strip() for l in lineas_filtradas)
    nombres.discard('')
    print(f"\n[{etiqueta}]")
    print(f"  Líneas brutas: {len(lineas)}")
    print(f"  Líneas (sin FLETE{', monto>0' if filtrar_monto else ''}): {len(lineas_filtradas)}")
    print(f"  product_id distintos: {len(pids)}")
    print(f"  Nombres distintos (agrupados por texto): {len(nombres)}")

print("\n=== Con filtro monto>0 ===")
contar_lineas(move_ids_all,         "TODAS las posted (todas las empresas)")
contar_lineas(move_ids_cobradas,    "Cobradas paid/partial (todas las empresas)")
contar_lineas(move_ids_co1,         "Cobradas company_id=1")
contar_lineas(move_ids_todas_co1,   "TODAS las posted company_id=1")

print("\n=== Sin filtro monto (quantity>0 solamente) ===")
contar_lineas(move_ids_all,         "TODAS las posted (todas las empresas)",  filtrar_monto=False)
contar_lineas(move_ids_cobradas,    "Cobradas (todas las empresas)",           filtrar_monto=False)
contar_lineas(move_ids_co1,         "Cobradas company_id=1",                  filtrar_monto=False)
contar_lineas(move_ids_todas_co1,   "TODAS las posted company_id=1",          filtrar_monto=False)
