# Referencia — Integración Odoo (XML-RPC)

## Tabla de contenidos

1. Autenticación canónica
2. Modelos usados en el proyecto
3. Dominios comunes (filtros)
4. Patrón N+1 y cómo evitarlo
5. Introspección defensiva con `fields_get`
6. Anti-patrones a rechazar
7. Snippets listos para copiar

## 1. Autenticación canónica

```python
from utils.odoo_utils import (
    get_odoo_models, ODOO_DB, ODOO_PASSWORD, ODOO_COMPANY_ID
)
import logging

uid, models, err = get_odoo_models()
if not uid:
    logging.error("No se pudo autenticar contra Odoo: %s", err)
    return jsonify({"error": "Servicio Odoo no disponible"}), 503
```

`get_odoo_models` ya implementa 3 reintentos con backoff y devuelve `(None, None, traceback)` cuando falla. No reimplementes la lógica de conexión.

## 2. Modelos usados en el proyecto

| Modelo | Uso típico | Campos clave |
|---|---|---|
| `res.partner` | Clientes, proveedores, contactos | `name`, `ref`, `vat`, `parent_id`, `company_id` |
| `sale.order` | Pedidos de venta | `name`, `date_order`, `partner_id`, `order_line`, `amount_total`, `state`, `company_id` |
| `sale.order.line` | Líneas de pedido | `order_id`, `product_id`, `name`, `product_uom_qty`, `qty_delivered`, `price_unit` |
| `stock.picking` | Albaranes/entregas | `name`, `origin`, `state`, `picking_type_id`, `scheduled_date`, `move_ids`, `move_line_ids` |
| `stock.move` | Movimientos de inventario | `product_id`, `product_uom_qty`, `state`, `quantity_done` o `qty_done` según versión |
| `account.move` | Facturas y asientos contables | `name`, `date`, `partner_id`, `invoice_line_ids`, `state`, `move_type`, `amount_total`, `company_id` |
| `account.payment` | Pagos | `amount`, `date`, `partner_id`, `payment_type`, `partner_type`, `state`, `company_id` |
| `account.account` | Plan de cuentas | `code`, `name`, `account_type`, `company_id` |
| `product.product` | Variantes de producto | `default_code`, `name`, `product_tmpl_id`, `categ_id` |

## 3. Dominios comunes

**Pagos de clientes en un rango:**
```python
domain = [
    ('company_id', '=', ODOO_COMPANY_ID),
    ('date', '>=', fecha_inicio),
    ('date', '<=', fecha_fin),
    ('state', '=', 'posted'),
    ('payment_type', '=', 'inbound'),
    ('partner_type', '=', 'customer'),
]
pagos = models.execute_kw(
    ODOO_DB, uid, ODOO_PASSWORD,
    'account.payment', 'search_read',
    [domain],
    {'fields': ['amount', 'date', 'partner_id']},
)
```

**Facturas emitidas:**
```python
domain = [
    ('company_id', '=', ODOO_COMPANY_ID),
    ('move_type', '=', 'out_invoice'),
    ('state', '=', 'posted'),
    ('date', '>=', fecha_inicio),
    ('date', '<=', fecha_fin),
]
```

**Buscar cliente por nombre parcial (insensible a mayúsculas):**
```python
domain = [('name', 'ilike', nombre)]
```

**Pedidos de uno o varios clientes:**
```python
domain = [
    ('company_id', '=', ODOO_COMPANY_ID),
    ('partner_id', 'in', partner_ids),
]
```

## 4. Patrón N+1 y cómo evitarlo

**Mal (hace 1 + N llamadas):**
```python
for order in orders:
    lines = models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD,
        'sale.order.line', 'search_read',
        [[('order_id', '=', order['id'])]],
        {'fields': ['product_id', 'product_uom_qty']},
    )
    # ...
```

**Bien (hace 2 llamadas totales):**
```python
all_line_ids = []
for o in orders:
    all_line_ids.extend(o.get('order_line') or [])

if all_line_ids:
    all_lines = models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD,
        'sale.order.line', 'search_read',
        [[('id', 'in', all_line_ids)]],
        {'fields': ['order_id', 'product_id', 'product_uom_qty', 'qty_delivered', 'price_unit']},
    )
    # Indexar por order_id si se necesita agrupar:
    lines_by_order = {}
    for ln in all_lines:
        oid = ln['order_id'][0] if isinstance(ln['order_id'], (list, tuple)) else ln['order_id']
        lines_by_order.setdefault(oid, []).append(ln)
```

Nota: los campos relacionales (`partner_id`, `product_id`, `order_id`) devuelven `[id, "display_name"]` desde `search_read`. Siempre extrae `[0]` antes de usar el id.

## 5. Introspección defensiva con `fields_get`

Los campos de `stock.move` cambiaron entre Odoo 14 y 17 (`quantity_done` vs `qty_done`). Antes de pedir un campo que no estás seguro que exista:

```python
try:
    fields_info = models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD,
        'stock.move', 'fields_get', [], {}
    )
    available = set(fields_info.keys()) if isinstance(fields_info, dict) else set()
except Exception:
    available = set()

m_fields = ['product_id', 'product_uom_qty', 'state']
if 'quantity_done' in available:
    m_fields.append('quantity_done')
elif 'qty_done' in available:
    m_fields.append('qty_done')
```

## 6. Anti-patrones a rechazar

- **`search_read` sin `fields`**: trae todos los campos, incluyendo pesados como `message_ids`. Siempre especifica `fields`.
- **Leer sin `company_id`**: mezcla datos de otras empresas. Siempre filtra por `ODOO_COMPANY_ID` en modelos con ese campo.
- **Abrir nueva conexión XML-RPC por request**: `get_odoo_models` ya está diseñado para ser llamado por request; no crees `ServerProxy` manualmente en otros lugares.
- **Exponer `err` o `traceback` al cliente**: loggea detalle, devuelve mensaje genérico.
- **Filtrar por nombre con `=`**: usa `ilike` porque Odoo no normaliza espacios ni acentos consistentemente.
- **Hardcodear `ODOO_COMPANY_ID = 1` en cada archivo**: importa desde `utils.odoo_utils`.

## 7. Snippets listos

**Saldo de una cuenta contable (balanza) por rango:**
```python
from utils.odoo_utils import obtener_saldo_cuenta_odoo

total = obtener_saldo_cuenta_odoo(
    codigo_cuenta='6101',
    fecha_inicio='2025-01-01',
    fecha_fin='2025-01-31',
    es_ingreso=False,
    columna_saldo='Debe',
)
```

**Pedidos de un cliente con sus líneas (patrón optimizado):**
```python
uid, models, err = get_odoo_models()
if not uid:
    return jsonify({"error": "Odoo no disponible"}), 503

try:
    partners = models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD,
        'res.partner', 'search_read',
        [[('name', 'ilike', nombre_cliente)]],
        {'fields': ['id', 'name', 'ref']},
    )
    if not partners:
        return jsonify({"pedidos": []}), 200

    partner_ids = [p['id'] for p in partners]
    orders = models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD,
        'sale.order', 'search_read',
        [[
            ('company_id', '=', ODOO_COMPANY_ID),
            ('partner_id', 'in', partner_ids),
        ]],
        {'fields': ['id', 'name', 'date_order', 'partner_id', 'order_line', 'amount_total', 'state']},
    )

    all_line_ids = [lid for o in orders for lid in (o.get('order_line') or [])]
    lines = []
    if all_line_ids:
        lines = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'sale.order.line', 'search_read',
            [[('id', 'in', all_line_ids)]],
            {'fields': ['order_id', 'product_id', 'name', 'product_uom_qty', 'price_unit']},
        )

    return jsonify({"pedidos": orders, "lineas": lines}), 200

except Exception as e:
    logging.exception("Error consultando pedidos de %s: %s", nombre_cliente, e)
    return jsonify({"error": "Error consultando Odoo"}), 500
```
