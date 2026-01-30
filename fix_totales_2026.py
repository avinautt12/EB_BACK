from db_conexion import obtener_conexion
from collections import defaultdict

# --- CONFIGURACIÓN ---
ANIO = 2026

def recalcular_formulas_flujo_manual(conexion, anio, mes):
    print(f"   ... Procesando Mes {mes}/{anio} ...")
    cursor = conexion.cursor(dictionary=True)
    
    fecha_actual = f"{anio}-{mes:02d}-01"
    
    # Calcular mes anterior para arrastrar saldo
    mes_anterior = mes - 1
    anio_anterior = anio
    if mes_anterior == 0:
        mes_anterior = 12
        anio_anterior = anio - 1
    fecha_anterior = f"{anio_anterior}-{mes_anterior:02d}-01"

    try:
        # 1. Cargar datos existentes
        sql_fetch = "SELECT id_concepto, monto_real, monto_proyectado FROM flujo_valores WHERE fecha_reporte = %s"
        cursor.execute(sql_fetch, (fecha_actual,))
        rows = cursor.fetchall()
        
        val_r = defaultdict(float)
        val_p = defaultdict(float)
        
        for r in rows:
            val_r[r['id_concepto']] = float(r['monto_real'] or 0)
            val_p[r['id_concepto']] = float(r['monto_proyectado'] or 0)

        # =============================================================
        # 2. DEFINICIÓN DE IDs (LISTAS COMPLETAS)
        # =============================================================
        ID_SALDO_INICIAL = 1
        ID_VENTAS = 2
        ID_TOTAL_RECUPERACION = 4
        
        # Otros Ingresos (Del 5 al 17)
        IDS_OTROS_INGRESOS = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]
        ID_TOTAL_OTROS_INGRESOS = 18
        
        ID_TOTAL_ENTRADA_EFECTIVO = 19
        
        # Salidas Proveedores (Pagos Reales 20-23 + Proyecciones 32-39)
        IDS_SALIDA_PROVEEDORES = [20, 21, 22, 23, 32, 33, 34, 35, 36, 37, 38, 39]
        ID_TOTAL_SALIDA_PROVEEDORES = 40
        
        # Gastos (Operativos + Impuestos + Fijos)
        # 24-27: Financieros/Laborales
        # 41-43: Impuestos/Nomina
        # 44-50: Fijos y Administrativos
        IDS_GASTOS = [24, 25, 26, 27, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50] 
        ID_TOTAL_GASTOS = 51
        
        # Créditos Bancarios
        IDS_PAGO_CREDITOS = [52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62]
        ID_TOTAL_PAGO_CREDITOS = 63
        
        ID_TOTAL_SALIDAS_EFECTIVO = 64
        ID_TOTAL_DISPONIBLE = 66

        # =============================================================
        # 3. CÁLCULOS MATEMÁTICOS
        # =============================================================
        
        # Helper para guardar
        def guardar(id_c, r, p):
            actualizar_valor_bd(cursor, id_c, fecha_actual, r, 'real')
            actualizar_valor_bd(cursor, id_c, fecha_actual, p, 'proyectado')
            val_r[id_c] = r
            val_p[id_c] = p

        # A) SALDO INICIAL (Arrastre del mes anterior)
        sql_ant = "SELECT monto_real, monto_proyectado FROM flujo_valores WHERE id_concepto = %s AND fecha_reporte = %s"
        cursor.execute(sql_ant, (ID_TOTAL_DISPONIBLE, fecha_anterior))
        res_prev = cursor.fetchone()
        
        si_r = float(res_prev['monto_real']) if res_prev else 0.0
        si_p = float(res_prev['monto_proyectado']) if res_prev else 0.0
        
        # Excepción Enero: Si no hay anterior, respetar lo manual
        if mes == 1 and si_r == 0: si_r = val_r[ID_SALDO_INICIAL]
        if mes == 1 and si_p == 0: si_p = val_p[ID_SALDO_INICIAL]
        
        guardar(ID_SALDO_INICIAL, si_r, si_p)

        # B) TOTAL RECUPERACION (= Ventas)
        guardar(ID_TOTAL_RECUPERACION, val_r[ID_VENTAS], val_p[ID_VENTAS])

        # C) TOTAL OTROS INGRESOS (Suma de 5 a 17)
        otros_r = sum(val_r[i] for i in IDS_OTROS_INGRESOS)
        otros_p = sum(val_p[i] for i in IDS_OTROS_INGRESOS)
        guardar(ID_TOTAL_OTROS_INGRESOS, otros_r, otros_p)

        # D) TOTAL ENTRADA EFECTIVO
        # Fórmula: Saldo Inicial + Recuperacion + Otros Ingresos
        ent_r = val_r[ID_SALDO_INICIAL] + val_r[ID_TOTAL_RECUPERACION] + otros_r
        ent_p = val_p[ID_SALDO_INICIAL] + val_p[ID_TOTAL_RECUPERACION] + otros_p
        guardar(ID_TOTAL_ENTRADA_EFECTIVO, ent_r, ent_p)

        # E) TOTAL SALIDA PROVEEDORES
        prov_r = sum(val_r[i] for i in IDS_SALIDA_PROVEEDORES)
        prov_p = sum(val_p[i] for i in IDS_SALIDA_PROVEEDORES)
        guardar(ID_TOTAL_SALIDA_PROVEEDORES, prov_r, prov_p)

        # F) TOTAL GASTOS
        gastos_r = sum(val_r[i] for i in IDS_GASTOS)
        gastos_p = sum(val_p[i] for i in IDS_GASTOS)
        guardar(ID_TOTAL_GASTOS, gastos_r, gastos_p)

        # G) TOTAL CREDITOS
        cred_r = sum(val_r[i] for i in IDS_PAGO_CREDITOS)
        cred_p = sum(val_p[i] for i in IDS_PAGO_CREDITOS)
        guardar(ID_TOTAL_PAGO_CREDITOS, cred_r, cred_p)

        # H) TOTAL SALIDAS EFECTIVO
        salidas_r = prov_r + gastos_r + cred_r
        salidas_p = prov_p + gastos_p + cred_p
        guardar(ID_TOTAL_SALIDAS_EFECTIVO, salidas_r, salidas_p)

        # I) TOTAL EFECTIVO DISPONIBLE
        disp_r = ent_r - salidas_r
        disp_p = ent_p - salidas_p
        guardar(ID_TOTAL_DISPONIBLE, disp_r, disp_p)

    except Exception as e:
        print(f"❌ Error en cálculo mes {mes}: {e}")

def actualizar_valor_bd(cursor, id_concepto, fecha, monto, tipo):
    col = 'monto_real' if tipo == 'real' else 'monto_proyectado'
    # Upsert seguro
    check = "SELECT id_valor FROM flujo_valores WHERE id_concepto = %s AND fecha_reporte = %s"
    cursor.execute(check, (id_concepto, fecha))
    res = cursor.fetchone()
    
    if res:
        uid = res['id_valor'] if isinstance(res, dict) else res[0]
        cursor.execute(f"UPDATE flujo_valores SET {col} = %s WHERE id_valor = %s", (monto, uid))
    else:
        v_r = monto if tipo == 'real' else 0
        v_p = monto if tipo == 'proyectado' else 0
        cursor.execute("INSERT INTO flujo_valores (id_concepto, fecha_reporte, monto_real, monto_proyectado) VALUES (%s, %s, %s, %s)", 
                       (id_concepto, fecha, v_r, v_p))

def main():
    print(f"🚀 Iniciando corrección de totales 2026...")
    conn = obtener_conexion()
    for m in range(1, 13):
        recalcular_formulas_flujo_manual(conn, ANIO, m)
        conn.commit()
    conn.close()
    print("✅ Corrección finalizada.")

if __name__ == '__main__':
    main()