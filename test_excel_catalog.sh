#!/bin/bash
# Tests rápidos para validar la funcionalidad de catálogo Excel
# Uso: chmod +x test_excel_catalog.sh && ./test_excel_catalog.sh

BASE_URL="http://localhost:5000"

echo "═══════════════════════════════════════════════════════════════"
echo "TESTING CATÁLOGO EXCEL PARA PROYECCIONES"
echo "═══════════════════════════════════════════════════════════════"

# Colores para output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Crear archivo Excel de prueba
echo -e "\n${YELLOW}[TEST 1]${NC} Creando archivo Excel de prueba..."

python3 << 'PYEOF'
from openpyxl import Workbook

# Crear workbook
wb = Workbook()
ws = wb.active
ws.title = "Productos"

# Headers
ws['A1'] = 'SKU'
ws['B1'] = 'NOMBRE'
ws['C1'] = 'COLOR'
ws['D1'] = 'TALLA'

# Datos
datos = [
    ('SKU-001', 'BICICLETA MOUNTAIN 29 ALUMINIO', 'ROJO', 'M'),
    ('SKU-002', 'BICICLETA RUTA 27 CARBONO', 'AZUL', 'L'),
    ('SKU-003', 'CASCO AERODINAMICO PRO', 'NEGRO', 'TU'),
    ('SKU-004', 'GUANTES PROFESIONALES', 'GRIS', 'M'),
    ('SKU-005', 'ZAPATILLAS TRAIL RUNNING', 'VERDE', 'N41'),
]

for idx, (sku, nombre, color, talla) in enumerate(datos, start=2):
    ws[f'A{idx}'] = sku
    ws[f'B{idx}'] = nombre
    ws[f'C{idx}'] = color
    ws[f'D{idx}'] = talla

# Guardar
wb.save('/tmp/test_productos.xlsx')
print("✅ Archivo creado: /tmp/test_productos.xlsx")
PYEOF

if [ ! -f /tmp/test_productos.xlsx ]; then
    echo -e "${RED}❌ Error: no se pudo crear el archivo Excel${NC}"
    exit 1
fi

# Test 2: Cargar archivo Excel
echo -e "\n${YELLOW}[TEST 2]${NC} Cargando archivo Excel..."

RESPONSE=$(curl -s -X POST "$BASE_URL/admin/productos-excel/cargar" \
  -F "file=@/tmp/test_productos.xlsx")

echo "Respuesta:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

CARGADOS=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('cargados', 0))" 2>/dev/null)

if [ "$CARGADOS" -eq 5 ]; then
    echo -e "${GREEN}✅ Cargados 5 productos exitosamente${NC}"
else
    echo -e "${RED}❌ Error: se esperaban 5 productos, solo se cargaron $CARGADOS${NC}"
fi

# Test 3: Listar productos
echo -e "\n${YELLOW}[TEST 3]${NC} Listando productos cargados..."

RESPONSE=$(curl -s "$BASE_URL/admin/productos-excel?limit=10")
echo "Respuesta:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

TOTAL=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('total', 0))" 2>/dev/null)
echo -e "${GREEN}✅ Total productos en catálogo: $TOTAL${NC}"

# Test 4: Buscar producto específico
echo -e "\n${YELLOW}[TEST 4]${NC} Buscando por SKU (SKU-001)..."

RESPONSE=$(curl -s "$BASE_URL/admin/productos-excel?search=SKU-001")
echo "Respuesta:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

# Test 5: Búsqueda fulltext
echo -e "\n${YELLOW}[TEST 5]${NC} Búsqueda fulltext (palabra: 'bicicleta')..."

RESPONSE=$(curl -s "$BASE_URL/admin/productos-excel?search=bicicleta")
echo "Respuesta:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

FOUND=$(echo "$RESPONSE" | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('productos', [])))" 2>/dev/null)
echo -e "${GREEN}✅ Encontrados $FOUND productos con 'bicicleta'${NC}"

# Test 6: Eliminar un producto
echo -e "\n${YELLOW}[TEST 6]${NC} Eliminando producto (SKU-005)..."

RESPONSE=$(curl -s -X DELETE "$BASE_URL/admin/productos-excel/SKU-005")
echo "Respuesta:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

RESULT=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('eliminado', False))" 2>/dev/null)
if [ "$RESULT" == "True" ]; then
    echo -e "${GREEN}✅ Producto eliminado exitosamente${NC}"
fi

# Test 7: Verificar total después de eliminar
echo -e "\n${YELLOW}[TEST 7]${NC} Verificando total después de eliminar..."

RESPONSE=$(curl -s "$BASE_URL/admin/productos-excel")
TOTAL=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('total', 0))" 2>/dev/null)
echo -e "${GREEN}✅ Total productos ahora: $TOTAL (era 5, ahora debería ser 4)${NC}"

# Test 8: Cargar el mismo archivo de nuevo (test upsert)
echo -e "\n${YELLOW}[TEST 8]${NC} Cargando el mismo archivo de nuevo (test upsert)..."

RESPONSE=$(curl -s -X POST "$BASE_URL/admin/productos-excel/cargar" \
  -F "file=@/tmp/test_productos.xlsx")

echo "Respuesta:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

DUPLICADOS=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('duplicados_actualizados', 0))" 2>/dev/null)
echo -e "${GREEN}✅ Duplicados actualizados: $DUPLICADOS${NC}"

# Test 9: Vaciar catálogo (con confirmación)
echo -e "\n${YELLOW}[TEST 9]${NC} Intentando vaciar sin confirmación (debería fallar)..."

RESPONSE=$(curl -s -X POST "$BASE_URL/admin/productos-excel/vaciar")
echo "Respuesta esperada (error):"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

# Test 10: Vaciar con confirmación
echo -e "\n${YELLOW}[TEST 10]${NC} Vaciando catálogo con confirmación..."

RESPONSE=$(curl -s -X POST "$BASE_URL/admin/productos-excel/vaciar" \
  -H "X-Confirm-Action: VACIAR_CATALOGO")

echo "Respuesta:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

ELIMINADOS=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('eliminados', 0))" 2>/dev/null)
echo -e "${GREEN}✅ Productos eliminados: $ELIMINADOS${NC}"

# Final
echo -e "\n═══════════════════════════════════════════════════════════════"
echo -e "${GREEN}✅ TODOS LOS TESTS COMPLETADOS${NC}"
echo "═══════════════════════════════════════════════════════════════"
