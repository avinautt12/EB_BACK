# test_odoo_manual.py
from utils.odoo_utils import obtener_saldo_cuenta_odoo
from datetime import date

# --- CONFIGURACIÓN DE LA PRUEBA ---
ANIO = 2026  # Cambia esto al año que quieras probar (ej. 2025 o 2026)
MES = 1      # Enero

# Fechas automáticas (Primer y último día del mes)
import calendar
ultimo_dia = calendar.monthrange(ANIO, MES)[1]
fecha_inicio = f"{ANIO}-{MES:02d}-01"
fecha_fin = f"{ANIO}-{MES:02d}-{ultimo_dia}"

print(f"\n🧪 --- INICIANDO PRUEBA DE CONEXIÓN ODOO ---")
print(f"📅 Periodo: {fecha_inicio} al {fecha_fin}")
print("-" * 50)

# ---------------------------------------------------------
# PRUEBA 1: VENTAS (Ingreso)
# Cuenta: 102.01.013 (La que vi en tu base de datos)
# ---------------------------------------------------------
cuenta_ventas = "102.01.013" # <--- VERIFICA QUE SEA ESTA
print(f"1️⃣  Probando VENTAS (Cuenta {cuenta_ventas})...")
try:
    saldo_ventas = obtener_saldo_cuenta_odoo(cuenta_ventas, fecha_inicio, fecha_fin, es_ingreso=True)
    print(f"   ✅ Resultado Odoo: ${saldo_ventas:,.2f}")
except Exception as e:
    print(f"   ❌ Falló: {e}")

print("-" * 50)

# ---------------------------------------------------------
# PRUEBA 2: GASTOS FIJOS (Egreso por Grupo)
# Cuenta: 601 (Busca 601.01, 601.02, etc.)
# ---------------------------------------------------------
cuenta_gastos = "601" 
print(f"2️⃣  Probando GASTOS FIJOS (Grupo {cuenta_gastos}%)...")
try:
    saldo_gastos = obtener_saldo_cuenta_odoo(cuenta_gastos, fecha_inicio, fecha_fin, es_ingreso=False)
    print(f"   ✅ Resultado Odoo: ${saldo_gastos:,.2f}")
except Exception as e:
    print(f"   ❌ Falló: {e}")

print("-" * 50)

# ---------------------------------------------------------
# PRUEBA 3: CRÉDITO BANCARIO (Egreso Exacto)
# Cuenta: 252.01.03 (La que mencionaste arriba)
# ---------------------------------------------------------
cuenta_credito = "252.01.03"
print(f"3️⃣  Probando CRÉDITO BANCARIO (Cuenta {cuenta_credito})...")
try:
    saldo_credito = obtener_saldo_cuenta_odoo(cuenta_credito, fecha_inicio, fecha_fin, es_ingreso=False)
    print(f"   ✅ Resultado Odoo: ${saldo_credito:,.2f}")
except Exception as e:
    print(f"   ❌ Falló: {e}")

print("-" * 50)
print("🏁 Prueba finalizada.")