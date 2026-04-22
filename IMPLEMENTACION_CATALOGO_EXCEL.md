# Implementación: Catálogo de Productos Excel para Proyecciones

## ✅ Completado

Se ha implementado un sistema completo para gestionar productos desde Excel mientras se establece el catálogo de Odoo.

### Archivos Creados/Modificados

#### 1. **`services/forecast_excel_service.py`** (NUEVO)
Servicio con toda la lógica de gestión de productos Excel:

- ✅ `ensure_excel_producto_table()` - Crear tabla si no existe
- ✅ `get_product_from_sources(sku)` - Buscar producto en Excel o Odoo
- ✅ `load_excel_products(file_content)` - Parsear y cargar Excel
- ✅ `list_excel_products(search, limit, offset)` - Listar con búsqueda
- ✅ `delete_excel_product(sku)` - Eliminar producto
- ✅ `clear_excel_catalog()` - Vaciar catálogo
- ✅ `get_valid_skus()` - Obtener SKUs válidos (Excel + Odoo)

#### 2. **`routes/forecast.py`** (MODIFICADO)
- ✅ Importar servicio Excel
- ✅ Reemplazar `get_valid_skus()` en validación de proyecciones
- ✅ Agregar 4 endpoints de admin:
  - `POST /admin/productos-excel/cargar`
  - `GET /admin/productos-excel`
  - `DELETE /admin/productos-excel/<sku>`
  - `POST /admin/productos-excel/vaciar`

#### 3. **`GUIA_CATALOGO_EXCEL_PROYECCIONES.md`** (NUEVO)
Documentación completa con:
- Diagrama de arquitectura
- API Reference detallada
- Ejemplos de uso
- Flujos de negocio
- FAQ y troubleshooting

---

## 🔄 Flujo de Funcionamiento

### Carga de Productos

```
1. Admin carga archivo Excel
   POST /admin/productos-excel/cargar
   
2. Sistema parsea Excel (SKU, NOMBRE, COLOR, TALLA)

3. Valida unicidad de SKU en el archivo

4. Inserta/actualiza en BD (ON DUPLICATE KEY UPDATE)

5. Retorna resumen de cargados, duplicados, errores
```

### Validación en Proyecciones

```
1. Usuario intenta agregar proyección
   POST /forecast/importar-proyecciones
   
2. Sistema obtiene SKUs válidos:
   - Primero busca en forecast_excel_productos
   - Si no existe, busca en odoo_catalogo
   - Si tampoco existe, rechaza con error
   
3. Si SKU es válido, proyección se guarda

✓ El usuario ya no recibe "SKU no existe" si está en Excel
```

---

## 📊 Esquema de Base de Datos

```sql
CREATE TABLE forecast_excel_productos (
    sku VARCHAR(100) PRIMARY KEY,
    nombre VARCHAR(400) NOT NULL,
    color VARCHAR(150),
    talla VARCHAR(100),
    origen ENUM('excel', 'odoo') DEFAULT 'excel',
    cargado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
    actualizado_en DATETIME ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_origen (origen),
    FULLTEXT INDEX idx_ft_nombre (nombre)
);
```

---

## 🎯 Casos de Uso Resueltos

### ✅ Caso 1: Productos en Excel, no en Odoo
```
Antes: ❌ "SKU no existe" → Usuario frustrado
Ahora: ✅ Validación contra Excel → Proyección guardada
```

### ✅ Caso 2: Transición Excel → Odoo
```
Fase 1: Excel es la fuente principal
Fase 2: Se poblaDoo en paralelo
Fase 3: Se sincroniza cuando está listo
Fase 4: Se vacía Excel (opcional)
```

### ✅ Caso 3: Gestión de catálogos duplicados
```
Mismo SKU en Excel y Odoo?
→ Excel tiene prioridad (configurable)
```

---

## 🚀 Cómo Empezar

### 1. Verificar que el servicio se carga
```bash
cd /path/to/EB_BACK
python3 -c "from services.forecast_excel_service import *; print('OK')"
```

### 2. Crear archivo Excel de prueba

| SKU | NOMBRE | COLOR | TALLA |
|-----|--------|-------|-------|
| SKU-001 | BICICLETA MOUNTAIN 29 | ROJO | M |
| SKU-002 | BICICLETA RUTA 27 | AZUL | L |
| SKU-003 | CASCO PROFESIONAL | NEGRO | TU |

### 3. Cargar vía cURL
```bash
curl -X POST http://localhost:5000/admin/productos-excel/cargar \
  -F "file=@productos.xlsx"
```

Respuesta esperada:
```json
{
  "cargados": 3,
  "total_filas_procesadas": 3,
  "duplicados_actualizados": 0,
  "errores": []
}
```

### 4. Listar productos cargados
```bash
curl http://localhost:5000/admin/productos-excel?limit=10
```

### 5. Quitar un producto
```bash
curl -X DELETE http://localhost:5000/admin/productos-excel/SKU-001
```

---

## ⚙️ Configuración Opciones

### Cambiar orden de prioridad (Excel ↔ Odoo)
En `services/forecast_excel_service.py`, función `get_product_from_sources()`:

```python
# Actualmente: Excel primero, Odoo segundo
# Para invertir:
# 1. Buscar primero en odoo_catalogo
# 2. Fallback a forecast_excel_productos
```

### Aumentar límite de búsqueda
En `list_excel_products()`:
```python
limit = min(limit, 500)  # Cambiar 500 a otro número
```

---

## 🔒 Seguridad (próximos pasos)

### TODO: Agregar autenticación (CRÍTICO para producción)

Los endpoints de admin NO tienen JWT implementado aún. Antes de deployar:

```python
from utils.jwt_utils import require_jwt

@forecast_bp.route('/admin/...')
@require_jwt
def endpoint():
    # solo usuarios autenticados
```

### TODO: Agregar control de permisos por rol

Solo admins pueden:
- Cargar Excel
- Vaciar catálogo
- Eliminar productos

---

## 📝 Notas Importantes

### Deduplicación automática
- Si cargas el mismo SKU dos veces → se actualiza
- Campos como `nombre`, `color`, `talla` se sobrescriben
- Timestamps se actualizan

### Búsqueda fulltext
- `?search=bici` encuentra "BICICLETA MOUNTAIN"
- `?search=290189-010` encuentra exactamente ese SKU
- Case-insensitive

### Performance
- Índice FULLTEXT en `nombre`
- Índice en `origen` para filtrar rápido
- Máximo 500 resultados por query (hardcoded)

### Desarrollo vs Producción
- **Desarrollo**: Cargar Excel para testing
- **Producción**: Sincronizar con Odoo, luego vaciar Excel

---

## 📞 Soporte & Troubleshooting

### Problema: "Tabla no existe"
```sql
SELECT COUNT(*) FROM forecast_excel_productos;
```
Si retorna error, ejecutar:
```python
from services.forecast_excel_service import ensure_excel_producto_table
ensure_excel_producto_table()
```

### Problema: "No me reconoce los SKUs"
1. Verificar que están en Excel:
   ```bash
   curl "http://localhost:5000/admin/productos-excel?search=TU_SKU"
   ```
2. Verificar que proyección usa el mismo SKU (¿espacios extra?, ¿mayúsculas?)

### Problema: Quiero cambiar de Excel a Odoo
```bash
# 1. Vaciar Excel
curl -X POST http://localhost:5000/admin/productos-excel/vaciar \
  -H "X-Confirm-Action: VACIAR_CATALOGO"

# 2. El sistema ahora usa solo Odoo (fallback automático)
```

---

## 📌 Resumen de cambios

| Archivo | Líneas | Cambio |
|---------|--------|--------|
| `services/forecast_excel_service.py` | +378 | NUEVO - Servicio completo |
| `routes/forecast.py` | +162 | NUEVO - 4 endpoints admin |
| `routes/forecast.py` | -26 | MODIFICADO - Validación SKU |
| `GUIA_CATALOGO_EXCEL_PROYECCIONES.md` | +400 | NUEVO - Documentación |

**Total líneas agregadas: ~700**

---

## ✨ Features Implementados

- ✅ Cargar productos desde Excel
- ✅ Validación automática de SKU en proyecciones
- ✅ Búsqueda fulltext por nombre
- ✅ Listar con paginación
- ✅ Eliminar productos individuales
- ✅ Vaciar catálogo completo (con confirmación)
- ✅ Upsert automático de duplicados
- ✅ Prioridad Excel > Odoo (configurable)
- ✅ Índices para performance
- ✅ Logging de todas las operaciones
- ✅ Documentación completa

---

## 🎓 Próximos Pasos Recomendados

1. **Seguridad**: Agregar `@require_jwt` a endpoints
2. **Roles**: Implementar `@require_admin()` decorator
3. **Auditoría**: Registrar quién carga qué, cuándo
4. **Sincronización**: Endpoint `/admin/sincronizar-odoo-excel`
5. **Alertas**: Notificar cuando catálogo esté incompleto
6. **Tests**: Crear `tests/test_forecast_excel.py`
