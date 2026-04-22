# Guía de Catálogo de Productos Excel — Proyecciones

## Problema que soluciona

Antes de que los productos estén disponibles en Odoo, necesitas permitir que los usuarios carguen proyecciones usando un catálogo temporal desde Excel. El sistema ahora:

- ✅ Acepta un Excel con productos (SKU, NOMBRE, COLOR, TALLA)
- ✅ Valida SKUs contra ese Excel cuando se cargan proyecciones
- ✅ Permite cambiar dinámicamente la fuente (Excel → Odoo) sin modificar código
- ✅ Mantiene ambas fuentes en sincronía

## Arquitectura

```
┌─────────────────────────────────────────┐
│  Usuario sube archivo Excel             │
│  (SKU | NOMBRE | COLOR | TALLA)          │
└──────────────┬──────────────────────────┘
               │
               ▼
    POST /admin/productos-excel/cargar
               │
               ▼
┌──────────────────────────────────────────────────────┐
│  forecast_excel_productos TABLE (origen='excel')     │
│  ├─ SKU (primary key)                                │
│  ├─ nombre                                           │
│  ├─ color                                            │
│  ├─ talla                                            │
│  └─ cargado_en, actualizado_en                       │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│  Validación de SKU (al cargar proyecciones)          │
│  1. Busca en forecast_excel_productos (prioridad)    │
│  2. Si no existe, busca en odoo_catalogo (fallback)  │
└──────────────────────────────────────────────────────┘
```

## Instalación

### 1. Crear tabla (automático)

Al iniciar la aplicación, se ejecuta:

```python
_ensure_excel_producto_table()
```

Esto crea la tabla `forecast_excel_productos` con estructura:

```sql
CREATE TABLE IF NOT EXISTS forecast_excel_productos (
    sku VARCHAR(100) NOT NULL PRIMARY KEY,
    nombre VARCHAR(400) NOT NULL,
    color VARCHAR(150) DEFAULT NULL,
    talla VARCHAR(100) DEFAULT NULL,
    origen ENUM('excel', 'odoo') DEFAULT 'excel',
    cargado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_origen (origen),
    FULLTEXT idx_ft_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

## API Reference

### 1. Cargar productos desde Excel

**POST** `/admin/productos-excel/cargar`

Carga un archivo Excel con la siguiente estructura:

| Columna | Requerida | Tipo | Ejemplo |
|---------|-----------|------|---------|
| SKU | Sí | String | `290189-010` |
| NOMBRE | Sí | String | `BICICLETA MOUNTAIN 29 ALUMINIO` |
| COLOR | No | String | `ROJO` |
| TALLA | No | String | `M` |

**Request:**

```bash
curl -X POST http://localhost:5000/admin/productos-excel/cargar \
  -F "file=@productos.xlsx"
```

**Response (200 OK):**

```json
{
  "cargados": 150,
  "total_filas_procesadas": 150,
  "duplicados_actualizados": 5,
  "duplicados_actualizados_skus": ["SKU123", "SKU456"]
}
```

O si hay errores:

```json
{
  "cargados": 145,
  "total_filas_procesadas": 150,
  "duplicados_actualizados": 5,
  "errores": [
    "Fila 10: SKU vacío",
    "Fila 25: SKU \"ABC123\" duplicado dentro del archivo"
  ]
}
```

**Status Codes:**

- `200` - OK, productos cargados
- `400` - Errores de formato o validación
- `500` - Error al guardar en BD

---

### 2. Listar productos Excel

**GET** `/admin/productos-excel`

Lista todos los productos cargados desde Excel (paginados).

**Query Parameters:**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| search | string | "" | Búsqueda por SKU exacto o NOMBRE (fulltext) |
| limit | int | 100 | Máximo 500 |
| offset | int | 0 | Paginación |

**Request:**

```bash
# Listar primeros 100
curl http://localhost:5000/admin/productos-excel

# Buscar por SKU exacto
curl "http://localhost:5000/admin/productos-excel?search=290189-010"

# Buscar por palabra clave (fulltext)
curl "http://localhost:5000/admin/productos-excel?search=bicicleta"

# Paginación
curl "http://localhost:5000/admin/productos-excel?limit=50&offset=100"
```

**Response (200 OK):**

```json
{
  "total": 500,
  "limit": 100,
  "offset": 0,
  "productos": [
    {
      "sku": "290189-010",
      "nombre": "BICICLETA MOUNTAIN 29 ALUMINIO",
      "color": "ROJO",
      "talla": "M",
      "cargado_en": "2026-04-21T10:30:45",
      "actualizado_en": "2026-04-21T10:30:45"
    }
  ]
}
```

---

### 3. Eliminar un producto

**DELETE** `/admin/productos-excel/<sku>`

Elimina un producto específico del catálogo Excel.

**Request:**

```bash
curl -X DELETE http://localhost:5000/admin/productos-excel/290189-010
```

**Response (200 OK):**

```json
{
  "eliminado": true,
  "sku": "290189-010"
}
```

**Status Codes:**

- `200` - Eliminado
- `404` - SKU no encontrado
- `400` - SKU vacío

---

### 4. Vaciar catálogo Excel completo

**POST** `/admin/productos-excel/vaciar`

⚠️ **ACCIÓN DESTRUCTIVA** — Elimina TODOS los productos del catálogo Excel.

Requiere confirmación vía header `X-Confirm-Action`.

**Request:**

```bash
curl -X POST http://localhost:5000/admin/productos-excel/vaciar \
  -H "X-Confirm-Action: VACIAR_CATALOGO"
```

**Response (200 OK):**

```json
{
  "eliminados": 500,
  "mensaje": "Catálogo Excel vaciado"
}
```

**Response (403 Forbidden) — sin header:**

```json
{
  "error": "Acción no confirmada. Envía header X-Confirm-Action: VACIAR_CATALOGO"
}
```

---

## Flujo de uso

### Escenario 1: Proyecciones con productos de Excel (antes de Odoo)

```
1. Admin carga archivo Excel con productos
   POST /admin/productos-excel/cargar → 150 productos cargados

2. Usuario intenta agregar proyección manualmente
   POST /forecast/importar-proyecciones
   → Sistema valida SKU contra forecast_excel_productos
   → ✅ Aceptado, porque existe en Excel

3. Usuario carga plantilla de proyecciones
   POST /forecast/importar
   → Sistema valida cada SKU contra forecast_excel_productos
   → ✅ Todos los SKUs existen, proyección guardada
```

### Escenario 2: Transición Excel → Odoo

```
1. Productos en Excel siguen siendo la fuente principal
   GET /admin/productos-excel → 150 productos

2. Admin comienza a sincronizar Odoo
   Backend: _trigger_catalogo_sync() → Carga productos a odoo_catalogo

3. En paralelo, Excel sigue siendo útil si necesitas:
   - Eliminar un producto del catálogo
     DELETE /admin/productos-excel/<sku>
   
   - Actualizar un producto
     POST /admin/productos-excel/cargar (upsert automático)

4. Cuando Odoo esté completo:
   - Vacía el catálogo Excel
     POST /admin/productos-excel/vaciar
   - Sistema vuelve a usar solo odoo_catalogo
```

---

## Validación de SKU en Proyecciones

Cuando un usuario carga una proyección, el sistema hace:

```python
def _load_valid_skus():
    # 1. De Excel (prioridad)
    SELECT DISTINCT sku FROM forecast_excel_productos WHERE origen = 'excel'
    
    # 2. De Odoo (fallback)
    SELECT referencia_interna FROM odoo_catalogo
    
    return union(excel_skus, odoo_skus)
```

### Ejemplo: Validación con ambas fuentes

```
Excel tiene:        | Odoo tiene:       | Resultado (válido)
─────────────────────────────────────────────────────────
SKU-001             | SKU-100           | SKU-001 ✅ (Excel)
SKU-002             | SKU-100           | SKU-002 ✅ (Excel)
                    | SKU-100           | SKU-100 ✅ (Odoo)
                    | SKU-200           | SKU-200 ✅ (Odoo)
SKU-999             |                   | ❌ No validado
```

---

## Notas importantes

### Deduplicación

- Si cargas el mismo Excel dos veces, los SKUs duplicados se **actualizan** (no se duplican)
- Los timestamps `cargado_en` y `actualizado_en` se actualizan

### Búsqueda fulltext

- `?search=bici` encontrará "BICICLETA MOUNTAIN 29"
- `?search=290189-010` encontrará exactamente ese SKU

### Performance

- Índice `FULLTEXT` en `nombre` para búsquedas rápidas
- Índice `idx_origen` para filtrar por fuente
- Máximo 500 resultados por query (limitado en código)

### Seguridad

- Los endpoints de admin NO tienen autenticación JWT implementada aún
- **TODO**: Agregar `@require_jwt` a los endpoints antes de producción
- El header de confirmación `X-Confirm-Action` protege la acción de vaciar

---

## Próximos pasos

### 1. Agregar autenticación (CRÍTICO para producción)

```python
from utils.jwt_utils import require_jwt

@forecast_bp.route('/admin/productos-excel/cargar', methods=['POST'])
@require_jwt
def cargar_productos_excel_admin():
    # ... codigo
```

### 2. Agregar permisos por rol

```python
@require_jwt
def require_admin_role(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        claims = verify_jwt_from_request()
        if claims.get('rol') != 'admin':
            return jsonify({'error': 'Acceso denegado'}), 403
        return f(*args, **kwargs)
    return wrapper
```

### 3. Crear endpoints de sincronización Excel ↔ Odoo

Cuando Odoo esté listo, copiar productos de `odoo_catalogo` a `forecast_excel_productos`:

```python
@forecast_bp.route('/admin/sincronizar-odoo-excel', methods=['POST'])
def sincronizar_odoo_excel():
    # INSERT INTO forecast_excel_productos
    # SELECT referencia_interna, nombre_producto, ... FROM odoo_catalogo
    # ON DUPLICATE KEY UPDATE ...
```

---

## SQL para debugging

```sql
-- Ver total de productos Excel
SELECT COUNT(*) FROM forecast_excel_productos WHERE origen = 'excel';

-- Ver últimos 10 productos cargados
SELECT sku, nombre, cargado_en FROM forecast_excel_productos 
ORDER BY cargado_en DESC LIMIT 10;

-- Buscar producto por nombre
SELECT * FROM forecast_excel_productos 
WHERE origen = 'excel' AND MATCH(nombre) AGAINST('bicicleta' IN BOOLEAN MODE);

-- Ver productos que existen en ambas fuentes
SELECT e.sku, e.nombre, o.nombre_producto
FROM forecast_excel_productos e
LEFT JOIN odoo_catalogo o ON e.sku = o.referencia_interna
WHERE e.origen = 'excel' AND o.referencia_interna IS NOT NULL;

-- Limpiar tabla (CUIDADO!)
DELETE FROM forecast_excel_productos WHERE origen = 'excel';
```

---

## Testing

### Test 1: Cargar archivo válido

```bash
# Crear archivo Excel de prueba (con headers: SKU, NOMBRE, COLOR, TALLA)
# Luego cargar:
curl -X POST http://localhost:5000/admin/productos-excel/cargar \
  -F "file=@test_productos.xlsx"

# Verificar que se cargó
curl http://localhost:5000/admin/productos-excel?limit=5
```

### Test 2: Validar SKU en proyección

```bash
# Cargar un Excel con 3 productos: SKU1, SKU2, SKU3
# Luego intentar cargar proyección con SKU1
# Debe aceptarse porque SKU1 existe en Excel

POST /forecast/importar-proyecciones
{
  "clave_cliente": "CLI001",
  "periodo": "2026-2027",
  "proyecciones": [
    {
      "sku": "SKU1",  # ← Existe en Excel, debe validar ✅
      "producto": "...",
      "mayo": 10,
      ...
    }
  ]
}
```

### Test 3: Verificar fallback a Odoo

```bash
# Si eliminas el Excel pero tienes Odoo poblado:
POST /admin/productos-excel/vaciar \
  -H "X-Confirm-Action: VACIAR_CATALOGO"

# Proyecciones con SKUs de Odoo ahora deben validar contra odoo_catalogo
# La validación sucede naturalmente porque es el fallback
```

---

## FAQ

**P: ¿Qué pasa si el SKU existe en Excel y en Odoo?**  
R: Se usa el de Excel (tiene prioridad). El origen se marca como `'excel'`.

**P: ¿Puedo cambiar el orden de prioridad Excel ↔ Odoo?**  
R: Sí, modifica `_get_product_from_sources()` en forecast.py.

**P: ¿Cómo actualizo un producto después de cargarlo?**  
R: Carga el Excel nuevamente con el producto actualizado. Es un `INSERT ... ON DUPLICATE KEY UPDATE`.

**P: ¿Se puede cargar parcialmente si hay errores?**  
R: Sí, se cargan los productos válidos y se retornan los errores. Puedes reintentar solo los que fallaron.

**P: ¿Qué campos son obligatorios en el Excel?**  
R: Solo `SKU` y `NOMBRE`. `COLOR` y `TALLA` son opcionales.

---

## Soporte

Si encuentras errores, revisa:

1. **Tabla existe?** `SHOW TABLES LIKE 'forecast_excel_%';`
2. **Permisos BD?** Asegúrate que el usuario MySQL puede `INSERT/UPDATE/DELETE`
3. **Logs?** Busca `[cargar_productos_excel]` en logs de Flask
