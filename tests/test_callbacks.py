"""Rendu des pages et des callbacks sur données synthétiques ; règles d'interface (icônes d'aide, équipe)."""
import os
import re

import pytest

from d3dash import figures as F
from d3dash.app import ROUTES, creer_app
from d3dash.config import EQUIPE, Config

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture()
def app(donnees):
    return creer_app(Config(auth_active=False, code_hash="", secret_key=""), donnees)


def cb(app, sortie):
    for k, v in app.callback_map.items():
        if sortie in k:
            return v["callback"].__wrapped__
    raise KeyError(sortie)


def texte(x):
    return str(x)


@pytest.mark.parametrize("chemin", list(ROUTES) + ["/inconnue"])
def test_routage(app, chemin):
    page, classe = cb(app, "page.children")(chemin, "")
    assert page is not None and classe.startswith("racine")


def test_vues_ecran(app):
    """Les vues construites pour un écran d'ordinateur sont marquées sur la racine (un léger
    défilement y est accepté)."""
    assert cb(app, "page.children")("/", "")[1] == "racine racine-ecran"
    assert cb(app, "page.children")("/classement", "")[1] == "racine racine-ecran"
    assert cb(app, "page.children")("/fiche", "")[1] == "racine"


def test_accueil(app, donnees):
    from d3dash.pages import accueil
    lay = texte(accueil.layout())
    assert lay.count("kpi-val") == 6
    assert "data-aide" in lay and "Provinces prioritaires" in lay
    for m in accueil.MESURES_CARTE:
        # le callback rend la carte, sa légende, sa ligne « Lecture : », **la liste**, le titre du
        # panneau et l'adresse du classement complet : la liste suit la mesure choisie
        fig, legende, lec, liste, titre, lien = cb(app, "acc-carte.figure")(m)
        assert legende is not None and "limites de région" in lec
        assert len([t for t in fig.data if t.fill == "toself"]) == 45
        assert any(t.line.color == F.ENCRE for t in fig.data if t.fill == "toself")
        assert titre == accueil.TITRES_LISTE[m] and lien.endswith("" if m == "score_priorite" else m)
        assert "tab tab-top10" in texte(liste)


def test_kpis_sans_icone(donnees):
    from d3dash.pages import accueil
    kp = texte(accueil.bloc_kpis(donnees))
    assert "className='aide'" not in kp  # aucune icône « i » sur les chiffres clés


def test_clic_carte_vers_fiche():
    from dash.exceptions import PreventUpdate
    from d3dash.navigation import lien_fiche
    assert lien_fiche({"points": [{"customdata": "BF0003"}]}) == "/fiche?pcode=BF0003"
    with pytest.raises(PreventUpdate):
        lien_fiche({"points": [{"customdata": "javascript:alert(1)"}]})


def test_classement(app):
    f = cb(app, "cla-table.data")
    data, cols, resume, fig, titre, lec, note, d_an, d_st, leg, err, cache = f("score_priorite", 2024, "PUBLIC")
    assert err == "" and cache is False  # pas de bloc erreur quand les données répondent
    assert len(data) == 45 and data[0]["rang"] == 1 and d_an and d_st
    assert "Lecture" in texte(lec)
    assert texte(leg).count("leg-pastille") == 5  # légende écrite à 5 classes, jamais une barre continue
    data, cols, resume, _fig, _t, _l, _n, _d_an, d_st, *_ = f("eleves_par_maitre", 2019, "TOTAL")
    assert d_st is False and "2019-2020" in resume
    vals = [r["epm"] for r in data]
    assert vals == sorted(vals, reverse=True)
    data, cols, *_ = f("deficit_enseignants", 2024, "PUBLIC")
    assert any(c["id"] == "valeur" for c in cols)


def test_export_classement(app):
    sortie = cb(app, "cla-download.data")(1, "score_priorite", 2024, "PUBLIC", None)
    contenu = sortie["content"]
    assert contenu.startswith("\ufeff") and ";" in contenu and len(contenu.strip().splitlines()) == 46


def test_fiche(app, donnees):
    pcode = donnees["priorite"].pcode_province.iloc[0]
    r = cb(app, "fic-identite.children")(pcode, 2024, "PUBLIC")
    ident, kp, carte = r[0], r[1], r[2]
    assert len(kp) == 4
    region = donnees["priorite"].set_index("pcode_province").loc[pcode, "code_region"]
    n_region = (donnees["priorite"].code_region == region).sum()
    couleurs = [t.fillcolor for t in carte.data if t.fill == "toself"]
    assert couleurs.count(F.BLEU) == 1 and couleurs.count(F.BLEU_REGION) == n_region - 1  # région en bleu


def test_besoins(app):
    f = cb(app, "bes-kpis.children")
    kp, fig_s, lec, fig_c, leg, normes, prov, err, cache = f("S2_retour_avant_crise", "moyen", 50, 50, "TOTAL")
    assert err == "" and cache is False
    assert len(kp) == 4 and len(fig_s.data) == 2 and "choisi" in texte(normes)
    # la norme choisie est marquée autrement que par la couleur seule
    assert "ligne-centrale" in texte(normes) and "aria-current" in texte(normes)
    # légende de carte écrite (5 classes et leur ligne « Lecture : »), pas la barre de couleur de Plotly
    assert texte(leg).count("leg-case") == 5 and "Lecture" in texte(leg)
    kp60 = f("S2_retour_avant_crise", "moyen", 60, 50, "TOTAL")[0]
    assert texte(kp60[1]) != texte(kp[1])


def test_implantation(app, donnees):
    f = cb(app, "imp-table.data")
    data, tips, resume, fig, titre, err, cache = f("", "tous")
    assert err == "" and cache is False
    # la phrase de résumé est une `constat()` : les nombres sont enveloppés dans <span class="chiffre">
    assert len(data) == len(donnees["implantation"]) and "sites candidats" in texte(resume)
    data_f, *_ = f("", "fiables")
    assert all(r["fiabilite"] == "Fiable" for r in data_f) and len(data_f) < len(data)
    # la page est passée au découpage 2025 : le filtre de province porte un code de province 2025
    pcode = donnees["decoupage_sites"].pcode_province_2025.iloc[0]
    data_p, _, _, _, titre_p, _e, _c = f(pcode, "tous")
    assert 0 < len(data_p) < len(data) and "·" in titre_p
    sortie = cb(app, "imp-download.data")(1, pcode, "tous")
    assert len(sortie["content"].strip().splitlines()) == len(data_p) + 1


def test_icones_aide_site(app, donnees):
    """Exactement 4 icônes « i » sur tout le site : normes, score de priorité, scénarios et
    fiabilité des sites. Une cinquième serait à justifier."""
    par_page = {}
    for chemin in ("/", "/classement", "/fiche", "/besoins-2030", "/implantation", "/a-propos"):
        par_page[chemin] = texte(cb(app, "page.children")(chemin, "")[0]).count("className='aide'")
    assert sum(par_page.values()) == 4, par_page
    assert par_page["/"] == 1 and par_page["/besoins-2030"] == 2 and par_page["/implantation"] == 1
    assert par_page["/fiche"] == 0 and par_page["/a-propos"] == 0


def test_equipe_parametre_unique():
    """Le nom d'équipe n'est écrit qu'à un seul endroit du code (config.py)."""
    trouves = []
    for dossier, _, fichiers in os.walk(os.path.join(RACINE, "d3dash")):
        for f in fichiers:
            if f.endswith(".py") and re.search(re.escape(EQUIPE), open(os.path.join(dossier, f), encoding="utf-8").read()):
                trouves.append(f)
    assert trouves == ["config.py"]


def test_methode(app):
    """Rendue par le routeur, la page porte le nom d'équipe, les deux cases d'équipe avec leur
    titre professionnel, et exactement les sections de méthode déclarées par le module."""
    from d3dash.pages import methode
    lay = texte(cb(app, "page.children")("/a-propos", "")[0])
    assert EQUIPE in lay and "John Lamien" in lay and "Normes" in lay
    assert "Ingénieur en intelligence artificielle" in lay
    assert re.findall(r"id='(s-[a-z0-9-]+)'", lay) == [a for a, _ in methode.SECTIONS]
