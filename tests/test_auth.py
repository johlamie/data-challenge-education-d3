import pytest
from werkzeug.security import generate_password_hash

from d3dash.app import creer_app
from d3dash.config import Config

CODE = "code-de-test-123"


@pytest.fixture()
def client(donnees):
    cfg = Config(auth_active=True, code_hash=generate_password_hash(CODE), secret_key="x" * 64, max_essais=3,
                 fenetre_essais_s=60)
    app = creer_app(cfg, donnees)
    app.server.testing = True
    return app.server.test_client()


def _jeton(client):
    r = client.get("/connexion")
    assert r.status_code == 200
    with client.session_transaction() as s:
        return s["jeton"]


def test_sans_session_redirige_ou_401(client):
    r = client.get("/")
    assert r.status_code == 302 and "/connexion" in r.headers["Location"]
    assert client.get("/_dash-layout").status_code == 401
    assert client.post("/_dash-update-component", json={}).status_code == 401
    assert client.get("/_dash-component-suites/dash/dash-renderer/build/dash_renderer.min.js").status_code == 401
    assert client.get("/sante").status_code == 200


def test_mauvais_code_puis_limite(client):
    j = _jeton(client)
    for _ in range(3):
        r = client.post("/connexion", data={"code": "faux", "jeton": j, "suite": "/"})
        assert r.status_code == 401
    r = client.post("/connexion", data={"code": CODE, "jeton": j, "suite": "/"})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0


def test_jeton_formulaire_obligatoire(client):
    _jeton(client)
    r = client.post("/connexion", data={"code": CODE, "jeton": "autre", "suite": "/"})
    assert r.status_code == 400


def test_bon_code_et_session(client):
    j = _jeton(client)
    r = client.post("/connexion", data={"code": CODE, "jeton": j, "suite": "//evil.example/x"})
    assert r.status_code == 302 and r.headers["Location"] == "/"
    cookie = r.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie
    assert client.get("/").status_code == 200
    assert client.get("/_dash-layout").status_code == 200
    r = client.get("/")
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert client.get("/deconnexion").status_code == 302
    assert client.get("/").status_code == 302


def test_code_jamais_dans_les_reponses(client):
    j = _jeton(client)
    r = client.post("/connexion", data={"code": CODE, "jeton": j, "suite": "/"})
    assert CODE not in r.get_data(as_text=True)


TRAVERSEES = ("/assets/icones/../aide.js", "/assets/icones/..%2faide.js",
              "/assets/icones/x/../../nav.js", "/assets/icones/..%2Faide.js",
              "/assets/icones/..\\aide.js")


def test_remontee_de_repertoire_jamais_libre(client):
    """Une remontée depuis /assets/icones/ ne doit jamais servir un fichier sans session."""
    for url in TRAVERSEES:
        r = client.get(url)
        assert r.status_code != 200, f"{url} servi sans session ({r.status_code})"


def test_liste_blanche_exacte(client):
    """Seuls les fichiers que la page de connexion référence sont libres ; aucune autre icône."""
    for url in ("/assets/tokens.css", "/assets/style.css", "/assets/favicon.svg",
                "/assets/icones/monogramme.svg"):
        assert client.get(url).status_code == 200, url
    for url in ("/assets/icones/classement.svg", "/assets/icones/vue-ensemble.svg",
                "/assets/aide.js", "/assets/nav.js", "/assets/tableau.js"):
        assert client.get(url).status_code != 200, url


def test_page_connexion_charge_ses_ressources(client):
    """Les <link> de la page de connexion sont tous dans la liste blanche."""
    import re
    corps = client.get("/connexion").get_data(as_text=True)
    for href in re.findall(r'href="(/assets/[^"]+)"', corps):
        assert client.get(href).status_code == 200, href


def test_auth_desactivable(donnees):
    app = creer_app(Config(auth_active=False, code_hash="", secret_key=""), donnees)
    c = app.server.test_client()
    assert c.get("/").status_code == 200


def test_auth_active_sans_secret_refusee(donnees):
    with pytest.raises(RuntimeError):
        creer_app(Config(auth_active=True, code_hash="", secret_key="k" * 64), donnees)


# --- Code du jury, adresse réelle derrière le proxy inverse, cookie Secure -------------------------
# Empreintes jetables, fabriquées ici : aucune empreinte réelle n'entre dans ce dépôt.
CODE_JURY = "code-du-jury-456"
PROXY = "10.9.8.7"          # pair direct de confiance (en production : 192.0.2.10)
HORS_PROXY = "192.0.2.44"   # pair direct quelconque : son X-Forwarded-For ne vaut rien
CLIENT_A = "203.0.113.5"
CLIENT_B = "198.51.100.9"


@pytest.fixture()
def client_proxy(donnees):
    cfg = Config(auth_active=True, code_hash=generate_password_hash(CODE), secret_key="x" * 64, max_essais=3,
                 code_hash_jury=generate_password_hash(CODE_JURY), fenetre_essais_s=60, proxys_confiance=(PROXY,))
    app = creer_app(cfg, donnees)
    app.server.testing = True
    return app.server.test_client()


def _poster(client, code, jeton, pair=None, xff=None):
    """POST /connexion depuis un pair donné, avec l'en-tête X-Forwarded-For éventuel du proxy."""
    base = {"REMOTE_ADDR": pair} if pair else {}
    entetes = {"X-Forwarded-For": xff} if xff else {}
    return client.post("/connexion", data={"code": code, "jeton": jeton, "suite": "/"},
                       environ_base=base, headers=entetes)


def test_code_jury_accepte_et_code_equipe_toujours_valide(client_proxy):
    j = _jeton(client_proxy)
    assert _poster(client_proxy, "faux", j).status_code == 401
    assert _poster(client_proxy, CODE_JURY, j).status_code == 302
    assert client_proxy.get("/").status_code == 200
    client_proxy.get("/deconnexion")
    j = _jeton(client_proxy)
    assert _poster(client_proxy, CODE, j).status_code == 302
    assert client_proxy.get("/").status_code == 200


def test_code_jury_inactif_si_empreinte_absente(client):
    """Sans DC_EDU_CODE_HASH_JURY, le code du jury n'est qu'un code faux de plus."""
    j = _jeton(client)
    assert _poster(client, CODE_JURY, j).status_code == 401
    assert _poster(client, CODE, j).status_code == 302


def test_limite_par_adresse_reelle_derriere_le_proxy(client_proxy):
    """Trois échecs du client A le bloquent ; le client B, par le même proxy, passe toujours."""
    j = _jeton(client_proxy)
    for _ in range(3):
        assert _poster(client_proxy, "faux", j, PROXY, CLIENT_A).status_code == 401
    r = _poster(client_proxy, CODE, j, PROXY, CLIENT_A)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0
    assert _poster(client_proxy, CODE, j, PROXY, CLIENT_B).status_code == 302


def test_entete_ignore_depuis_un_pair_non_de_confiance(client_proxy):
    """Usurpation : un client direct qui change X-Forwarded-For à chaque essai se bloque quand même."""
    j = _jeton(client_proxy)
    for i in range(3):
        assert _poster(client_proxy, "faux", j, HORS_PROXY, f"203.0.113.{i}").status_code == 401
    assert _poster(client_proxy, CODE, j, HORS_PROXY, "203.0.113.99").status_code == 429
    # le vrai client A, lui, n'a rien à voir avec ces essais
    assert _poster(client_proxy, CODE, j, PROXY, CLIENT_A).status_code == 302


def test_entete_multivalue_la_valeur_de_droite_fait_foi(client_proxy):
    """Le proxy écrase l'en-tête : seule la DERNIÈRE valeur est la sienne, la première vient du client."""
    j = _jeton(client_proxy)
    for _ in range(3):
        assert _poster(client_proxy, "faux", j, PROXY, f"{CLIENT_B}, {CLIENT_A}").status_code == 401
    assert _poster(client_proxy, CODE, j, PROXY, CLIENT_A).status_code == 429
    assert _poster(client_proxy, CODE, j, PROXY, f"{CLIENT_A}, {CLIENT_B}").status_code == 302


def test_entete_malforme_retombe_sur_le_pair_direct(client_proxy):
    """Une valeur qui n'est pas une adresse IP est ignorée : la clé reste l'adresse du proxy."""
    j = _jeton(client_proxy)
    for valeur in ("pas-une-ip", "203.0.113.5:9999", " "):
        assert _poster(client_proxy, "faux", j, PROXY, valeur).status_code == 401
    assert _poster(client_proxy, CODE, j, PROXY).status_code == 429
    assert _poster(client_proxy, CODE, j, PROXY, CLIENT_A).status_code == 302


def test_cookie_secure_quand_configure(donnees):
    cfg = Config(auth_active=True, code_hash=generate_password_hash(CODE), secret_key="x" * 64,
                 cookie_secure=True, proxys_confiance=(PROXY,))
    c = creer_app(cfg, donnees).server.test_client()
    cookie = c.get("/connexion").headers["Set-Cookie"]
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=Strict" in cookie


def test_cookie_sans_secure_par_defaut(client_proxy):
    """En HTTP local (DC_EDU_COOKIE_SECURE absent) l'attribut Secure rendrait la session inutilisable."""
    cookie = client_proxy.get("/connexion").headers["Set-Cookie"]
    assert "Secure" not in cookie
