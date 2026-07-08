import os
import secrets
from pathlib import Path

from flask import Flask, abort, render_template, request, session, send_from_directory, url_for
from flask_login import LoginManager
from werkzeug.security import generate_password_hash
from sqlalchemy import text

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from .extensions import db
from .models import User, BlogPost, Project, SiteSetting



def normalize_database_url(value):
    """Render/Heroku tarzı postgres:// URL'lerini SQLAlchemy için normalize eder."""
    if not value:
        return ""
    value = value.strip()
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql://", 1)
    return value


def cloudinary_is_configured():
    return all(
        os.environ.get(key)
        for key in ["CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET"]
    )


def ensure_writable_directory(path, fallback):
    """Klasör yazılamıyorsa uygulamayı patlatmak yerine lokal fallback kullanır."""
    path = Path(path)
    fallback = Path(fallback)

    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return path
    except OSError:
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback



login_manager = LoginManager()
login_manager.login_view = "admin.login"
login_manager.login_message = "Admin paneline erişmek için giriş yapmalısın."


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    root_dir = Path(__file__).resolve().parent.parent

    database_url = normalize_database_url(os.environ.get("DATABASE_URL", ""))

    # Ücretsiz deployment mantığı:
    # - DATABASE_URL varsa veritabanı Supabase/Neon/Railway gibi harici Postgres'te durur.
    # - Cloudinary ayarlıysa görseller local diske yazılmaz.
    # - Local/ücretli disk kullanımında instance/ veya DATA_DIR fallback olarak çalışır.
    data_dir = Path(os.environ.get("DATA_DIR") or root_dir / "instance")
    fallback_data_dir = root_dir / "instance"

    if database_url:
        db_uri = database_url
        db_path = None
    else:
        data_dir = ensure_writable_directory(data_dir, fallback_data_dir)
        db_path = Path(os.environ.get("DB_PATH") or data_dir / "site.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_uri = f"sqlite:///{db_path}"

    uploads_dir = Path(os.environ.get("UPLOAD_DIR") or data_dir / "uploads")
    if not cloudinary_is_configured():
        uploads_dir = ensure_writable_directory(uploads_dir, fallback_data_dir / "uploads")

    is_debug = os.environ.get("FLASK_DEBUG", "0") == "1"

    secret_key = os.environ.get("SECRET_KEY", "")
    if not secret_key:
        if is_debug:
            secret_key = "dev-secret-key-change-me"
        else:
            # Prod'da SECRET_KEY unutulursa sessizce zayıf anahtarla açılmak yerine
            # rastgele güvenli bir anahtar üretilir. Bu anahtar restart'ta değişir,
            # yani oturumlar restart sonrası geçersiz kalır -- bu yüzden gerçek
            # deploymentta SECRET_KEY'i env'e eklemek şart.
            secret_key = secrets.token_hex(32)
            app.logger.warning(
                "SECRET_KEY env değişkeni tanımlı değil. Geçici rastgele bir anahtar "
                "üretildi; kalıcı oturumlar için Render/host ortamına SECRET_KEY eklemelisin."
            )

    app.config["SECRET_KEY"] = secret_key
    app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
    app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_UPLOAD_MB", "6")) * 1024 * 1024
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    app.config["UPLOAD_FOLDER"] = uploads_dir
    app.config["UPLOAD_URL_PREFIX"] = os.environ.get("UPLOAD_URL_PREFIX", "uploads")

    db.init_app(app)
    login_manager.init_app(app)

    from .routes import main_bp
    from .admin_routes import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    @app.context_processor
    def inject_site_settings():
        return {
            "site": get_site_settings(),
            "csrf_token": get_csrf_token,
            "media_url": media_url,
        }

    def media_url(value):
        """Admin'den yüklenen görselleri güvenli ve esnek şekilde URL'e çevirir.

        Desteklenen kayıt biçimleri:
        - https://res.cloudinary.com/...  -> aynen döner
        - uploads/foo.jpg                 -> /uploads/foo.jpg
        - /uploads/foo.jpg                -> aynen döner
        - static/uploads/foo.jpg          -> /uploads/foo.jpg
        - app/static/uploads/foo.jpg      -> /uploads/foo.jpg
        - css/style.css gibi statik dosya -> /static/css/style.css
        """
        if not value:
            return ""

        value = str(value).strip().replace("\\", "/")
        if value.startswith(("http://", "https://", "data:")):
            return value

        if value.startswith("/uploads/") or value.startswith("/static/"):
            return value

        for prefix in ("app/static/", "static/"):
            if value.startswith(prefix):
                value = value[len(prefix):]

        upload_prefix = str(app.config.get("UPLOAD_URL_PREFIX", "uploads")).strip("/")
        if upload_prefix and value.startswith(f"{upload_prefix}/"):
            return url_for("uploaded_file", filename=value.split("/", 1)[1])

        if "/uploads/" in value:
            return url_for("uploaded_file", filename=value.split("/uploads/", 1)[1])

        return url_for("static", filename=value)


    def get_csrf_token():
        token = session.get("_csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["_csrf_token"] = token
        return token

    @app.before_request
    def protect_mutating_requests():
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return

        # Beğeni uçları session tabanlı toggle çalıştığı için ayrı korunuyor.
        if request.endpoint in {"main.blog_like", "main.project_like"}:
            return

        expected = session.get("_csrf_token")
        submitted = request.form.get("_csrf_token") or request.headers.get("X-CSRFToken")
        if not expected or not submitted or not secrets.compare_digest(expected, submitted):
            abort(400)

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        # Site kendi CSS/JS'i dışında hiçbir harici kaynak yüklemiyor; script-src'yi 'self'
        # ile kısıtlamak, admin panelinden (rich editor "HTML kaynak" modu) yanlışlıkla ya da
        # bir hesap ele geçirilmesi durumunda kaydedilebilecek <script> enjeksiyonlarının
        # tarayıcıda çalışmasını engeller (stored XSS'e karşı ek katman).
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'self'"
        )
        if request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    @app.errorhandler(404)
    def handle_404(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def handle_403(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(413)
    def handle_413(error):
        return render_template("errors/413.html"), 413

    @app.errorhandler(500)
    def handle_500(error):
        return render_template("errors/500.html"), 500

    with app.app_context():
        db.create_all()
        migrate_database()
        seed_database()

    return app




DEFAULT_SETTINGS = {
    "site_name": "Mühendisim",
    "owner_name": "Mehmet",
    "brand_initial": "M",
    "site_logo": "",
    "favicon_image": "",
    "hero_eyebrow": "Mekatronik • Yazılım • Otomasyon",
    "hero_title": "Merhaba, ben Mehmet. Projelerimi ve teknik notlarımı burada paylaşıyorum.",
    "hero_subtitle": "Gömülü sistemler, yapay zekâ, PLC otomasyonu, IoT ve mobil uygulama geliştirme üzerine notlarımı, proje günlüklerimi ve teknik içeriklerimi sade bir arşivde topluyorum.",
    "about_title": "Merhaba, ben Mehmet.",
    "about_intro": "Mekatronik mühendisliği odağında yazılım, elektronik, otomasyon ve yapay zekâ alanlarında kendimi geliştiren bir mühendis adayıyım.",
    "about_content": "<h2>Odaklandığım Alanlar</h2><p>Gömülü sistemler, PLC otomasyonu, HMI tasarımı, Python, Flutter, kontrol sistemleri ve yapay zekâ destekli mühendislik uygulamalarıyla ilgileniyorum.</p><h2>Bu site neden var?</h2><p>Bu siteyi hem portfolyo hem de düzenli teknik not arşivi olarak kullanıyorum. Projelerimi, öğrendiklerimi, çözüm yaklaşımlarımı ve mühendislik deneyimlerimi burada topluyorum.</p><h2>Kullandığım Teknolojiler</h2><p>Python, Flask, Flutter, Dart, C/C++, MATLAB/Simulink, PLC, HMI, Arduino, sensör sistemleri ve temel yapay zekâ araçları.</p>",
    "short_about_title": "Mühendislikte öğrenmeyi, üretmeyi ve not almayı seven bir yolculuk.",
    "short_about_text": "Mekatronik mühendisliği odağında yazılım, elektronik, kontrol, otomasyon ve yapay zekâ alanlarında projeler geliştiriyorum. Bu site hem portfolyo hem de teknik not arşivi olarak tasarlandı.",
    "contact_title": "Benimle iletişime geç.",
    "contact_text": "Proje, iş birliği, teknik soru veya geri bildirim için mesaj bırakabilirsin.",
    "email": "mail@example.com",
    "github_url": "https://github.com/",
    "linkedin_url": "https://www.linkedin.com/",
    "instagram_url": "",
    "x_url": "",
    "location": "İstanbul, Türkiye",
}


def get_site_settings():
    settings = DEFAULT_SETTINGS.copy()
    try:
        for item in SiteSetting.query.all():
            settings[item.key] = item.value
    except Exception:
        pass
    return settings


def seed_settings():
    for key, value in DEFAULT_SETTINGS.items():
        if not SiteSetting.query.filter_by(key=key).first():
            db.session.add(SiteSetting(key=key, value=value))



def migrate_database():
    """SQLite için basit kolon ekleme migrasyonu.
    Harici Postgres/Supabase kullanımında db.create_all fresh schema için yeterli tutulur.
    """
    if db.engine.dialect.name != "sqlite":
        return

    migrations = {
        "blog_post": {
            "meta_description": "VARCHAR(260) DEFAULT ''",
            "reading_time": "INTEGER DEFAULT 1",
            "view_count": "INTEGER DEFAULT 0",
            "like_count": "INTEGER DEFAULT 0",
            "is_featured": "BOOLEAN DEFAULT 0",
        },
        "project": {
            "meta_description": "VARCHAR(260) DEFAULT ''",
            "reading_time": "INTEGER DEFAULT 1",
            "view_count": "INTEGER DEFAULT 0",
            "like_count": "INTEGER DEFAULT 0",
            "is_featured": "BOOLEAN DEFAULT 0",
        },
        "message": {
            "is_read": "BOOLEAN DEFAULT 0",
        },
    }

    for table, columns in migrations.items():
        existing = {
            row[1] for row in db.session.execute(text(f"PRAGMA table_info({table})")).fetchall()
        }

        for column, definition in columns.items():
            if column not in existing:
                db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))

    db.session.commit()


def seed_database():
    from flask import current_app

    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    is_debug = os.environ.get("FLASK_DEBUG", "0") == "1"

    if not admin_password:
        if is_debug:
            admin_password = "admin123"
        else:
            # Prod'da ADMIN_PASSWORD unutulmuşsa "admin123" ile canlıya çıkmak yerine
            # rastgele güçlü bir şifre üretip loglara bir kereliğine yazıyoruz.
            admin_password = secrets.token_urlsafe(12)
            current_app.logger.warning(
                "ADMIN_PASSWORD env değişkeni tanımlı değil. Geçici admin şifresi "
                "üretildi: %s -- lütfen giriş yaptıktan sonra Hesap sayfasından "
                "değiştir ve host ortamına ADMIN_PASSWORD ekle.",
                admin_password,
            )

    if not User.query.filter_by(username=admin_username).first():
        user = User(
            username=admin_username,
            password_hash=generate_password_hash(admin_password)
        )
        db.session.add(user)

    if BlogPost.query.count() == 0:
        samples = [
            BlogPost(
                title="Gömülü Sistemlerde Başlangıç Rehberi",
                slug="gomulu-sistemlerde-baslangic-rehberi",
                summary="Mikrodenetleyici, sensör, haberleşme protokolleri ve proje geliştirme mantığına kısa bir giriş.",
                content="""<p>Gömülü sistemler; donanım ve yazılımın birlikte çalıştığı, belirli bir görevi yerine getirmek için tasarlanan sistemlerdir.</p>
                <p>Bu alanda ilerlemek için C/C++, temel elektronik, mikrodenetleyiciler, haberleşme protokolleri ve test mantığı birlikte öğrenilmelidir.</p>""",
                category="Gömülü Sistemler",
                tags="Embedded, Arduino, STM32, Elektronik",
                status="published",
                meta_description="Mühendislik odaklı teknik not ve proje açıklaması.",
                reading_time=1,
                view_count=0,
                like_count=0,
                is_featured=False
            ),
            BlogPost(
                title="PLC ile Fabrika Otomasyonuna Giriş",
                slug="plc-ile-fabrika-otomasyonuna-giris",
                summary="PLC, HMI, sensörler ve alarm senaryoları üzerinden otomasyon sistemlerinin temel mantığı.",
                content="""<p>PLC sistemleri endüstriyel otomasyonun merkezinde yer alır. Sensörlerden gelen sinyaller değerlendirilir ve çıkış elemanları kontrol edilir.</p>
                <p>Bir otomasyon projesinde güvenlik senaryoları, manuel/otomatik modlar ve hata durumları dikkatli tasarlanmalıdır.</p>""",
                category="Otomasyon",
                tags="PLC, HMI, Endüstri, Otomasyon",
                status="published",
                meta_description="Mühendislik odaklı teknik not ve proje açıklaması.",
                reading_time=1,
                view_count=0,
                like_count=0,
                is_featured=False
            ),
            BlogPost(
                title="Yapay Zekâ Projelerinde Veri Mantığı",
                slug="yapay-zeka-projelerinde-veri-mantigi",
                summary="Bir yapay zekâ projesinde veri toplama, etiketleme, model seçimi ve değerlendirme adımları.",
                content="""<p>Yapay zekâ projelerinde modelden önce veri kalitesi gelir. Hatalı veya dengesiz veri, güçlü modellerde bile kötü sonuçlara neden olabilir.</p>
                <p>Bu nedenle veri seti, problem tanımı ve başarı metriği en başta netleştirilmelidir.</p>""",
                category="Yapay Zekâ",
                tags="AI, Machine Learning, Python, Veri",
                status="published",
                meta_description="Mühendislik odaklı teknik not ve proje açıklaması.",
                reading_time=1,
                view_count=0,
                like_count=0,
                is_featured=False
            ),
        ]
        db.session.add_all(samples)

    if Project.query.count() == 0:
        projects = [
            Project(
                title="Factory Emergency & Security Automation",
                slug="factory-emergency-security-automation",
                summary="PLC + HMI tabanlı yangın, gaz, su baskını ve güvenlik otomasyonu.",
                content="""<p>Bu projede fabrika ortamında acil durumların algılanması ve HMI üzerinden izlenmesi hedeflenmiştir.</p>
                <p>Yangın, gaz, su baskını ve güvenlik senaryoları ayrı modüller halinde tasarlanmıştır.</p>""",
                technologies="PLC, HMI, FPWIN Pro, EBPro",
                github_url="",
                demo_url="",
                status="published",
                meta_description="Mühendislik odaklı teknik not ve proje açıklaması.",
                reading_time=1,
                view_count=0,
                like_count=0,
                is_featured=False
            ),
            Project(
                title="Sniper Localization with TDOA-CNN",
                slug="sniper-localization-tdoa-cnn",
                summary="Mikrofon dizisi ile ses kaynağı yön ve konum tahmini üzerine yapay zekâ destekli proje.",
                content="""<p>TDOA yaklaşımı ve CNN modeli kullanılarak ses kaynağının konumlandırılması amaçlanmıştır.</p>""",
                technologies="Python, CNN, Signal Processing, TDOA",
                github_url="",
                demo_url="",
                status="published",
                meta_description="Mühendislik odaklı teknik not ve proje açıklaması.",
                reading_time=1,
                view_count=0,
                like_count=0,
                is_featured=False
            ),
            Project(
                title="Flutter Engineering Calculator",
                slug="flutter-engineering-calculator",
                summary="Mühendislik hesaplamaları için modüler Flutter mobil uygulama.",
                content="""<p>Flutter ile mekanik, elektrik, otomasyon ve temel mühendislik hesaplarını bir araya getiren mobil uygulama.</p>""",
                technologies="Flutter, Dart, Mobile App",
                github_url="",
                demo_url="",
                status="published",
                meta_description="Mühendislik odaklı teknik not ve proje açıklaması.",
                reading_time=1,
                view_count=0,
                like_count=0,
                is_featured=False
            ),
        ]
        db.session.add_all(projects)

    db.session.commit()
