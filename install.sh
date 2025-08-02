#!/bin/bash

# StrophenBoost - Professional Live Streaming Platform Installation
# Automated deployment script for production environments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Installation configuration
DOMAIN=""
EMAIL=""
CLOUDFLARE_API_TOKEN=""
APP_USER=""
IS_ROOT=false
RTMP_PORT=1935
WEB_PORT=5000
DB_PASSWORD=""
FLASK_SECRET=""

generate_password() {
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -base64 32 | tr -d '\n'
    else
        tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32
    fi
}

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

error_exit() {
    print_error "Installation failed: $1"
    exit 1
}

check_privileges() {
    print_status "Checking system privileges..."
    
    if [ "$EUID" -eq 0 ]; then
        print_status "Running as root - will create secure application user"
        IS_ROOT=true
        APP_USER="strophenboost"
        
        if ! id "$APP_USER" >/dev/null 2>&1; then
            print_status "Creating application user: $APP_USER"
            useradd -m -s /bin/bash -G sudo "$APP_USER" 2>/dev/null || true
            mkdir -p "/home/$APP_USER"
            chown "$APP_USER:$APP_USER" "/home/$APP_USER"
        fi
    else
        print_status "Running as regular user - checking sudo access"
        IS_ROOT=false
        APP_USER=$USER
        
        if ! sudo -n true 2>/dev/null; then
            print_status "This script requires sudo privileges. Please enter your password:"
            sudo true || error_exit "Unable to obtain sudo privileges"
        fi
    fi
    
    print_success "Privileges verified for user: $APP_USER"
}

collect_info() {
    echo
    echo "================================================================"
    echo "           StrophenBoost Installation Setup                     "
    echo "================================================================"
    echo
    
    while [ -z "$DOMAIN" ]; do
        echo -n "Enter your domain name (e.g., streaming.example.com): "
        read DOMAIN
        if ! echo "$DOMAIN" | grep -qE '^[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]\.[a-zA-Z]{2,}$'; then
            print_error "Invalid domain format. Please use format: subdomain.example.com"
            DOMAIN=""
        fi
    done
    
    while [ -z "$EMAIL" ]; do
        echo -n "Enter your email for SSL certificates: "
        read EMAIL
        if ! echo "$EMAIL" | grep -qE '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'; then
            print_error "Invalid email format. Please try again."
            EMAIL=""
        fi
    done
    
    echo
    print_status "For DNS verification, you need a Cloudflare API Token with Zone:Edit permissions"
    print_status "Get it from: https://dash.cloudflare.com/profile/api-tokens"
    echo
    while [ -z "$CLOUDFLARE_API_TOKEN" ]; do
        echo -n "Enter your Cloudflare API Token: "
        read CLOUDFLARE_API_TOKEN
        if [ ${#CLOUDFLARE_API_TOKEN} -lt 20 ]; then
            print_error "API token seems too short. Please verify and try again."
            CLOUDFLARE_API_TOKEN=""
        fi
    done
    
    print_status "Generating secure passwords..."
    DB_PASSWORD=$(generate_password)
    FLASK_SECRET=$(generate_password)
    
    echo
    echo "Configuration Summary:"
    echo "  Domain: $DOMAIN"
    echo "  Email: $EMAIL"
    echo "  App User: $APP_USER"
    echo "  RTMP Port: $RTMP_PORT"
    echo "  Web Port: $WEB_PORT"
    echo
    
    echo -n "Continue with installation? (y/N): "
    read -n 1 REPLY
    echo
    if [ "$REPLY" != "y" ] && [ "$REPLY" != "Y" ]; then
        print_status "Installation cancelled by user."
        exit 0
    fi
    
    print_success "Configuration confirmed. Starting installation..."
}

update_system() {
    print_status "Updating system packages..."
    if [ "$IS_ROOT" = true ]; then
        apt update -y && apt upgrade -y
    else
        sudo apt update -y && sudo apt upgrade -y
    fi
    print_success "System packages updated"
}

install_dependencies() {
    print_status "Installing system dependencies..."
    
    PACKAGES="python3 python3-pip python3-venv postgresql postgresql-contrib nginx certbot python3-certbot-dns-cloudflare ffmpeg git curl wget ufw supervisor build-essential libssl-dev libffi-dev python3-dev pkg-config libpq-dev openssl"
    
    if [ "$IS_ROOT" = true ]; then
        apt install -y $PACKAGES
    else
        sudo apt install -y $PACKAGES
    fi
    
    print_success "System dependencies installed"
}

setup_database() {
    print_status "Setting up PostgreSQL database..."
    
    if [ "$IS_ROOT" = true ]; then
        systemctl start postgresql
        systemctl enable postgresql
    else
        sudo systemctl start postgresql
        sudo systemctl enable postgresql
    fi
    
    if [ "$IS_ROOT" = true ]; then
        sudo -u postgres psql -c "CREATE USER $APP_USER WITH PASSWORD '$DB_PASSWORD';" 2>/dev/null || true
        sudo -u postgres psql -c "CREATE DATABASE strophenboost OWNER $APP_USER;" 2>/dev/null || true
        sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE strophenboost TO $APP_USER;" 2>/dev/null || true
    else
        sudo -u postgres psql -c "CREATE USER $APP_USER WITH PASSWORD '$DB_PASSWORD';" 2>/dev/null || true
        sudo -u postgres psql -c "CREATE DATABASE strophenboost OWNER $APP_USER;" 2>/dev/null || true
        sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE strophenboost TO $APP_USER;" 2>/dev/null || true
    fi
    
    print_success "PostgreSQL database configured"
}

setup_application() {
    print_status "Setting up StrophenBoost application..."
    
    if [ "$IS_ROOT" = true ]; then
        mkdir -p /opt/strophenboost
        cp -r . /opt/strophenboost/
        cd /opt/strophenboost
        
        sudo -u "$APP_USER" python3 -m venv venv
        sudo -u "$APP_USER" bash -c "source venv/bin/activate && pip install --upgrade pip"
        sudo -u "$APP_USER" bash -c "source venv/bin/activate && pip install flask flask-sqlalchemy flask-login flask-socketio flask-cors flask-wtf gunicorn psycopg2-binary google-genai email-validator werkzeug sqlalchemy gevent eventlet"
        
        chown -R "$APP_USER:$APP_USER" /opt/strophenboost
    else
        sudo mkdir -p /opt/strophenboost
        sudo cp -r . /opt/strophenboost/
        cd /opt/strophenboost
        
        python3 -m venv venv
        source venv/bin/activate
        pip install --upgrade pip
        pip install flask flask-sqlalchemy flask-login flask-socketio flask-cors flask-wtf gunicorn psycopg2-binary google-genai email-validator werkzeug sqlalchemy gevent eventlet
        
        sudo chown -R "$USER:$USER" /opt/strophenboost
    fi
    
    cat > /opt/strophenboost/.env << 'ENVEOF'
DATABASE_URL=postgresql://${APP_USER}:${DB_PASSWORD}@localhost/strophenboost
PGHOST=localhost
PGPORT=5432
PGUSER=${APP_USER}
PGPASSWORD=${DB_PASSWORD}
PGDATABASE=strophenboost
FLASK_SECRET_KEY=${FLASK_SECRET}
SESSION_SECRET=${FLASK_SECRET}
DOMAIN=${DOMAIN}
EMAIL=${EMAIL}
ENVEOF
    
    # Replace variables in .env file
    sed -i "s/\${APP_USER}/$APP_USER/g" /opt/strophenboost/.env
    sed -i "s/\${DB_PASSWORD}/$DB_PASSWORD/g" /opt/strophenboost/.env
    sed -i "s/\${FLASK_SECRET}/$FLASK_SECRET/g" /opt/strophenboost/.env
    sed -i "s/\${DOMAIN}/$DOMAIN/g" /opt/strophenboost/.env
    sed -i "s/\${EMAIL}/$EMAIL/g" /opt/strophenboost/.env
    
    if [ "$IS_ROOT" = true ]; then
        chown "$APP_USER:$APP_USER" /opt/strophenboost/.env
        chmod 600 /opt/strophenboost/.env
    else
        chmod 600 /opt/strophenboost/.env
    fi
    
    print_success "Application setup completed"
}

setup_ssl() {
    print_status "Setting up SSL certificates..."
    
    if [ "$IS_ROOT" = true ]; then
        mkdir -p /etc/letsencrypt
        cat > /etc/letsencrypt/cloudflare.ini << CFEOF
dns_cloudflare_api_token = $CLOUDFLARE_API_TOKEN
CFEOF
        chmod 600 /etc/letsencrypt/cloudflare.ini
    else
        sudo mkdir -p /etc/letsencrypt
        sudo tee /etc/letsencrypt/cloudflare.ini > /dev/null << CFEOF
dns_cloudflare_api_token = $CLOUDFLARE_API_TOKEN
CFEOF
        sudo chmod 600 /etc/letsencrypt/cloudflare.ini
    fi
    
    print_status "Obtaining SSL certificate for $DOMAIN..."
    if [ "$IS_ROOT" = true ]; then
        certbot certonly --dns-cloudflare --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini --email "$EMAIL" --agree-tos --no-eff-email --non-interactive -d "$DOMAIN" || print_warning "SSL certificate setup failed - will configure later"
    else
        sudo certbot certonly --dns-cloudflare --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini --email "$EMAIL" --agree-tos --no-eff-email --non-interactive -d "$DOMAIN" || print_warning "SSL certificate setup failed - will configure later"
    fi
    
    print_success "SSL configuration completed"
}

configure_nginx() {
    print_status "Configuring Nginx..."
    
    if [ "$IS_ROOT" = true ]; then
        rm -f /etc/nginx/sites-enabled/default
    else
        sudo rm -f /etc/nginx/sites-enabled/default
    fi
    
    NGINX_CONFIG="/etc/nginx/sites-available/strophenboost"
    SSL_CERT="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
    
    if [ -f "$SSL_CERT" ]; then
        # HTTPS configuration
        if [ "$IS_ROOT" = true ]; then
            cat > "$NGINX_CONFIG" << 'NGINXEOF'
server {
    listen 80;
    server_name DOMAIN_PLACEHOLDER;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name DOMAIN_PLACEHOLDER;
    
    ssl_certificate /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/privkey.pem;
    
    client_max_body_size 100M;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /socket.io/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    location /static/ {
        alias /opt/strophenboost/static/;
        expires 30d;
    }
    
    location /stream_output/ {
        alias /opt/strophenboost/stream_output/;
        expires 1s;
        add_header Access-Control-Allow-Origin "*";
    }
}
NGINXEOF
            sed -i "s/DOMAIN_PLACEHOLDER/$DOMAIN/g" "$NGINX_CONFIG"
        else
            sudo tee "$NGINX_CONFIG" > /dev/null << NGINXEOF
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN;
    
    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    
    client_max_body_size 100M;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    location /socket.io/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    location /static/ {
        alias /opt/strophenboost/static/;
        expires 30d;
    }
    
    location /stream_output/ {
        alias /opt/strophenboost/stream_output/;
        expires 1s;
        add_header Access-Control-Allow-Origin "*";
    }
}
NGINXEOF
        fi
    else
        # HTTP-only configuration
        print_warning "SSL certificate not found - configuring HTTP only"
        if [ "$IS_ROOT" = true ]; then
            cat > "$NGINX_CONFIG" << NGINXEOF
server {
    listen 80;
    server_name $DOMAIN;
    
    client_max_body_size 100M;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    location /socket.io/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    location /static/ {
        alias /opt/strophenboost/static/;
        expires 30d;
    }
    
    location /stream_output/ {
        alias /opt/strophenboost/stream_output/;
        expires 1s;
        add_header Access-Control-Allow-Origin "*";
    }
}
NGINXEOF
        else
            sudo tee "$NGINX_CONFIG" > /dev/null << NGINXEOF
server {
    listen 80;
    server_name $DOMAIN;
    
    client_max_body_size 100M;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    location /socket.io/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    location /static/ {
        alias /opt/strophenboost/static/;
        expires 30d;
    }
    
    location /stream_output/ {
        alias /opt/strophenboost/stream_output/;
        expires 1s;
        add_header Access-Control-Allow-Origin "*";
    }
}
NGINXEOF
        fi
    fi
    
    if [ "$IS_ROOT" = true ]; then
        ln -sf "$NGINX_CONFIG" /etc/nginx/sites-enabled/
        nginx -t || error_exit "Nginx configuration test failed"
    else
        sudo ln -sf "$NGINX_CONFIG" /etc/nginx/sites-enabled/
        sudo nginx -t || error_exit "Nginx configuration test failed"
    fi
    
    print_success "Nginx configured successfully"
}

configure_supervisor() {
    print_status "Configuring Supervisor..."
    
    if [ "$IS_ROOT" = true ]; then
        mkdir -p /var/log/strophenboost
        chown "$APP_USER:$APP_USER" /var/log/strophenboost
    else
        sudo mkdir -p /var/log/strophenboost
        sudo chown "$APP_USER:$APP_USER" /var/log/strophenboost
    fi
    
    SUPERVISOR_CONFIG="/etc/supervisor/conf.d/strophenboost.conf"
    if [ "$IS_ROOT" = true ]; then
        cat > "$SUPERVISOR_CONFIG" << SUPERVISOREOF
[program:strophenboost]
command=/opt/strophenboost/venv/bin/gunicorn --bind 127.0.0.1:5000 --workers 4 --worker-class gevent --worker-connections 1000 --timeout 300 main:app
directory=/opt/strophenboost
user=$APP_USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/strophenboost/app.log
environment=PATH="/opt/strophenboost/venv/bin"

[program:strophenboost-rtmp]
command=/opt/strophenboost/venv/bin/python start_rtmp_server.py
directory=/opt/strophenboost
user=$APP_USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/strophenboost/rtmp.log
environment=PATH="/opt/strophenboost/venv/bin"
SUPERVISOREOF
    else
        sudo tee "$SUPERVISOR_CONFIG" > /dev/null << SUPERVISOREOF
[program:strophenboost]
command=/opt/strophenboost/venv/bin/gunicorn --bind 127.0.0.1:5000 --workers 4 --worker-class gevent --worker-connections 1000 --timeout 300 main:app
directory=/opt/strophenboost
user=$APP_USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/strophenboost/app.log
environment=PATH="/opt/strophenboost/venv/bin"

[program:strophenboost-rtmp]
command=/opt/strophenboost/venv/bin/python start_rtmp_server.py
directory=/opt/strophenboost
user=$APP_USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/strophenboost/rtmp.log
environment=PATH="/opt/strophenboost/venv/bin"
SUPERVISOREOF
    fi
    
    print_success "Supervisor configured"
}

configure_firewall() {
    print_status "Configuring firewall..."
    
    if [ "$IS_ROOT" = true ]; then
        ufw --force reset
        ufw default deny incoming
        ufw default allow outgoing
        ufw allow ssh
        ufw allow 80/tcp
        ufw allow 443/tcp
        ufw allow "$RTMP_PORT/tcp"
        ufw --force enable
    else
        sudo ufw --force reset
        sudo ufw default deny incoming
        sudo ufw default allow outgoing
        sudo ufw allow ssh
        sudo ufw allow 80/tcp
        sudo ufw allow 443/tcp
        sudo ufw allow "$RTMP_PORT/tcp"
        sudo ufw --force enable
    fi
    
    print_success "Firewall configured"
}

initialize_database() {
    print_status "Initializing database..."
    
    cd /opt/strophenboost
    
    if [ "$IS_ROOT" = true ]; then
        sudo -u "$APP_USER" bash -c "
            source venv/bin/activate
            export DATABASE_URL='postgresql://$APP_USER:$DB_PASSWORD@localhost/strophenboost'
            export FLASK_SECRET_KEY='$FLASK_SECRET'
            export SESSION_SECRET='$FLASK_SECRET'
            python3 -c 'from app import app, db; app.app_context().push(); db.create_all(); print(\"Database initialized\")'
        "
    else
        source venv/bin/activate
        export DATABASE_URL="postgresql://$APP_USER:$DB_PASSWORD@localhost/strophenboost"
        export FLASK_SECRET_KEY="$FLASK_SECRET"
        export SESSION_SECRET="$FLASK_SECRET"
        python3 -c "from app import app, db; app.app_context().push(); db.create_all(); print('Database initialized')"
    fi
    
    print_success "Database initialized"
}

create_admin_user() {
    print_status "Creating admin user..."
    
    ADMIN_PASSWORD=$(generate_password | head -c 16)
    
    cd /opt/strophenboost
    
    if [ "$IS_ROOT" = true ]; then
        sudo -u "$APP_USER" bash -c "
            source venv/bin/activate
            export DATABASE_URL='postgresql://$APP_USER:$DB_PASSWORD@localhost/strophenboost'
            export FLASK_SECRET_KEY='$FLASK_SECRET'
            export SESSION_SECRET='$FLASK_SECRET'
            python3 -c '
from app import app, db
from models import User
from werkzeug.security import generate_password_hash

with app.app_context():
    admin = User.query.filter_by(username=\"admin\").first()
    if not admin:
        admin = User(
            username=\"admin\",
            email=\"$EMAIL\",
            password_hash=generate_password_hash(\"$ADMIN_PASSWORD\"),
            is_broadcaster=True
        )
        db.session.add(admin)
        db.session.commit()
        print(\"Admin user created successfully\")
    else:
        print(\"Admin user already exists\")
'
        "
    else
        source venv/bin/activate
        export DATABASE_URL="postgresql://$APP_USER:$DB_PASSWORD@localhost/strophenboost"
        export FLASK_SECRET_KEY="$FLASK_SECRET"
        export SESSION_SECRET="$FLASK_SECRET"
        python3 -c "
from app import app, db
from models import User
from werkzeug.security import generate_password_hash

with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='$EMAIL',
            password_hash=generate_password_hash('$ADMIN_PASSWORD'),
            is_broadcaster=True
        )
        db.session.add(admin)
        db.session.commit()
        print('Admin user created successfully')
    else:
        print('Admin user already exists')
"
    fi
    
    cat > /opt/strophenboost/admin_credentials.txt << CREDEOF
StrophenBoost Admin Credentials
==============================
Username: admin
Password: $ADMIN_PASSWORD
Email: $EMAIL
Domain: https://$DOMAIN
RTMP: rtmp://$DOMAIN:$RTMP_PORT/live
CREDEOF
    
    if [ "$IS_ROOT" = true ]; then
        chown "$APP_USER:$APP_USER" /opt/strophenboost/admin_credentials.txt
        chmod 600 /opt/strophenboost/admin_credentials.txt
    fi
    
    print_success "Admin user created"
}

start_services() {
    print_status "Starting services..."
    
    if [ "$IS_ROOT" = true ]; then
        supervisorctl reread
        supervisorctl update
        supervisorctl start strophenboost
        supervisorctl start strophenboost-rtmp
        systemctl restart nginx
        systemctl enable nginx
        systemctl enable supervisor
    else
        sudo supervisorctl reread
        sudo supervisorctl update
        sudo supervisorctl start strophenboost
        sudo supervisorctl start strophenboost-rtmp
        sudo systemctl restart nginx
        sudo systemctl enable nginx
        sudo systemctl enable supervisor
    fi
    
    print_success "All services started"
}

show_completion_info() {
    echo
    echo "================================================================"
    echo "                 Installation Complete!                        "
    echo "================================================================"
    echo
    
    print_success "StrophenBoost has been successfully installed!"
    echo
    echo "Access Information:"
    if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
        echo "  Website: https://$DOMAIN"
    else
        echo "  Website: http://$DOMAIN"
    fi
    echo "  RTMP Server: rtmp://$DOMAIN:$RTMP_PORT/live"
    echo "  Stream Setup: https://$DOMAIN/streaming/setup"
    echo
    
    if [ -f /opt/strophenboost/admin_credentials.txt ]; then
        echo "Admin Credentials:"
        grep -E "(Username|Password)" /opt/strophenboost/admin_credentials.txt | sed 's/^/  /'
        echo
    fi
    
    echo "System Information:"
    echo "  Application User: $APP_USER"
    echo "  Application Path: /opt/strophenboost"
    echo "  Logs: /var/log/strophenboost/"
    echo
    
    print_success "Your streaming platform is ready to use!"
}

main() {
    echo
    cat << 'BANNEREOF'
  ____  _                  _                ____                  _   
 / ___|| |_ _ __ ___  _ __ | |__   ___ _ __ | __ )  ___   ___  ___| |_ 
 \___ \| __| '__/ _ \| '_ \| '_ \ / _ \ '_ \|  _ \ / _ \ / _ \/ __| __|
  ___) | |_| | | (_) | |_) | | | |  __/ | | | |_) | (_) | (_) \__ \ |_ 
 |____/ \__|_|  \___/| .__/|_| |_|\___|_| |_|____/ \___/ \___/|___/\__|
                     |_|                                               
        Professional Live Streaming Platform Installation
BANNEREOF
    echo
    
    check_privileges
    collect_info
    update_system
    install_dependencies
    setup_database
    setup_application
    setup_ssl
    configure_nginx
    configure_supervisor
    configure_firewall
    initialize_database
    create_admin_user
    start_services
    show_completion_info
}

trap 'error_exit "Script interrupted at line $LINENO"' ERR

main "$@"
