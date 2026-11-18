"""Outil de contrôle de la base réelle (`outils/verifier_donnees_reelles.py`) rejoué sur le jeu synthétique :
ses contrôles tournent sur une source injectée, authentification désactivée. Il ne doit ni trébucher sur un
callback côté navigateur, ni manquer un callback en panne.

Les comptes de la base réelle (351 communes 2025, 2 646 sites) ne sont pas vérifiables ici : le jeu de
démonstration en a moins. Ce test porte sur l'étape des callbacks et sur l'absence d'exception.
"""
import importlib.util
from pathlib import Path

import pytest

from d3dash import db
from d3dash.app import creer_app
from d3dash.config import Config
from d3dash.demo import SourceSynthetique

COMMUNES_DEMO = 182  # le jeu synthétique a 4 zones par province (+ 2 communes nées du découpage 2025)
CHEMIN_OUTIL = Path(__file__).resolve().parent.parent / "outils" / "verifier_donnees_reelles.py"


def _outil():
    spec = importlib.util.spec_from_file_location("verifier_donnees_reelles", CHEMIN_OUTIL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


V = _outil()


class SourceSansDecoupage:
    """Base où l'étape d3a_09b/d3a_09 n'a pas tourné : les vues de constat répondent, pas le découpage 2025."""

    derniere_erreur_decoupage = "UndefinedTable"

    def __init__(self, source):
        self.source = source

    def charger(self):
        brut = dict(self.source.charger())
        for cle in db.TABLES:
            brut.pop(cle, None)
        return brut


def _app(d):
    return creer_app(Config(auth_active=False, code_hash="", secret_key=""), d)


@pytest.fixture()
def source_installee():
    """Rend la source installée au test suivant : un test dégradé ne laisse pas sa base en place."""
    precedente = db._DONNEES
    yield db.installer
    db.installer(precedente)


def test_controles_complets_sur_le_jeu_synthetique(donnees, capsys):
    anomalies = V.controler(donnees, communes_attendues=COMMUNES_DEMO)
    sortie = capsys.readouterr().out
    assert "callbacks principaux : 10 / 10" in sortie
    assert "en echec : aucun" in sortie
    assert "pages rendues : 7 / 7" in sortie
    assert anomalies == 0, sortie
    # aucune valeur de données dans la sortie : seulement des comptes, des booléens et des noms de colonnes
    assert "PROVINCE FICTIVE" not in sortie and "LOCALITE" not in sortie


def test_callbacks_cote_navigateur_ignores(donnees):
    """La page Implantation enregistre un `clientside_callback` (pose des bornes de zoom) : son entrée de
    `callback_map` n'a pas de fonction Python, et l'outil doit l'ignorer au lieu de lever KeyError."""
    app = _app(donnees)
    assert any("callback" not in v for v in app.callback_map.values()), "plus aucun callback clientside"
    cbs = V._callbacks(app)
    assert cbs and all(callable(f) for f in cbs.values())
    assert len(cbs) < len(app.callback_map)


def test_chaque_callback_principal_est_appele_avec_les_donnees(donnees, capsys):
    app = _app(donnees)
    assert V._controler_callbacks(donnees, app) == 0
    sortie = capsys.readouterr().out
    for libelle in ("Vue d'ensemble - carte", "Classement - tableau et carte", "Classement - export CSV",
                    "Fiche province", "Besoins 2030 - decoupage 2025", "Implantation - tout le pays",
                    "Implantation - une province 2025", "Implantation - liste vide",
                    "Implantation - export CSV", "Implantation - recadrage de la carte"):
        assert f"{libelle} : ok" in sortie, libelle
    # le filtre de la page Implantation porte bien un code de province 2025, et il filtre vraiment
    n_tous = int(sortie.split("sites listes :")[1].split("|")[0])
    n_prov = int(sortie.split("sites de la province 2025 :")[1].split("|")[0])
    assert 0 < n_prov < n_tous


def test_un_callback_en_panne_est_signale_et_compte(source, source_installee, capsys):
    """Découpage 2025 illisible : les deux pages de projection rendent leur bloc d'erreur. L'outil doit le
    voir (un bloc rouge n'est pas un succès) et rendre un code de sortie non nul."""
    d = db.Donnees(SourceSansDecoupage(source), ttl_s=3600)
    source_installee(d)
    echecs = V._controler_callbacks(d, _app(d))
    sortie = capsys.readouterr().out
    assert echecs > 0
    assert "Besoins 2030 - decoupage 2025 : bloc d'erreur" in sortie
    assert "Implantation - tout le pays : bloc d'erreur" in sortie
    assert "Vue d'ensemble - carte : ok" in sortie  # les pages de constat ne sont pas touchées
    assert V.controler(d, communes_attendues=COMMUNES_DEMO) > 0
