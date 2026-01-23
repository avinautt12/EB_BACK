import mysql.connector
from mysql.connector import pooling

# --- TUS CREDENCIALES ---
db_config = {
    'host': "127.0.0.1",
    'user': "root",
    'password': "1234",
    'database': "elite_bike_db",
    'port': 3306
}

# Variable global donde guardaremos la "piscina" de conexiones
db_pool = None

def obtener_conexion():
    global db_pool

    # 1. Si es la primera vez que se llama, creamos el Pool
    if db_pool is None:
        try:
            db_pool = mysql.connector.pooling.MySQLConnectionPool(
                pool_name="pool_elite_bike",
                pool_size=5,  # Mantiene 5 conexiones abiertas listas para usar
                pool_reset_session=True,
                **db_config
            )
            print("✅ Pool de conexiones iniciado correctamente.")
        except Exception as e:
            print(f"❌ Error al crear el pool: {e}")
            # Si falla el pool, intentamos conectar a la antigua para no romper nada
            return mysql.connector.connect(**db_config)

    # 2. Pedimos una conexión prestada del pool
    try:
        conexion = db_pool.get_connection()
        
        # Verificar que la conexión siga viva
        if not conexion.is_connected():
            conexion.reconnect(attempts=3, delay=0)
            
        return conexion

    except Exception as e:
        print(f"⚠️ Error obteniendo conexión del pool (usando fallback): {e}")
        return mysql.connector.connect(**db_config)