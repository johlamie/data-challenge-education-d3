"""Authentification par code d'accès partagé.

- Le code n'est jamais stocké en clair par l'appli : seule son empreinte (scrypt, werkzeug) est lue
  depuis l'environnement (DC_EDU_CODE_HASH).
- Session Flask signée (DC_EDU_SECRET_KEY), cookie HttpOnly, SameSite=Strict, Secure si DC_EDU_COOKIE_SECURE,
  durée limitée.
- Un second code facultatif (accès du jury) est accepté par son empreinte DC_EDU_CODE_HASH_JURY.
- Limitation des essais par adresse IP : DC_EDU_MAX_ESSAIS échecs par fenêtre de DC_EDU_FENETRE_ESSAIS secondes.
- Derrière un proxy inverse, l'adresse réelle du client n'est lue dans X-Forwarded-For que si la connexion
  vient d'un proxy listé dans DC_EDU_PROXYS_CONFIANCE ; sinon l'en-tête est entièrement ignoré.
- Activable / désactivable par DC_EDU_AUTH (1 par défaut).
"""
import collections
import datetime as dt
import hmac
import html
import ipaddress
import secrets
import threading
import time

from flask import Response, redirect, request, session
from werkzeug.security import check_password_hash

# Liste blanche EXACTE : uniquement les fichiers que la page de connexion référence elle-même
# (PAGE ci-dessous + le masque CSS `.monogramme` de assets/style.css). Aucun préfixe : un préfixe
# `/assets/icones/` laisserait passer `/assets/icones/../aide.js`, que ni Flask ni Werkzeug ne
# normalise. Toute autre ressource (icônes de navigation, scripts Dash) exige une session.
CHEMINS_LIBRES = frozenset((
    "/connexion", "/deconnexion", "/sante",
    "/assets/tokens.css",            # <link> de PAGE
    "/assets/style.css",             # <link> de PAGE
    "/assets/favicon.svg",           # <link rel="icon"> de PAGE
    "/assets/icones/monogramme.svg",  # masque CSS de .monogramme, seule icône de PAGE
))
# Un chemin contenant une remontée ou un séparateur encodé n'est jamais libre, même après décodage.
SUSPECT = ("..", "%2f", "%2F", "%5c", "%5C", "\\")


def _chemin_libre(chemin, brut=""):
    """Vrai seulement pour un chemin exactement listé et dépourvu de toute séquence de remontée."""
    if any(s in chemin or s in brut for s in SUSPECT):
        return False
    return chemin in CHEMINS_LIBRES


class LimiteurEssais:
    def __init__(self, max_essais, fenetre_s):
        self.max = max_essais
        self.fenetre = fenetre_s
        self._echecs = collections.defaultdict(collections.deque)
        self._verrou = threading.Lock()

    def _purger(self, cle, now):
        q = self._echecs[cle]
        while q and now - q[0] > self.fenetre:
            q.popleft()
        return q

    def bloque(self, cle):
        with self._verrou:
            q = self._purger(cle, time.time())
            if len(q) >= self.max:
                return int(self.fenetre - (time.time() - q[0])) + 1
            return 0

    def echec(self, cle):
        with self._verrou:
            self._purger(cle, time.time()).append(time.time())

    def succes(self, cle):
        with self._verrou:
            self._echecs.pop(cle, None)


class ProxyDeConfiance:
    """Intergiciel WSGI : ne croit X-Forwarded-For que si la connexion vient d'un proxy listé.

    Le proxy nginx ÉCRASE X-Forwarded-For avec l'adresse du client (`proxy_set_header X-Forwarded-For
    $remote_addr`) ; on lit donc la DERNIÈRE valeur, la seule qu'il ait écrite lui-même — jamais la
    première, qui serait contrôlée par le client. Une valeur qui n'est pas une adresse IP est ignorée :
    REMOTE_ADDR garde alors l'adresse du pair direct. X-Forwarded-Proto n'est délibérément pas cru :
    l'attribut Secure du cookie vient de la configuration (DC_EDU_COOKIE_SECURE), pas d'un en-tête.
    """

    def __init__(self, application, proxys):
        self.application = application
        self.proxys = frozenset(proxys)

    def __call__(self, environ, start_response):
        if environ.get("REMOTE_ADDR") in self.proxys:
            client = environ.get("HTTP_X_FORWARDED_FOR", "").split(",")[-1].strip()
            try:
                environ["REMOTE_ADDR"] = str(ipaddress.ip_address(client))
            except ValueError:
                pass
        return self.application(environ, start_response)


# Tâche unique : ni rail, ni bandeau, ni lien vers l'application.
PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Connexion · Salles &amp; Maîtres</title>
<link rel="stylesheet" href="/assets/tokens.css"><link rel="stylesheet" href="/assets/style.css">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml"></head>
<body class="page-connexion"><main class="carte-connexion">
<div class="marque"><span class="monogramme" aria-hidden="true"></span>
<h1>Salles &amp; Maîtres</h1></div>
<p class="co-sous">Primaire, Burkina Faso · tableau de bord privé (Data Challenge Éducation)</p>
{message}
<form method="post" action="/connexion" autocomplete="off">
<input type="hidden" name="jeton" value="{jeton}"><input type="hidden" name="suite" value="{suite}">
<label for="code">Code d'accès</label>
<input id="code" name="code" type="password" required autofocus autocomplete="current-password">
<button type="submit" class="btn-plein">Se connecter</button></form>
<p class="co-conf">Données confidentielles : ne pas diffuser.</p></main></body></html>"""


def _message(texte):
    """Message d'erreur de connexion : même gabarit que le bloc erreur du kit, version compacte."""
    return f'<section class="bloc-erreur" role="alert"><p>{texte}</p></section>'


def _suite_sure(s):
    return s if s and s.startswith("/") and not s.startswith("//") and "\\" not in s else "/"


def installer_auth(server, cfg):
    """Branche l'authentification sur le serveur Flask de Dash."""
    server.config.update(
        SESSION_COOKIE_NAME="dcedu_d3_session", SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_SECURE=cfg.cookie_secure, PERMANENT_SESSION_LIFETIME=dt.timedelta(hours=cfg.session_heures))
    if cfg.secret_key:
        server.secret_key = cfg.secret_key
    elif cfg.auth_active:
        raise RuntimeError("DC_EDU_SECRET_KEY manquante alors que l'authentification est active")
    else:
        server.secret_key = secrets.token_hex(32)
    if cfg.auth_active and not cfg.code_hash:
        raise RuntimeError("DC_EDU_CODE_HASH manquante alors que l'authentification est active")
    if cfg.proxys_confiance:
        server.wsgi_app = ProxyDeConfiance(server.wsgi_app, cfg.proxys_confiance)
    # Empreintes acceptées : code d'équipe + code du jury s'il est configuré (sinon la fonction est inactive).
    empreintes = [h for h in (cfg.code_hash, cfg.code_hash_jury) if h]
    limiteur = LimiteurEssais(cfg.max_essais, cfg.fenetre_essais_s)
    server.extensions["dcedu_d3_limiteur"] = limiteur

    def page(message="", suite="/", code=200):
        if "jeton" not in session:
            session["jeton"] = secrets.token_urlsafe(24)
        corps = PAGE.format(message=message, jeton=session["jeton"], suite=html.escape(_suite_sure(suite)))
        return Response(corps, status=code, mimetype="text/html")

    @server.route("/sante")
    def sante():
        return Response("ok", mimetype="text/plain")

    @server.route("/connexion", methods=["GET", "POST"])
    def connexion():
        if not cfg.auth_active:
            return redirect("/")
        ip = request.remote_addr or "?"
        if request.method == "GET":
            return page(suite=request.args.get("suite", "/"))
        attente = limiteur.bloque(ip)
        if attente:
            r = page(_message("Trop d'essais. Réessayez dans quelques minutes."), code=429)
            r.headers["Retry-After"] = str(attente)
            return r
        jeton = request.form.get("jeton", "")
        if not jeton or not hmac.compare_digest(jeton, session.get("jeton", "")):
            return page(_message("Formulaire expiré, recommencez."), code=400)
        code = request.form.get("code", "")
        # `any([...])` sur une liste déjà construite : les deux empreintes sont TOUJOURS vérifiées, donc le
        # temps de réponse ne révèle pas lequel des deux codes a été reconnu (ni lequel est configuré).
        if code and any([check_password_hash(h, code) for h in empreintes]):
            limiteur.succes(ip)
            session.clear()
            session.permanent = True
            session["auth"] = True
            session["depuis"] = int(time.time())
            return redirect(_suite_sure(request.form.get("suite")))
        limiteur.echec(ip)
        time.sleep(0.5)
        return page(_message("Code d'accès incorrect."), suite=request.form.get("suite", "/"), code=401)

    @server.route("/deconnexion")
    def deconnexion():
        session.clear()
        return redirect("/connexion")

    @server.before_request
    def garde():
        if not cfg.auth_active or session.get("auth") is True:
            return None
        p = request.path
        brut = (request.environ.get("RAW_URI") or request.environ.get("REQUEST_URI") or "").split("?", 1)[0]
        if _chemin_libre(p, brut):
            return None
        if p.startswith("/_dash") or request.method != "GET" or p.startswith("/_"):
            return Response('{"erreur": "authentification requise"}', status=401, mimetype="application/json")
        return redirect("/connexion?suite=" + (p if p != "/connexion" else "/"))

    return limiteur


def installer_entetes(server, csp_script_hashes=()):
    """En-têtes de sécurité ; la CSP interdit toute ressource externe (fonctionnement hors ligne garanti)."""
    script_src = " ".join(["'self'", "'unsafe-eval'", *[h if h.startswith("'") else f"'{h}'" for h in csp_script_hashes]])
    csp = ("default-src 'self'; " f"script-src {script_src}; " "style-src 'self' 'unsafe-inline'; "
           "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; worker-src 'self' blob:; "
           "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'")

    @server.after_request
    def entetes(r):
        r.headers["Content-Security-Policy"] = csp
        r.headers["X-Content-Type-Options"] = "nosniff"
        r.headers["X-Frame-Options"] = "DENY"
        r.headers["Referrer-Policy"] = "no-referrer"
        r.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        if not request.path.startswith(("/assets/", "/_dash-component-suites/")):
            r.headers["Cache-Control"] = "no-store"
        return r
