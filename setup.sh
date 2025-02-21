#!/bin/bash

# Setup script for Hamayesh Negar Docker deployment
# This script sets up the Docker environment and handles SSL certificate installation

set -e

echo "Setting up Hamayesh Negar Docker environment..."

mkdir -p docker/nginx/conf.d
mkdir -p docker/nginx/certs
mkdir -p docker/nginx/certbot/www
mkdir -p docker/nginx/certbot/conf
mkdir -p media
mkdir -p staticfiles

if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please create a .env file by copying .env-sample and edit it with your settings."
    exit 1
fi

source .env

chmod +x docker/entrypoint.sh
chmod +x docker/nginx/generate-ssl.sh
chmod +x docker/nginx/setup-letsencrypt.sh

if [ "${USE_LETSENCRYPT:-false}" = "true" ]; then
    echo "Setting up Let's Encrypt SSL certificates..."
    
    if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
        echo "Error: DOMAIN and EMAIL must be set in .env file for Let's Encrypt"
        echo "Please edit your .env file and run this script again."
        exit 1
    fi
    
    cd docker/nginx
    ./letsencrypt.sh
    cd ../..
fi

echo "Building Docker containers..."
docker-compose build

echo "Setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Start the application with: docker-compose up -d"
echo "2. Access the application at https://${DOMAIN:-localhost}"
echo ""

if [ "${USE_LETSENCRYPT:-false}" != "true" ]; then
    echo "For production deployment, set USE_LETSENCRYPT=true in your .env file and run this script again."
fi