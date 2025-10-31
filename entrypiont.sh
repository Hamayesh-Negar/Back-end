#!/bin/bash

set -e

mkdir -p /app/users/migrations
touch /app/users/migrations/__init__.py

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Checking database connection..."
python -c "
import os
import psycopg2
import time
from psycopg2 import sql
from dotenv import load_dotenv

load_dotenv()

db_url = os.environ.get('DATABASE_URL')
if not db_url:
    raise ValueError('DATABASE_URL environment variable is not set')
db_name = db_url.split('/')[-1]
user = db_url.split(':')[1].split('//')[1]
host = db_url.split('@')[1].split(':')[0]
port = db_url.split('@')[1].split(':')[1].split('/')[0]
password = db_url.split(':')[2].split('@')[0]

max_retries = 5
for attempt in range(max_retries):
    try:
        try:
            conn = psycopg2.connect(
                dbname=db_name,
                user=user,
                password=password,
                host=host,
                port=port
            )
            conn.close()
            print(f'Successfully connected to {db_name} database')
            break
        except psycopg2.OperationalError as e:
            if 'does not exist' in str(e):
                print(f'Database {db_name} does not exist, trying to create it...')

                conn = psycopg2.connect(
                    dbname='postgres',
                    user=user,
                    password=password,
                    host=host,
                    port=port
                )
                conn.autocommit = True
                cursor = conn.cursor()
                
                cursor.execute(\"\"\"
                    SELECT 1 FROM pg_database WHERE datname = %s
                \"\"\", (db_name,))
                
                if cursor.fetchone() is None:
                    cursor.execute(sql.SQL(\"\"\"
                        CREATE DATABASE {}
                    \"\"\").format(sql.Identifier(db_name)))
                    print(f'Created {db_name} database successfully')
                else:
                    print(f'Database {db_name} exists but connection failed for another reason')

                cursor.close()
                conn.close()
            else:
                raise
    except Exception as e:
        print(f'Connection attempt {attempt+1}/{max_retries} failed: {e}')
        if attempt < max_retries - 1:
            time.sleep(2)
        else:
            print('Warning: Failed to verify database after multiple attempts')
            print('The application will try to proceed, but may fail if the database is not properly set up')
"

echo "Applying migrations..."
python manage.py makemigrations --noinput
python manage.py migrate --fake-initial || echo "Migrations failed, but continuing..."


echo "Creating Django superuser if it does not exist..."
python manage.py shell -c "
import os
# Ensure the environment is set up
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hesabran.settings')
import django
from django.contrib.auth import get_user_model
django.setup()

User = get_user_model()

phone_number = os.environ.get('DJANGO_SUPERUSER_PHONE')
national_id = os.environ.get('DJANGO_SUPERUSER_NATIONAL_ID')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

# Validate inputs
if not phone_number:
    print('Error: Phone number is required')
    exit(1)
    
if not national_id or len(national_id) != 10:
    print('Error: National ID must be exactly 10 characters')
    exit(1)

# Check if superuser already exists by phone_number (USERNAME_FIELD)
if not User.objects.filter(phone_number=phone_number).exists():
    try:
        # Create superuser using the custom create_superuser method
        user = User.objects.create_superuser(
            phone_number=phone_number,
            password=password,
            national_id=national_id,
            first_name='Super',
            last_name='Admin',
        )
        print(f'  Phone: {phone_number}')
        print(f'  National ID: {national_id}')
    except Exception as e:
        print(f'✗ Error creating superuser: {e}')
        exit(1)
else:
    existing_user = User.objects.get(phone_number=phone_number)
    print(f'✓ Superuser with phone number {phone_number} already exists.')
"

mkdir -p /app/media
mkdir -p /app/staticfiles

if [ "$(id -u)" = "0" ]; then
    chown -R 1000:1000 /app/media /app/staticfiles
fi

echo "Starting web server..."
exec "$@" 
