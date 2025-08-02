#!/bin/bash

# StrophenBoost - Complete Installation Script with Let's Encrypt DNS
# This script automates the entire installation process including SSL certificates

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration variables
DOMAIN=""
EMAIL=""
CLOUDFLARE_API_TOKEN=""
DB_PASSWORD=$(openssl rand -base64 32)
FLASK_SECRET=$(openssl rand -base64 32)
RTMP_PORT=1935
WEB_PORT=5000

# Function to print colored output
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

# Function to check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "This script should not be run as root for security reasons."
        print_status "Please run as a regular user with sudo privileges."
        exit 1
    fi
}

# Function to collect user input
collect_info() {
    echo -e "${BLUE}=== StrophenBoost Installation Setup ===${NC}"
    echo ""
    
    # Domain name
    while [[ -z "$DOMAIN" ]]; do
        read -p "Enter your domain name (e.g., streaming.example.com): " DOMAIN
        if [[ ! "$DOMAIN" =~ ^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}$ ]]; then
            print_error "Invalid domain format. Please try again."
            DOMAIN=""
        fi
    done
    
    # Email for Let's Encrypt
    while [[ -z "$EMAIL" ]]; do
        read -p "Enter your email for Let's Encrypt notifications: " EMAIL
        if [[ ! "$EMAIL" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
            print_error "Invalid email format. Please try again."
            EMAIL=""
        fi
    done
    
    # Cloudflare API Token
    echo ""
    print_status "For DNS verification, you need a Cloudflare API Token with Zone:Edit permissions."
    print_status "Get it from: https://dash.cloudflare.com/profile/api-tokens"
    while [[ -z "$CLOUDFLARE_API_TOKEN" ]]; do
        read -p "Enter your Cloudflare API Token: " CLOUDFLARE_API_TOKEN
    done
    
    echo ""
    print_status "Configuration Summary:"
    echo "  Domain: $DOMAIN"
    echo "  Email: $EMAIL"
    echo "  RTMP Port: $RTMP_PORT"
    echo "  Web Port: $WEB_PORT"
    echo ""
    
    read -p "Continue with installation? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Installation cancelled."
        exit 0
    fi
}

# Function to update system
update_system() {
    print_status "Updating system packages..."
    sudo apt update && sudo apt upgrade -y
    print_success "System updated successfully"
}

# Function to install dependencies
install_dependencies() {
    print_status "Installing system dependencies..."
    
    # Essential packages
    sudo apt install -y \
        python3 \
        python3-pip \
        python3-venv \
        postgresql \
        postgresql-contrib \
        nginx \
        certbot \
        python3-certbot-nginx \
        python3-certbot-dns-cloudflare \
        ffmpeg \
        git \
        curl \
        wget \
        ufw \
        supervisor \
        build-essential \
        libssl-dev \
        libffi-dev \
        python3-dev \
        pkg-config \
        libpq-dev
    
    print_success "System dependencies installed"
}

# Function to setup PostgreSQL
setup_database() {
    print_status "Setting up PostgreSQL database..."
    
    # Start PostgreSQL service
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
    
    # Create database and user
    sudo -u postgres psql << EOF
CREATE USER strophenboost WITH PASSWORD '$DB_PASSWORD';
CREATE DATABASE strophenboost OWNER strophenboost;
GRANT ALL PRIVILEGES ON DATABASE strophenboost TO strophenboost;
\q
EOF
    
    print_success "PostgreSQL database configured"
}

# Function to setup application
setup_application() {
    print_status "Setting up StrophenBoost application..."
    
    # Create application directory
    sudo mkdir -p /opt/strophenboost
    sudo chown $USER:$USER /opt/strophenboost
    
    # Copy application files
    cp -r . /opt/strophenboost/
    cd /opt/strophenboost
    
    # Create virtual environment
    python3 -m venv venv
    source venv/bin/activate
    
    # Install Python dependencies
    pip install --upgrade pip
    pip install -r requirements.txt || pip install \
        flask \
        flask-sqlalchemy \
        flask-login \
        flask-socketio \
        flask-cors \
        flask-wtf \
        gunicorn \
        psycopg2-binary \
        google-genai \
        email-validator \
        werkzeug \
        sqlalchemy
    
    # Create environment file
    cat > .env << EOF
# Database Configuration
DATABASE_URL=postgresql://strophenboost:$DB_PASSWORD@localhost/strophenboost
PGHOST=localhost
PGPORT=5432
PGUSER=strophenboost
PGPASSWORD=$DB_PASSWORD
PGDATABASE=strophenboost

# Flask Configuration
FLASK_SECRET_KEY=$FLASK_SECRET
SESSION_SECRET=$FLASK_SECRET

# Domain Configuration
DOMAIN=$DOMAIN
EMAIL=$EMAIL

# Optional: Add your Gemini API key here for AI features
# GEMINI_API_KEY=your_gemini_api_key_here
EOF
    
    # Set proper permissions
    chmod 600 .env
    
    print_success "Application setup completed"
}

# Function to setup Cloudflare credentials for certbot
setup_cloudflare_dns() {
    print_status "Setting up Cloudflare DNS credentials..."
    
    # Create Cloudflare credentials file
    sudo mkdir -p /etc/letsencrypt
    sudo tee /etc/letsencrypt/cloudflare.ini > /dev/null << EOF
dns_cloudflare_api_token = $CLOUDFLARE_API_TOKEN
EOF
    
    # Secure the credentials file
    sudo chmod 600 /etc/letsencrypt/cloudflare.ini
    
    print_success "Cloudflare DNS credentials configured"
}

# Function to obtain SSL certificate
obtain_ssl_certificate() {
    print_status "Obtaining SSL certificate via DNS verification..."
    
    # Request certificate using DNS verification
    sudo certbot certonly \
        --dns-cloudflare \
        --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini \
        --email $EMAIL \
        --agree-tos \
        --no-eff-email \
        -d $DOMAIN \
        -d *.$DOMAIN
    
    if [[ $? -eq 0 ]]; then
        print_success "SSL certificate obtained successfully"
    else
        print_error "Failed to obtain SSL certificate"
        print_warning "You can manually configure SSL later or use HTTP for now"
    fi
}

# Function to configure Nginx
configure_nginx() {
    print_status "Configuring Nginx..."
    
    # Remove default site
    sudo rm -f /etc/nginx/sites-enabled/default
    
    # Create StrophenBoost Nginx configuration
    sudo tee /etc/nginx/sites-available/strophenboost > /dev/null << 'EOF'
# StrophenBoost Nginx Configuration

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name DOMAIN_PLACEHOLDER;
    return 301 https://$server_name$request_uri;
}

# Main HTTPS server
server {
    listen 443 ssl http2;
    server_name DOMAIN_PLACEHOLDER;
    
    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/privkey.pem;
    ssl_trusted_certificate /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/chain.pem;
    
    # SSL Security Settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # File upload size limit
    client_max_body_size 100M;
    
    # Proxy settings
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection 'upgrade';
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_cache_bypass $http_upgrade;
    
    # Main application
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
    
    # WebSocket support for real-time features
    location /socket.io/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Static files
    location /static/ {
        alias /opt/strophenboost/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # HLS streaming files
    location /stream_output/ {
        alias /opt/strophenboost/stream_output/;
        expires 1s;
        add_header Cache-Control "no-cache";
        add_header Access-Control-Allow-Origin "*";
        add_header Access-Control-Allow-Methods "GET, OPTIONS";
        add_header Access-Control-Allow-Headers "Range";
    }
}

# RTMP status page (optional, for monitoring)
server {
    listen 8080;
    server_name DOMAIN_PLACEHOLDER;
    
    location /rtmp-status {
        return 200 "RTMP Server Status: Active\nPort: 1935\nProtocol: RTMP/TCP";
        add_header Content-Type text/plain;
    }
}
EOF
    
    # Replace placeholder with actual domain
    sudo sed -i "s/DOMAIN_PLACEHOLDER/$DOMAIN/g" /etc/nginx/sites-available/strophenboost
    
    # Enable the site
    sudo ln -sf /etc/nginx/sites-available/strophenboost /etc/nginx/sites-enabled/
    
    # Test Nginx configuration
    sudo nginx -t
    
    if [[ $? -eq 0 ]]; then
        print_success "Nginx configuration is valid"
    else
        print_error "Nginx configuration has errors"
        exit 1
    fi
}

# Function to configure Supervisor for process management
configure_supervisor() {
    print_status "Configuring Supervisor for process management..."
    
    # Create Supervisor configuration for Flask app
    sudo tee /etc/supervisor/conf.d/strophenboost.conf > /dev/null << EOF
[program:strophenboost]
command=/opt/strophenboost/venv/bin/gunicorn --bind 127.0.0.1:5000 --workers 4 --worker-class gevent --worker-connections 1000 --timeout 300 --keep-alive 2 --preload --access-logfile /var/log/strophenboost/access.log --error-logfile /var/log/strophenboost/error.log main:app
directory=/opt/strophenboost
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/strophenboost/app.log
environment=PATH="/opt/strophenboost/venv/bin"

[program:strophenboost-rtmp]
command=/opt/strophenboost/venv/bin/python start_rtmp_server.py
directory=/opt/strophenboost
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/strophenboost/rtmp.log
environment=PATH="/opt/strophenboost/venv/bin"
EOF
    
    # Create log directory
    sudo mkdir -p /var/log/strophenboost
    sudo chown www-data:www-data /var/log/strophenboost
    
    # Set proper ownership for application
    sudo chown -R www-data:www-data /opt/strophenboost
    
    print_success "Supervisor configuration completed"
}

# Function to configure firewall
configure_firewall() {
    print_status "Configuring UFW firewall..."
    
    # Reset UFW to defaults
    sudo ufw --force reset
    
    # Set default policies
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    
    # Allow SSH
    sudo ufw allow ssh
    
    # Allow HTTP and HTTPS
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    
    # Allow RTMP
    sudo ufw allow $RTMP_PORT/tcp
    
    # Allow monitoring port (optional)
    sudo ufw allow 8080/tcp
    
    # Enable firewall
    sudo ufw --force enable
    
    print_success "Firewall configured"
}

# Function to initialize database
initialize_database() {
    print_status "Initializing database..."
    
    cd /opt/strophenboost
    source venv/bin/activate
    
    # Set environment variables
    export DATABASE_URL="postgresql://strophenboost:$DB_PASSWORD@localhost/strophenboost"
    export FLASK_SECRET_KEY="$FLASK_SECRET"
    export SESSION_SECRET="$FLASK_SECRET"
    
    # Initialize database tables
    python3 -c "
from app import app, db
with app.app_context():
    db.create_all()
    print('Database tables created successfully')
"
    
    print_success "Database initialized"
}

# Function to start services
start_services() {
    print_status "Starting services..."
    
    # Reload Supervisor configuration
    sudo supervisorctl reread
    sudo supervisorctl update
    
    # Start application services
    sudo supervisorctl start strophenboost
    sudo supervisorctl start strophenboost-rtmp
    
    # Start and enable services
    sudo systemctl restart nginx
    sudo systemctl enable nginx
    sudo systemctl enable supervisor
    
    print_success "All services started"
}

# Function to setup automatic SSL renewal
setup_ssl_renewal() {
    print_status "Setting up automatic SSL certificate renewal..."
    
    # Create renewal hook script
    sudo tee /etc/letsencrypt/renewal-hooks/deploy/nginx-reload.sh > /dev/null << 'EOF'
#!/bin/bash
systemctl reload nginx
EOF
    
    sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/nginx-reload.sh
    
    # Test renewal process
    sudo certbot renew --dry-run
    
    print_success "SSL auto-renewal configured"
}

# Function to create admin user
create_admin_user() {
    print_status "Creating admin user..."
    
    cd /opt/strophenboost
    source venv/bin/activate
    
    # Set environment variables
    export DATABASE_URL="postgresql://strophenboost:$DB_PASSWORD@localhost/strophenboost"
    
    python3 -c "
from app import app, db
from models import User
from werkzeug.security import generate_password_hash
import secrets

with app.app_context():
    # Check if admin user exists
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin_password = secrets.token_urlsafe(12)
        admin = User(
            username='admin',
            email='$EMAIL',
            password_hash=generate_password_hash(admin_password),
            is_broadcaster=True
        )
        db.session.add(admin)
        db.session.commit()
        
        print(f'Admin user created successfully!')
        print(f'Username: admin')
        print(f'Password: {admin_password}')
        print(f'Email: $EMAIL')
        
        # Save credentials to file
        with open('/opt/strophenboost/admin_credentials.txt', 'w') as f:
            f.write(f'StrophenBoost Admin Credentials\\n')
            f.write(f'Username: admin\\n')
            f.write(f'Password: {admin_password}\\n')
            f.write(f'Email: $EMAIL\\n')
            f.write(f'Domain: https://$DOMAIN\\n')
    else:
        print('Admin user already exists')
"
    
    print_success "Admin user setup completed"
}

# Function to display final information
display_final_info() {
    echo ""
    echo -e "${GREEN}=== Installation Complete! ===${NC}"
    echo ""
    print_success "StrophenBoost has been successfully installed!"
    echo ""
    echo -e "${BLUE}Access Information:${NC}"
    echo "  🌐 Website: https://$DOMAIN"
    echo "  📺 RTMP Server: rtmp://$DOMAIN:$RTMP_PORT/live"
    echo "  📊 Stream Setup: https://$DOMAIN/streaming/setup"
    echo ""
    echo -e "${BLUE}Admin Credentials:${NC}"
    if [[ -f /opt/strophenboost/admin_credentials.txt ]]; then
        cat /opt/strophenboost/admin_credentials.txt | sed 's/^/  /'
    fi
    echo ""
    echo -e "${BLUE}Important Files:${NC}"
    echo "  📁 Application: /opt/strophenboost"
    echo "  🔧 Nginx Config: /etc/nginx/sites-available/strophenboost"
    echo "  📋 Supervisor: /etc/supervisor/conf.d/strophenboost.conf"
    echo "  📄 Logs: /var/log/strophenboost/"
    echo ""
    echo -e "${BLUE}Useful Commands:${NC}"
    echo "  sudo supervisorctl status          - Check service status"
    echo "  sudo supervisorctl restart all    - Restart services"
    echo "  sudo nginx -t                     - Test Nginx config"
    echo "  sudo certbot renew               - Renew SSL certificates"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "  1. Visit https://$DOMAIN and login with admin credentials"
    echo "  2. Configure your streaming software using the setup guide"
    echo "  3. Add your Gemini API key in /opt/strophenboost/.env for AI features"
    echo "  4. Customize your platform settings in the admin panel"
    echo ""
    print_success "Installation completed successfully!"
}

# Main installation function
main() {
    echo -e "${BLUE}"
    cat << 'EOF'
  ____  _                  _                ____                  _   
 / ___|| |_ _ __ ___  _ __ | |__   ___ _ __ | __ )  ___   ___  ___| |_ 
 \___ \| __| '__/ _ \| '_ \| '_ \ / _ \ '_ \|  _ \ / _ \ / _ \/ __| __|
  ___) | |_| | | (_) | |_) | | | |  __/ | | | |_) | (_) | (_) \__ \ |_ 
 |____/ \__|_|  \___/| .__/|_| |_|\___|_| |_|____/ \___/ \___/|___/\__|
                     |_|                                               
        Professional Live Streaming Platform Installation
EOF
    echo -e "${NC}"
    
    # Run installation steps
    check_root
    collect_info
    update_system
    install_dependencies
    setup_database
    setup_application
    setup_cloudflare_dns
    obtain_ssl_certificate
    configure_nginx
    configure_supervisor
    configure_firewall  
    initialize_database
    create_admin_user
    start_services
    setup_ssl_renewal
    display_final_info
}

# Error handling
trap 'print_error "Installation failed at line $LINENO. Check the logs for details."' ERR

# Run main function
main "$@"