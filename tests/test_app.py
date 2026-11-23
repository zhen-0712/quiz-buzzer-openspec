from quiz_buzzer import create_app


def test_application_serves_the_starter_page(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite3")})

    response = app.test_client().get("/")

    assert response.status_code == 200
    assert "課堂搶答系統" in response.get_data(as_text=True)
