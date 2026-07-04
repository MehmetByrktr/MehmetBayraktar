from functools import wraps
from pathlib import Path
from time import time
from uuid import uuid4

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from slugify import slugify
from sqlalchemy import or_
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .models import User, BlogPost, Project, Message, SiteSetting
from . import DEFAULT_SETTINGS, get_site_settings
from .routes import calculate_reading_time


admin_bp = Blueprint("admin", __name__)
_LOGIN_ATTEMPTS = {}
ALLOWED_UPLOAD_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

@admin_bp.context_processor
def inject_admin_badges():
    try:
        if current_user.is_authenticated:
            return {"unread_message_count": Message.query.filter_by(is_read=False).count()}
    except Exception:
        pass
    return {"unread_message_count": 0}



def save_upload(file):
    if not file or not file.filename:
        return None

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        flash("Yalnızca JPG, PNG, WEBP veya GIF görsel yükleyebilirsin.", "danger")
        return None

    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{uuid4().hex}{extension}"
    target = upload_dir / safe_name
    file.save(target)

    return f"{current_app.config.get('UPLOAD_URL_PREFIX', 'uploads')}/{safe_name}"


def make_unique_slug(model, base_slug, current_id=None):
    clean_slug = slugify(base_slug or "icerik") or "icerik"
    candidate = clean_slug
    counter = 2

    while True:
        query = model.query.filter_by(slug=candidate)
        if current_id is not None:
            query = query.filter(model.id != current_id)

        if not query.first():
            return candidate

        candidate = f"{clean_slug}-{counter}"
        counter += 1


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    client_key = request.headers.get("X-Forwarded-For", request.remote_addr or "local").split(",")[0].strip()
    attempt = _LOGIN_ATTEMPTS.get(client_key, {"count": 0, "last": 0})
    locked = attempt["count"] >= 5 and (time() - attempt["last"]) < 15 * 60

    if request.method == "POST":
        if locked:
            flash("Çok fazla hatalı deneme yapıldı. 15 dakika sonra tekrar dene.", "danger")
            return render_template("admin/login.html")

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            _LOGIN_ATTEMPTS.pop(client_key, None)
            login_user(user)
            return redirect(url_for("admin.dashboard"))

        _LOGIN_ATTEMPTS[client_key] = {"count": attempt["count"] + 1, "last": time()}
        flash("Kullanıcı adı veya şifre hatalı.", "danger")

    return render_template("admin/login.html")


@admin_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("admin.login"))


@admin_bp.route("/")
@login_required
def dashboard():
    published_blogs = BlogPost.query.filter_by(status="published").count()
    draft_blogs = BlogPost.query.filter_by(status="draft").count()
    published_projects = Project.query.filter_by(status="published").count()
    draft_projects = Project.query.filter_by(status="draft").count()

    total_blog_views = sum((item.view_count or 0) for item in BlogPost.query.all())
    total_project_views = sum((item.view_count or 0) for item in Project.query.all())
    total_blog_likes = sum((item.like_count or 0) for item in BlogPost.query.all())
    total_project_likes = sum((item.like_count or 0) for item in Project.query.all())

    stats = {
        "blogs": BlogPost.query.count(),
        "projects": Project.query.count(),
        "messages": Message.query.count(),
        "unread_messages": Message.query.filter_by(is_read=False).count(),
        "draft_blogs": draft_blogs,
        "published_blogs": published_blogs,
        "draft_projects": draft_projects,
        "published_projects": published_projects,
        "total_views": total_blog_views + total_project_views,
        "total_likes": total_blog_likes + total_project_likes,
    }

    chart_data = {
        "status": {
            "labels": ["Yayındaki Blog", "Taslak Blog", "Yayındaki Proje", "Taslak Proje"],
            "values": [published_blogs, draft_blogs, published_projects, draft_projects],
        },
        "engagement": {
            "labels": ["Blog Görüntülenme", "Proje Görüntülenme", "Toplam Beğeni", "Mesaj"],
            "values": [total_blog_views, total_project_views, total_blog_likes + total_project_likes, Message.query.count()],
        }
    }

    top_blogs = BlogPost.query.order_by(BlogPost.view_count.desc()).limit(5).all()
    top_projects = Project.query.order_by(Project.view_count.desc()).limit(5).all()
    latest_messages = Message.query.order_by(Message.created_at.desc()).limit(5).all()

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        chart_data=chart_data,
        top_blogs=top_blogs,
        top_projects=top_projects,
        latest_messages=latest_messages
    )


@admin_bp.route("/blogs")
@login_required
def blogs():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    category = request.args.get("category", "").strip()

    query = BlogPost.query

    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                BlogPost.title.ilike(like),
                BlogPost.summary.ilike(like),
                BlogPost.content.ilike(like),
                BlogPost.tags.ilike(like),
            )
        )

    if status:
        query = query.filter(BlogPost.status == status)

    if category:
        query = query.filter(BlogPost.category == category)

    posts = query.order_by(BlogPost.created_at.desc()).all()

    categories = [
        row[0] for row in db.session.query(BlogPost.category)
        .distinct()
        .order_by(BlogPost.category.asc())
        .all()
        if row[0]
    ]

    return render_template(
        "admin/blogs.html",
        posts=posts,
        categories=categories,
        q=q,
        selected_status=status,
        selected_category=category
    )


@admin_bp.route("/blogs/new", methods=["GET", "POST"])
@login_required
def blog_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        slug = make_unique_slug(BlogPost, request.form.get("slug") or title)
        cover = save_upload(request.files.get("cover_image"))

        post = BlogPost(
            title=title,
            slug=slug,
            summary=request.form.get("summary", "").strip(),
            content=request.form.get("content", "").strip(),
            cover_image=cover,
            category=request.form.get("category", "Genel").strip(),
            tags=request.form.get("tags", "").strip(),
            status=request.form.get("status", "draft"),
            meta_description=request.form.get("meta_description", "").strip(),
            reading_time=calculate_reading_time(request.form.get("content", "")),
            is_featured=bool(request.form.get("is_featured"))
        )
        db.session.add(post)
        db.session.commit()
        flash("Blog yazısı oluşturuldu.", "success")
        return redirect(url_for("admin.blogs"))

    return render_template("admin/blog_form.html", post=None)


@admin_bp.route("/blogs/<int:post_id>/edit", methods=["GET", "POST"])
@login_required
def blog_edit(post_id):
    post = db.session.get(BlogPost, post_id) or BlogPost.query.get_or_404(post_id)

    if request.method == "POST":
        post.title = request.form.get("title", "").strip()
        post.slug = make_unique_slug(BlogPost, request.form.get("slug") or post.title, current_id=post.id)
        post.summary = request.form.get("summary", "").strip()
        post.content = request.form.get("content", "").strip()
        post.category = request.form.get("category", "Genel").strip()
        post.tags = request.form.get("tags", "").strip()
        post.status = request.form.get("status", "draft")
        post.meta_description = request.form.get("meta_description", "").strip()
        post.reading_time = calculate_reading_time(post.content)
        post.is_featured = bool(request.form.get("is_featured"))

        if request.form.get("remove_cover_image") == "1":
            post.cover_image = None

        cover = save_upload(request.files.get("cover_image"))
        if cover:
            post.cover_image = cover

        db.session.commit()
        flash("Blog yazısı güncellendi.", "success")
        return redirect(url_for("admin.blogs"))

    return render_template("admin/blog_form.html", post=post)


@admin_bp.route("/blogs/<int:post_id>/delete", methods=["POST"])
@login_required
def blog_delete(post_id):
    post = BlogPost.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash("Blog yazısı silindi.", "success")
    return redirect(url_for("admin.blogs"))


@admin_bp.route("/projects")
@login_required
def projects():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    tech = request.args.get("tech", "").strip()

    query = Project.query

    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Project.title.ilike(like),
                Project.summary.ilike(like),
                Project.content.ilike(like),
                Project.technologies.ilike(like),
            )
        )

    if status:
        query = query.filter(Project.status == status)

    if tech:
        query = query.filter(Project.technologies.ilike(f"%{tech}%"))

    items = query.order_by(Project.created_at.desc()).all()

    tech_set = set()
    for project in Project.query.all():
        for item in (project.technologies or "").split(","):
            item = item.strip()
            if item:
                tech_set.add(item)

    return render_template(
        "admin/projects.html",
        projects=items,
        technologies=sorted(tech_set),
        q=q,
        selected_status=status,
        selected_tech=tech
    )


@admin_bp.route("/projects/new", methods=["GET", "POST"])
@login_required
def project_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        slug = make_unique_slug(Project, request.form.get("slug") or title)
        cover = save_upload(request.files.get("cover_image"))

        project = Project(
            title=title,
            slug=slug,
            summary=request.form.get("summary", "").strip(),
            content=request.form.get("content", "").strip(),
            cover_image=cover,
            technologies=request.form.get("technologies", "").strip(),
            github_url=request.form.get("github_url", "").strip(),
            demo_url=request.form.get("demo_url", "").strip(),
            status=request.form.get("status", "draft"),
            meta_description=request.form.get("meta_description", "").strip(),
            reading_time=calculate_reading_time(request.form.get("content", "")),
            is_featured=bool(request.form.get("is_featured"))
        )
        db.session.add(project)
        db.session.commit()
        flash("Proje oluşturuldu.", "success")
        return redirect(url_for("admin.projects"))

    return render_template("admin/project_form.html", project=None)


@admin_bp.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
@login_required
def project_edit(project_id):
    project = Project.query.get_or_404(project_id)

    if request.method == "POST":
        project.title = request.form.get("title", "").strip()
        project.slug = make_unique_slug(Project, request.form.get("slug") or project.title, current_id=project.id)
        project.summary = request.form.get("summary", "").strip()
        project.content = request.form.get("content", "").strip()
        project.technologies = request.form.get("technologies", "").strip()
        project.github_url = request.form.get("github_url", "").strip()
        project.demo_url = request.form.get("demo_url", "").strip()
        project.status = request.form.get("status", "draft")
        project.meta_description = request.form.get("meta_description", "").strip()
        project.reading_time = calculate_reading_time(project.content)
        project.is_featured = bool(request.form.get("is_featured"))

        if request.form.get("remove_cover_image") == "1":
            project.cover_image = None

        cover = save_upload(request.files.get("cover_image"))
        if cover:
            project.cover_image = cover

        db.session.commit()
        flash("Proje güncellendi.", "success")
        return redirect(url_for("admin.projects"))

    return render_template("admin/project_form.html", project=project)


@admin_bp.route("/projects/<int:project_id>/delete", methods=["POST"])
@login_required
def project_delete(project_id):
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    flash("Proje silindi.", "success")
    return redirect(url_for("admin.projects"))


@admin_bp.route("/messages")
@login_required
def messages():
    # Mesajlar artık sayfaya girince otomatik okunduya düşmez.
    # Kullanıcı manuel "Okundu Yap" demeden durum Yeni kalır.
    items = Message.query.order_by(Message.created_at.desc()).all()
    return render_template("admin/messages.html", messages=items)


@admin_bp.route("/messages/<int:message_id>/read", methods=["POST"])
@login_required
def message_mark_read(message_id):
    msg = Message.query.get_or_404(message_id)
    msg.is_read = True
    db.session.commit()
    flash("Mesaj okundu olarak işaretlendi.", "success")
    return redirect(url_for("admin.messages"))


@admin_bp.route("/messages/<int:message_id>/unread", methods=["POST"])
@login_required
def message_mark_unread(message_id):
    msg = Message.query.get_or_404(message_id)
    msg.is_read = False
    db.session.commit()
    flash("Mesaj okunmadı olarak işaretlendi.", "success")
    return redirect(url_for("admin.messages"))


@admin_bp.route("/messages/<int:message_id>/delete", methods=["POST"])
@login_required
def message_delete(message_id):
    msg = Message.query.get_or_404(message_id)
    db.session.delete(msg)
    db.session.commit()
    flash("Mesaj silindi.", "success")
    return redirect(url_for("admin.messages"))


@admin_bp.route("/messages/read-all", methods=["POST"])
@login_required
def messages_read_all():
    Message.query.filter_by(is_read=False).update({"is_read": True})
    db.session.commit()
    flash("Tüm mesajlar okundu olarak işaretlendi.", "success")
    return redirect(url_for("admin.messages"))



@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    editable_keys = [
        "site_name",
        "owner_name",
        "brand_initial",
        "hero_eyebrow",
        "hero_title",
        "hero_subtitle",
        "short_about_title",
        "short_about_text",
        "about_title",
        "about_intro",
        "about_content",
        "contact_title",
        "contact_text",
        "email",
        "github_url",
        "linkedin_url",
        "instagram_url",
        "x_url",
        "location",
    ]

    if request.method == "POST":
        for key in editable_keys:
            value = request.form.get(key, "").strip()
            item = SiteSetting.query.filter_by(key=key).first()
            if item:
                item.value = value
            else:
                db.session.add(SiteSetting(key=key, value=value))

        for key in ["site_logo", "favicon_image"]:
            if request.form.get(f"remove_{key}") == "1":
                item = SiteSetting.query.filter_by(key=key).first()
                if item:
                    item.value = ""

        logo_upload = save_upload(request.files.get("site_logo_file"))
        if logo_upload:
            item = SiteSetting.query.filter_by(key="site_logo").first()
            if item:
                item.value = logo_upload
            else:
                db.session.add(SiteSetting(key="site_logo", value=logo_upload))

        favicon_upload = save_upload(request.files.get("favicon_image_file"))
        if favicon_upload:
            item = SiteSetting.query.filter_by(key="favicon_image").first()
            if item:
                item.value = favicon_upload
            else:
                db.session.add(SiteSetting(key="favicon_image", value=favicon_upload))

        db.session.commit()
        flash("Site ayarları güncellendi.", "success")
        return redirect(url_for("admin.settings"))

    settings_data = get_site_settings()
    return render_template("admin/settings.html", settings=settings_data, keys=editable_keys)




@admin_bp.route("/blogs/<int:post_id>/toggle-status", methods=["POST"])
@login_required
def blog_toggle_status(post_id):
    post = BlogPost.query.get_or_404(post_id)
    post.status = "draft" if post.status == "published" else "published"
    db.session.commit()

    flash("Blog durumu güncellendi.", "success")
    return redirect(request.referrer or url_for("admin.blogs"))


@admin_bp.route("/projects/<int:project_id>/toggle-status", methods=["POST"])
@login_required
def project_toggle_status(project_id):
    project = Project.query.get_or_404(project_id)
    project.status = "draft" if project.status == "published" else "published"
    db.session.commit()

    flash("Proje durumu güncellendi.", "success")
    return redirect(request.referrer or url_for("admin.projects"))


@admin_bp.route("/blogs/<int:post_id>/duplicate", methods=["POST"])
@login_required
def blog_duplicate(post_id):
    post = BlogPost.query.get_or_404(post_id)

    copy = BlogPost(
        title=f"{post.title} - Kopya",
        slug=make_unique_slug(BlogPost, f"{post.slug}-kopya"),
        summary=post.summary,
        content=post.content,
        cover_image=post.cover_image,
        category=post.category,
        tags=post.tags,
        status="draft",
        meta_description=post.meta_description,
        reading_time=post.reading_time,
        view_count=0,
        is_featured=False,
    )

    db.session.add(copy)
    db.session.commit()

    flash("Blog taslak olarak kopyalandı.", "success")
    return redirect(url_for("admin.blog_edit", post_id=copy.id))


@admin_bp.route("/projects/<int:project_id>/duplicate", methods=["POST"])
@login_required
def project_duplicate(project_id):
    project = Project.query.get_or_404(project_id)

    copy = Project(
        title=f"{project.title} - Kopya",
        slug=make_unique_slug(Project, f"{project.slug}-kopya"),
        summary=project.summary,
        content=project.content,
        cover_image=project.cover_image,
        technologies=project.technologies,
        github_url=project.github_url,
        demo_url=project.demo_url,
        status="draft",
        meta_description=project.meta_description,
        reading_time=project.reading_time,
        view_count=0,
        is_featured=False,
    )

    db.session.add(copy)
    db.session.commit()

    flash("Proje taslak olarak kopyalandı.", "success")
    return redirect(url_for("admin.project_edit", project_id=copy.id))



@admin_bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    user = current_user

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        new_password_repeat = request.form.get("new_password_repeat", "")

        if not check_password_hash(user.password_hash, current_password):
            flash("Mevcut şifre hatalı.", "danger")
            return redirect(url_for("admin.account"))

        if len(new_password) < 10:
            flash("Yeni şifre en az 10 karakter olmalı.", "danger")
            return redirect(url_for("admin.account"))

        if new_password != new_password_repeat:
            flash("Yeni şifreler eşleşmiyor.", "danger")
            return redirect(url_for("admin.account"))

        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash("Admin şifresi güncellendi.", "success")
        return redirect(url_for("admin.account"))

    return render_template("admin/account.html")

@admin_bp.route("/preview/blog/<int:post_id>")
@login_required
def blog_preview(post_id):
    post = BlogPost.query.get_or_404(post_id)
    return render_template("blog_detail.html", post=post, is_liked=False)


@admin_bp.route("/preview/project/<int:project_id>")
@login_required
def project_preview(project_id):
    project = Project.query.get_or_404(project_id)
    return render_template("project_detail.html", project=project, is_liked=False)
