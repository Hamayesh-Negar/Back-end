#!/bin/bash

# This script automatically installs certbot and obtains Let's Encrypt SSL certificates
# for Hamayesh Negar. It reads domain and email from .env file.

set -e

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root or with sudo command."
    exit
fi


if [ -f "../../.env" ]; then
    source "../../.env"
else
    echo "Error: .env file not found!"
    exit 1
fi

if [ -z "$DOMAIN" ]; then
    echo "Error: DOMAIN is not set in .env file!"
    echo "Please add DOMAIN=yourdomain.com to your .env file."
    exit 1
fi

if [ -z "$EMAIL" ]; then
    echo "Error: EMAIL is not set in .env file!"
    echo "Please add EMAIL=your@email.com to your .env file."
    exit 1
fi

if [ -f /etc/debian_version ]; then
    OS="debian"
elif [ -f /etc/redhat-release ]; then
    OS="centos"
elif [ -f /etc/alpine-release ]; then
    OS="alpine"
else
    echo "Unsupported OS. Please install certbot manually."
    exit 1
fi

if ! command -v certbot &> /dev/null; then
    echo "Installing certbot..."
    
    if [ "$OS" = "debian" ]; then
        sudo apt-get update
        sudo apt-get install -y certbot
    elif [ "$OS" = "centos" ]; then
        sudo yum install -y epel-release
        sudo yum install -y certbot
    elif [ "$OS" = "alpine" ]; then
        sudo apk add certbot
    fi
fi

CERTS_DIR="./certs"
NGINX_CONTAINER_NAME="hamayesh-negar-nginx-1"

mkdir -p $CERTS_DIR

mkdir -p ./certbot/www/.well-known/acme-challenge
mkdir -p ./certbot/conf

if docker ps | grep -q "$NGINX_CONTAINER_NAME"; then
    echo "Stopping Nginx container temporarily..."
    docker-compose -f ../../docker-compose.yml stop nginx
    NGINX_WAS_RUNNING=true
else
    NGINX_WAS_RUNNING=false
fi

echo "Requesting Let's Encrypt certificate for $DOMAIN and www.$DOMAIN..."
sudo certbot certonly --standalone \
    --agree-tos \
    --non-interactive \
    --email $EMAIL \
    -d $DOMAIN -d www.$DOMAIN

echo "Copying certificates to Nginx certs directory..."
sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $CERTS_DIR/ssl.crt
sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $CERTS_DIR/ssl.key

sudo chmod 644 $CERTS_DIR/ssl.crt
sudo chmod 600 $CERTS_DIR/ssl.key

if [ "$NGINX_WAS_RUNNING" = true ]; then
    echo "Restarting Nginx container..."
    docker-compose -f ../../docker-compose.yml start nginx
fi

echo "SSL certificates successfully installed!"

echo "Do you want to setup automatic renewal for the certificates?"
select yn in "Yes" "No"; do
    case $yn in
        Yes ) break;;
        No ) exit;;
    esac
done

# Setup auto-renewal script
RENEWAL_SCRIPT="$PWD/renew-certs.sh"
cat > $RENEWAL_SCRIPT << EOL
#!/bin/bash

# Load environment variables
if [ -f "../../.env" ]; then
    source "../../.env"
else
    echo "Error: .env file not found!"
    exit 1
fi

certbot renew --quiet
if [ \$? -eq 0 ]; then
    cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $PWD/$CERTS_DIR/ssl.crt
    cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $PWD/$CERTS_DIR/ssl.key
    
    # Restart Nginx container
    cd ../..
    docker-compose restart nginx
    cd -
    
    echo "Certificates renewed and Nginx restarted at \$(date)" >> $PWD/cert-renewal.log
fi
EOL

chmod +x $RENEWAL_SCRIPT

echo "Do you want to add a cron job for automatic renewal?"
select yn in "Yes" "No"; do
    case $yn in
        Yes ) break;;
        No ) exit;;
    esac
done

echo "Setting up automatic renewal (requires sudo)..."
CRON_ENTRY="0 3 * * * $RENEWAL_SCRIPT"
(sudo crontab -l 2>/dev/null | grep -v "$RENEWAL_SCRIPT" ; echo "$CRON_ENTRY") | sudo crontab -

echo "Let's Encrypt SSL certificate has been installed successfully!"
echo "Certificate will automatically renew before it expires."
echo ""
echo "To test your SSL configuration, visit: https://www.ssllabs.com/ssltest/analyze.html?d=$DOMAIN"
echo ""
echo "Certificate Files:"
echo "- Certificate: $CERTS_DIR/ssl.crt"
echo "- Private Key: $CERTS_DIR/ssl.key"