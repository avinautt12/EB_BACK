from flask import Blueprint, jsonify, request
from db_conexion import obtener_conexion
from decimal import Decimal
from datetime import date, datetime
from collections import defaultdict
import calendar

# ==============================================================================
# FUNCIONES DE APOYO (UNIFICADAS)
# ==============================================================================

def actualizar_valor_bd(cursor, id_concepto, fecha, monto, tipo='real'):
    columna = 'monto_real' if tipo == 'real' else 'monto_proyectado'
    check_sql = "SELECT id_valor FROM flujo_valores WHERE id_concepto = %s AND fecha_reporte = %s"
    cursor.execute(check_sql, (id_concepto, fecha))
    registro = cursor.fetchone()
    
    if registro:
        uid = registro['id_valor'] if isinstance(registro, dict) else registro[0]
        cursor.execute(f"UPDATE flujo_valores SET {columna} = %s WHERE id_valor = %s", (monto, uid))
    else:
        v_r = monto if tipo == 'real' else 0
        v_p = monto if tipo == 'proyectado' else 0
        cursor.execute("INSERT INTO flujo_valores (id_concepto, fecha_reporte, monto_real, monto_proyectado) VALUES (%s, %s, %s, %s)", 
                       (id_concepto, fecha, v_r, v_p))

def recalcular_formulas_flujo(conexion, anio, mes):
    """
    REGLA: El Disponible REAL del mes anterior es el Saldo Inicial REAL Y PROYECTADO actual.
    """
    cursor = conexion.cursor(dictionary=True)
    fecha_actual = f"{anio}-{mes:02d}-01"
    
    if mes == 1:
        mes_ant, anio_ant = 12, anio - 1
    else:
        mes_ant, anio_ant = mes - 1, anio
    fecha_anterior = f"{anio_ant}-{mes_ant:02d}-01"

    try:
        # 1. ARRASTRE MANDATORIO: Real del mes pasado -> (Real y Proy) de este mes
        sql_ant = "SELECT monto_real FROM flujo_valores WHERE id_concepto = 66 AND fecha_reporte = %s"
        cursor.execute(sql_ant, (fecha_anterior,))
        res_prev = cursor.fetchone()
        
        # Disponible Real anterior
        saldo_arrastre = float(res_prev['monto_real']) if res_prev else 0.0

        # Cargar valores actuales para cálculos
        sql_fetch = "SELECT id_concepto, monto_real, monto_proyectado FROM flujo_valores WHERE fecha_reporte = %s"
        cursor.execute(sql_fetch, (fecha_actual,))
        rows = cursor.fetchall()
        val_r, val_p = defaultdict(float), defaultdict(float)
        for r in rows:
            val_r[r['id_concepto']] = float(r['monto_real'] or 0)
            val_p[r['id_concepto']] = float(r['monto_proyectado'] or 0)

        # IDs Clave
        ID_SI = 1; ID_VENTAS = 2; ID_RECUP = 4; ID_TOT_ING = 18; ID_TOT_ENT = 19
        IDS_OTROS = list(range(5, 18))
        IDS_PROV = [20, 21, 22, 23] + list(range(32, 40))
        IDS_GASTOS = [24, 25, 26, 27, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50]
        IDS_CRED = list(range(52, 63))
        ID_TOT_SAL = 64; ID_DISP = 66

        # APLICAR ARRASTRE (Mandatorio a menos que sea Enero 2026)
        if not (anio == 2026 and mes == 1):
            val_r[ID_SI] = saldo_arrastre
            val_p[ID_SI] = saldo_arrastre
            actualizar_valor_bd(cursor, ID_SI, fecha_actual, saldo_arrastre, 'real')
            actualizar_valor_bd(cursor, ID_SI, fecha_actual, saldo_arrastre, 'proyectado')

        # 2. CÁLCULOS (Ambas columnas)
        for tipo in ['real', 'proy']:
            v_map = val_r if tipo == 'real' else val_p
            
            # Totales de Ingresos
            actualizar_valor_bd(cursor, ID_RECUP, fecha_actual, v_map[ID_VENTAS], tipo)
            v_map[ID_RECUP] = v_map[ID_VENTAS]
            
            s_otros = sum(v_map[i] for i in IDS_OTROS)
            actualizar_valor_bd(cursor, ID_TOT_ING, fecha_actual, s_otros, tipo)
            v_map[ID_TOT_ING] = s_otros
            
            ent = v_map[ID_SI] + v_map[ID_RECUP] + s_otros
            actualizar_valor_bd(cursor, ID_TOT_ENT, fecha_actual, ent, tipo)
            v_map[ID_TOT_ENT] = ent
            
            # Totales de Salidas
            prov = sum(v_map[i] for i in IDS_PROV)
            gst = sum(v_map[i] for i in IDS_GASTOS)
            crd = sum(v_map[i] for i in IDS_CRED)
            tot_sal = prov + gst + crd
            
            actualizar_valor_bd(cursor, 40, fecha_actual, prov, tipo) # Total Prov
            actualizar_valor_bd(cursor, 51, fecha_actual, gst, tipo)  # Total Gastos
            actualizar_valor_bd(cursor, 63, fecha_actual, crd, tipo)  # Total Cred
            actualizar_valor_bd(cursor, ID_TOT_SAL, fecha_actual, tot_sal, tipo)
            v_map[ID_TOT_SAL] = tot_sal
            
            # Disponible Final
            disp = ent - tot_sal
            actualizar_valor_bd(cursor, ID_DISP, fecha_actual, disp, tipo)

    except Exception as e:
        print(f"❌ Error mes {mes}/{anio}: {e}")

# ==============================================================================
# SCRIPT DE EJECUCIÓN MANUAL (PARA EL FIX)
# ==============================================================================
def main_fix():
    conn = obtener_conexion()
    for anio in [2026, 2027]:
        print(f"🚀 Corrigiendo año {anio} con regla Real -> SI...")
        for m in range(1, 13):
            recalcular_formulas_flujo(conn, anio, m)
            conn.commit()
    conn.close()
    print("✅ Proceso finalizado.")

if __name__ == '__main__':
    main_fix()