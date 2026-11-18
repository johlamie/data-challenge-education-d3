"""Création de l'application Dash (fabrique), routage et assemblage des pages."""
import logging
import os
from urllib.parse import parse_qs

import dash
from dash import Input, Output, State, dcc, html

from . import __version__, db
from .auth import installer_auth, installer_entetes
from .composants import (PAGES, classes_nav, fraicheur, id_nav, lien_evitement, page_introuvable, rail,
                         tete_mobile)
from .config import Config
from .meta import EQUIPE
from .pages import accueil, besoins, classement, fiche, implantation, methode

ROUTES = {"/": accueil, "/classement": classement, "/fiche": fiche, "/besoins-2030": besoins,
          "/implantation": implantation, "/a-propos": methode, "/methode": methode}
MODULES = (accueil, classement, fiche, besoins, implantation, methode)
# vues construites pour tenir sur un écran d'ordinateur : au-dessus de 961 px le document ne
# défile pas du tout (c'est la liste qui défile dans son panneau, style.css § 16)
PLEIN_ECRAN = (accueil, classement, implantation)
ICI = os.path.dirname(os.path.abspath(__file__))

INDEX = """<!DOCTYPE html>
<html lang="fr">
<head>
{%metas%}
<title>{%title%}</title>
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
{%css%}
</head>
<body>
{%app_entry%}
<footer>{%config%}{%scripts%}{%renderer%}</footer>
</body>
</html>"""


def creer_app(cfg=None, donnees=None):
    cfg = cfg or Config()
    if donnees is not None:
        db.installer(donnees)
    routes = dict(ROUTES)
    modules = list(MODULES)
    if cfg.demo:  # page de démonstration du kit : uniquement en mode données fictives
        from .pages import kit
        routes["/_kit"] = kit
        modules.append(kit)
    app = dash.Dash(
        __name__, title="Salles de classe et enseignants · Burkina Faso", update_title="Chargement…",
        assets_folder=os.path.join(os.path.dirname(ICI), "assets"), serve_locally=True,
        suppress_callback_exceptions=True, compress=True, external_stylesheets=[], external_scripts=[],
        meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1, viewport-fit=cover"},
                   {"name": "robots", "content": "noindex, nofollow"}])
    app.index_string = INDEX
    if cfg.demo:
        # bandeau pleine largeur, rouge, texte complet : jamais adouci, replié ni transformé en puce neutre.
        # `role="alert"` (et non `note`) : un lecteur d'écran doit annoncer tout de suite que les chiffres
        # sont fictifs.
        bandeau = html.Div([html.B("Données fictives"),
                            html.Span(" · démonstration du design : aucun chiffre, nom ou classement affiché "
                                      "n'est réel", className="bd-suite"),
                            " · ", html.Span(EQUIPE, className="bd-eq")],
                           className="bandeau-demo", role="alert")
    else:
        bandeau = html.Div(f"Données confidentielles · usage interne · {EQUIPE} · version {__version__}",
                           className="bandeau-conf", role="note")
    app.layout = html.Div([
        dcc.Location(id="url", refresh=False),
        # premier élément focalisable de la page : sauter le rail (et, sur le Classement, ses
        # dizaines de liens de province) pour atteindre le contenu au clavier
        lien_evitement(),
        bandeau,
        tete_mobile(cfg.auth_active),
        html.Div([rail(cfg.auth_active),
                  # tabIndex=-1 : le focus suit vraiment le lien d'évitement (cible non focalisable sinon)
                  html.Main(id="page", className="travail", tabIndex="-1")], className="coque"),
    ], id="racine", className="racine")

    @app.callback(Output("page", "children"), Output("racine", "className"),
                  Input("url", "pathname"), Input("url", "search"))
    def router(chemin, recherche):
        mod = routes.get((chemin or "/").rstrip("/") or "/")
        if mod is None:
            return page_introuvable(), "racine"
        q = {k: v[0] for k, v in parse_qs((recherche or "").lstrip("?")).items()}
        # vues construites pour un écran d'ordinateur : marquées pour que la rangée principale occupe la hauteur
        return mod.layout(**q), ("racine racine-ecran" if mod in PLEIN_ECRAN else "racine")

    @app.callback([Output(id_nav(h), "className") for h, _, _ in PAGES]
                  + [Output(id_nav(h, "navm"), "className") for h, _, _ in PAGES]
                  + [Output(id_nav(h), "aria-current") for h, _, _ in PAGES]
                  + [Output(id_nav(h, "navm"), "aria-current") for h, _, _ in PAGES],
                  Input("url", "pathname"))
    def actif(chemin):
        return classes_nav(chemin)

    @app.callback(Output("rail-fraicheur", "children"), Input("url", "pathname"))
    def maj_fraicheur(_chemin):
        try:
            return fraicheur(db.donnees())
        except Exception:
            return fraicheur(None)

    @app.callback(Output("nav-menu", "hidden"), Output("nav-bascule", "aria-expanded"),
                  Input("nav-bascule", "n_clicks"), State("nav-menu", "hidden"), prevent_initial_call=True)
    def bascule(n, ferme):
        # `ferme` est l'état avant le clic : s'il était caché, le menu s'ouvre
        return (not ferme), ("true" if ferme else "false")

    for mod in modules:
        mod.register(app)
    installer_auth(app.server, cfg)
    try:
        hashes = app.csp_hashes()
    except Exception:
        hashes = []
    installer_entetes(app.server, hashes)
    return app


def creer_app_production():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    cfg = Config()
    if cfg.demo:
        from .demo import SourceDemo
        logging.getLogger("d3dash").warning("MODE DÉMO : données synthétiques fictives, aucune connexion à la base")
        d = db.Donnees(SourceDemo(), ttl_s=10 ** 9)
        return creer_app(cfg, d)
    d = db.Donnees(db.SourcePostgres(cfg), ttl_s=cfg.cache_ttl_s)
    app = creer_app(cfg, d)
    try:
        d.get()  # préchargement ; en cas d'échec, nouvel essai à la première requête
        logging.getLogger("d3dash").info("données chargées")
    except Exception as e:
        logging.getLogger("d3dash").error("préchargement impossible : %s", type(e).__name__)
    return app
