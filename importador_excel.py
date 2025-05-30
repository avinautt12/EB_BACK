import pandas as pd
from db_conexion import obtener_conexion  # ✅ importar conexión

# Leer Excel
archivo_excel = "facturas.xlsx"
df = pd.read_excel(archivo_excel)

# Renombrar columnas
df = df.rename(columns={
    'Líneas de factura/Número': 'numero_factura',
    'Líneas de factura/Producto/Referencia interna': 'referencia_interna',
    'Líneas de factura/Producto/Nombre': 'nombre_producto',
    'Contacto/Comprador': 'comprador',
    'Líneas de factura/Contacto/Referencia': 'contacto_referencia',
    'Líneas de factura/Contacto/Nombre': 'contacto_nombre',
    'Valor depreciable': 'valor_depreciable',
    'Contacto/Addenda': 'addenda',
    'Líneas de factura/Fecha de factura': 'fecha_factura',
    'Líneas de factura/Precio unitario': 'precio_unitario',
    'Líneas de factura/Cantidad': 'cantidad',
    'Líneas de factura/Producto/Categoría del producto': 'categoria_producto',
    'Líneas de factura/Estado': 'estado_factura',
    'Líneas de factura/Producto/Costo': 'costo_producto'
})

df = df.where(pd.notna(df), None)

def clean_for_sql(val):
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    if isinstance(val, str):
        val = val.strip()
        if val.lower() == 'nan' or val == '':
            return None
    return val

def safe_decimal(value):
    try:
        if pd.isna(value) or value is None:
            return None
        return float(value)
    except (ValueError, TypeError):
        return None

# Conectarse a MySQL
conexion = obtener_conexion()
cursor = conexion.cursor()

# Insertar los datos
for _, fila in df.iterrows():
    sql = """
        INSERT INTO monitor_odoo (
            numero_factura, referencia_interna, nombre_producto, comprador,
            contacto_referencia, contacto_nombre, valor_depreciable, addenda,
            fecha_factura, precio_unitario, cantidad, categoria_producto,
            estado_factura, costo_producto
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    try:
        cantidad = int(fila['cantidad']) if fila['cantidad'] is not None else 0
    except:
        cantidad = 0

    fecha = None
    if fila['fecha_factura'] is not None:
        try:
            fecha_dt = pd.to_datetime(fila['fecha_factura'], errors='coerce')
            if pd.notna(fecha_dt):
                fecha = fecha_dt.date()
        except:
            fecha = None

    valores_raw = [
        fila['numero_factura'], fila['referencia_interna'], fila['nombre_producto'], fila['comprador'],
        fila['contacto_referencia'], fila['contacto_nombre'], safe_decimal(fila['valor_depreciable']), fila['addenda'],
        fecha,
        safe_decimal(fila['precio_unitario']), cantidad,
        fila['categoria_producto'], fila['estado_factura'], safe_decimal(fila['costo_producto'])
    ]
    valores = tuple(clean_for_sql(v) for v in valores_raw)

    cursor.execute(sql, valores)

conexion.commit()
cursor.close()
#conexion.close()

print("✅ Datos insertados correctamente.")
print(len(df))  

