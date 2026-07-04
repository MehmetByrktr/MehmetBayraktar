from app import create_app

app = create_app()
app.config["TESTING"] = True

with app.test_client() as client:
    for path in ["/", "/blog", "/projeler", "/hakkimda", "/iletisim", "/robots.txt", "/sitemap.xml", "/admin/login"]:
        response = client.get(path)
        print(path, response.status_code)
        assert response.status_code < 500
