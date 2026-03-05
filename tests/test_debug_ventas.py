import xmlrpc.client
import ssl

# --- 1. TUS CREDENCIALES (Tal cual las tienes) ---
ODOO_URL = 'https://ebik.odoo.com'
ODOO_DB = 'ebik-prod-15375115'
ODOO_USER = 'sistemas@elitebike-mx.com'
ODOO_PASSWORD = 'bb36fdae62c3c113fb91de0143eba06da199672d'

# --- 2. CONFIGURACIÓN DE LA PRUEBA ---
CUENTA_A_PROBAR = '102.01.013'  # Ventas Generales / Santander
FECHA_INICIO = '2026-02-01'
FECHA_FIN = '2026-02-28'

# Aquí ponemos las palabras que quieres filtrar (Cópialas EXACTAS de tu BD)
PALABRAS_EXCLUIDAS = ['TRASPASO', 'DEVOLUCION'] 

def run_test():
    print("\n--- INICIANDO DIAGNÓSTICO DE VENTAS GENERALES ---")
    print(f"Buscando en cuenta: {CUENTA_A_PROBAR}")
    print(f"Periodo: {FECHA_INICIO} al {FECHA_FIN}")
    print(f"Filtros activos: {PALABRAS_EXCLUIDAS}\n")

    try:
        # Conexión
        context = ssl._create_unverified_context()
        common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common', context=context)
        models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object', context=context)
        uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})

        if not uid:
            print("❌ Error de autenticación en Odoo")
            return

        # Búsqueda
        domain = [
            ('date', '>=', FECHA_INICIO),
            ('date', '<=', FECHA_FIN),
            ('parent_state', '=', 'posted'), # Solo publicados
            ('account_id.code', '=like', CUENTA_A_PROBAR + '%')
        ]
        
        # Pedimos campos clave para entender el contexto
        campos = ['date', 'name', 'ref', 'debit', 'credit', 'partner_id']
        apuntes = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'search_read', [domain], {'fields': campos})

        suma_total_sin_filtro = 0.0
        suma_total_con_filtro = 0.0
        
        print(f"{'FECHA':<12} | {'MONTO (Debe-Haber)':<20} | {'ESTADO':<10} | {'DESCRIPCIÓN DETECTADA'}")
        print("-" * 100)

        for linea in apuntes:
            # 1. Calculamos el monto (Asumimos naturaleza DEUDORA: Debe - Haber)
            # Si fuera acreedora sería al revés, pero para bancos suele ser así.
            monto = linea['debit'] - linea['credit']
            
            suma_total_sin_filtro += monto

            # 2. Construimos el texto completo donde buscaremos
            # Unimos: Nombre del asiento + Referencia
            texto_completo = (str(linea['name'] or '') + ' ' + str(linea['ref'] or '')).upper()
            
            # 3. Aplicamos el filtro
            es_excluido = False
            palabra_detectada = ""
            
            for palabra in PALABRAS_EXCLUIDAS:
                # Usamos upper() para asegurar que mayúsculas/minúsculas no afecten
                if palabra.upper() in texto_completo:
                    es_excluido = True
                    palabra_detectada = palabra
                    break
            
            # 4. Imprimimos resultado
            if es_excluido:
                estado = f"⛔ IGNORADO ({palabra_detectada})"
                color = "\033[91m" # Rojo
            else:
                estado = "✅ SUMADO"
                color = "\033[92m" # Verde
                suma_total_con_filtro += monto
                
            reset = "\033[0m"
            
            # Solo imprimimos si el monto no es cero para no llenar de basura
            if abs(monto) > 0.01:
                print(f"{color}{linea['date']:<12} | ${monto:,.2f}{' ':<10} | {estado:<20} | {texto_completo[:50]}...{reset}")

        print("-" * 100)
        print(f"\n📊 RESUMEN FINAL:")
        print(f"   Total Odoo (Bruto):   ${suma_total_sin_filtro:,.2f}")
        print(f"   Total Filtrado (Neto): ${suma_total_con_filtro:,.2f}")
        
        diferencia = suma_total_sin_filtro - suma_total_con_filtro
        print(f"   Diferencia (Excluido): ${diferencia:,.2f}")

    except Exception as e:
        print(f"❌ Error crítico: {e}")

if __name__ == '__main__':
    run_test()