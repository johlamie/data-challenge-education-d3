"""Classement (`/classement`) : structure « plan de travail », tableau lisible, carte réelle, état vide."""
from pathlib import Path

import pytest
from dash.exceptions import PreventUpdate

from d3dash import figures as F
from d3dash.app import creer_app
from d3dash.config import Config
from d3dash.meta import MESURES
from d3dash.pages import classement

RACINE = Path(__file__).resolve().parent.parent


def texte(x):
    return str(x)


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
    return texte(classement.layout())


def test_structure_plan_de_travail(page):
    """En-tête, phrase de résumé, barre de filtres sans cadre, puis tableau (gauche) et carte (droite)."""
    assert "travail-tete" in page and "Classement des provinces" in page
    assert "className='constat'" in page
    assert "className='barre-filtres'" in page
    assert "className='rangee'" in page
    assert "zone-liste" in page and "zone-carte" in page and "bloc-carte" in page
    assert "Exporter en CSV" in page and "btn-contour" in page


def test_filtres_sans_cadre_et_export_sur_la_rangee(page):
    """Aucun panneau autour des filtres, et l'export est le dernier enfant de la barre de filtres
    — donc la seule action, poussée à droite par `margin-left: auto` (`.barre-filtres`)."""
    assert "panneau-controles" not in page and "ligne-outils" not in page
    contenu = [c for c in classement.layout().children if getattr(c, "id", None) == "cla-contenu"][0]
    barre = [c for c in contenu.children if getattr(c, "className", None) == "barre-filtres"][0]
    enfants = barre.children
    assert [getattr(c, "className", None) for c in enfants[:3]] == [
        "filtre filtre-large", "filtre filtre-moyen", "filtre filtre-moyen"]
    assert enfants[3].id == "cla-export-btn" and enfants[3].className == "btn-contour"
    # la note contextuelle a quitté la barre : elle est la note du panneau du tableau
    assert enfants[4] is None
    assert "Span(id='cla-note', className='note')" in str(classement.layout())


def test_mention_de_decoupage_dans_l_entete(page):
    """Page de constat : la pastille fixe « Données 2017-2025 · découpage d'avant 2025 »."""
    from d3dash.meta import DECOUPAGE_CONSTAT
    assert "className='decoupage'" in page and DECOUPAGE_CONSTAT in page
    assert page.index("tete-droite") < page.index("barre-filtres")


def test_identifiants_de_callbacks_conserves(page):
    for id_ in ("cla-mesure", "cla-annee", "cla-statut", "cla-table", "cla-carte", "cla-titre-carte",
                "cla-lecture", "cla-legende", "cla-resume", "cla-note", "cla-export-btn", "cla-download",
                "cla-aller"):
        assert id_ in page, id_


def test_aucune_classe_heritee(page):
    """Les classes de la section « Compatibilité » de style.css ont disparu de cette page."""
    for legacy in ("titre-page", "sous-titre", "carte-bloc", "bloc-entete", "ligne-principale",
                   "ligne-classement", "filtres-compacts", "filtres-classement", "filtre-2col",
                   "btn-outline-primary", "mb-0"):
        assert legacy not in page, legacy


def test_aucune_icone_aide_le_score_est_explique_en_mots(page):
    """Règle utilisateur : pas d'icône « i » ici ; le score et les classes P1-P3 sont écrits en toutes lettres."""
    assert "className='aide'" not in page
    assert "0 à 100" in page and "P1 = priorité robuste" in page


def _largeurs_declarees():
    """Largeur déclarée de chaque colonne, lue dans `style_cell_conditional`."""
    return {r["if"]["column_id"]: int(r["width"].removesuffix("px")) for r in classement.LARGEURS}


# Largeur utile du panneau du tableau à 1366×768, **mesurée** sur la démo : 692 px de conteneur
# moins la barre de défilement verticale du corps. Le composant agrandit les largeurs déclarées
# pour remplir son conteneur, mais ne les réduit **jamais** : au-delà, la dernière colonne est
# rognée sans défilement possible.
LARGEUR_UTILE_1366 = 682


def test_toutes_les_colonnes_tiennent_a_1366(app):
    """Aucun critère ne peut déborder du panneau : la somme des largeurs de la configuration la
    plus large (8 colonnes, un critère qui ajoute sa colonne de mesure) tient dans les 682 px
    utiles mesurés à 1366×768."""
    larg = _largeurs_declarees()
    pires = []
    for mesure in MESURES:
        ids = [c["id"] for c in classement.colonnes(mesure)]
        # toute colonne rendue porte une largeur déclarée : sans largeur, une cellule longue
        # pousse le tableau hors de son panneau (DataTable 4.5)
        assert set(ids) <= set(larg), (mesure, ids)
        pires.append((sum(larg[i] for i in ids), mesure))
    total, pire = max(pires)
    assert total == classement.LARGEUR_TOTALE_MAX, (total, pire)
    assert total <= LARGEUR_UTILE_1366, (total, pire)
    # et la configuration la plus étroite reste assez large pour que l'étirement garde des
    # proportions lisibles (jamais moins de la moitié de la largeur utile)
    assert min(pires)[0] >= LARGEUR_UTILE_1366 // 2


def test_minima_de_lisibilite_par_colonne():
    """Chaque colonne reste au-dessus de son minimum **mesuré** : mot le plus long de l'en-tête
    + 8 px de flèche de tri + 16 px de remplissage. En dessous, l'en-tête perd des lettres
    (« Régio ») ou tombe sur une ligne de plus, ce qui mange le budget vertical."""
    minima = {"rang": 55, "province": 76, "valeur": 95, "score": 55, "classe": 68,
              "epm": 86, "eps": 86, "region": 66}
    larg = _largeurs_declarees()
    assert set(larg) == set(minima)
    for col, mini in minima.items():
        assert larg[col] >= mini, (col, larg[col], mini)


def test_le_tableau_defile_dans_son_bloc_s_il_deborde():
    """Filet de sécurité : sur une fenêtre plus étroite, le tableau défile **dans son bloc**.
    Le `.dash-spreadsheet-inner` du composant est livré en `overflow-x: hidden` : sans cette
    règle, le dépassement est rogné en silence (en-tête figé et corps défilent ensemble)."""
    css = (RACINE / "assets" / "page-classement.css").read_text(encoding="utf-8")
    assert ".p-classement .dash-spreadsheet-inner { overflow-x: auto; }" in css


def test_aucune_cellule_tronquee_par_des_points_de_suspension():
    """Un nom passe à la ligne, un nombre garde sa largeur : jamais de « … » (le DataTable n'a
    pas d'attribut `title`, une cellule tronquée serait illisible)."""
    assert classement.STYLE_CELLULE["textOverflow"] == "clip"
    assert classement.STYLE_CELLULE["whiteSpace"] == "nowrap"      # les nombres ne se coupent pas
    renvois = {r["if"]["column_id"] for r in classement.LARGEURS if r.get("whiteSpace") == "normal"}
    assert renvois == {"province", "region"}                        # les textes, eux, passent à la ligne
    assert classement.STYLE_ENTETE["whiteSpace"] == "normal"


def test_colonnes_en_toutes_lettres():
    """Aucune abréviation non expliquée dans les en-têtes, et l'unité est dite quand il y en a une.

    L'échelle 0-100 du score et la définition de P1/P2/P3 sont écrites sous le tableau : les
    en-têtes restent courts (« Score », « Priorité ») plutôt que de tomber sur trois lignes."""
    for mesure in MESURES:
        noms = [c["name"] for c in classement.colonnes(mesure)]
        assert "Score" in noms and "Priorité" in noms
        assert not any("Ens." in n or "/maître" in n or "> 3 km" in n for n in noms), noms
        # la mesure choisie n'a sa colonne que si elle n'est pas déjà une colonne fixe
        attendu = mesure not in classement.MESURES_SANS_COLONNE
        cols = classement.colonnes(mesure)
        assert any(c["id"] == "valeur" for c in cols) is attendu
        # Ordre de lecture d'un téléphone : la mesure qui **fait** le classement vient juste après
        # le nom de province, la région passe en dernier.
        assert noms[:2] == ["Rang", "Province"] and noms[-1] == "Région"
        if attendu:
            # la colonne de la mesure classée garde son libellé entier et son unité
            assert noms[2] == classement.titre_mesure(mesure)
        else:
            assert noms[2] in ("Score", "Élèves par maître", "Élèves par salle")
    assert classement.titre_mesure("acces_part_hors_3km").endswith("(en %)")


def test_carte_reelle_et_legende_ecrite(app):
    """45 contours réels, contour noir sur les 10 premières, légende HTML à 5 classes (pas de barre Plotly)."""
    data, cols, resume, fig, titre, lec, note, d_an, d_st, leg, *_ = cb(app, "cla-table.data")(
        "deficit_enseignants", 2024, "PUBLIC")
    provinces = [t for t in fig.data if t.fill == "toself"]
    assert len(provinces) == 45
    assert sum(1 for t in provinces if t.line.color == F.ENCRE) == 10
    assert not any(getattr(t.marker, "showscale", None) for t in fig.data)  # légende écrite en HTML
    legende = texte(leg)
    assert legende.count("leg-case") == 5 and "Enseignants manquants" in legende
    assert "Les 45 provinces classées selon" in resume and titre == "Enseignants manquants"
    assert len(data) == 45 and any(c["id"] == "valeur" for c in cols)


def test_clic_sur_la_carte_ouvre_la_fiche(app):
    """Clic sur un remplissage : Plotly renvoie tout le tableau `customdata`, la fiche s'ouvre quand même."""
    ouvrir = cb(app, "cla-aller.href")
    assert ouvrir({"points": [{"customdata": ["BF0017"] * 85, "pointNumber": None}]}) == "/fiche?pcode=BF0017"
    assert ouvrir({"points": [{"customdata": "BF0003"}]}) == "/fiche?pcode=BF0003"
    with pytest.raises(PreventUpdate):
        ouvrir({"points": [{"customdata": ["javascript:alert(1)"]}]})


def test_etat_vide_quand_un_filtre_ne_laisse_rien(app):
    """Filtre de colonne sans résultat : ce qui manque **et** quoi faire, jamais un tableau vide."""
    f = cb(app, "cla-vide.children")
    assert f(None) is None and f([{"rang": 1}]) is None
    vide = texte(f([]))
    assert "Aucune province ne correspond à ce filtre." in vide
    assert "Effacez les filtres" in vide and "Effacer les filtres" in vide
    effacer = cb(app, "cla-table.filter_query")
    assert effacer(1) == ""
    # le bouton naît avec l'état vide : son apparition ne doit pas effacer le filtre toute seule
    with pytest.raises(PreventUpdate):
        effacer(0)


def test_panne_de_donnees_un_seul_bloc_erreur(app, monkeypatch):
    """Base injoignable : **un** bloc rouge et rien d'autre — ni état vide, ni export actif, ni
    « Données indisponibles » sur la carte."""
    def _panne():
        raise RuntimeError("base injoignable")
    monkeypatch.setattr(classement, "donnees", _panne)
    sortie = cb(app, "cla-table.data")("score_priorite", 2024, "PUBLIC")
    data, cols, resume, _fig, _titre, lecture_, note, _a, _s, legende, erreur, cache = sortie
    assert "bloc-erreur" in texte(erreur) and cache is True      # le contenu entier disparaît
    assert data == [] and cols == [] and resume == "" and note == ""
    assert lecture_ == "" and legende is None
    # l'état vide du tableau ne contredit plus le bloc erreur : il n'est rendu que s'il y a des colonnes
    assert "bloc-erreur" not in texte(note)


def test_tri_atteignable_a_la_souris_et_au_clavier(app):
    """La page dit « cliquez sur un en-tête pour trier » : la phrase doit être vraie.

    Toute la cellule d'en-tête déclenche le tri (pseudo-élément du contrôle de tri étendu à la
    cellule, dans `assets/style.css`) et le contrôle est focalisable au clavier
    (`assets/tableau.js`), avec un anneau de focus visible.
    """
    css = (RACINE / "assets" / "style.css").read_text(encoding="utf-8")
    assert ".dash-table-container th.dash-header .column-header--sort::after" in css
    assert "inset: 0" in css.split("column-header--sort::after")[1][:200]
    assert "column-header--sort:focus-visible::after" in css
    js = (RACINE / "assets" / "tableau.js").read_text(encoding="utf-8")
    assert "tabindex" in js and "aria-label" in js and "Enter" in js
    # et la phrase reste affichée : elle est la note du panneau du tableau (`cla-note`),
    # écrite par le callback dans les deux cas — mesure annuelle ou non
    note_annuelle = cb(app, "cla-table.data")("deficit_enseignants", 2024, "PUBLIC")[6]
    note_fixe = cb(app, "cla-table.data")("score_priorite", 2024, "PUBLIC")[6]
    assert "cliquez sur un en-tête pour trier" in note_annuelle
    assert "cliquez sur un en-tête pour trier" in note_fixe
    # la note dit aussi pourquoi les deux menus sont désactivés sur une mesure non annuelle
    assert "l'année et le secteur n'y changent rien" in note_fixe


def test_champ_de_filtre_focalisable_et_tactile():
    """Le champ de filtre d'un tableau porte l'anneau de focus du kit et 44 px sous 961 px."""
    css = (RACINE / "assets" / "style.css").read_text(encoding="utf-8")
    assert ".dash-table-container .dash-filter input:focus-visible" in css
    assert "outline: 2px solid var(--ring)" in css.split(".dash-filter input:focus-visible")[1][:220]
    bloc = css.split("@media (max-width: 960px)")[1]
    assert ".dash-table-container .dash-filter input { min-height: 44px; }" in bloc
