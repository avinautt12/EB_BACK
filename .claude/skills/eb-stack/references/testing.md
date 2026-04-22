# Referencia — Testing (pytest + Jasmine)

## Tabla de contenidos

1. pytest — plantilla básica
2. pytest — mockear Odoo
3. pytest — mockear MySQL
4. pytest — cliente Flask
5. Jasmine — plantilla de service
6. Jasmine — plantilla de component
7. Comandos de ejecución

## 1. pytest — plantilla básica

```python
# EB_BACK/tests/test_<dominio>.py
import pytest
from unittest.mock import MagicMock, patch


def test_algo_basico():
    resultado = 2 + 2
    assert resultado == 4
```

`pytest-mock` ya está en `requirements.txt`, así que puedes usar el fixture `mocker` en lugar de `@patch` cuando prefieras.

## 2. pytest — mockear Odoo

Nunca llames a Odoo real desde un test unitario. Mockea `get_odoo_models` para devolver un `models` falso con `execute_kw` como `MagicMock`.

```python
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def odoo_mock():
    """Devuelve (uid, models_mock) ya autenticados."""
    models = MagicMock()
    return 1, models


@patch('routes.<dominio>.get_odoo_models')
def test_listar_pedidos_filtra_por_empresa(mock_get, odoo_mock):
    mock_get.return_value = (odoo_mock[0], odoo_mock[1], None)
    # La siguiente llamada a execute_kw devolverá esta lista:
    odoo_mock[1].execute_kw.return_value = [
        {'id': 1, 'name': 'S00001', 'amount_total': 1500.0},
    ]

    from app import create_app
    app = create_app()
    client = app.test_client()

    # Simular login (token válido) — ajustar según tu helper
    resp = client.get('/pedidos', headers={'Authorization': 'Bearer test-token'})
    assert resp.status_code == 200

    # Verifica que el dominio incluyó company_id
    call_args = odoo_mock[1].execute_kw.call_args
    domain = call_args.args[4][0]  # [db, uid, pwd, model, method, [domain], opts]
    assert any(term[0] == 'company_id' for term in domain), \
        "La consulta debe filtrar por company_id"


@patch('routes.<dominio>.get_odoo_models')
def test_maneja_fallo_de_autenticacion(mock_get):
    mock_get.return_value = (None, None, 'connection refused')

    from app import create_app
    app = create_app()
    client = app.test_client()
    resp = client.get('/pedidos', headers={'Authorization': 'Bearer test-token'})

    assert resp.status_code == 503
    assert b'Odoo' in resp.data or b'disponible' in resp.data
```

## 3. pytest — mockear MySQL

```python
from unittest.mock import MagicMock, patch


@pytest.fixture
def db_mock():
    conexion = MagicMock()
    cursor = MagicMock()
    conexion.cursor.return_value = cursor
    return conexion, cursor


@patch('routes.<dominio>.obtener_conexion')
def test_listar_devuelve_registros(mock_conn, db_mock):
    conexion, cursor = db_mock
    mock_conn.return_value = conexion
    cursor.fetchall.return_value = [
        {'id': 1, 'nombre': 'Ana'},
        {'id': 2, 'nombre': 'Luis'},
    ]

    from app import create_app
    client = create_app().test_client()
    resp = client.get('/<dominio>', headers={'Authorization': 'Bearer test-token'})

    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body['datos']) == 2
    cursor.close.assert_called_once()
    conexion.close.assert_called_once()
```

## 4. pytest — cliente Flask

Para tests de integración liviana usa `app.test_client()`. Si necesitas bypassear el JWT, crea un fixture que monkeypatchee `verificar_token`:

```python
@pytest.fixture
def cliente_autenticado(monkeypatch):
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    monkeypatch.setattr(
        'utils.jwt_utils.verificar_token',
        lambda tok: {'usuario': 'test', 'rol': 'Admin'},
    )
    return app.test_client()
```

Uso:

```python
def test_algo(cliente_autenticado):
    resp = cliente_autenticado.get('/ruta', headers={'Authorization': 'Bearer x'})
    assert resp.status_code == 200
```

## 5. Jasmine — plantilla de service

```typescript
// src/app/services/<dominio>.service.spec.ts
import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { <Dominio>Service, <Dominio> } from './<dominio>.service';
import { environment } from '../../environments/environment';

describe('<Dominio>Service', () => {
  let service: <Dominio>Service;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [<Dominio>Service],
    });
    service = TestBed.inject(<Dominio>Service);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('debe crearse', () => {
    expect(service).toBeTruthy();
  });

  it('listar() hace GET a /<dominio> y cachea el resultado', () => {
    const fake: <Dominio>[] = [{ id: 1, nombre: 'Ana' }];

    service.listar().subscribe(data => {
      expect(data).toEqual(fake);
    });

    const req = httpMock.expectOne(`${environment.apiUrl}/<dominio>`);
    expect(req.request.method).toBe('GET');
    req.flush(fake);

    // Segunda llamada debe venir de caché (no hay request HTTP extra).
    service.listar().subscribe(data => expect(data).toEqual(fake));
    httpMock.expectNone(`${environment.apiUrl}/<dominio>`);
  });

  it('crear() invalida la caché', () => {
    const nuevo: <Dominio> = { id: 2, nombre: 'Luis' };
    service.crear({ nombre: 'Luis' }).subscribe();

    const req = httpMock.expectOne(`${environment.apiUrl}/<dominio>`);
    expect(req.request.method).toBe('POST');
    req.flush(nuevo);

    // Tras crear, listar() debe ir a la red de nuevo.
    service.listar().subscribe();
    httpMock.expectOne(`${environment.apiUrl}/<dominio>`);
  });
});
```

## 6. Jasmine — plantilla de component

```typescript
// src/app/views/<dominio>/<dominio>.component.spec.ts
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { of, throwError } from 'rxjs';

import { <Dominio>Component } from './<dominio>.component';
import { <Dominio>Service } from '../../services/<dominio>.service';

describe('<Dominio>Component', () => {
  let fixture: ComponentFixture<<Dominio>Component>;
  let component: <Dominio>Component;
  let svcSpy: jasmine.SpyObj<<Dominio>Service>;

  beforeEach(async () => {
    svcSpy = jasmine.createSpyObj('<Dominio>Service', ['listar']);

    await TestBed.configureTestingModule({
      imports: [<Dominio>Component, HttpClientTestingModule],
      providers: [{ provide: <Dominio>Service, useValue: svcSpy }],
    }).compileComponents();

    fixture = TestBed.createComponent(<Dominio>Component);
    component = fixture.componentInstance;
  });

  it('carga registros al iniciar', () => {
    svcSpy.listar.and.returnValue(of([{ id: 1, nombre: 'Ana' }]));
    fixture.detectChanges();
    expect(component.registros.length).toBe(1);
    expect(component.cargando).toBeFalse();
  });

  it('maneja errores de carga', () => {
    svcSpy.listar.and.returnValue(throwError(() => new Error('fallo red')));
    fixture.detectChanges();
    expect(component.error).toBe('fallo red');
    expect(component.cargando).toBeFalse();
  });
});
```

## 7. Comandos de ejecución

**Backend (desde `EB_BACK/`):**

```bash
# Todos los tests, salida compacta
pytest tests/ -q

# Un archivo
pytest tests/test_<dominio>.py -v

# Un test específico
pytest tests/test_<dominio>.py::test_maneja_fallo_de_autenticacion -v

# Con coverage
pytest tests/ --cov=routes --cov=utils --cov-report=term-missing
```

**Frontend (desde `EB_FRONT/`):**

```bash
# Una corrida (ideal para CI y para verificar antes de cerrar)
ng test --watch=false --browsers=ChromeHeadless

# Modo watch (desarrollo)
ng test

# Un archivo específico
ng test --include='**/<dominio>.service.spec.ts'
```
