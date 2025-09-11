import os
import redis
from rq import Worker, Queue, Connection

# Importar la conexión de Redis desde tu módulo de email
try:
    from routes.email import redis_conn
except ImportError:
    # Fallback si no puede importar
    redis_conn = redis.Redis(host='localhost', port=6379, db=0)

if __name__ == '__main__':
    with Connection(redis_conn):
        worker = Worker(['emails'])
        print("🚀 Worker de emails iniciado. Esperando trabajos...")
        worker.work()