# Deploy Automático con GitHub Actions

Este proyecto puede desplegarse automáticamente en Hetzner haciendo `push` a `main`.

## Cómo funciona

El workflow [deploy.yml](../.github/workflows/deploy.yml) se ejecuta en GitHub Actions y abre una sesión SSH contra tu servidor de Hetzner. Una vez dentro:

1. Entra en el directorio del proyecto.
2. Ejecuta `./deploy.sh`.
3. El script hace `git pull`, reconstruye contenedores y valida `/health/`.

## Requisitos en el servidor

Antes de activar el workflow, el servidor debe tener:

1. Docker y Docker Compose instalados.
2. El repositorio ya clonado en la ruta final.
3. El archivo `.env` de producción creado.
4. La clave SSH del servidor con acceso de lectura al repositorio si `deploy.sh` va a hacer `git pull`.
5. Permisos para ejecutar `docker compose` con el usuario usado por GitHub Actions.

## Secrets necesarios en GitHub

Añade estos secrets en GitHub: `Settings > Secrets and variables > Actions`.

| Secret | Ejemplo | Descripción |
|---|---|---|
| `HETZNER_HOST` | `123.123.123.123` | IP o dominio del servidor |
| `HETZNER_PORT` | `22` | Puerto SSH |
| `HETZNER_USER` | `root` o `deploy` | Usuario SSH |
| `HETZNER_SSH_PRIVATE_KEY` | `-----BEGIN OPENSSH PRIVATE KEY-----...` | Clave privada usada por GitHub Actions |
| `HETZNER_PROJECT_PATH` | `/opt/authent/backend` | Ruta donde vive el repo backend en el servidor |
| `DEPLOY_HEALTH_URL` | `http://localhost:8004/health/` | URL interna para validar despliegue |
| `DEPLOY_SITE_URL` | `https://authent.tudominio.com` | URL pública mostrada al final del deploy |

## Recomendación de claves SSH

Usa dos claves separadas:

1. Una clave de despliegue del servidor a GitHub para que `git pull` funcione en Hetzner.
2. Otra clave privada guardada en `HETZNER_SSH_PRIVATE_KEY` para que GitHub Actions pueda entrar al servidor.

## Preparación mínima del servidor

Ejemplo orientativo:

```bash
mkdir -p /opt/authent/backend /opt/authent/frontend
cd /opt/authent/backend
git clone git@github.com:TU_USUARIO/TU_REPO.git .
cp .env.example .env
printf '\nFRONTEND_DIR=../frontend\n' >> .env
chmod +x deploy.sh
```

Después completa `.env` con tus valores reales de producción.

El frontend debe desplegarse por separado dentro de `/opt/authent/frontend`.

## Activación

Cuando subas cambios a `main`, GitHub Actions ejecutará el despliegue automáticamente.

También puedes lanzarlo manualmente desde la pestaña `Actions` con `workflow_dispatch`.

## Notas

1. Si usas un usuario no root, ese usuario debe tener acceso al socket de Docker.
2. Si prefieres no hacer `git pull` en el servidor, se puede adaptar el workflow para copiar el código o desplegar imágenes desde un registry.
3. El despliegue actual usa `deploy.sh`; por tanto cualquier cambio futuro en el proceso debe centralizarse ahí.
4. Para HTTPS gratuito, el dominio debe apuntar al servidor y los puertos `80` y `443` deben estar abiertos para que Caddy emita el certificado de Let's Encrypt.