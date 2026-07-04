# Mühendisim V30 Render Deploy Ready

Bu sürüm deployment için hazırlandı.

## Eklenenler
- Render Blueprint: `render.yaml`
- Procfile
- Persistent disk uyumluluğu:
  - `DATA_DIR`
  - `UPLOAD_DIR`
  - `DB_PATH`
  - `UPLOAD_URL_PREFIX`
- `/uploads/<dosya>` route'u eklendi; yüklenen görseller persistent diskten servis edilir.
- `scripts/backup.sh`
- `scripts/make_secret.py`
- `scripts/smoke_test.py`
- `DEPLOY_RENDER.md`
- `DEPLOY_VPS.md`
- `.gitignore`
- Güncellenmiş `.env.example`
- Güncellenmiş yayın kontrol listesi
