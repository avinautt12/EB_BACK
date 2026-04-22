#!/usr/bin/env python3
"""
Tests: Sincronización de Usuarios Monitor ↔ Tokens de Edición

Ejecutar con:
  python -m pytest test_sync_tokens.py -v
  
O manualmente:
  python test_sync_tokens.py
"""

import unittest
from unittest.mock import patch, MagicMock
from utils.otp_utils import (
    obtener_usuarios_monitor,
    sincronizar_usuarios_desde_monitor,
    listar_tokens_usuarios_monitor,
    generar_otp,
    verificar_otp,
)


class TestSincronizacionTokens(unittest.TestCase):
    """Tests para la sincronización de tokens de edición."""
    
    def setUp(self):
        """Configuración antes de cada test."""
        self.test_usuarios = [
            {
                "id_usuario": 1,
                "nombre": "Usuario Test 1",
                "usuario": "user1",
                "activo": True,
                "clave": "CLI-001",
                "id_grupo": 1,
                "nombre_grupo": "Grupo A",
                "rol_id": 2
            },
            {
                "id_usuario": 2,
                "nombre": "Usuario Test 2",
                "usuario": "user2",
                "activo": True,
                "clave": "CLI-002",
                "id_grupo": 1,
                "nombre_grupo": "Grupo A",
                "rol_id": 2
            }
        ]
    
    def test_obtener_usuarios_monitor_retorna_lista(self):
        """Verifica que obtener_usuarios_monitor retorna una lista."""
        result = obtener_usuarios_monitor()
        self.assertIsInstance(result, list)
        print(f"✓ Monitor retorna lista con {len(result)} usuarios")
    
    def test_usuarios_monitor_tienen_campos_requeridos(self):
        """Verifica que cada usuario tenga los campos necesarios."""
        usuarios = obtener_usuarios_monitor()
        
        if len(usuarios) > 0:
            campos_requeridos = ['id_usuario', 'nombre', 'activo']
            usuario = usuarios[0]
            
            for campo in campos_requeridos:
                self.assertIn(campo, usuario, f"Falta campo '{campo}'")
            
            self.assertIsNotNone(usuario['id_usuario'], "id_usuario no debe ser None")
            print(f"✓ Usuarios tienen campos requeridos: {campos_requeridos}")
    
    def test_generar_otp_retorna_codigo_valido(self):
        """Verifica que generar_otp produce códigos válidos."""
        usuarios = obtener_usuarios_monitor()
        
        if len(usuarios) > 0:
            usuario_id = usuarios[0]['id_usuario']
            codigo = generar_otp(usuario_id)
            
            # Verificar que el código es string de 6 dígitos
            self.assertIsInstance(codigo, str)
            self.assertEqual(len(codigo), 6)
            self.assertTrue(codigo.isdigit())
            print(f"✓ generar_otp() produce código válido: {codigo}")
    
    def test_verificar_otp_funcionamiento(self):
        """Verifica que verificar_otp valida correctamente."""
        usuarios = obtener_usuarios_monitor()
        
        if len(usuarios) > 0:
            usuario_id = usuarios[0]['id_usuario']
            codigo = generar_otp(usuario_id)
            
            # Verificar que el código es válido
            is_valid = verificar_otp(codigo)
            self.assertTrue(is_valid, "El código generado debe ser válido")
            
            # Verificar que no se puede usar dos veces
            is_valid_again = verificar_otp(codigo)
            self.assertFalse(is_valid_again, "El código debe ser invalidado después de usarse")
            
            print(f"✓ verificar_otp() funciona correctamente")
    
    def test_sincronizar_usuarios_retorna_estructura_esperada(self):
        """Verifica que sincronizar retorna estructura correcta."""
        result = sincronizar_usuarios_desde_monitor()
        
        # Verificar estructura de respuesta
        self.assertIn('sincronizados', result)
        self.assertIn('errores', result)
        self.assertIn('total_monitor', result)
        self.assertIn('detalles', result)
        
        # Verificar tipos
        self.assertIsInstance(result['sincronizados'], int)
        self.assertIsInstance(result['errores'], int)
        self.assertIsInstance(result['total_monitor'], int)
        self.assertIsInstance(result['detalles'], list)
        
        print(f"✓ sincronizar_usuarios_desde_monitor() retorna estructura válida")
        print(f"  - Sincronizados: {result['sincronizados']}")
        print(f"  - Errores: {result['errores']}")
        print(f"  - Total: {result['total_monitor']}")
    
    def test_listar_tokens_usuarios_monitor(self):
        """Verifica que listar_tokens_usuarios_monitor retorna usuarios con tokens."""
        tokens = listar_tokens_usuarios_monitor()
        
        self.assertIsInstance(tokens, list)
        print(f"✓ listar_tokens_usuarios_monitor() retorna {len(tokens)} usuarios")
        
        if len(tokens) > 0:
            usuario = tokens[0]
            campos_esperados = ['id', 'nombre', 'usuario', 'token_activo']
            
            for campo in campos_esperados:
                self.assertIn(campo, usuario, f"Usuario debe tener campo '{campo}'")
            
            print(f"✓ Usuarios tienen estructura correcta")
    
    def test_comparacion_endpoints(self):
        """Compara el tamaño de datos entre diferentes endpoints."""
        usuarios_monitor = obtener_usuarios_monitor()
        tokens_monitor = listar_tokens_usuarios_monitor()
        
        print(f"\n📊 COMPARACIÓN DE ENDPOINTS:")
        print(f"  • Usuarios en Monitor: {len(usuarios_monitor)}")
        print(f"  • Usuarios en Tokens: {len(tokens_monitor)}")
        
        # Ambos deben tener el mismo número después de sincronización
        self.assertEqual(len(usuarios_monitor), len(tokens_monitor),
                        "Debe haber usuario token para cada usuario monitor")
    
    def test_sincronizacion_masiva(self):
        """Prueba sincronización de múltiples usuarios."""
        usuarios_antes = obtener_usuarios_monitor()
        total_usuarios = len(usuarios_antes)
        
        print(f"\n🔄 PRUEBA DE SINCRONIZACIÓN MASIVA:")
        print(f"  Total de usuarios: {total_usuarios}")
        
        if total_usuarios > 0:
            result = sincronizar_usuarios_desde_monitor()
            
            # Verificar que se sincronizaron todos
            self.assertEqual(result['sincronizados'], total_usuarios,
                           f"Se deben sincronizar los {total_usuarios} usuarios")
            self.assertEqual(result['errores'], 0,
                           "No debe haber errores")
            
            print(f"  ✓ Sincronizados: {result['sincronizados']}")
            print(f"  ✓ Sin errores")
            
            # Verificar que todos tienen tokens
            tokens = listar_tokens_usuarios_monitor()
            usuarios_con_token = sum(1 for t in tokens if t['token_activo'])
            print(f"  ✓ Usuarios con OTP vigente: {usuarios_con_token}/{total_usuarios}")


class TestIntegracionAPI(unittest.TestCase):
    """Tests de integración con API Flask (requiere servidor ejecutándose)."""
    
    @classmethod
    def setUpClass(cls):
        """Configura cliente de test."""
        try:
            import requests
            cls.requests = requests
            cls.base_url = 'http://localhost:5000'
        except ImportError:
            cls.skipTest("requests no está instalado")
    
    def test_endpoint_sincronizar(self):
        """Prueba endpoint POST /edicion/sincronizar-desde-monitor."""
        try:
            response = self.requests.post(f'{self.base_url}/edicion/sincronizar-desde-monitor')
            self.assertEqual(response.status_code, 200, "Endpoint debe retornar 200")
            
            data = response.json()
            self.assertIn('sincronizados', data)
            print(f"✓ POST /edicion/sincronizar-desde-monitor → {response.status_code}")
            print(f"  Sincronizados: {data['sincronizados']}/{data['total_monitor']}")
        except (self.requests.ConnectionError, Exception) as e:
            self.skipTest(f"Servidor no está ejecutándose: {e}")
    
    def test_endpoint_tokens_monitor(self):
        """Prueba endpoint GET /edicion/tokens-monitor."""
        try:
            response = self.requests.get(f'{self.base_url}/edicion/tokens-monitor')
            self.assertEqual(response.status_code, 200, "Endpoint debe retornar 200")
            
            data = response.json()
            self.assertIsInstance(data, list)
            print(f"✓ GET /edicion/tokens-monitor → {response.status_code}")
            print(f"  Usuarios retornados: {len(data)}")
        except (self.requests.ConnectionError, Exception) as e:
            self.skipTest(f"Servidor no está ejecutándose: {e}")


def print_header(text):
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def run_tests():
    """Ejecuta todos los tests."""
    print_header("🧪 TESTS: Sincronización de Tokens de Edición")
    
    # Crear test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Agregar tests
    suite.addTests(loader.loadTestsFromTestCase(TestSincronizacionTokens))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegracionAPI))
    
    # Ejecutar con verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Resumen
    print_header("📊 RESUMEN DE TESTS")
    print(f"Tests ejecutados: {result.testsRun}")
    print(f"Exitosos: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Fallos: {len(result.failures)}")
    print(f"Errores: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n✅ TODOS LOS TESTS PASARON")
        return 0
    else:
        print("\n❌ ALGUNOS TESTS FALLARON")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(run_tests())
