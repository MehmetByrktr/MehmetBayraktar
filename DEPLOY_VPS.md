# VPS ile Yayına Alma

Render yerine VPS kullanacaksan örnek akış:

```bash
sudo apt update
sudo apt install python3-venv python3-pip nginx certbot python3-certbot-nginx -y

cd /var/www
git clone https://github.com/KULLANICI_ADIN/muhendisim.git
cd muhendisim
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env`:

```text
SECRET_KEY=<uzun-rastgele-key>
ADMIN_USERNAME=<admin>
ADMIN_PASSWORD=<guclu-sifre>
FLASK_DEBUG=0
SESSION_COOKIE_SECURE=1
DATA_DIR=/var/www/muhendisim/data
UPLOAD_DIR=/var/www/muhendisim/data/uploads
DB_PATH=/var/www/muhendisim/data/site.db
UPLOAD_URL_PREFIX=uploads
```

Gunicorn test:

```bash
gunicorn -w 2 -b 127.0.0.1:8000 wsgi:app
```

Systemd servis örneği:

```ini
[Unit]
Description=Muhendisim Flask App
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/muhendisim
EnvironmentFile=/var/www/muhendisim/.env
ExecStart=/var/www/muhendisim/.venv/bin/gunicorn -w 2 -b 127.0.0.1:8000 wsgi:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Nginx örneği:

```nginx
server {
    server_name example.com www.example.com;

    client_max_body_size 8M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

SSL:

```bash
sudo certbot --nginx -d example.com -d www.example.com
```
