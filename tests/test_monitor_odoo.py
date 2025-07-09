import os
import sys
import pytest
from werkzeug.datastructures import FileStorage
from io import BytesIO
import pandas as pd
from unittest.mock import patch, MagicMock

# Añade el directorio raíz al path para las importaciones
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Fixture para la aplicación Flask
@pytest.fixture
def app():
    from app import app as flask_app
    flask_app.config['TESTING'] = True
    flask_app.config['UPLOAD_FOLDER'] = 'test_uploads'
    yield flask_app

# Fixture para el cliente de prueba
@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def sample_excel_file():
    # Crear un DataFrame con TODAS las columnas que el endpoint espera
    data = {
        'Líneas de factura/Número': ['FACT-001', 'FACT-002'],
        'Líneas de factura/Producto/Referencia interna': ['REF-001', 'REF-002'],
        'Líneas de factura/Producto/Nombre': ['Producto A', 'Producto B'],
        'Contacto/Comprador': ['Comprador 1', 'Comprador 2'],
        'Líneas de factura/Contacto/Referencia': ['CONT-001', 'CONT-002'],
        'Líneas de factura/Contacto/Nombre': ['Contacto A', 'Contacto B'],
        'Valor depreciable': [100.50, 200.75],
        'Contacto/Addenda': ['Addenda 1', 'Addenda 2'],
        'Líneas de factura/Fecha de factura': ['2024-06-01', '2024-06-02'],
        'Líneas de factura/Precio unitario': [10.0, 20.0],
        'Líneas de factura/Cantidad': [5, 10],
        'Líneas de factura/Producto/Categoría del producto': ['Cat A', 'Cat B'],
        'Líneas de factura/Estado': ['Pagado', 'Pendiente'],
        'Líneas de factura/Producto/Costo': [7.0, 15.0]
    }

    df = pd.DataFrame(data)

    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False)
    writer.close()
    output.seek(0)

    return FileStorage(
        stream=output,
        filename='test_file.xlsx',
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# Tests actualizados
def test_importar_facturas_success(client, sample_excel_file, mocker):
    # Mock de la conexión a la base de datos
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mocker.patch('routes.monitor_odoo.obtener_conexion', return_value=mock_conn)
    mock_conn.cursor.return_value = mock_cursor
    
    # Simular que no hay errores en la ejecución
    mock_cursor.execute.return_value = None
    mock_cursor.rowcount = 2
    
    # Crear carpeta de uploads de prueba si no existe
    if not os.path.exists('test_uploads'):
        os.makedirs('test_uploads')
    
    # Llamar al endpoint
    response = client.post(
        '/importar_facturas',  # Asegúrate que esta ruta coincida con tu blueprint
        data={'file': sample_excel_file},
        content_type='multipart/form-data'
    )
    
    # Verificaciones
    assert response.status_code == 200
    assert response.json['success'] is True
    assert response.json['count'] == 2
    assert mock_cursor.execute.call_count >= 2
    mock_conn.commit.assert_called_once()

# ... (resto de tus tests)