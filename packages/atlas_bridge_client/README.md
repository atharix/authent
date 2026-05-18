# atlas-bridge-client

Cliente HTTP en Python para el inbound API de Atlas (`/api/bridge/inbound/*`).

Sin acoplamiento a Django: usable desde cualquier servicio Python (Authent, ERP Olimpus, scripts, etc.).

## Instalación

```bash
pip install -e ./packages/atlas_bridge_client
```

## Uso

```python
from atlas_bridge_client import AtlasBridgeClient, LeadIn, AccountIn

client = AtlasBridgeClient(
    api_key="atlas_...",
    base_url="https://atlas.atharix.com",
    timeout=10.0,
    max_retries=3,
)

# 1) Crear lead (idempotente por email/phone)
result = client.create_lead(LeadIn(
    first_name="Ana",
    email="ana@example.com",
    source_detail="authent.signup",
    tags=["authent"],
))
# → LeadResult(lead_id=UUID, created=True|False)

# 2) Convertir lead → account
result = client.convert_lead_to_account(
    email="ana@example.com",
    account=AccountIn(
        name="Ana SAS",
        tax_id="900123456",
        industry="Tech",
        customer_entity_type="company",
    ),
    create_if_missing=True,
)
# → ConvertResult(account_id=UUID, lead_id=UUID, created=True|False)
```

## Excepciones

Todas heredan de `AtlasBridgeError`:

- `AuthError` — 401 (API key inválida o expirada)
- `PermissionError` — 403 (la API key no tiene el scope requerido)
- `NotFoundError` — 404
- `ValidationError` — 400/422 (payload mal formado)
- `ServerError` — 5xx (reintentado automáticamente)
- `NetworkError` — fallo de red/timeout (reintentado automáticamente)

## Retries

Por defecto: 3 intentos con backoff exponencial (1s, 2s, 4s) **solo** para `ServerError` y `NetworkError`. Errores 4xx no se reintentan.

## Tests

```bash
pip install -e ".[test]"
pytest
```
