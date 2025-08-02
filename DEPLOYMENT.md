# StrophenBoost Deployment Guide

## Quick Installation

For a complete automated installation with SSL certificates, use the provided installation script:

```bash
# Make the script executable and run it
chmod +x install.sh
./install.sh
```

The script will automatically:
- Install all system dependencies (Python, PostgreSQL, Nginx, FFmpeg, etc.)
- Configure SSL certificates via Let's Encrypt with DNS verification
- Set up the database and application
- Configure Nginx as a reverse proxy
- Set up process management with Supervisor
- Configure firewall rules
- Create an admin user account

## Prerequisites

### System Requirements
- Ubuntu 20.04+ or Debian 11+ (VPS/Server)
- Minimum 2GB RAM, 2 CPU cores
- 20GB+ storage space
- Root or sudo access

### DNS Configuration
- Domain name pointing to your server IP
- Cloudflare DNS management (for automated SSL)

### Required Information
Before running the installation script, prepare:

1. **Domain Name**: Your streaming platform domain (e.g., `streaming.example.com`)
2. **Email Address**: For Let's Encrypt notifications
3. **Cloudflare API Token**: 
   - Go to https://dash.cloudflare.com/profile/api-tokens
   - Create a token with `Zone:Edit` permissions for your domain

## Installation Process

### 1. Download and Prepare
```bash
# Download the project files to your server
git clone <your-repo-url> strophenboost
cd strophenboost

# Make the installation script executable
chmod +x install.sh
```

### 2. Run Installation
```bash
./install.sh
```

The script will prompt you for:
- Your domain name
- Email address for SSL certificates
- Cloudflare API token

### 3. Post-Installation
After successful installation:

1. **Access Your Platform**: Visit `https://yourdomain.com`
2. **Login as Admin**: Use the credentials shown at the end of installation
3. **Configure Streaming**: Visit `/streaming/setup` for software configuration guides
4. **Add API Keys**: Edit `/opt/strophenboost/.env` to add your Gemini API key for AI features

## Manual Installation (Advanced)

If you prefer manual installation or need custom configuration:

### 1. System Dependencies
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib nginx certbot ffmpeg git curl
```

### 2. Database Setup
```bash
sudo -u postgres createuser --interactive strophenboost
sudo -u postgres createdb strophenboost -O strophenboost
```

### 3. Application Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install flask flask-sqlalchemy flask-login flask-socketio flask-cors gunicorn psycopg2-binary
```

### 4. SSL Certificate (Manual)
```bash
# Install Cloudflare plugin
sudo apt install python3-certbot-dns-cloudflare

# Create credentials file
sudo nano /etc/letsencrypt/cloudflare.ini
# Add: dns_cloudflare_api_token = YOUR_TOKEN

# Obtain certificate
sudo certbot certonly --dns-cloudflare --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini -d yourdomain.com
```

## Configuration Files

### Nginx Configuration
Located at `/etc/nginx/sites-available/strophenboost`
- Handles HTTPS termination
- Proxies requests to Flask application
- Serves static files and streaming content
- Includes security headers

### Supervisor Configuration
Located at `/etc/supervisor/conf.d/strophenboost.conf`
- Manages Flask application process
- Manages RTMP server process
- Automatic restart on failure
- Logging configuration

### Environment Variables
Located at `/opt/strophenboost/.env`
- Database connection settings
- Flask secret keys
- API keys and tokens
- Domain configuration

## Service Management

### Check Service Status
```bash
sudo supervisorctl status strophenboost
sudo systemctl status nginx
```

### Restart Services
```bash
sudo supervisorctl restart strophenboost
sudo systemctl restart nginx
```

### View Logs
```bash
# Application logs
tail -f /var/log/strophenboost/app.log

# RTMP server logs
tail -f /var/log/strophenboost/rtmp.log

# Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

## Firewall Configuration

The installation script configures UFW with these rules:
- Port 22 (SSH)
- Port 80 (HTTP) - redirects to HTTPS
- Port 443 (HTTPS)
- Port 1935 (RTMP)
- Port 8080 (Monitoring - optional)

## SSL Certificate Management

### Automatic Renewal
Certificates auto-renew via cron job. Test renewal:
```bash
sudo certbot renew --dry-run
```

### Manual Renewal
```bash
sudo certbot renew
sudo systemctl reload nginx
```

## Troubleshooting

### Common Issues

#### RTMP Connection Issues
1. Check firewall: `sudo ufw status`
2. Verify RTMP server: `sudo supervisorctl status strophenboost-rtmp`
3. Test port: `telnet your-domain.com 1935`

#### SSL Certificate Issues
1. Verify DNS propagation: `nslookup your-domain.com`
2. Check Cloudflare API token permissions
3. Verify domain ownership in Cloudflare

#### Database Connection Issues
1. Check PostgreSQL status: `sudo systemctl status postgresql`
2. Verify database credentials in `.env` file
3. Test connection: `psql -h localhost -U strophenboost -d strophenboost`

### Log Locations
- Application: `/var/log/strophenboost/app.log`
- RTMP Server: `/var/log/strophenboost/rtmp.log`
- Nginx: `/var/log/nginx/`
- PostgreSQL: `/var/log/postgresql/`

## Performance Optimization

### For High Traffic
1. Increase Gunicorn workers in Supervisor config
2. Configure Nginx caching for static content
3. Set up PostgreSQL connection pooling
4. Consider Redis for session storage

### For Multiple Streams
1. Increase system file limits
2. Optimize FFmpeg settings for your hardware
3. Configure load balancing if needed
4. Monitor disk space for stream recordings

## Security Best Practices

1. **Keep System Updated**: Regular `apt update && apt upgrade`
2. **Monitor Logs**: Set up log monitoring and alerts
3. **Backup Database**: Regular PostgreSQL backups
4. **Secure SSH**: Use key-based authentication, disable password login
5. **Monitor Resources**: Set up system monitoring (CPU, RAM, disk)

## Scaling Considerations

### Horizontal Scaling
- Load balancer (HAProxy/Nginx)
- Multiple application servers
- Shared database server
- Distributed file storage for streams

### Vertical Scaling
- Increase server resources
- Optimize database performance
- Use SSD storage for better I/O
- Configure Nginx caching

## Support

If you encounter issues during deployment:
1. Check the logs for error messages
2. Verify all prerequisites are met
3. Ensure DNS configuration is correct
4. Confirm API tokens have proper permissions

For additional help, consult the application documentation or create an issue in the project repository.