"""Entry point used by `flask run` (via FLASK_APP=wsgi.py) and by `python wsgi.py`."""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
