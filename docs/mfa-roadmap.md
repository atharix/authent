# Segundo factor por correo (MFA) — estado y trabajo pendiente

> Septiembre 2026. El login de Authent puede partirse en dos pasos. Está
> **implementado y activable por producto**; hoy ningún producto lo tiene
> encendido hasta que su frontal sepa manejar la respuesta de dos pasos.

---

## Qué cambió

`POST /api/auth/login/` deja de devolver siempre `{access, refresh, user}`.
Cuando la `Application` que llama (identificada por su `X-API-Key`) tiene
`enforce_mfa = True` y la contraseña es correcta, responde **200 sin tokens**:

```json
{
  "mfa_required": true,
  "mfa_method": "email",
  "mfa_token": "<firmado, TTL 10 min>",
  "email_hint": "l******a@projects.ec",
  "code_length": 6,
  "expires_in": 600,
  "resend_in": 60,
  "delivered": true
}
```

Los tokens salen del **paso 2**:

| Endpoint | Entrada | Salida |
|---|---|---|
| `POST /api/auth/mfa/verify/` | `mfa_token`, `code`, `remember_device?`, `device_name?` | `{access, refresh, user, device_token?, device_trusted_days?}` |
| `POST /api/auth/mfa/resend/` | `mfa_token` | `{sent, expires_in, resend_in}` · 429 dentro del cooldown |

Errores del paso 2:

- `400 mfa_invalid_code` con `attempts_left` — código incorrecto, el desafío sigue vivo.
- `401 mfa_restart` — caducado, agotado (5 intentos) o token manipulado. Volver al paso 1.
- `503 mfa_email_failed` — no se pudo entregar el correo; el registro se anula para que el reintento emita uno nuevo.

**Equipos de confianza**: con `remember_device`, el paso 2 devuelve un
`device_token` opaco (30 días). El cliente lo guarda y lo manda en el login;
mientras siga vivo, ese equipo no ve el código. Se listan y revocan en
`GET/DELETE /api/auth/trusted-devices/`, y **cualquier cambio de contraseña los
revoca todos**.

---

## Compatibilidad — por qué nadie se ha roto

`Application.enforce_mfa` es `False` por defecto. Con el flag apagado el login
recorre exactamente el mismo código de siempre y devuelve el mismo cuerpo byte a
byte. Ningún producto nota el cambio hasta que se le enciende el flag.

El orden es **siempre**: publicar la librería → desplegar Authent → desplegar el
frontal del producto → encender el flag de ese producto. Nunca al revés: con el
flag encendido y un frontal antiguo, el login devuelve un cuerpo sin `access` y
el cliente rompe.

---

## La librería compartida se publica aparte

El proxy no vive en ningún backend: es `atharix_auth`
(`git@github.com:atharix/atharix_auth.git`), montado como submódulo en
`vendor/atharix_authent` de **cuatro** backends — `atlas_backend`,
`delta_backend`, `metis/backend` y `prometheus/backend` — e instalado dentro de
la imagen con `pip install -e`, **no montado en runtime**.

Versión de este cambio: **0.2.0**. Secuencia:

1. Commit y push en `atharix_auth` (login con `device_token`, `mfa/verify/`, `mfa/resend/`, equipos de confianza, hooks post-login movidos a la verificación).
2. En cada backend que deba recogerlo: `git submodule update --remote vendor/atharix_authent` y commit del puntero.
3. Reconstruir la imagen de ese backend. Sin rebuild, el contenedor sigue con el proxy viejo.

Subir a 0.2.0 es **seguro para quien no active MFA**: el `device_token` es
opcional, la rama del desafío nunca se dispara con `enforce_mfa=False`, y las
rutas nuevas quedan enrutadas sin que nadie las llame. Hoy Delta apunta a un
commit anterior (`c3ee058`) y Metis no tiene el submódulo inicializado en local:
conviene alinearlos en el mismo pase para que no diverjan más.

---

## Pendiente por producto

### Atlas — hecho, falta desplegarlo

- [x] Librería compartida: `mfa/verify/`, `mfa/resend/`, `device_token` en el login, hooks post-login movidos a la verificación.
- [x] Frontend web y nativo: login en dos pasos, reenvío con cooldown del servidor, "recordar este equipo".
- [ ] Publicar `atharix_auth` 0.2.0 y bumpear el submódulo en `atlas_backend`.
- [ ] **Reconstruir la imagen de `atlas_web`** (el paquete va dentro de la imagen).
- [ ] Encender `enforce_mfa` en la Application `atlas` (admin de Authent) **después** de desplegar web.
- [ ] Pantalla de Seguridad: listar y revocar equipos de confianza (el backend ya lo expone).

### Delta, Metis y Prometheus — pendiente

Los tres comparten la misma lista:

- [ ] Bumpear el submódulo a 0.2.0 (seguro sin activar nada; los deja al día).
- [ ] Implementar en su frontal la respuesta `mfa_required` y la pantalla del código.
- [ ] Pasar `device_token` en el login y guardar el que devuelva la verificación.
- [ ] Verificar que su capa propia no aplaste el cuerpo ni fuerce `200` descartando campos (era el defecto del proxy compartido, ya corregido ahí, pero Atlas tenía además una `LoginView` local en `app/atharix_auth/views.py` con el mismo patrón).
- [ ] Encender `enforce_mfa` en su Application, y solo entonces.

---

## Decisiones tomadas

1. **Obligatorio para todos los usuarios**, no solo administradores.
2. **Segundo factor, no vía alternativa**: el código solo se pide después de una contraseña válida. Nunca sirve para entrar sin ella — si sirviera, "acceso al buzón" pasaría a ser "acceso a la cuenta" para toda la base.
3. **Activación por producto** vía `Application.enforce_mfa`, no global.

## Decisiones abiertas

- **Passkey obligatoria**: con MFA real, el gate de passkeys del cliente pierde su razón de ser como muro. Convertirlo en recomendación (banner) es una decisión de producto pendiente.
- **Auto-login tras registro o reseteo de contraseña**: hoy, con MFA activo, esos flujos mandan al login en vez de encadenar un segundo código. Se podría emitir una prueba de posesión del correo de vida corta que se canjee sin código.
- **TOTP y aprobación push** como factores adicionales al correo.
- **`X-Forwarded-For`**: el proxy no lo reenvía, así que `UserSession` guarda la IP del contenedor y el user-agent de httpx. Cualquier heurística de riesgo por IP/UA necesita arreglar eso primero (y que Caddy reescriba la cabecera, no que la acepte del cliente).

---

## Deuda que este trabajo deja a la vista

- `PasswordReset` guarda el PIN **en claro**, de 4 dígitos, sin contador de intentos y sin throttle, mientras el correo promete "máximo 5 intentos". El OTP nuevo (`EmailOtp`) sí está hasheado y con contador: el reseteo de contraseña debería migrar al mismo patrón.
- `app/users/serializers.py` y `app/users/views.py` son módulos legacy sombreados por los paquetes homónimos. Confunden al grepear.
- `TestPasswordReset` está obsoleto (usa campos que no existen). La cobertura real del OTP está en `users/tests_mfa.py`.
