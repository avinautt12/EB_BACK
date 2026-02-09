import sys
import os
# Ajuste de ruta para encontrar tus módulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.odoo_utils import obtener_saldo_cuenta_odoo

def prueba_ventas_reales(anio, mes):
    # Usamos la serie 4 que encontraste en el plan de cuentas de Odoo
    cuenta_ventas = '401.01.01' 
    fecha_inicio = f"{anio}-{mes:02d}-01"
    fecha_fin = f"{anio}-{mes:02d}-31" # Ajustar según el mes

    print(f"🔍 Consultando lo FACTURADO GENUINAMENTE (Cuenta {cuenta_ventas})...")
    
    # El motor de balanza restará automáticamente Notas de Crédito (Haber - Debe)
    monto = obtener_saldo_cuenta_odoo(cuenta_ventas, fecha_inicio, fecha_fin)
    
    print(f"💰 Venta Neta Real: ${monto:,.2f}")
    print(f"Nota: Este valor excluye anticipos no facturados y descuenta devoluciones.")

if __name__ == "__main__":
    prueba_ventas_reales(2026, 1)