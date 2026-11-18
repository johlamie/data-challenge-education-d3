"""Point d'entrée WSGI (gunicorn wsgi:server)."""
from d3dash.app import creer_app_production

app = creer_app_production()
server = app.server
