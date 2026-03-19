# Authent — Guía de Integración

Documento de referencia para los servicios **Iris**, **Atlas** y **Hub**.  
Cubre autenticación con API Key, flujo JWT, todos los endpoints y ejemplos de uso.

---

## Índice

1. [Visión general](#1-visión-general)
2. [Base URL y entornos](#2-base-url-y-entornos)
3. [Autenticación de servicio — X-API-Key](#3-autenticación-de-servicio--x-api-key)
4. [Autenticación de usuario — JWT Bearer](#4-autenticación-de-usuario--jwt-bearer)
5. [Referencia de endpoints](#5-referencia-de-endpoints)
   - [Login](#51-login)
   - [Registro](#52-registro)
   - [Perfil](#53-perfil)
   - [Renovar token](#54-renovar-token)
   - [Verificar token](#55-verificar-token)
   - [Logout](#56-logout)
   - [Restablecimiento de contraseña](#57-restablecimiento-de-contraseña)
   - [Cambio de contraseña](#58-cambio-de-contraseña)
   - [Gestión de sesiones](#59-gestión-de-sesiones)
6. [Códigos de error](#6-códigos-de-error)
7. [Ejemplos rápidos](#7-ejemplos-rápidos)

---

## 1. Visión general

**Authent** es un microservicio centralizado de autenticación. Gestiona usuarios, sesiones y tokens JWT para todos los servicios integrados.

```
Cliente → X-API-Key (identifica el servicio) → Authent
Usuario → Bearer Token (identifica al usuario) → Recursos protegidos
```

Cada request a `/api/` requiere dos niveles de identificación:

| Nivel | Header | Quién lo envía |
|-------|--------|----------------|
| Servicio | `X-API-Key` | Siempre — el backend de Iris/Atlas/Hub |
| Usuario | `Authorization: Bearer <token>` | Solo en endpoints que requieren sesión activa |

---

## 2. Base URL y entornos

| Entorno | URL base |
|---------|----------|
| Desarrollo | `http://localhost:8004` |
| Producción | `https://<dominio-produccion>` |

Todos los endpoints tienen el prefijo `/api/auth/`.

---

## 3. Autenticación de servicio — X-API-Key

### API Keys por servicio

| Servicio | API Key |
|----------|---------|
| **Iris** | `ak_iris00000000000000000000000000000000000000000000` |
| **Atlas** | `ak_atlas0000000000000000000000000000000000000000000` |
| **Hub** | `ak_hub000000000000000000000000000000000000000000000` |

> ⚠️ Estas son las claves de **desarrollo**. Las claves de producción deben generarse desde el panel de administración y almacenarse como variables de entorno, nunca en el código fuente.

### Rutas exentas de X-API-Key

Las siguientes rutas **no requieren** el header `X-API-Key`:

```
/admin/
/api/schema/
/api/docs/
/api/redoc/
/health/
/ready/
/live/
```

### Errores de autenticación de servicio

| Situación | Código HTTP | Respuesta |
|-----------|------------|-----------|
| Header ausente | `401` | `{"error": "API key required.", "code": "missing_api_key"}` |
| Key inválida o inactiva | `401` | `{"error": "Invalid or inactive API key.", "code": "invalid_api_key"}` |

### Uso en cada request

```http
X-API-Key: ak_iris00000000000000000000000000000000000000000000
```

---

## 4. Autenticación de usuario — JWT Bearer

Authent emite tokens JWT firmados con HS256.

### Tiempos de vida

| Token | Duración |
|-------|----------|
| Access token | **1 hora** |
| Refresh token | **30 días** |

El refresh token rota en cada uso (`ROTATE_REFRESH_TOKENS = True`). El token anterior queda invalidado automáticamente.

### Payload del access token (claims)

```json
{
  "token_type": "access",
  "exp": 1742000000,
  "iat": 1741996400,
  "jti": "abc123...",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "usuario@ejemplo.com",
  "first_name": "Juan",
  "last_name": "García",
  "full_name": "Juan García",
  "is_staff": false,
  "email_verified": true
}
```

> El campo `user_id` es un **UUID v4** (no un entero secuencial).

### Uso en requests autenticados

```http
Authorization: Bearer <access_token>
X-API-Key: ak_iris00000000000000000000000000000000000000000000
```

---

## 5. Referencia de endpoints

---

### 5.1 Login

Autentica a un usuario y devuelve tokens JWT.

```
POST /api/auth/login/
```

**Headers requeridos:**

```http
Content-Type: application/json
X-API-Key: <api_key_del_servicio>
```

**Request body:**

```json
{
  "email": "usuario@ejemplo.com",
  "password": "contraseña123"
}
```

**Response `200 OK`:**

```json
{
  "access": "<access_token_jwt>",
  "refresh": "<refresh_token_jwt>",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "usuario@ejemplo.com",
    "first_name": "Juan",
    "last_name": "García",
    "full_name": "Juan García",
    "is_staff": false,
    "email_verified": true,
    "date_joined": "2025-01-15T10:30:00Z",
    "last_login": "2025-06-01T08:00:00Z",
    "avatar": null
  }
}
```

**Errores:**

| HTTP | Motivo |
|------|--------|
| `401` | Credenciales incorrectas |
| `400` | Campos faltantes o formato inválido |

---

### 5.2 Registro

Crea una cuenta nueva y devuelve los tokens JWT (mismo formato que login).

```
POST /api/auth/register/
```

**Headers requeridos:**

```http
Content-Type: application/json
X-API-Key: <api_key_del_servicio>
```

**Request body:**

```json
{
  "email": "nuevo@ejemplo.com",
  "password": "contraseña123",
  "first_name": "Ana",
  "last_name": "López"
}
```

> Contraseña mínima: **6 caracteres**.

**Response `201 Created`:**

```json
{
  "message": "User registered successfully",
  "access": "<access_token_jwt>",
  "refresh": "<refresh_token_jwt>",
  "user": {
    "id": "7c9e6679-7425-40de-a571-4ac60d1bed3f",
    "email": "nuevo@ejemplo.com",
    "first_name": "Ana",
    "last_name": "López",
    "full_name": "Ana López",
    "is_staff": false,
    "email_verified": false,
    "date_joined": "2025-06-01T12:00:00Z",
    "last_login": null,
    "avatar": null
  }
}
```

**Errores:**

| HTTP | Motivo |
|------|--------|
| `400` | Email ya registrado |
| `400` | Contraseña demasiado corta (< 6 caracteres) |
| `400` | Campos requeridos faltantes |

---

### 5.3 Perfil

Devuelve el perfil del usuario autenticado.

#### Obtener perfil

```
GET /api/auth/profile/
```

**Headers requeridos:**

```http
Authorization: Bearer <access_token>
X-API-Key: <api_key_del_servicio>
```

**Response `200 OK`:**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "usuario@ejemplo.com",
  "first_name": "Juan",
  "last_name": "García",
  "full_name": "Juan García",
  "is_staff": false,
  "email_verified": true,
  "date_joined": "2025-01-15T10:30:00Z",
  "last_login": "2025-06-01T08:00:00Z",
  "avatar": null
}
```

#### Actualizar perfil

```
PUT  /api/auth/update-profile/   ← reemplazo completo
PATCH /api/auth/update-profile/  ← actualización parcial (recomendado)
```

**Headers requeridos:**

```http
Content-Type: application/json
Authorization: Bearer <access_token>
X-API-Key: <api_key_del_servicio>
```

**Request body (PATCH — campos opcionales):**

```json
{
  "first_name": "Juan Carlos",
  "last_name": "García"
}
```

**Response `200 OK`:** perfil actualizado (mismo formato que GET).

---

### 5.4 Renovar token

Emite un nuevo access token a partir del refresh token.  
El refresh token anterior queda **invalidado** y se devuelve uno nuevo.

```
POST /api/auth/token/refresh/
```

**Headers requeridos:**

```http
Content-Type: application/json
X-API-Key: <api_key_del_servicio>
```

**Request body:**

```json
{
  "refresh": "<refresh_token_actual>"
}
```

**Response `200 OK`:**

```json
{
  "access": "<nuevo_access_token>",
  "refresh": "<nuevo_refresh_token>"
}
```

**Errores:**

| HTTP | Motivo |
|------|--------|
| `401` | Refresh token expirado, inválido o ya usado |

---

### 5.5 Verificar token

Comprueba si un access token es válido sin acceder a un recurso protegido.

```
GET /api/auth/verify-token/
```

**Headers requeridos:**

```http
Authorization: Bearer <access_token>
X-API-Key: <api_key_del_servicio>
```

**Response `200 OK`:**

```json
{
  "valid": true,
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "usuario@ejemplo.com",
  "exp": 1742000000
}
```

**Errores:**

| HTTP | Motivo |
|------|--------|
| `401` | Token expirado o inválido |

---

### 5.6 Logout

Invalida el refresh token (lo agrega a la blacklist).

```
POST /api/auth/logout/
```

**Headers requeridos:**

```http
Content-Type: application/json
Authorization: Bearer <access_token>
X-API-Key: <api_key_del_servicio>
```

**Request body:**

```json
{
  "refresh": "<refresh_token>"
}
```

**Response `200 OK`:**

```json
{
  "message": "Logout successful."
}
```

---

### 5.7 Restablecimiento de contraseña

Flujo de 3 pasos para recuperar acceso sin estar autenticado.

---

#### Paso 1 — Solicitar PIN

Envía un PIN numérico al email del usuario.

```
POST /api/auth/password-reset/request/
```

**Headers:**

```http
Content-Type: application/json
X-API-Key: <api_key_del_servicio>
```

**Request body:**

```json
{
  "email": "usuario@ejemplo.com"
}
```

**Response `200 OK`:**

```json
{
  "hash_token": "a1b2c3d4e5f6..."
}
```

> Guardar el `hash_token` en el cliente: se necesita en los pasos 2 y 3.

---

#### Paso 2 — Verificar PIN

Comprueba que el PIN recibido por email sea correcto.

```
POST /api/auth/password-reset/verify/
```

**Headers:**

```http
Content-Type: application/json
X-API-Key: <api_key_del_servicio>
```

**Request body:**

```json
{
  "email": "usuario@ejemplo.com",
  "hash_token": "a1b2c3d4e5f6...",
  "pin": "1234"
}
```

**Response `200 OK`:**

```json
{
  "valid": true
}
```

**Errores:**

| HTTP | Motivo |
|------|--------|
| `400` | PIN incorrecto o expirado |

---

#### Paso 3 — Establecer nueva contraseña

Cambia la contraseña. Solo funciona si el PIN fue verificado en el paso anterior.

```
POST /api/auth/password-reset/confirm/
```

**Headers:**

```http
Content-Type: application/json
X-API-Key: <api_key_del_servicio>
```

**Request body:**

```json
{
  "email": "usuario@ejemplo.com",
  "hash_token": "a1b2c3d4e5f6...",
  "pin": "1234",
  "new_password": "nuevaContraseña456",
  "new_password_confirm": "nuevaContraseña456"
}
```

**Response `200 OK`:**

```json
{
  "message": "Password reset successful."
}
```

---

### 5.8 Cambio de contraseña

Para usuarios autenticados que quieren cambiar su contraseña conociendo la actual.

```
POST /api/auth/password-change/
```

**Headers requeridos:**

```http
Content-Type: application/json
Authorization: Bearer <access_token>
X-API-Key: <api_key_del_servicio>
```

**Request body:**

```json
{
  "old_password": "contraseñaActual",
  "new_password": "nuevaContraseña789",
  "new_password_confirm": "nuevaContraseña789"
}
```

**Response `200 OK`:**

```json
{
  "message": "Password changed successfully."
}
```

**Errores:**

| HTTP | Motivo |
|------|--------|
| `400` | Contraseña actual incorrecta |
| `400` | Las contraseñas nuevas no coinciden |
| `400` | Nueva contraseña demasiado corta |

---

### 5.9 Gestión de sesiones

Permite rastrear y revocar sesiones por dispositivo.

#### Listar sesiones activas

```
GET /api/auth/sessions/
```

**Headers requeridos:**

```http
Authorization: Bearer <access_token>
X-API-Key: <api_key_del_servicio>
```

**Response `200 OK`:**

```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "device_name": "Chrome / macOS",
    "ip_address": "192.168.1.1",
    "created_at": "2025-06-01T08:00:00Z",
    "last_activity": "2025-06-01T10:00:00Z",
    "is_current": true
  }
]
```

#### Registrar sesión de dispositivo

```
POST /api/auth/sessions/
```

**Request body:**

```json
{
  "device_name": "Chrome / macOS",
  "ip_address": "192.168.1.1"
}
```

#### Revocar una sesión específica

```
DELETE /api/auth/sessions/{id}/revoke/
```

#### Revocar todas las sesiones (excepto la actual)

```
DELETE /api/auth/sessions/revoke_all/
```

---

## 6. Códigos de error

### Errores de autenticación de servicio (middleware)

| Código HTTP | `code` | Descripción |
|-------------|--------|-------------|
| `401` | `missing_api_key` | Header `X-API-Key` no presente |
| `401` | `invalid_api_key` | API Key desconocida o desactivada |

### Errores de autenticación de usuario (JWT)

| Código HTTP | Descripción |
|-------------|-------------|
| `401` | Access token expirado o inválido |
| `401` | Refresh token expirado, ya usado o en blacklist |
| `403` | Sin permisos para el recurso solicitado |

### Errores de validación

| Código HTTP | Descripción |
|-------------|-------------|
| `400` | Datos de entrada inválidos (detalle en el body) |
| `404` | Recurso no encontrado |

### Formato de error estándar DRF

```json
{
  "detail": "Given token not valid for any token type",
  "code": "token_not_valid",
  "messages": [
    {
      "token_class": "AccessToken",
      "token_type": "access",
      "message": "Token is invalid or expired"
    }
  ]
}
```

---

## 7. Ejemplos rápidos

### Login completo con curl

```bash
# Iris realizando login de un usuario
curl -X POST http://localhost:8004/api/auth/login/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ak_iris00000000000000000000000000000000000000000000" \
  -d '{"email": "usuario@ejemplo.com", "password": "contraseña123"}'
```

### Obtener perfil con curl

```bash
curl http://localhost:8004/api/auth/profile/ \
  -H "Authorization: Bearer <access_token>" \
  -H "X-API-Key: ak_iris00000000000000000000000000000000000000000000"
```

### Renovar token con curl

```bash
curl -X POST http://localhost:8004/api/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ak_atlas0000000000000000000000000000000000000000000" \
  -d '{"refresh": "<refresh_token>"}'
```

### Cliente JavaScript (fetch)

```javascript
const BASE_URL = 'http://localhost:8004';
const API_KEY = 'ak_iris00000000000000000000000000000000000000000000';

// Login
async function login(email, password) {
  const response = await fetch(`${BASE_URL}/api/auth/login/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
    },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) throw new Error('Login failed');
  return response.json(); // { access, refresh, user }
}

// Request autenticado
async function getProfile(accessToken) {
  const response = await fetch(`${BASE_URL}/api/auth/profile/`, {
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'X-API-Key': API_KEY,
    },
  });

  if (!response.ok) throw new Error('Unauthorized');
  return response.json();
}

// Renovar access token
async function refreshToken(refreshToken) {
  const response = await fetch(`${BASE_URL}/api/auth/token/refresh/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
    },
    body: JSON.stringify({ refresh: refreshToken }),
  });

  if (!response.ok) throw new Error('Refresh failed — redirect to login');
  return response.json(); // { access, refresh }
}
```

### Flujo recomendado de manejo de tokens

```
1. Login → guardar access + refresh en memoria/storage seguro
2. Cada request → enviar access token en Authorization header
3. Si response 401 → intentar renovar con refresh token
4. Si renovación falla → redirigir a login
5. Logout → llamar /api/auth/logout/ para invalidar refresh token
```

---

## Recursos adicionales

| Recurso | URL |
|---------|-----|
| Swagger UI (desarrollo) | `http://localhost:8004/api/docs/` |
| ReDoc (desarrollo) | `http://localhost:8004/api/redoc/` |
| OpenAPI schema JSON | `http://localhost:8004/api/schema/` |
| Panel de administración | `http://localhost:8004/admin/` |
