from db_conexion import obtener_conexion
from collections import defaultdict

# ==============================================================================
# 1. FUNCIÓN DE APOYO (APUNTANDO A TABLAS UNIFICADAS)
# ==============================================================================
def actualizar_valor_bd(cursor, id_concepto, fecha, monto, tipo='real'):
    columna = 'monto_real' if tipo == 'real' else 'monto_proyectado'
    
    # CAMBIO: Usamos la tabla unificada
    check_sql = "SELECT id_valor FROM flujo_valores_unificados WHERE id_concepto = %s AND fecha_reporte = %s"
    cursor.execute(check_sql, (id_concepto, fecha))
    registro = cursor.fetchone()
    
    if registro:
        # Manejo seguro si devuelve diccionario o tupla
        uid = registro['id_valor'] if isinstance(registro, dict) else registro[0]
        cursor.execute(f"UPDATE flujo_valores_unificados SET {columna} = %s WHERE id_valor = %s", (monto, uid))
    else:
        v_r = monto if tipo == 'real' else 0
        v_p = monto if tipo == 'proyectado' else 0
        # CAMBIO: Insert en tabla unificada
        cursor.execute("INSERT INTO flujo_valores_unificados (id_concepto, fecha_reporte, monto_real, monto_proyectado) VALUES (%s, %s, %s, %s)", 
                       (id_concepto, fecha, v_r, v_p))

# ==============================================================================
# 2. LÓGICA DE CÁLCULO (CON NUEVOS IDs 1-99)
# ==============================================================================
def recalcular_formulas_flujo(conexion, anio, mes):
    """
    REGLA: El Disponible REAL del mes anterior (ID 99) es el Saldo Inicial (ID 1) actual.
    """
    print(f"🧮 Recalculando UNIFICADO para {mes}/{anio}...")
    cursor = conexion.cursor(dictionary=True)
    
    fecha_actual = f"{anio}-{mes:02d}-01"
    
    # Calcular mes anterior
    if mes == 1:
        mes_ant, anio_ant = 12, anio - 1
    else:
        mes_ant, anio_ant = mes - 1, anio
    fecha_anterior = f"{anio_ant}-{mes_ant:02d}-01"

    try:
        # ==========================================
        # 1. DEFINICIÓN DE GRUPOS (ACTUALIZADO SEGÚN TU BD)
        # ==========================================
        
        # --- CONCEPTOS DE SALDO Y ENTRADAS ---
        ID_SALDO_INICIAL = 1
        ID_SALDO_FINAL = 99
        
        ID_VENTAS = 2
        ID_RECUPERACION = 3  # Espejo de ventas
        
        # Otros Ingresos: Deudores(4), Compra USD(5), Creditos(6), Otros(7)
        IDS_OTROS_INGRESOS = [4, 5, 6, 7] 
        
        ID_TOTAL_ENTRADAS = 8 # Suma de Saldo Inicial + Recuperacion + Otros

        # --- CONCEPTOS DE SALIDAS (AGRUPACIÓN SOLICITADA) ---
        
        # GRUPO 1: GASTOS OPERATIVOS (ID 49)
        # Incluye: Proveedores (20-23), Importaciones(24), Anticipos(25),
        # Gastos Fijos(40), Nomina(41), PTU(42), Impuestos(43)
        IDS_PARA_GASTOS_OPERATIVOS = [20, 21, 22, 23, 24, 25, 40, 41, 42, 43]
        ID_RESUMEN_GASTOS_OP = 49

        # GRUPO 2: FINANCIEROS Y OTROS
        # Incluye: Creditos Bancarios(50), Comisiones(51), Particulares(52), Devoluciones(100)
        IDS_FINANCIEROS = [50, 51, 52, 100]

        # GRUPO 3: MOVIMIENTOS / INVERSIONES
        # Incluye: Inversiones enviados a BBVA/Monex (60)
        IDS_MOVIMIENTOS = [60]
        
        ID_TOTAL_SALIDAS = 90 # Suma de todo lo anterior

        # ==========================================
        # 2. CARGA DE DATOS
        # ==========================================
        
        # A. Arrastre de Saldo del mes anterior
        sql_ant = "SELECT monto_real FROM flujo_valores_unificados WHERE id_concepto = %s AND fecha_reporte = %s"
        cursor.execute(sql_ant, (ID_SALDO_FINAL, fecha_anterior))
        res_prev = cursor.fetchone()
        saldo_arrastre = float(res_prev['monto_real']) if res_prev else 0.0

        # B. Valores actuales del mes
        sql_fetch = "SELECT id_concepto, monto_real, monto_proyectado FROM flujo_valores_unificados WHERE fecha_reporte = %s"
        cursor.execute(sql_fetch, (fecha_actual,))
        rows = cursor.fetchall()
        
        val_r, val_p = defaultdict(float), defaultdict(float)
        for r in rows:
            val_r[r['id_concepto']] = float(r['monto_real'] or 0)
            val_p[r['id_concepto']] = float(r['monto_proyectado'] or 0)

        # C. Aplicar Arrastre (Si no es el primer mes histórico)
        if not (anio == 2026 and mes == 1):
            val_r[ID_SALDO_INICIAL] = saldo_arrastre
            val_p[ID_SALDO_INICIAL] = saldo_arrastre
            actualizar_valor_bd(cursor, ID_SALDO_INICIAL, fecha_actual, saldo_arrastre, 'real')
            actualizar_valor_bd(cursor, ID_SALDO_INICIAL, fecha_actual, saldo_arrastre, 'proyectado')

        # ==========================================
        # 3. CÁLCULOS MATEMÁTICOS
        # ==========================================
        for tipo in ['real', 'proyectado']:
            v_map = val_r if tipo == 'real' else val_p
            
            # --- A. INGRESOS ---
            # 1. Total Recuperacion (Es espejo de Ventas ID 2)
            actualizar_valor_bd(cursor, ID_RECUPERACION, fecha_actual, v_map[ID_VENTAS], tipo)
            v_map[ID_RECUPERACION] = v_map[ID_VENTAS]
            
            # 2. Total Entradas (Saldo Inicial + Recuperacion + Otros)
            s_otros = sum(v_map[i] for i in IDS_OTROS_INGRESOS)
            total_entradas = v_map[ID_SALDO_INICIAL] + v_map[ID_RECUPERACION] + s_otros
            
            actualizar_valor_bd(cursor, ID_TOTAL_ENTRADAS, fecha_actual, total_entradas, tipo)
            v_map[ID_TOTAL_ENTRADAS] = total_entradas
            
            # --- B. SALIDAS ---
            
            # 1. Calcular TOTAL GASTOS OPERATIVOS (ID 49)
            # Suma de Proveedores + Nomina + Impuestos + Gastos Fijos
            suma_operativos = sum(v_map[i] for i in IDS_PARA_GASTOS_OPERATIVOS)
            actualizar_valor_bd(cursor, ID_RESUMEN_GASTOS_OP, fecha_actual, suma_operativos, tipo)
            v_map[ID_RESUMEN_GASTOS_OP] = suma_operativos

            # 2. Calcular Financieros y Movimientos
            suma_financieros = sum(v_map[i] for i in IDS_FINANCIEROS)
            suma_movimientos = sum(v_map[i] for i in IDS_MOVIMIENTOS)
            
            # 3. Calcular TOTAL SALIDAS (ID 90)
            # Suma de (Gastos Operativos) + (Financieros) + (Movimientos)
            gran_total_salidas = suma_operativos + suma_financieros + suma_movimientos
            actualizar_valor_bd(cursor, ID_TOTAL_SALIDAS, fecha_actual, gran_total_salidas, tipo)
            v_map[ID_TOTAL_SALIDAS] = gran_total_salidas
            
            # --- C. SALDO FINAL (ID 99) ---
            # Disponible = Total Entradas - Total Salidas
            disponible_final = total_entradas - gran_total_salidas
            actualizar_valor_bd(cursor, ID_SALDO_FINAL, fecha_actual, disponible_final, tipo)

    except Exception as e:
        print(f"❌ Error mes {mes}/{anio}: {e}")

# ==============================================================================
# EJECUCIÓN
# ==============================================================================
def main_fix():
    conn = obtener_conexion()
    if not conn:
        return
        
    print("🚀 Iniciando recálculo en TABLAS UNIFICADAS...")
    # Recalculamos todo 2026 y 2027 para asegurar que el arrastre se propague
    for anio in [2026, 2027]:
        for m in range(1, 13):
            recalcular_formulas_flujo(conn, anio, m)
            conn.commit() # Guardamos mes a mes para que el siguiente mes lea el saldo correcto
            
    conn.close()
    print("✅ Proceso finalizado exitosamente.")

if __name__ == '__main__':
    main_fix()