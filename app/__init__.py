import os
import secrets
from pathlib import Path

from flask import Flask, abort, request, session, send_from_directory
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


login_manager = LoginManager()
login_manager.login_view = "admin.login"
login_manager.login_message = "Admin paneline erişmek için giriş yapmalısın."


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    root_dir = Path(__file__).resolve().parent.parent

    # Production persistence:
    # Render/VPS gibi ortamlarda DATA_DIR kalıcı diske işaret eder.
    # Lokal geliştirmede instance/ kullanılır.
    data_dir = Path(os.environ.get("DATA_DIR", root_dir / "instance"))
    uploads_dir = Path(os.environ.get("UPLOAD_DIR", data_dir / "uploads"))
    db_path = Path(os.environ.get("DB_PATH", data_dir / "site.db"))

    data_dir.mkdir(parents=True, exist_ok=True)
    uploads_dir.mkdir(parents=True, exist_ok=True)

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", f"sqlite:///{db_path}")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
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
        return {"site": get_site_settings(), "csrf_token": get_csrf_token}


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
        if request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

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
    db.create_all mevcut tabloları değiştirmez; bu yüzden yeni SEO kolonlarını eldeki DB'ye ekliyoruz.
    """
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
    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")

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
