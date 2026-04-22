# Referencia — Seguridad

Este archivo reúne reglas que a veces se relajan en el calor del momento. Respétalas siempre.

## Tabla de contenidos

1. Secretos y `.env`
2. JWT
3. CORS
4. Multi-empresa (Odoo)
5. Inyección y validación
6. Logs y PII
7. Checklist antes de commit

## 1. Secretos y `.env`

- Nunca escribas valores de secretos en el código. Léelos con `os.getenv('NOMBRE', default)` y documenta el default solo cuando sea seguro (URLs públicas, IDs fijos).
- `.env` NO se commitea. Confirma que está en `.gitignore`.
- Si un secreto se filtró a git (historial, logs, commits viejos), rótalo inmediatamente — cambiar el archivo local no es suficiente. Avisa al equipo.
- Nunca imprimas el contenido de `.env` en un endpoint, no lo mandes por email, no lo pongas en un mensaje de error. Los passwords de Odoo y MySQL están ahí.

## 2. JWT

- Firma con `JWT_SECRET` de `.env`. Nunca lo hardcodees.
- Duración razonable: 8-24 horas según el rol. Tokens más largos aumentan el riesgo si se filtran.
- En el backend, valida con `utils.jwt_utils.verificar_token(token)`. La función devuelve el payload si es válido, `None` si no.
- Agrega el patrón `_auth_usuario()` en blueprints (ver `references/backend.md`) para no duplicar la lectura del header.
- En el frontend, guarda el token en `localStorage` (o mejor: `sessionStorage` si se prefiere que expire al cerrar navegador). Nunca lo pongas en una cookie sin `HttpOnly` + `Secure` + `SameSite=Strict`.
- No loggees el token completo. Si quieres rastrear, loggea solo los últimos 6 caracteres o el `jti` del payload.

## 3. CORS

`app.py` tiene la lista blanca `allowed_origins`. Reglas:

- Agregar un dominio a la lista, nunca usar `*`.
- `supports_credentials=True` requiere origen explícito (por eso no se puede combinar con `*`).
- Solo exponer los headers estrictamente necesarios (`Content-Disposition`, `Content-Type`).
- Para desarrollo, el bloque "handler que refleja localhost/127.0.0.1" ya permite cualquier puerto; no toques eso a menos que sea necesario.

## 4. Multi-empresa (Odoo)

El grupo Elite Bike tiene la instancia Odoo compartida con otras empresas. Sin filtrar por `company_id`, tus reportes mezclan datos y nadie lo nota hasta que los números salen mal.

```python
from utils.odoo_utils import ODOO_COMPANY_ID
# ODOO_COMPANY_ID = 1  (Elite Bike)

domain = [
    ('company_id', '=', ODOO_COMPANY_ID),  # SIEMPRE primero
    # ... resto de condiciones
]
```

Modelos afectados (lista no exhaustiva): `account.move`, `account.payment`, `account.move.line`, `account.journal`, `sale.order`, `purchase.order`, `stock.picking`, `stock.move`, `product.product`, `product.template`, `crm.lead`, `hr.employee`, `project.project`.

`res.partner` SÍ tiene `company_id` pero normalmente es `False` (compartidos entre empresas) — filtrar ahí excluye contactos válidos. Revisa caso por caso.

## 5. Inyección y validación

**SQL:**
- Siempre usa placeholders `%s` con tupla de parámetros. Nunca concatenes:
  ```python
  # MAL
  cursor.execute(f"SELECT * FROM usuarios WHERE id = {user_id}")
  # BIEN
  cursor.execute("SELECT * FROM usuarios WHERE id = %s", (user_id,))
  ```
- Si necesitas un `IN (...)` dinámico: construye placeholders `','.join(['%s'] * len(ids))`.

**Odoo:**
- Los domains no son SQL pero sí ejecutan en Odoo. Nunca metas strings sin validar en operadores: valida el operador contra una lista blanca (`'=', '!=', 'in', 'ilike', ...`).

**Payload JSON:**
- Valida que cada campo obligatorio exista y tenga el tipo esperado. No confíes en que el frontend mande lo correcto.
- Sanitiza strings antes de guardarlos (strip, longitud máxima). Para correos, valida con regex. Para roles, lista blanca.

**Subida de archivos:**
- `werkzeug.utils.secure_filename` para nombres. Valida extensión contra una lista blanca. Almacena en `temp_uploads/` con nombre único (UUID). Nunca ejecutes archivos subidos.

## 6. Logs y PII

Información que NO debe aparecer en logs:
- Passwords (hasheados o en plano).
- Tokens JWT completos.
- Números de tarjeta, CVV, NIP.
- Contenido del `.env`.
- Detalles internos de excepciones que expongas al cliente.

Información OK en logs:
- ID numérico del usuario.
- Usuario (login), correo (con discreción — si la base es grande, considera correlation IDs).
- Operación realizada (login, crear pedido, actualizar cliente).
- Timestamp, nivel, módulo.

## 7. Checklist antes de commit

- [ ] `.env` no está en el diff
- [ ] No hay credenciales en strings literales
- [ ] No hay URLs de Odoo/test/prod hardcodeadas (vienen de `utils/odoo_utils.py` o `.env`)
- [ ] Todo endpoint no-público valida JWT
- [ ] Consultas Odoo afectadas filtran por `ODOO_COMPANY_ID`
- [ ] Consultas SQL usan placeholders
- [ ] No hay `print` que expongan datos sensibles
- [ ] Mensajes de error al cliente no filtran información interna (paths, stack traces, SQL)
- [ ] Si agregaste un origen a CORS, es legítimo
- [ ] Si agregaste una dependencia, revisaste que sea mantenida y sin CVEs activos
