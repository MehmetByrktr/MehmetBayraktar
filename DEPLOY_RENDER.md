# Render ile Yayına Alma

Bu paket Render için hazırlandı.

## Neden Render?

Render, Flask uygulamasını GitHub üzerinden deploy edebilir. Custom domain ekleyince TLS/HTTPS sertifikasını otomatik oluşturup yeniler. Bu proje SQLite veritabanı ve yüklenen görseller kullandığı için kalıcı disk gerekir.

## 1. GitHub'a yükle

```bash
git init
git add .
git commit -m "launch ready"
git branch -M main
git remote add origin https://github.com/KULLANICI_ADIN/muhendisim.git
git push -u origin main
```

## 2. Render servis oluştur

Render Dashboard > New > Web Service > GitHub repo seç.

Ayarlar:

```text
Runtime: Python
Build Command: pip install -r requirements.txt
Start Command: gunicorn -w 2 -b 0.0.0.0:$PORT wsgi:app
Health Check Path: /
```

Bu pakette `render.yaml` var. Blueprint ile kurarsan bu ayarların çoğunu otomatik alır.

## 3. Persistent Disk

Disk ekle:

```text
Mount Path: /var/data
Size: 1 GB
```

Environment variables:

```text
DATA_DIR=/var/data
UPLOAD_DIR=/var/data/uploads
DB_PATH=/var/data/site.db
UPLOAD_URL_PREFIX=uploads
FLASK_DEBUG=0
SESSION_COOKIE_SECURE=1
MAX_UPLOAD_MB=6
SECRET_KEY=<uzun-rastgele-key>
ADMIN_USERNAME=<admin-kullanici>
ADMIN_PASSWORD=<guclu-sifre>
```

`SECRET_KEY` için:

```bash
python scripts/make_secret.py
```

## 4. İlk giriş

```text
https://SENIN-SERVISIN.onrender.com/admin/login
```

Giriş yaptıktan sonra Admin > Hesap / Şifre kısmından şifreyi yeniden değiştir.

## 5. Domain bağlama

Render Dashboard > Service > Settings > Custom Domains.

Domain ekle, Render'ın verdiği DNS kaydını domain sağlayıcında tanımla. Render domain doğrulanınca HTTPS/TLS'i otomatik yönetir.

## 6. Yedek

Render disk kullandığında veritabanı ve yüklemeler `/var/data` altında kalır. Ara ara backup al:

```bash
DATA_DIR=/var/data UPLOAD_DIR=/var/data/uploads BACKUP_DIR=/var/data/backups bash scripts/backup.sh
```

## 7. Kontrol

Yayından sonra kontrol et:

```text
/
 /admin/login
 /sitemap.xml
 /robots.txt
 /uploads/<yüklenen-dosya>
```
