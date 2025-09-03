#!/bin/bash

# GitHub PR Rules Analyzer Deployment Script
# This script handles the deployment of the application to production

set -e

# Configuration
APP_NAME="github-pr-rules-analyzer"
APP_DIR="/opt/$APP_NAME"
SERVICE_FILE="/etc/systemd/system/$APP_NAME.service"
NGINX_CONFIG="/etc/nginx/sites-available/$APP_NAME"
PYTHON_VENV="$APP_DIR/venv"
DATABASE_FILE="$APP_DIR/app.db"
LOG_DIR="$APP_DIR/logs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   error "This script must be run as root"
fi

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --app-dir)
            APP_DIR="$2"
            shift 2
            ;;
        --venv-dir)
            PYTHON_VENV="$2"
            shift 2
            ;;
        --db-file)
            DATABASE_FILE="$2"
            shift 2
            ;;
        --log-dir)
            LOG_DIR="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --app-dir DIR         Application directory (default: /opt/github-pr-rules-analyzer)"
            echo "  --venv-dir DIR        Python virtual environment directory (default: /opt/github-pr-rules-analyzer/venv)"
            echo "  --db-file FILE        Database file path (default: /opt/github-pr-rules-analyzer/app.db)"
            echo "  --log-dir DIR         Log directory (default: /opt/github-pr-rules-analyzer/logs)"
            echo "  --help                Show this help message"
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
done

# Create application directory
log "Creating application directory: $APP_DIR"
mkdir -p "$APP_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$(dirname "$DATABASE_FILE")"

# Copy application files
log "Copying application files..."
cp -r . "$APP_DIR/"
cd "$APP_DIR"

# Create Python virtual environment
log "Creating Python virtual environment..."
python3 -m venv "$PYTHON_VENV"
source "$PYTHON_VENV/bin/activate"

# Install dependencies
log "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create environment configuration
log "Creating environment configuration..."
cat > "$APP_DIR/.env" << EOF
# Application Configuration
APP_NAME=github-pr-rules-analyzer
DEBUG=False
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO

# Database Configuration
DATABASE_URL=sqlite:///$DATABASE_FILE

# GitHub API Configuration
GITHUB_TOKEN=${GITHUB_TOKEN:-}
GITHUB_API_BASE_URL=https://api.github.com

# LLM Service Configuration
LLM_API_KEY=${LLM_API_KEY:-}
LLM_API_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4
LLM_MAX_TOKENS=1000
LLM_TEMPERATURE=0.3

# Security Configuration
SECRET_KEY=${SECRET_KEY:-$(python3 -c 'import secrets; print(secrets.token_hex(32))')}

# Logging Configuration
LOG_FILE=$LOG_DIR/app.log
LOG_LEVEL=INFO
LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s
EOF

# Create systemd service file
log "Creating systemd service file..."
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=GitHub PR Rules Analyzer
After=network.target

[Service]
Type=exec
User=www-data
Group=www-data
WorkingDirectory=$APP_DIR
Environment=PATH=$PYTHON_VENV/bin
ExecStart=$PYTHON_VENV/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=$APP_DIR $LOG_DIR $(dirname "$DATABASE_FILE")
ProtectHome=true
RemoveIPC=true

[Install]
WantedBy=multi-user.target
EOF

# Create nginx configuration
log "Creating nginx configuration..."
cat > "$NGINX_CONFIG" << EOF
server {
    listen 80;
    server_name _;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Static files
    location /static/ {
        alias $APP_DIR/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # API endpoints
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # Timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    # Main application
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # Timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;
}

# HTTPS redirect (uncomment if SSL is configured)
# server {
#     listen 443 ssl http2;
#     server_name _;
#
#     ssl_certificate /path/to/your/cert.pem;
#     ssl_certificate_key /path/to/your/key.pem;
#
#     # SSL configuration
#     ssl_protocols TLSv1.2 TLSv1.3;
#     ssl_ciphers HIGH:!aNULL:!MD5;
#     ssl_prefer_server_ciphers on;
#
#     # Include the same location blocks as above
# }
EOF

# Enable and start the service
log "Enabling and starting the service..."
systemctl daemon-reload
systemctl enable "$APP_NAME"
systemctl start "$APP_NAME"

# Enable nginx site
log "Enabling nginx site..."
ln -sf "$NGINX_CONFIG" "/etc/nginx/sites-enabled/$APP_NAME"
nginx -t && systemctl reload nginx

# Set proper permissions
log "Setting file permissions..."
chown -R www-data:www-data "$APP_DIR"
chmod -R 755 "$APP_DIR"
chmod 644 "$SERVICE_FILE"
chmod 644 "$NGINX_CONFIG"
chmod 600 "$APP_DIR/.env"

# Create log rotation
log "Setting up log rotation..."
cat > "/etc/logrotate.d/$APP_NAME" << EOF
$LOG_DIR/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 www-data www-data
    postrotate
        systemctl reload $APP_NAME
    endscript
}
EOF

# Create backup script
log "Creating backup script..."
cat > "$APP_DIR/backup.sh" << EOF
#!/bin/bash

# Backup script for GitHub PR Rules Analyzer
BACKUP_DIR="/var/backups/$APP_NAME"
DATE=\$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="\$BACKUP_DIR/backup_\$DATE.tar.gz"

# Create backup directory
mkdir -p "\$BACKUP_DIR"

# Create backup
tar -czf "\$BACKUP_FILE" \\
    -C "$(dirname "$DATABASE_FILE")" "$(basename "$DATABASE_FILE")" \\
    -C "$APP_DIR" logs \\
    -C "$APP_DIR" .env

# Keep only last 7 days of backups
find "\$BACKUP_DIR" -name "backup_*.tar.gz" -mtime +7 -delete

echo "Backup created: \$BACKUP_FILE"
EOF

chmod +x "$APP_DIR/backup.sh"

# Create cron job for backups
log "Setting up automated backups..."
(crontab -l 2>/dev/null; echo "0 2 * * * $APP_DIR/backup.sh") | crontab -

# Create health check script
log "Creating health check script..."
cat > "$APP_DIR/health_check.sh" << EOF
#!/bin/bash

# Health check script for GitHub PR Rules Analyzer
HEALTH_URL="http://localhost:8000/api/v1/health"
RESPONSE=\$(curl -s -o /dev/null -w "%{http_code}" "\$HEALTH_URL")

if [ "\$RESPONSE" -eq 200 ]; then
    echo "Service is healthy"
    exit 0
else
    echo "Service is unhealthy (HTTP \$RESPONSE)"
    exit 1
fi
EOF

chmod +x "$APP_DIR/health_check.sh"

# Create monitoring script
log "Creating monitoring script..."
cat > "$APP_DIR/monitor.sh" << EOF
#!/bin/bash

# Monitoring script for GitHub PR Rules Analyzer
LOG_FILE="$LOG_DIR/monitor.log"
DATE=\$(date '+%Y-%m-%d %H:%M:%S')

# Check if service is running
if ! systemctl is-active --quiet "$APP_NAME"; then
    echo "[\$DATE] ERROR: Service $APP_NAME is not running" >> "\$LOG_FILE"
    systemctl restart "$APP_NAME"
    echo "[\$DATE] INFO: Attempted to restart service" >> "\$LOG_FILE"
fi

# Check disk space
DISK_USAGE=\$(df "$APP_DIR" | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "\$DISK_USAGE" -gt 90 ]; then
    echo "[\$DATE] WARNING: Disk usage is \${DISK_USAGE}%" >> "\$LOG_FILE"
fi

# Check database size
DB_SIZE=\$(du -h "$DATABASE_FILE" | cut -f1)
echo "[\$DATE] INFO: Database size: \$DB_SIZE" >> "\$LOG_FILE"

# Check log file size
LOG_SIZE=\$(du -h "$LOG_DIR/app.log" | cut -f1)
echo "[\$DATE] INFO: Log file size: \$LOG_SIZE" >> "\$LOG_FILE"
EOF

chmod +x "$APP_DIR/monitor.sh"

# Add to cron job for monitoring
(crontab -l 2>/dev/null; echo "*/5 * * * * $APP_DIR/monitor.sh") | crontab -

# Create update script
log "Creating update script..."
cat > "$APP_DIR/update.sh" << EOF
#!/bin/bash

# Update script for GitHub PR Rules Analyzer
set -e

APP_DIR="$APP_DIR"
PYTHON_VENV="$PYTHON_VENV"
SERVICE_FILE="$SERVICE_FILE"

log() {
    echo "[\$(date '+%Y-%m-%d %H:%M:%S')] \$1"
}

# Stop the service
log "Stopping service..."
systemctl stop "$APP_NAME"

# Backup current version
log "Creating backup..."
$APP_DIR/backup.sh

# Update application files
log "Updating application files..."
cd "$APP_DIR"
git pull origin main

# Update dependencies
log "Updating dependencies..."
source "$PYTHON_VENV/bin/activate"
pip install -r requirements.txt

# Restart the service
log "Starting service..."
systemctl start "$APP_NAME"

# Verify service is running
sleep 5
if systemctl is-active --quiet "$APP_NAME"; then
    log "Service updated successfully"
else
    log "ERROR: Service failed to start after update"
    systemctl status "$APP_NAME"
    exit 1
fi
EOF

chmod +x "$APP_DIR/update.sh"

# Display completion message
log "Deployment completed successfully!"
log "Application is running at: http://localhost"
log "Service status: systemctl status $APP_NAME"
log "Access logs: journalctl -u $APP_NAME -f"
log "Application logs: tail -f $LOG_DIR/app.log"

echo ""
echo "Configuration files created:"
echo "  - Service: $SERVICE_FILE"
echo "  - Nginx: $NGINX_CONFIG"
echo "  - Environment: $APP_DIR/.env"
echo ""
echo "Scripts created:"
echo "  - Backup: $APP_DIR/backup.sh"
echo "  - Health Check: $APP_DIR/health_check.sh"
echo "  - Monitoring: $APP_DIR/monitor.sh"
echo "  - Update: $APP_DIR/update.sh"
echo ""
echo "Next steps:"
echo "1. Edit $APP_DIR/.env with your configuration"
echo "2. Set GitHub API token: export GITHUB_TOKEN=your_token"
echo "3. Set LLM API key: export LLM_API_KEY=your_key"
echo "4. Restart the service: systemctl restart $APP_NAME"
echo "5. Check service status: systemctl status $APP_NAME"
