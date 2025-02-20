#!/bin/bash

set -e

echo "Waiting for postgres..."
while ! nc -z $DATABASE_HOST $DATABASE_PORT; do
  sleep 0.1
done
echo "PostgreSQL started"

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Applying migrations..."
python manage.py migrate

if [ "$DJANGO_SUPERUSER_EMAIL" ] && [ "$DJANGO_SUPERUSER_PASSWORD" ] && [ "$DJANGO_SUPERUSER_PHONE" ]; then
  echo "Creating superuser..."
  python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Hamayesh_Negar_django.settings')
django.setup()
from user.models import User
if not User.objects.filter(email='$DJANGO_SUPERUSER_EMAIL').exists():
    User.objects.create_superuser('$DJANGO_SUPERUSER_EMAIL', '$DJANGO_SUPERUSER_PHONE', '$DJANGO_SUPERUSER_PASSWORD', first_name='Admin', last_name='User')
    print('Superuser created')
else:
    print('Superuser already exists')
  "
else
  echo "Environment variables not set, using manage.py createsuperuser..."
  python manage.py createsuperuser
fi

mkdir -p /app/media
mkdir -p /app/staticfiles

if [ "$(id -u)" = "0" ]; then
    chown -R 1000:1000 /app/media /app/staticfiles
fi

exec "$@"
