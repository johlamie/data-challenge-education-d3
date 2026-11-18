"""Besoins 2030 (`/besoins-2030`) : composition du kit, libellés en mots simples, carte réelle et
légende écrite, sensibilité aux normes, et **découpage 2025** (47 provinces) sur tout ce qui est par
province. Aucun calcul n'est vérifié ici (voir tests/test_calculs.py et tests/test_decoupage_2025.py)."""
import pytest

from d3dash import calculs as C
from d3dash import decoupage as D25
from d3dash.app import creer_app
from d3dash.config import Config
from d3dash.meta import DECOUPAGE_2025, NORMES_CLASSE, NORMES_ENSEIGNANT, POPULATIONS, SCENARIOS
from d3dash.pages import besoins

# classes héritées de « 16. Compatibilité » (assets/style.css) : la page refondue n'en utilise plus
LEGACY = ("titre-page", "sous-titre", "carte-bloc", "page-besoins", "ligne-kpi ", "filtres-besoins",
          "filtre-scenario", "table-dc", "table-normes", "table-sm", "table-responsive", "col-num",
          "col-reg", "bloc-entete")


def texte(x):
    return str(x)


def mots(x):
    """Texte visible d'un arbre de composants (str() échappe les espaces insécables des milliers)."""
    if isinstance(x, str):
        return x
    if isinstance(x, (list, tuple)):
        return "".join(mots(i) for i in x)
    enfants = getattr(x, "children", None)
    return mots(enfants) if enfants is not None else ""


def cb(app, sortie):
    for k, v in app.callback_map.items():
        if sortie in k:
            return v["callback"].__wrapped__
    raise KeyError(sortie)


@pytest.fixture()
def app(donnees):
    return creer_app(Config(auth_active=False, code_hash="", secret_key=""), donnees)


@pytest.fixture()
def page():
    return texte(besoins.layout())


@pytest.fixture()
def rendu(app):
    """Sortie complète du callback dans le cas nominal."""
    return cb(app, "bes-kpis.children")("S2_retour_avant_crise", "moyen", 50, 50, "TOTAL")


def test_structure_du_kit(page):
    """La page est une pile de blocs du kit : en-tête, filtres, bande de 4 chiffres, deux rangées 5/7."""
    assert "pile p-besoins" in page
    assert "travail-tete" in page and "Besoins en 2030" in page
    assert page.count("bande-kpi ligne-kpi-4") == 1
    assert page.count("grille-fiche grille-fiche-57") == 2
    assert "bloc-carte" in page and "zone-carte" in page


def test_aucune_classe_de_compatibilite(page):
    assert [c for c in LEGACY if c in page] == []


def test_identifiants_conserves(page):
    for id_ in ("bes-scenario", "bes-pop", "bes-nc", "bes-nm", "bes-statut", "bes-kpis", "bes-scenarios",
                "bes-lecture-scenarios", "bes-carte", "bes-normes", "bes-provinces"):
        assert f"id='{id_}'" in page, id_


def test_valeurs_des_options_inchangees(page):
    """Les libellés passent en mots simples, les valeurs restent celles de meta.py (callbacks et outils)."""
    for v in list(SCENARIOS) + list(POPULATIONS):
        assert f"'value': '{v}'" in page, v
    for n in set(NORMES_CLASSE) | set(NORMES_ENSEIGNANT):
        assert f"'value': {n}" in page, n
    assert "Retour au taux d'avant-crise (S2, central)" in page
    # « 50 (norme officielle) » était coupé dans un champ de 184 px (les 5 filtres sur une rangée) :
    # le libellé court suffit, « norme officielle » restant écrit dans l'icône « i » du champ.
    assert "50 (norme)" in page and "ancien plafond" in page and "norme officielle" not in page



def test_deux_icones_aide_et_aucune_sur_un_chiffre(page, rendu):
    """Cet écran porte 2 des 4 icônes « i » du site (scénarios, normes) et aucune sur un chiffre clé."""
    assert page.count("className='aide'") == 2
    assert "className='aide'" not in texte(rendu[0])


def test_chiffres_cles(rendu):
    kp = rendu[0]
    assert len(kp) == 4
    assert "kpi kpi-aide" in texte(kp[1]) and "kpi kpi-aide" in texte(kp[2])  # 2 cellules à infobulle
    assert texte(kp[0]).count("kpi-aide") == 0 and texte(kp[3]).count("kpi-aide") == 0


def test_carte_reelle_et_legende_ecrite(rendu):
    """47 contours réels (découpage 2025), rampe ocre à 5 classes, légende HTML avec son unité et sa
    ligne « Lecture : »."""
    fig, leg = rendu[3], texte(rendu[4])
    assert len([t for t in fig.data if t.fill == "toself"]) == 47
    assert not any(t.type.endswith("mapbox") for t in fig.data)
    assert leg.count("leg-case") == 5 and "Salles à construire d'ici 2030" in leg
    assert "Lecture" in leg


def test_graphique_scenarios_sans_accent(rendu):
    """Séries encre + ocre (jetons de figures.py) : le bleu de sélection ne sert pas à une série."""
    fig = rendu[1]
    couleurs = [t.marker.color for t in fig.data]
    assert couleurs == [F_ENCRE, F_OCRE]


def test_tables_de_sensibilite(app):
    """Une ligne par norme ; la norme choisie est marquée en neutre et par un texte, jamais par la couleur seule."""
    f = cb(app, "bes-kpis.children")
    normes = texte(f("S2_retour_avant_crise", "moyen", 60, 45, "TOTAL")[5])
    assert normes.count("ligne-centrale") == 2  # une ligne choisie par tableau
    assert normes.count("· choisi") == 2 and normes.count("aria-current") == 2
    for lib in list(besoins.LIB_NORMES_CLASSE.values()) + list(besoins.LIB_NORMES_ENSEIGNANT.values()):
        assert lib in normes, lib


def test_les_chiffres_suivent_la_norme(app):
    """La norme change bien tous les chiffres de la page (contrat d'outils/verifier_d3.py)."""
    f = cb(app, "bes-kpis.children")
    a = f("S2_retour_avant_crise", "moyen", 50, 50, "TOTAL")
    b = f("S2_retour_avant_crise", "moyen", 60, 50, "TOTAL")
    assert texte(a[0][1]) != texte(b[0][1])      # salles à construire
    assert texte(a[5]) != texte(b[5])            # effet de la norme
    assert texte(a[6]) != texte(b[6])            # provinces


def test_tableau_provinces(rendu):
    """10 lignes, un lien vers la fiche, les nombres jamais tronqués, un défilement interne au bloc."""
    prov = texte(rendu[6])
    assert prov.count("/fiche?pcode=") == 10
    assert "table-defile" in prov and "tab tab-top10" in prov
    assert prov.count("c-num") >= 40 and "Lecture" in prov


# ---- découpage 2025 -----------------------------------------------------------------------------------------
def test_titre_et_mention_de_decoupage(page):
    """Le titre de la page et la mention fixe, dans l'en-tête, en pastille neutre."""
    assert "Besoins en 2030 (nouveau découpage 2025)" in page
    assert DECOUPAGE_2025 == "Projection 2030 · découpage 2025 (47 provinces)"
    assert DECOUPAGE_2025 in page and "className='decoupage'" in page
    # la page n'annonce plus 45 provinces nulle part
    assert "45 provinces" not in page and "sur 45" not in page
    assert "47 provinces" in page and "10 sur 47" in page


@pytest.mark.parametrize("scenario,nc,nm", [("S2_retour_avant_crise", 50, 50), ("S3_universel", 60, 45)])
def test_les_provinces_de_la_page_sont_les_47_du_decoupage_2025(app, donnees, scenario, nc, nm):
    """47 provinces sur la carte et dans la liste, et des totaux nationaux inchangés : la somme des
    47 provinces 2025 est exactement celle des 45 provinces d'avant 2025."""
    b25 = D25.besoins_province_2025(donnees, scenario, "moyen", "TOTAL", nc, nm)
    ancien = C.besoins_province(donnees, scenario, "moyen", "TOTAL", nc, nm)
    assert len(b25) == 47 and b25.pcode_province_2025.nunique() == 47
    for col in ("salles_a_construire_2030", "enseignants_supplementaires_2030", "eleves_2030",
                "salles_reouvrables"):
        assert b25[col].sum() == ancien[col].sum(), col
    kp, _, _, fig, _, _, prov, *_ = cb(app, "bes-kpis.children")(scenario, "moyen", nc, nm, "TOTAL")
    # un contour par province 2025 sur la carte, et les 10 premières de la même table dans la liste
    assert len([t for t in fig.data if t.fill == "toself"]) == 47
    for nom in b25.province_nom.head(10):
        assert nom in mots(prov), nom
    # le chiffre clé national reste le total, c'est-à-dire la somme des 47 provinces affichées
    from d3dash.meta import fmt_nombre
    assert fmt_nombre(b25.salles_a_construire_2030.sum()) in mots(kp[1])


def test_anciennement_et_lien_vers_la_fiche_de_l_ancienne_province(app, donnees, rendu):
    """Une province renommée ou scindée en 2025 porte son nom d'avant, dans la liste et dans le survol
    de la carte ; son lien ouvre la fiche de l'**ancienne** province (la Fiche est sur l'ancien découpage)."""
    b25 = D25.besoins_province_2025(donnees).head(10)
    renommees = b25[b25.anciennement.notna()]
    assert len(renommees), "le jeu de démonstration doit contenir une province renommée dans le top 10"
    prov, fig = mots(rendu[6]), rendu[3]
    for r in renommees.itertuples():
        assert f"anciennement : {r.anciennement}" in prov
        assert f"/fiche?pcode={r.pcode_province}" in texte(rendu[6])
        assert f"Fiche de l'ancienne province {r.anciennement}" in texte(rendu[6])
    survols = [t.text for t in fig.data if t.fill == "toself"]
    for r in renommees.itertuples():
        assert any(s and f"anciennement : {r.anciennement}" in s for s in survols), r.province_nom
    # aucune ligne « anciennement » là où le nom n'a pas changé
    assert prov.count("anciennement : ") == len(renommees)


def test_tables_du_decoupage_absentes_bloc_erreur(app, source, monkeypatch):
    """Les tables `decoupage_2025_*` viennent d'une étape additive du pipeline : si elles manquent,
    cette page de projection affiche son bloc rouge — jamais une moitié de page sur l'ancien découpage."""
    from test_decoupage_2025 import SourceDegradee

    from d3dash import db
    d = db.Donnees(SourceDegradee(source), ttl_s=3600)
    assert d.decoupage_disponible is False
    monkeypatch.setattr(besoins, "donnees", lambda: d)
    sortie = cb(app, "bes-kpis.children")("S2_retour_avant_crise", "moyen", 50, 50, "TOTAL")
    assert "bloc-erreur" in texte(sortie[7]) and sortie[8] is True
    assert sortie[6] is None and sortie[4] is None


def test_etat_erreur(app, monkeypatch):
    """Base injoignable : le bloc erreur remplace les chiffres, aucune valeur périmée n'est affichée."""
    monkeypatch.setattr(besoins, "donnees", _base_en_panne)
    sortie = cb(app, "bes-kpis.children")("S2_retour_avant_crise", "moyen", 50, 50, "TOTAL")
    # un seul bloc rouge, au-dessus du contenu, et le contenu disparaît
    assert "bloc-erreur" in texte(sortie[7]) and sortie[8] is True
    assert "bloc-erreur" not in texte(sortie[0])
    assert sortie[2] is None and sortie[4] is None and sortie[5] is None and sortie[6] is None


def _base_en_panne():
    raise RuntimeError("base injoignable")


F_ENCRE = "#16222E"
F_OCRE = "#B36C16"
