# Authent — Funcionalidades requeridas para el Frontend

> Documento de referencia para equipos de frontend que integren con el servicio de autenticación **Authent**.  
> Base URL: `http://localhost:8020/api`  
> Swagger interactivo: `http://localhost:8020/api/docs/`

---

## Tabla de contenidos

1. [Autenticación](#1-autenticación)
2. [Registro de usuario](#2-registro-de-usuario)
3. [Gestión de perfil](#3-gestión-de-perfil)
4. [Recuperación de contraseña](#4-recuperación-de-contraseña)
5. [Cambio de contraseña](#5-cambio-de-contraseña)
6. [Gestión de sesiones / dispositivos](#6-gestión-de-sesiones--dispositivos)
7. [Términos y condiciones](#7-términos-y-condiciones)
8. [Notificaciones](#8-notificaciones)
9. [Países y ubicaciones](#9-países-y-ubicaciones)
10. [Consideraciones generales](#10-consideraciones-generales)

---

## 1. Autenticación

### 1.1 Login

**Endpoint:** `POST /auth/login/`

El usuario se autentifica con email y contraseña. El backend devuelve un par de tokens JWT.

**Campos del formulario:**
- `email` — texto, requerido
- `password` — contraseña, requerido

**Respuesta exitosa:**
```json
{
  "access": "<jwt_access_token>",
  "refresh": "<jwt_refresh_token>",
  "user": { "id", "email", "first_name", "last_name", "profile_type", ... }
}
```

**Comportamiento esperado en el frontend:**
- Almacenar `access` y `refresh` de forma segura (httpOnly cookie o memoria — evitar `localStorage` para el access token).
- Decodificar el access token para leer claims básicos (`full_name`, `is_staff`, `email_verified`).
- Redirigir al dashboard tras login exitoso.
- Mostrar mensaje de error genérico en credenciales incorrectas (no revelar si el email existe).

---

### 1.2 Logout

**Endpoint:** `POST /auth/logout/`  
**Requiere:** `Authorization: Bearer <access_token>`

Invalida la sesión actual en el servidor.

**Comportamiento esperado:**
- Limpiar tokens del almacenamiento local.
- Redirigir a la pantalla de login.
- Cancelar cualquier petición en vuelo antes de limpiar tokens.

---

### 1.3 Renovar token (Token Refresh)

**Endpoint:** `POST /auth/token/refresh/`

Emite un nuevo par access + refresh a partir del refresh token actual.

**Comportamiento esperado:**
- Implementar un interceptor HTTP global que detecte respuestas `401 Unauthorized`.
- Intentar renovar el token automáticamente una sola vez.
- Si la renovación falla, forzar logout y redirigir al login.
- Controlar concurrencia: si múltiples peticiones fallan a la vez, ejecutar el refresh una sola vez y reintentar todas las peticiones en cola.

> **Duración de tokens:** Access = 1 día | Refresh = 30 días (rotación en cada uso).

---

### 1.4 Verificar token

**Endpoint:** `GET /auth/verify-token/`  
**Requiere:** `Authorization: Bearer <access_token>`

Útil para validar si el token sigue siendo válido al recargar la app.

---

## 2. Registro de usuario

**Endpoint:** `POST /auth/register/`

**Campos del formulario:**
| Campo | Tipo | Requerido | Notas |
|---|---|---|---|
| `email` | email | ✅ | Único en el sistema |
| `first_name` | texto | ✅ | |
| `last_name` | texto | ✅ | |
| `password` | contraseña | ✅ | Mínimo 8 caracteres, validar fortaleza |
| `password_confirm` | contraseña | ✅ | Confirmar en el cliente |
| `phone_number` | tel | ❌ | Formato `+52XXXXXXXXXX` |
| `birth_date` | date | ❌ | |
| `gender` | select | ❌ | `M`, `F`, `O`, `P` |

**Comportamiento esperado:**
- Validar que las contraseñas coincidan antes de enviar.
- Mostrar indicador de fortaleza de contraseña.
- Tras registro exitoso, redirigir al login (o hacer login automático si la API lo permite).
- Mostrar errores de campo (email ya registrado, contraseña débil, etc.).

---

## 3. Gestión de perfil

### 3.1 Ver perfil

**Endpoint:** `GET /auth/profile/`  
**Requiere:** autenticación

Devuelve todos los datos del usuario autenticado.

**Datos a mostrar:**
- Avatar (`avatar` — URL firmada, expira en 30 min; recargar si se muestra mucho tiempo)
- Nombre completo
- Email (con badge si `email_verified = false`)
- Número de teléfono
- Fecha de nacimiento
- Género
- Tipo de perfil (`developer`, `client`, `admin`)
- Fecha de registro (`date_joined`)

### 3.2 Editar perfil

**Endpoint:** `PATCH /auth/update-profile/`  
**Requiere:** autenticación

**Campos editables:**
- `first_name`, `last_name`
- `phone_number`
- `birth_date`
- `gender`
- `avatar` — upload de imagen (multipart/form-data)

**Comportamiento esperado:**
- Preview local del avatar antes de subir.
- Validar tamaño y tipo del archivo de imagen en el cliente.
- Indicador de carga durante el upload.
- Las URLs de avatar son signed URLs con expiración — no cachear indefinidamente.

---

## 4. Recuperación de contraseña

Flujo en **3 pasos** obligatorios, sin posibilidad de saltarse ninguno.

### Paso 1 — Solicitar PIN

**Endpoint:** `POST /auth/password-reset/request/`

**Campos:** `email`

**Respuesta:**
```json
{
  "message": "Reset PIN sent to your email",
  "hash_token": "<token_seguro>"
}
```

> Guardar `hash_token` en estado local (necesario para los pasos 2 y 3).

### Paso 2 — Verificar PIN

**Endpoint:** `POST /auth/password-reset/verify/`

**Campos:**
- `email`
- `pin` — 4 dígitos numéricos recibidos por email
- `hash_token` — obtenido en el paso 1

> El PIN expira en **15 minutos**. Mostrar un contador regresivo opcional.

### Paso 3 — Nueva contraseña

**Endpoint:** `POST /auth/password-reset/confirm/`

**Campos:**
- `email`
- `pin`
- `hash_token`
- `new_password`
- `new_password_confirm`

**Comportamiento esperado:**
- Limpiar el `hash_token` del estado tras el éxito.
- Redirigir al login con mensaje de confirmación.
- Manejar el error de PIN expirado mostrando opción de reenviar.

---

## 5. Cambio de contraseña

**Endpoint:** `POST /auth/password-change/`  
**Requiere:** autenticación (usuario ya logueado)

**Campos:**
- `current_password`
- `new_password`
- `new_password_confirm`

**Comportamiento esperado:**
- Disponible solo dentro de la configuración de cuenta del usuario autenticado.
- No mezclar con el flujo de recuperación.

---

## 6. Gestión de sesiones / dispositivos

### 6.1 Listar sesiones activas

**Endpoint:** `GET /auth/sessions/`  
**Requiere:** autenticación

Muestra todos los dispositivos donde el usuario tiene sesión activa.

**Datos a mostrar por sesión:**
| Campo | Descripción |
|---|---|
| `device_name` | Nombre del dispositivo |
| `device_type` | `mobile`, `tablet`, `desktop`, `other` |
| `os_name` / `os_version` | Sistema operativo |
| `browser` / `browser_version` | Navegador |
| `ip_address` | IP de origen |
| `country` / `city` | Ubicación aproximada |
| `last_activity` | Última actividad |
| `is_current_device` | Marcar visualmente como "Este dispositivo" |

### 6.2 Revocar sesión específica

**Endpoint:** `DELETE /auth/sessions/{id}/revoke/`  
**Requiere:** autenticación

> No se puede revocar la sesión actual desde esta pantalla (usar logout).

### 6.3 Revocar todas las sesiones

**Endpoint:** `DELETE /auth/sessions/revoke_all/`  
**Requiere:** autenticación

Cierra todas las sesiones excepto la actual.

**Comportamiento esperado:**
- Pedir confirmación antes de ejecutar.
- Mostrar el número de sesiones que se cerrarán.

### 6.4 Crear sesión (registro de dispositivo)

**Endpoint:** `POST /auth/sessions/`  
**Requiere:** autenticación

Registrar información del dispositivo actual tras el login. Enviar automáticamente:
- `jti` — del JWT actual
- `refresh_token_hash` — hash del refresh token
- `device_name`, `device_type`, `os_name`, `os_version`, `browser`, `browser_version`, `user_agent`
- `ip_address`

---

## 7. Términos y condiciones

### 7.1 Ver términos vigentes

**Endpoint:** `GET /auth/terms/`  
**Público**

Mostrar el contenido de los términos activos antes del registro o al solicitarlos.

### 7.2 Verificar si el usuario debe aceptar

**Endpoint:** `GET /auth/terms/check/`  
**Requiere:** autenticación

**Respuesta:**
```json
{
  "needs_acceptance": true,
  "latest_version": "1.2",
  "terms_content": "..."
}
```

**Comportamiento esperado:**
- Llamar a este endpoint tras cada login.
- Si `needs_acceptance = true`, mostrar modal obligatorio con el contenido de los términos antes de continuar.
- No permitir continuar hasta que el usuario los acepte.

### 7.3 Aceptar términos

**Endpoint:** `POST /auth/terms/accept/`  
**Requiere:** autenticación

**Body:** `{ "version": "1.2" }`

---

## 8. Notificaciones

**Endpoint base:** `GET /core/notifications/`  
**Requiere:** autenticación

### 8.1 Listar notificaciones

Mostrar listado paginado con filtros:
- `?is_read=false` — solo no leídas
- `?ordering=-created_at` — más recientes primero

**Datos a mostrar por notificación:**
| Campo | Descripción |
|---|---|
| `title` | Título |
| `message` | Cuerpo del mensaje |
| `notification_type` | `info`, `success`, `warning`, `error`, `reminder`, `message` |
| `is_read` | Estado de lectura |
| `created_at` | Fecha |
| `url` | Enlace opcional al hacer clic |

### 8.2 Marcar como leída

**Endpoint:** `PATCH /core/notifications/{id}/`  
`{ "is_read": true }`

### 8.3 Indicador de notificaciones no leídas

- Mostrar badge con conteo de `is_read = false` en la barra de navegación.
- Actualizar periódicamente o via polling ligero.

---

## 9. Países y ubicaciones

### 9.1 Países

**Endpoint:** `GET /core/countries/`  
**Público**

Listado de países. Útil para selectores en formularios (dirección, perfil, etc.).

### 9.2 Ubicaciones

**Endpoint:** `GET /core/locations/`  
**Requiere:** autenticación

Listado de ubicaciones geográficas registradas en el sistema (puntos de interés, sedes, etc.).

---

## 10. Consideraciones generales

### Cabeceras requeridas

Todas las peticiones a `/api/` deben incluir:

```
X-API-Key: <api_key_de_la_aplicacion>
Authorization: Bearer <access_token>   ← solo en endpoints protegidos
Content-Type: application/json
```

> La `X-API-Key` identifica a la aplicación cliente en el sistema. Debe mantenerse en variables de entorno y nunca exponerse en el código fuente del frontend.

### Manejo de errores

| Código | Significado | Acción en el frontend |
|---|---|---|
| `400` | Datos inválidos | Mostrar errores de campo del body |
| `401` | Token inválido o expirado | Intentar refresh; si falla, logout |
| `403` | Sin permisos | Mostrar página de acceso denegado |
| `404` | Recurso no encontrado | Mostrar estado vacío |
| `429` | Rate limit excedido | Mostrar mensaje de espera con reintentos |
| `500` | Error del servidor | Mostrar mensaje genérico, reportar a Sentry |

### Paginación

```json
{
  "count": 100,
  "next": "http://...?page=2",
  "previous": null,
  "results": [...]
}
```

Implementar carga de páginas adicionales o scroll infinito usando `next`.

### Tipos de perfil

| `profile_type` | Acceso esperado |
|---|---|
| `client` | Usuario final del ecosistema |
| `developer` | Acceso a documentación técnica y herramientas |
| `admin` | Panel administrativo completo |

### Verificación de email

El campo `email_verified` en el perfil indica si el usuario completó la verificación.  
Mostrar un banner o alerta contextual si es `false`, invitando a verificar.

### Idioma

Enviar `Accept-Language: es` (o el idioma del usuario) en todas las peticiones para recibir mensajes de error localizados.

### Seguridad

- Nunca almacenar `access_token` en `localStorage` (XSS). Preferir httpOnly cookies o memoria en el estado de la aplicación.
- Regenerar el par de tokens tras cambio de contraseña.
- Limpiar todo el estado de autenticación al logout.
- No mostrar detalles internos de error al usuario final.
