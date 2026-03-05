import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import traceback
from utils.odoo_utils import get_odoo_models, ODOO_DB, ODOO_PASSWORD

def diagnostico_lc657():
    print("🚀 Escaneando Productos Ofertados en Odoo para LC657...")
    uid, models = get_odoo_models()
    if not uid: return
    
    # LA MISMA FECHA OFICIAL DEL BACKEND
    fecha_inicio = '2025-07-01'
    fecha_fin = '2026-06-30'

    # Buscamos el ID interno de LC657
    partners = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'res.partner', 'search_read',
        [[('ref', '=', 'LC657')]], {'fields': ['id']})
    
    if not partners:
        print("❌ No se encontró al cliente LC657 en Odoo.")
        return
        
    p_id = partners[0]['id']

    domain_ofertado = [
        ('move_id.move_type', '=', 'out_invoice'), 
        ('move_id.state', '=', 'posted'),
        ('move_id.invoice_date', '>=', fecha_inicio),
        ('move_id.invoice_date', '<=', fecha_fin),
        ('quantity', '!=', 0),
        ('partner_id', '=', p_id),
        ('product_id.product_tmpl_id.product_tag_ids.name', 'ilike', 'Ofertado')
    ]
    
    lineas = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'search_read', 
        [domain_ofertado], {'fields': ['move_id', 'product_id', 'price_subtotal', 'date', 'name']})
    
    total = 0
    print("\n=======================================================")
    print("🧾 LÍNEAS DE FACTURA (PRODUCTOS OFERTADOS) ENCONTRADAS")
    print("=======================================================")
    
    # Ordenar por fecha para leerlo más fácil
    lineas_ordenadas = sorted(lineas, key=lambda k: k.get('date', ''))
    
    for l in lineas_ordenadas:
        sub = float(l['price_subtotal'])
        total += sub
        factura = l['move_id'][1] if l.get('move_id') else 'Sin Factura'
        producto = l['product_id'][1] if l.get('product_id') else l.get('name', 'Desconocido')
        
        print(f"📅 {l.get('date')} | 🧾 {factura[:20]:<20} | 💰 ${sub:>8,.2f} | 📦 {producto[:40]}")
        
    print("-" * 55)
    print(f"💰 TOTAL ODOO RESULTANTE:   ${total:,.2f}")
    print(f"💰 TOTAL EXCEL (Tu foto):   $15,672.07")
    print(f"📉 DIFERENCIA DETECTADA:    ${abs(15672.07 - total):,.2f}")
    print("=======================================================")

if __name__ == '__main__':
    diagnostico_lc657()