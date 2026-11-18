"""Fiche province (/fiche) : balisage du kit, infobulles sans icône, scénarios en langage courant.

Les valeurs chiffrées ne sont pas re-testées ici (tests/test_callbacks.py::test_fiche) : ces tests
portent sur l'interface, pas sur les calculs.
"""
from pathlib import Path

import pytest

from d3dash import db
from d3dash.app import creer_app
from d3dash.config import Config
from d3dash.meta import DECOUPAGE_CONSTAT
from d3dash.pages import fiche

RACINE = Path(__file__).resolve().parent.parent

# classes d'une version antérieure de la page : la fiche n'en pose aucune
LEGACY = ("carte-bloc", "bloc-entete", "filtres-fiche", "filtre-province", "fiche-carte", "page-fiche",
          "table-dc", "col-num", "table-sm", "mb-0", "mb-1", "ms-2", "g-3", "Row(", "Col(")


@pytest.fixture()
def app(donnees):
    return creer_app(Config(auth_active=False, code_hash="", secret_key=""), donnees)


def cb(app, sortie):
    for k, v in app.callback_map.items():
        if sortie in k:
            return v["callback"].__wrapped__
    raise KeyError(sortie)


def test_gabarit_compose_le_kit(donnees):
    """En-tête, barre de filtres sans cadre, rangée identité/situation puis deux rangées 7/5, sans
    classe héritée."""
    h = str(fiche.layout())
    assert "travail-tete" in h and "className='pile p-fiche'" in h
    for cls in ("barre-filtres", "filtre-large", "filtre-moyen", "fiche-haut", "fiche-identite", "fiche-kpis",
                "zone-carte", "grille-fiche", "legende-situation"):
        assert cls in h, cls
    for mauvais in LEGACY:
        assert mauvais not in h, mauvais
    for id_ in ("fic-province", "fic-annee", "fic-statut", "fic-carte", "fic-identite", "fic-kpis",
                "fic-titre-evol", "fic-evol", "fic-lecture-evol", "fic-composantes", "fic-robustesse",
                "fic-2030", "fic-crise"):
        assert f"'{id_}'" in h, id_


def test_premiere_rangee_sans_blanc(donnees):
    """La première rangée n'ouvre de blanc pour **aucune** province.

    C'est la **carte de situation** qui absorbe l'écart entre les deux panneaux, dans les deux
    sens : plafonnée, elle rendrait le panneau « Situation » plus haut que l'identité et la bande
    des 4 chiffres encaisserait la différence (47 px de vide au-dessus, 51 px en dessous mesurés).
    Elle remplit donc la hauteur de son panneau, bornée par un plancher de lisibilité de 140 px
    qui borne du même coup le blanc résiduel (≤ 9 px, soit ~5 px de part et d'autre).
    """
    css = (RACINE / "assets" / "style.css").read_text(encoding="utf-8")
    bloc = css.split("13. Fiche province")[1].split("/* ==")[0]
    carte = bloc.split(".fiche-haut .zone-carte {")[1].split("}")[0]
    for regle in ("flex: 1 1 auto", "min-height: 140px", "max-height: none", "max-width: none",
                  "aspect-ratio: auto"):
        assert regle in carte, regle
    kpis = bloc.split(".fiche-kpis {")[1].split("}")[0]
    assert "margin-top: 12px" in kpis and "flex: 1 1 auto" in kpis and "margin-top: auto" not in kpis
    cellule = bloc.split(".fiche-kpis .kpi {")[1].split("}")[0]
    assert "justify-content: center" in cellule and "padding: 8px 12px" in cellule
    assert "margin-bottom" not in bloc.split(".f-rang {")[1].split("}")[0]
    # Remise à zéro sous 961 px, à la **même spécificité** (0,2,0) : en une colonne il n'y a plus
    # d'écart à absorber, la carte reprend son format et sa hauteur naturelle.
    mobile = css.split("@media (max-width: 960px)")[1].split(".fiche-haut .zone-carte {")[1].split("}")[0]
    for regle in ("flex: 0 0 auto", "min-height: 0", "aspect-ratio: 1000 / 733"):
        assert regle in mobile, regle
    # et la ligne « Lecture : » de la Situation tient sur une ligne
    h = str(fiche.layout())
    assert "province en bleu foncé, sa région en bleu clair." in h


def test_mention_de_decoupage_dans_l_entete(donnees):
    """Page de constat : la pastille fixe « Données 2017-2025 · découpage d'avant 2025 »."""
    h = str(fiche.layout())
    assert "className='decoupage'" in h and DECOUPAGE_CONSTAT in h


def test_fiche_rendu_complet(app, donnees):
    """Parcours heureux : les dix sorties du callback sont remplies et portent le balisage attendu."""
    pcode = donnees["priorite"].sort_values("rang_priorite").pcode_province.iloc[0]
    ident, kp, carte, tete, evol, lec, comp, rob, t2030, crise = cb(app, "fic-identite.children")(
        pcode, 2024, "PUBLIC")
    assert "f-region" in str(ident) and "badge" in str(ident) and "sur 45" in str(ident)
    assert len(kp) == 4 and "Élèves par maître" in str(kp[0])
    # aucune icône « i » : infobulle sur les deux seuls libellés non évidents
    assert "className='aide'" not in str(kp)
    assert sum("kpi kpi-aide" in str(c) for c in kp) == 2
    assert "kpi-aide" in str(kp[2]) and "kpi-aide" in str(kp[3])
    assert "primaire public" in str(tete) and "Évolution de" in str(tete)
    assert carte.data and evol.data and comp.data
    assert "Lecture : " in str(lec) and "Lecture : " in str(rob)
    assert "liste-chiffres" in str(crise) and "panneau-pied" in str(crise) and "lien-suite" in str(crise)
    assert "sites fiables" in str(crise)


def test_scenarios_en_langage_courant(app, donnees):
    """Les quatre scénarios sont nommés en clair, le code entre parenthèses, le central est mis en valeur."""
    pcode = donnees["priorite"].pcode_province.iloc[0]
    t2030 = cb(app, "fic-identite.children")(pcode, 2024, "PUBLIC")[8]
    h = str(t2030)
    assert "tab" in h and "table-defile" in h and "c-num" in h
    for lib in ("Si rien ne change (S1)", "Retour au taux d'avant-crise (S2, central)",
                "Même taux, sans réouverture des salles (S2b)", "Tous les enfants scolarisés (S3)"):
        assert lib in h, lib
    assert h.count("ligne-centrale") == 1
    assert "Lecture : " in h


def test_etat_vide_sans_scenario(source, monkeypatch):
    """Province sans scénario 2030 : état vide du kit (ce qui manque et quoi faire), jamais un tableau vide."""
    d = db.Donnees(source, ttl_s=3600)
    db.installer(d)
    d.get()
    jeu = d.get()
    pcode = jeu["priorite"].pcode_province.iloc[0]
    sans = jeu["province_2030"][jeu["province_2030"].pcode_province != pcode]
    monkeypatch.setitem(jeu, "province_2030", sans)
    h = str(fiche._table_2030(d, pcode))
    assert "className='vide'" in h and "ne sont pas calculés" in h and "Besoins 2030" in h
    assert "<table" not in h.lower() and "Table(" not in h


def test_infobulle_des_kpis_suit_le_secteur(app, donnees):
    """L'infobulle d'un chiffre clé dit le secteur **affiché** : devant un chiffre « public + privé »,
    elle ne peut pas dire « dans le public »."""
    pcode = donnees["priorite"].pcode_province.iloc[0]
    for statut, attendu, interdit in (("PUBLIC", "dans le public.", "public et le privé"),
                                      ("TOTAL", "dans le public et le privé.", "dans le public.")):
        kp = str(cb(app, "fic-identite.children")(pcode, 2024, statut)[1])
        assert attendu in kp, statut
        assert interdit not in kp, statut


def test_sous_titre_sans_repetition(app, donnees):
    """Quand les noms de 2025 sont ceux d'aujourd'hui, la région est écrite **une** fois : pas de
    « Région Region Fictive 02 · découpage 2025 : … région Region Fictive 02 »."""
    pcode = donnees["priorite"].pcode_province.iloc[0]
    ident = str(cb(app, "fic-identite.children")(pcode, 2024, "PUBLIC")[0])
    assert "découpage 2025" not in ident
    assert ident.count("Region Fictive") == 1 or ident.count("Région Region") == 0
    # un vrai redécoupage, lui, reste annoncé
    pa = {"province_nouvelle": "PROVINCE FICTIVE 99", "region_nouvelle": "REGION FICTIVE 99"}
    r = donnees["priorite"].set_index("pcode_province").loc[pcode]
    r = {"province": r["province"], "region": r["region"], "classe_priorite": r["classe_priorite"],
         "rang_priorite": r["rang_priorite"], "score_priorite": r["score_priorite"]}
    assert "découpage 2025" in str(fiche._identite(r, pa))


def test_composantes_avec_piste_et_valeurs_alignees(app, donnees):
    """« Pourquoi cette priorité ? » : piste claire derrière chaque barre et valeur à droite."""
    from d3dash import figures as Fg
    pcode = donnees["priorite"].pcode_province.iloc[0]
    fig = cb(app, "fic-identite.children")(pcode, 2024, "PUBLIC")[6]
    assert len(fig.data) == 2                      # la piste, puis la barre
    assert fig.data[0].marker.color == Fg.PISTE and set(fig.data[0].x) == {100}
    assert fig.data[1].marker.color == Fg.PISTE_PLEINE
    assert fig.layout.barmode == "overlay"
    assert fig.layout.yaxis.ticklabelstandoff == 8  # l'air entre le libellé et la piste


def test_graphique_evolution_annees_lisibles(app, donnees):
    """Axe du temps : l'année de début, à l'horizontale."""
    pcode = donnees["priorite"].pcode_province.iloc[0]
    fig = cb(app, "fic-identite.children")(pcode, 2024, "PUBLIC")[4]
    assert list(fig.layout.xaxis.ticktext) == ["2017", "2018", "2019", "2020", "2021", "2022",
                                               "2023", "2024"]
    assert fig.layout.xaxis.tickangle == 0
    assert all("-" in v for v in fig.layout.xaxis.tickvals)      # les périodes restent les valeurs
    # l'étiquette de la norme ne se pose plus sur la graduation « 50 », à gauche
    note = [a for a in fig.layout.annotations if "norme" in (a.text or "")][0]
    assert note.xanchor == "right"
