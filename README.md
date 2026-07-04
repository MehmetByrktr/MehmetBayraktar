# Mühendisim

Siyah uzay temalı mühendislik blog + proje portfolyo sitesi.

## Lokal kurulum

```bash
cd muhendisim_glass_blog
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Mac/Linux

pip install -r requirements.txt
copy .env.example .env
python run.py
```

Site:
```text
http://127.0.0.1:5000
```

Admin:
```text
http://127.0.0.1:5000/admin/login
```

## Yayın öncesi zorunlu işler

`.env` dosyasındaki değerleri değiştir:

```text
SECRET_KEY
ADMIN_USERNAME
ADMIN_PASSWORD
FLASK_DEBUG=0
SESSION_COOKIE_SECURE=1  # HTTPS aktifken
```

## Production çalıştırma örneği

```bash
gunicorn -w 2 -b 0.0.0.0:8000 wsgi:app
```

## Son sürümde eklenen yayın hazırlıkları

- Public navbar’dan admin linki kaldırıldı.
- CSRF koruması eklendi.
- İletişim formuna honeypot spam koruması eklendi.
- Login denemeleri için basit brute-force yavaşlatma eklendi.
- Upload dosya tipi kontrolü eklendi.
- Maksimum upload boyutu ayarlanabilir hale geldi.
- Güvenlik header’ları eklendi.
- Mesaj silme, tümünü okundu yapma ve okunmadı yapma eklendi.
- Admin şifre değiştirme sayfası eklendi.
- Gizlilik ve çerez politikası sayfaları eklendi.
- Blog/proje beğenileri toggle mantığına alındı.
