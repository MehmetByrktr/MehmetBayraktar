# Yayın Öncesi Kontrol Listesi

## Ücretsiz deployment

- GitHub repo hazır.
- Render Free Web Service oluşturuldu.
- Build Command:
  - `pip install -r requirements.txt`
- Start Command:
  - `gunicorn -w 2 -b 0.0.0.0:$PORT wsgi:app`
- Supabase project oluşturuldu.
- `DATABASE_URL` Render Environment'a eklendi.
- Cloudinary hesabı oluşturuldu.
- Cloudinary env değerleri Render'a eklendi.
- Render Environment'da şu değerler var:
  - `PYTHON_VERSION=3.11.9`
  - `SECRET_KEY`
  - `ADMIN_USERNAME`
  - `ADMIN_PASSWORD`
  - `FLASK_DEBUG=0`
  - `SESSION_COOKIE_SECURE=1`
  - `DATABASE_URL`
  - `CLOUDINARY_CLOUD_NAME`
  - `CLOUDINARY_API_KEY`
  - `CLOUDINARY_API_SECRET`
  - `CLOUDINARY_FOLDER=muhendisim`
- Render Environment'da şunlar yok:
  - `DATA_DIR=/var/data`
  - `UPLOAD_DIR=/var/data/uploads`
  - `DB_PATH=/var/data/site.db`
- Admin login test edildi.
- Blog/proje ekleme test edildi.
- Görsel yükleme test edildi.
- İletişim formu test edildi.
- `/sitemap.xml` ve `/robots.txt` kontrol edildi.
- Domain bağlandı.
- HTTPS aktif oldu.
