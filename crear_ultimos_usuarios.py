#!/usr/bin/env python3
"""Crear usuarios para los últimos 6 clientes sin usuario vinculado."""

from db_conexion import obtener_conexion
import random
import string

conn = obtener_conexion()
cursor = conn.cursor(dictionary=True)

# Obtener clientes sin usuario
cursor.execute('''
    SELECT c.id, c.nombre_cliente, c.clave, c.id_grupo
    FROM clientes c
    LEFT JOIN usuarios u ON u.cliente_id = c.id
    WHERE u.id IS NULL
''')

clientes = cursor.fetchall()
print(f'Encontrados {len(clientes)} clientes sin usuario')

def generar_username(nombre):
    partes = nombre.upper().split()
    base = ''.join([p[0] for p in partes if p])[:4]
    suffix = ''.join(random.choices(string.digits, k=3))
    return f'{base}{suffix}'

def generar_password():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=12))

insert_cursor = conn.cursor()
creados = 0

for cliente in clientes:
    try:
        username = generar_username(cliente['nombre_cliente'])
        password = generar_password()
        
        insert_cursor.execute('''
            INSERT INTO usuarios (
                nombre, correo, usuario, contrasena,
                cliente_id, id_grupo, rol_id, activo, clave
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            cliente['nombre_cliente'],
            f'{username}@elitebike.local',
            username,
            password,
            cliente['id'],
            cliente['id_grupo'],
            2,
            1,
            cliente['clave']
        ))
        
        print(f'✅ {username:12} para {cliente["nombre_cliente"]}')
        creados += 1
    except Exception as e:
        print(f'❌ Error para {cliente["nombre_cliente"]}: {e}')

conn.commit()
cursor.close()
insert_cursor.close()
conn.close()

print(f'\n✅ Total creados: {creados}')
