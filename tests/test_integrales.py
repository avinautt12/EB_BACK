import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import traceback
from utils.odoo_utils import get_odoo_models, ODOO_DB, ODOO_PASSWORD

def test_integrales_odoo():
    print("🚀 Iniciando Test de Integrales desde Odoo...")
    uid, models = get_odoo_models()
    
    if not uid:
        print("❌ Error: No se pudo conectar a Odoo")
        return

    # Fechas de la temporada
    fecha_inicio = '2025-06-01'
    fecha_fin = '2026-05-31'

    # Nuestro mapa de agrupaciones
    integrales_map = {
        'Integral 1': ['EC216', 'JC539'],
        'Integral 2': ['GC411', 'MC679', 'MC677', 'LC657'],
        'Integral 3': ['LC625', 'LC627', 'LC626']
    }

    # 1. Hacemos una lista plana de todas las claves que nos interesan
    claves_hijas = []
    for hijas in integrales_map.values():
        claves_hijas.extend(hijas)

    print(f"🔍 Buscando estas {len(claves_hijas)} claves en Odoo: {claves_hijas}")

    # 2. Buscar en Odoo a los contactos (res.partner) para saber su ID interno
    # En Odoo la clave usualmente viene en el campo 'ref' (Referencia interna) o en el 'name'
    partners_odoo = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'res.partner', 'search_read',
        [[]], {'fields': ['id', 'name', 'ref']})

    # Diccionario para mapear: ID de Odoo -> Tu Clave (ej: 4562 -> 'LC657')
    odoo_id_to_clave = {}
    
    for p in partners_odoo:
        ref_odoo = str(p.get('ref', '')).strip().upper()
        name_odoo = str(p.get('name', '')).strip().upper()

        for clave in claves_hijas:
            # Si la clave coincide exactamente con la Referencia o está dentro del Nombre
            if clave == ref_odoo or clave in name_odoo:
                odoo_id_to_clave[p['id']] = clave
                break

    print(f"\n✅ Se encontraron {len(odoo_id_to_clave)} coincidencias en Odoo:")
    for oid, clave in odoo_id_to_clave.items():
        print(f"   - Odoo ID [{oid}] pertenece a la Clave: {clave}")

    if not odoo_id_to_clave:
        print("\n⚠️ No se encontraron las claves en Odoo. Revisa cómo están guardadas.")
        return

    # 3. Buscar las Notas de Crédito (G02) SOLO para los IDs encontrados
    domain_nc = [
        ('move_id.move_type', '=', 'out_refund'),
        ('move_id.state', '=', 'posted'),
        ('move_id.invoice_date', '>=', fecha_inicio),
        ('move_id.invoice_date', '<=', fecha_fin),
        ('move_id.l10n_mx_edi_usage', '=', 'G02'),
        ('quantity', '=', 1),
        ('partner_id', 'in', list(odoo_id_to_clave.keys())) # ¡Filtro mágico por ID!
    ]

    print("\n📥 Descargando Notas de Crédito (G02) para estas sucursales...")
    lineas_nc = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'search_read',
        [domain_nc], {'fields': ['partner_id', 'price_subtotal', 'name']})

    # 4. Sumar los montos filtrando exactamente como en el Excel
    sumatorias_hijas = {clave: 0.0 for clave in claves_hijas}

    for linea in lineas_nc:
        nombre_producto = str(linea['name'] or '').upper()
        
        # Validamos lo que NO queremos (Garantías y Anticipos)
        es_garantia = 'GARANTIA' in nombre_producto or 'DESCGARANTIA' in nombre_producto
        es_aplant = 'APLANT' in nombre_producto or 'ANTICIPO' in nombre_producto
        
        # Validamos lo que SÍ queremos (Los que tienes filtrados en tu Excel)
        # Ajusta estas palabras clave según lo que hayas palomeado en tu filtro de Excel
        es_descuento_valido = 'DESC' in nombre_producto or 'DESCESPECIAL' in nombre_producto or 'DESCPAGO' in nombre_producto

        if not es_garantia and not es_aplant and es_descuento_valido:
            partner_id = linea['partner_id'][0]
            clave_encontrada = odoo_id_to_clave.get(partner_id)
            
            monto = float(linea['price_subtotal'])
            if clave_encontrada:
                sumatorias_hijas[clave_encontrada] += monto

    # 5. Imprimir el Reporte de Sumatorias en Consola
    print("\n" + "="*50)
    print("📊 REPORTE DE DEDUCCIONES POR INTEGRAL (TEST)")
    print("="*50)

    for padre, hijas in integrales_map.items():
        print(f"\n🏢 {padre}:")
        suma_padre = 0.0
        for hija in hijas:
            monto_hija = sumatorias_hijas[hija]
            suma_padre += monto_hija
            print(f"   ↳ {hija}: ${monto_hija:,.2f}")

        print(f"   {'-'*25}")
        print(f"   💰 TOTAL {padre}: ${suma_padre:,.2f}")
    
    print("\n" + "="*50)

if __name__ == '__main__':
    test_integrales_odoo()