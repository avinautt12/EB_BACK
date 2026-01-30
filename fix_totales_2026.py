from db_conexion import obtener_conexion
from collections import defaultdict

def actualizar_valor_bd(cursor, id_concepto, fecha, monto, tipo):
    """Esta función DEBE estar definida antes de ser llamada"""
    col = 'monto_real' if tipo == 'real' else 'monto_proyectado'
    check = "SELECT id_valor FROM flujo_valores WHERE id_concepto = %s AND fecha_reporte = %s"
    cursor.execute(check, (id_concepto, fecha))
    res = cursor.fetchone()
    
    if res:
        # Manejo para diccionarios o tuplas según la conexión
        uid = res['id_valor'] if isinstance(res, dict) else res[0]
        cursor.execute(f"UPDATE flujo_valores SET {col} = %s WHERE id_valor = %s", (monto, uid))
    else:
        v_r = monto if tipo == 'real' else 0
        v_p = monto if tipo == 'proyectado' else 0
        cursor.execute("INSERT INTO flujo_valores (id_concepto, fecha_reporte, monto_real, monto_proyectado) VALUES (%s, %s, %s, %s)", 
                       (id_concepto, fecha, v_r, v_p))

def recalcular_formulas_flujo_manual(conexion, anio, mes):
    print(f"   ... Procesando Mes {mes:02d}/{anio} ...")
    cursor = conexion.cursor(dictionary=True)
    
    fecha_actual = f"{anio}-{mes:02d}-01"
    
    if mes == 1:
        mes_anterior, anio_anterior = 12, anio - 1
    else:
        mes_anterior, anio_anterior = mes - 1, anio
    fecha_anterior = f"{anio_anterior}-{mes_anterior:02d}-01"

    try:
        sql_fetch = "SELECT id_concepto, monto_real, monto_proyectado FROM flujo_valores WHERE fecha_reporte = %s"
        cursor.execute(sql_fetch, (fecha_actual,))
        rows = cursor.fetchall()
        
        val_r, val_p = defaultdict(float), defaultdict(float)
        for r in rows:
            val_r[r['id_concepto']] = float(r['monto_real'] or 0)
            val_p[r['id_concepto']] = float(r['monto_proyectado'] or 0)

        # IDs de conceptos según tu base de datos
        ID_SALDO_INICIAL = 1
        ID_TOTAL_RECUPERACION = 4
        IDS_OTROS_INGRESOS = list(range(5, 18)) # 5 al 17
        ID_TOTAL_OTROS_INGRESOS = 18
        ID_TOTAL_ENTRADA_EFECTIVO = 19
        IDS_SALIDA_PROVEEDORES = [20, 21, 22, 23] + list(range(32, 40)) #
        ID_TOTAL_SALIDA_PROVEEDORES = 40
        IDS_GASTOS = [24, 25, 26, 27, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50] 
        ID_TOTAL_GASTOS = 51
        IDS_PAGO_CREDITOS = list(range(52, 63))
        ID_TOTAL_PAGO_CREDITOS = 63
        ID_TOTAL_SALIDAS_EFECTIVO = 64
        ID_TOTAL_DISPONIBLE = 66

        def guardar(id_c, r, p):
            actualizar_valor_bd(cursor, id_c, fecha_actual, r, 'real')
            actualizar_valor_bd(cursor, id_c, fecha_actual, p, 'proyectado')
            val_r[id_c], val_p[id_c] = r, p

        # 1. SALDO INICIAL (Arrastre del mes pasado)
        sql_ant = "SELECT monto_real FROM flujo_valores WHERE id_concepto = %s AND fecha_reporte = %s"
        cursor.execute(sql_ant, (ID_TOTAL_DISPONIBLE, fecha_anterior))
        res_prev = cursor.fetchone()
        
        si_r = float(res_prev['monto_real']) if res_prev else 0.0
        # Excepción Enero 2026: usar el registro manual 15
        if anio == 2026 and mes == 1:
            si_r = val_r[ID_SALDO_INICIAL]
        
        guardar(ID_SALDO_INICIAL, si_r, si_r) # Se asume SI Proyectado = SI Real

        # 2. ENTRADAS
        otros_r = sum(val_r[i] for i in IDS_OTROS_INGRESOS)
        guardar(ID_TOTAL_OTROS_INGRESOS, otros_r, otros_r)

        # FÓRMULA CLAVE: Saldo Inicial + Recuperación + Otros
        ent_r = val_r[ID_SALDO_INICIAL] + val_r[ID_TOTAL_RECUPERACION] + otros_r
        guardar(ID_TOTAL_ENTRADA_EFECTIVO, ent_r, ent_r)

        # 3. SALIDAS
        prov_r = sum(val_r[i] for i in IDS_SALIDA_PROVEEDORES)
        guardar(ID_TOTAL_SALIDA_PROVEEDORES, prov_r, prov_r)

        gastos_r = sum(val_r[i] for i in IDS_GASTOS)
        guardar(ID_TOTAL_GASTOS, gastos_r, gastos_r)

        salidas_r = prov_r + gastos_r + sum(val_r[i] for i in IDS_PAGO_CREDITOS)
        guardar(ID_TOTAL_SALIDAS_EFECTIVO, salidas_r, salidas_r)

        # 4. DISPONIBLE FINAL
        disp_r = ent_r - salidas_r
        guardar(ID_TOTAL_DISPONIBLE, disp_r, disp_r)

    except Exception as e:
        print(f"❌ Error en cálculo mes {mes}/{anio}: {e}")

def main():
    conn = obtener_conexion()
    for anio in [2026, 2027]:
        print(f"🚀 Iniciando año {anio}...")
        for m in range(1, 13):
            recalcular_formulas_flujo_manual(conn, anio, m)
            conn.commit()
    conn.close()
    print("✅ Corrección multianual finalizada.")

if __name__ == '__main__':
    main()