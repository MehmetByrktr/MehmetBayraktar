import math
import re
from html import unescape
from datetime import datetime
from time import time
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from sqlalchemy import or_

from .extensions import db
from .models import BlogPost, Project, Message


main_bp = Blueprint("main", __name__)

# İletişim formu için basit IP bazlı hız sınırlama (spam/kötüye kullanım önleme).
# Honeypot alanı botların büyük kısmını zaten eler; bu, kalan senaryolar için ek katman.
_CONTACT_ATTEMPTS = {}
_CONTACT_WINDOW_SECONDS = 10 * 60
_CONTACT_MAX_PER_WINDOW = 5


def contact_rate_limited(client_key):
    now = time()
    history = [t for t in _CONTACT_ATTEMPTS.get(client_key, []) if now - t < _CONTACT_WINDOW_SECONDS]
    _CONTACT_ATTEMPTS[client_key] = history
    return len(history) >= _CONTACT_MAX_PER_WINDOW


def register_contact_attempt(client_key):
    _CONTACT_ATTEMPTS.setdefault(client_key, []).append(time())



def calculate_reading_time(content):
    text_content = re.sub(r"<[^>]+>", " ", content or "")
    text_content = unescape(text_content)
    words = re.findall(r"\w+", text_content, flags=re.UNICODE)
    return max(1, math.ceil(len(words) / 200))


def bump_view_count(item):
    item.view_count = (item.view_count or 0) + 1
    db.session.commit()


@main_bp.route("/")
def home():
    latest_blogs = (
        BlogPost.query
        .filter_by(status="published")
        .order_by(BlogPost.created_at.desc())
        .limit(3)
        .all()
    )
    latest_projects = (
        Project.query
        .filter_by(status="published")
        .order_by(Project.created_at.desc())
        .limit(3)
        .all()
    )

    featured_project = (
        Project.query
        .filter_by(status="published", is_featured=True)
        .order_by(Project.updated_at.desc())
        .first()
    ) or (latest_projects[0] if latest_projects else None)

    featured_blogs = (
        BlogPost.query
        .filter_by(status="published", is_featured=True)
        .order_by(BlogPost.updated_at.desc())
        .limit(3)
        .all()
    )
    featured_projects = (
        Project.query
        .filter_by(status="published", is_featured=True)
        .order_by(Project.updated_at.desc())
        .limit(3)
        .all()
    )

    return render_template(
        "home.html",
        latest_blogs=latest_blogs,
        latest_projects=latest_projects,
        featured_project=featured_project,
        featured_blogs=featured_blogs,
        featured_projects=featured_projects
    )


@main_bp.route("/blog")
def blog_list():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    query = BlogPost.query.filter_by(status="published")

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

    if category:
        query = query.filter(BlogPost.category == category)

    posts = query.order_by(BlogPost.created_at.desc()).all()

    categories = [
        row[0] for row in db.session.query(BlogPost.category)
        .filter(BlogPost.status == "published")
        .distinct()
        .order_by(BlogPost.category.asc())
        .all()
        if row[0]
    ]

    return render_template(
        "blog_list.html",
        posts=posts,
        categories=categories,
        selected_category=category,
        q=q
    )


@main_bp.route("/blog/<slug>")
def blog_detail(slug):
    post = BlogPost.query.filter_by(slug=slug, status="published").first_or_404()
    bump_view_count(post)
    liked_items = set(session.get("liked_items", []))
    is_liked = f"blog:{post.id}" in liked_items
    return render_template("blog_detail.html", post=post, is_liked=is_liked)


@main_bp.route("/projeler")
def project_list():
    q = request.args.get("q", "").strip()
    tech = request.args.get("tech", "").strip()

    query = Project.query.filter_by(status="published")

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

    if tech:
        query = query.filter(Project.technologies.ilike(f"%{tech}%"))

    projects = query.order_by(Project.created_at.desc()).all()

    tech_set = set()
    for project in Project.query.filter_by(status="published").all():
        for item in (project.technologies or "").split(","):
            item = item.strip()
            if item:
                tech_set.add(item)

    return render_template(
        "project_list.html",
        projects=projects,
        technologies=sorted(tech_set),
        selected_tech=tech,
        q=q
    )


@main_bp.route("/projeler/<slug>")
def project_detail(slug):
    project = Project.query.filter_by(slug=slug, status="published").first_or_404()
    bump_view_count(project)
    liked_items = set(session.get("liked_items", []))
    is_liked = f"project:{project.id}" in liked_items
    return render_template("project_detail.html", project=project, is_liked=is_liked)


@main_bp.route("/hakkimda")
def about():
    return render_template("about.html")


@main_bp.route("/iletisim", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        client_key = request.headers.get("X-Forwarded-For", request.remote_addr or "local").split(",")[0].strip()

        # Botlara karşı görünmez honeypot alanı.
        if request.form.get("website", "").strip():
            return redirect(url_for("main.contact"))

        if contact_rate_limited(client_key):
            flash("Kısa sürede çok fazla mesaj gönderildi. Lütfen biraz sonra tekrar dene.", "danger")
            return redirect(url_for("main.contact"))

        register_contact_attempt(client_key)

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()

        if not name or not email or not subject or not message:
            flash("Lütfen tüm alanları doldur.", "danger")
            return redirect(url_for("main.contact"))

        if "@" not in email or "." not in email:
            flash("Geçerli bir e-posta adresi gir.", "danger")
            return redirect(url_for("main.contact"))

        if len(message) > 3000:
            flash("Mesaj 3000 karakteri geçmemeli.", "danger")
            return redirect(url_for("main.contact"))

        msg = Message(
            name=name[:120],
            email=email[:180],
            subject=subject[:180],
            message=message,
            is_read=False,
        )
        db.session.add(msg)
        db.session.commit()
        flash("Mesajın kaydedildi. En kısa sürede dönüş yapılacak.", "success")
        return redirect(url_for("main.contact"))

    return render_template("contact.html")




@main_bp.route("/blog/<slug>/like", methods=["POST"])
def blog_like(slug):
    post = BlogPost.query.filter_by(slug=slug, status="published").first_or_404()
    liked_items = set(session.get("liked_items", []))
    key = f"blog:{post.id}"

    if key in liked_items:
        post.like_count = max(0, (post.like_count or 0) - 1)
        liked_items.remove(key)
        liked = False
    else:
        post.like_count = (post.like_count or 0) + 1
        liked_items.add(key)
        liked = True

    session["liked_items"] = sorted(liked_items)
    session.modified = True
    db.session.commit()
    return jsonify({"ok": True, "likes": post.like_count, "liked": liked})


@main_bp.route("/projeler/<slug>/like", methods=["POST"])
def project_like(slug):
    project = Project.query.filter_by(slug=slug, status="published").first_or_404()
    liked_items = set(session.get("liked_items", []))
    key = f"project:{project.id}"

    if key in liked_items:
        project.like_count = max(0, (project.like_count or 0) - 1)
        liked_items.remove(key)
        liked = False
    else:
        project.like_count = (project.like_count or 0) + 1
        liked_items.add(key)
        liked = True

    session["liked_items"] = sorted(liked_items)
    session.modified = True
    db.session.commit()
    return jsonify({"ok": True, "likes": project.like_count, "liked": liked})



@main_bp.route("/gizlilik")
def privacy():
    return render_template("privacy.html")


@main_bp.route("/cerez-politikasi")
def cookies():
    return render_template("cookies.html")

@main_bp.route("/sitemap.xml")
def sitemap():
    pages = [
        {"loc": url_for("main.home", _external=True), "lastmod": datetime.utcnow()},
        {"loc": url_for("main.blog_list", _external=True), "lastmod": datetime.utcnow()},
        {"loc": url_for("main.project_list", _external=True), "lastmod": datetime.utcnow()},
        {"loc": url_for("main.about", _external=True), "lastmod": datetime.utcnow()},
        {"loc": url_for("main.contact", _external=True), "lastmod": datetime.utcnow()},
        {"loc": url_for("main.privacy", _external=True), "lastmod": datetime.utcnow()},
        {"loc": url_for("main.cookies", _external=True), "lastmod": datetime.utcnow()},
    ]

    for post in BlogPost.query.filter_by(status="published").all():
        pages.append({
            "loc": url_for("main.blog_detail", slug=post.slug, _external=True),
            "lastmod": post.updated_at or post.created_at,
        })

    for project in Project.query.filter_by(status="published").all():
        pages.append({
            "loc": url_for("main.project_detail", slug=project.slug, _external=True),
            "lastmod": project.updated_at or project.created_at,
        })

    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    for page in pages:
        xml.append("  <url>")
        xml.append(f"    <loc>{page['loc']}</loc>")
        xml.append(f"    <lastmod>{page['lastmod'].strftime('%Y-%m-%d')}</lastmod>")
        xml.append("  </url>")

    xml.append("</urlset>")

    return "\n".join(xml), 200, {"Content-Type": "application/xml; charset=utf-8"}


@main_bp.route("/robots.txt")
def robots():
    sitemap_url = url_for("main.sitemap", _external=True)
    content = f"User-agent: *\nAllow: /\nDisallow: /admin\nSitemap: {sitemap_url}\n"
    return content, 200, {"Content-Type": "text/plain; charset=utf-8"}
