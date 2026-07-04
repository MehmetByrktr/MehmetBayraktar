# Yayın Öncesi Kontrol Listesi

## Render önerilen ayarlar
- GitHub repo hazır.
- Render Web Service oluşturuldu.
- Start Command: `gunicorn -w 2 -b 0.0.0.0:$PORT wsgi:app`
- Persistent Disk eklendi:
  - Mount Path: `/var/data`
  - Size: `1 GB`
- Environment variables girildi:
  - `SECRET_KEY`
  - `ADMIN_USERNAME`
  - `ADMIN_PASSWORD`
  - `FLASK_DEBUG=0`
  - `SESSION_COOKIE_SECURE=1`
  - `DATA_DIR=/var/data`
  - `UPLOAD_DIR=/var/data/uploads`
  - `DB_PATH=/var/data/site.db`
  - `UPLOAD_URL_PREFIX=uploads`
- Admin login test edildi.
- İletişim formu test edildi.
- Görsel yükleme test edildi.
- `/sitemap.xml` ve `/robots.txt` kontrol edildi.
- Domain bağlandı.
- HTTPS aktif oldu.
- Google Search Console'a sitemap gönderildi.

## Yedek
```bash
DATA_DIR=/var/data UPLOAD_DIR=/var/data/uploads BACKUP_DIR=/var/data/backups bash scripts/backup.sh
```
