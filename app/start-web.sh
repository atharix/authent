#!/bin/bash

set -e

echo "Waiting for database..."
./wait-for-db.sh db 5432

echo "Creating required directories..."
mkdir -p /app/config/logs /app/config/staticfiles

# Solo crear migraciones en desarrollo; en producción deben venir del repositorio
if [ "$ENVIRONMENT" != "prod" ]; then
    echo "Development mode: creating migrations..."
    python manage.py makemigrations --noinput 2>/dev/null || true
fi

echo "Running migrations..."
python manage.py migrate --no-input

echo "Loading fixtures (idempotent; integrity errors are ignored)..."
for fixture in /seed/fixtures/*.json; do
    [ -f "$fixture" ] || continue
    name=$(basename "$fixture")
    echo "  → $name"
    python manage.py loaddata "$fixture" 2>&1 | tail -1 || true
done

# Re-aplica vat_options por país. Las migraciones de datos 0002/0003 corren
# antes que los fixtures de countries; sin esto los entornos fresh quedan
# con `vat_options=[]` y el frontend bloquea el TaxCodePicker.
echo "Seeding country VAT options..."
python manage.py seed_vat_options 2>&1 | tail -10 || true

echo "Collecting static files..."
python manage.py collectstatic --no-input --clear

echo "Checking for superuser..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser(
        email='admin@atharix.com',
        password='admin123',
        first_name='Admin',
        last_name='Hub',
    )
    print('Superuser created: admin@atharix.com / admin123')
else:
    print('Superuser already exists')
"

echo "Starting Django development server..."
python manage.py runserver 0.0.0.0:8000
