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
        # 1. DEFINICIÓN DE GRUPOS (IDs NUEVOS)
        # ==========================================
        ID_SALDO_INICIAL = 1
        ID_SALDO_FINAL = 99

        # --- ENTRADAS ---
        ID_VENTAS = 2
        ID_RECUPERACION = 3
        IDS_OTROS = [4, 5, 6, 7] # Deudores, Compra USD, Creditos, Otros
        ID_TOTAL_ENTRADAS = 8

        # --- SALIDAS ---
        # Proveedores (Sin el 24, porque lo movimos a Gastos)
        IDS_PROVEEDORES = [20, 21, 22, 23, 25] 
        
        # Operativos (Incluye Importaciones ID 24 para que sume al Total Gastos ID 49)
        IDS_OPERATIVOS = [24, 40, 41, 42, 43]
        ID_TOTAL_GASTOS = 49 

        IDS_FINANCIEROS = [51]
        IDS_MOVIMIENTOS = [60]
        
        ID_TOTAL_SALIDAS = 90

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
        for tipo in ['real', 'proy']:
            v_map = val_r if tipo == 'real' else val_p
            
            # --- INGRESOS ---
            # 1. Total Recuperacion (Es espejo de Ventas)
            actualizar_valor_bd(cursor, ID_RECUPERACION, fecha_actual, v_map[ID_VENTAS], tipo)
            v_map[ID_RECUPERACION] = v_map[ID_VENTAS]
            
            # 2. Total Entradas (Saldo Inicial + Ventas + Otros)
            s_otros = sum(v_map[i] for i in IDS_OTROS)
            ent = v_map[ID_SALDO_INICIAL] + v_map[ID_RECUPERACION] + s_otros
            
            actualizar_valor_bd(cursor, ID_TOTAL_ENTRADAS, fecha_actual, ent, tipo)
            v_map[ID_TOTAL_ENTRADAS] = ent
            
            # --- SALIDAS ---
            # 1. Suma de Grupos
            prov = sum(v_map[i] for i in IDS_PROVEEDORES)
            oper = sum(v_map[i] for i in IDS_OPERATIVOS) # Aquí ya incluye el 24 (Importaciones)
            fin  = sum(v_map[i] for i in IDS_FINANCIEROS)
            mov  = sum(v_map[i] for i in IDS_MOVIMIENTOS)
            
            # 2. Guardar Subtotal de Gastos (ID 49)
            actualizar_valor_bd(cursor, ID_TOTAL_GASTOS, fecha_actual, oper, tipo)

            # 3. Gran Total Salidas (ID 90)
            tot_sal = prov + oper + fin + mov
            actualizar_valor_bd(cursor, ID_TOTAL_SALIDAS, fecha_actual, tot_sal, tipo)
            v_map[ID_TOTAL_SALIDAS] = tot_sal
            
            # --- SALDO FINAL (ID 99) ---
            # Disponible = Total Entradas (que ya trae saldo inicial) - Total Salidas
            disp = ent - tot_sal
            actualizar_valor_bd(cursor, ID_SALDO_FINAL, fecha_actual, disp, tipo)

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