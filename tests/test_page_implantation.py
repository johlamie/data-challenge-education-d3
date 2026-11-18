"""Implantation (`/implantation`) : structure « plan de travail » (carte dans la colonne large),
légendes du kit, état vide, statuts écrits et **découpage 2025** (47 provinces)."""
import pytest

from d3dash import calculs as C
from d3dash import decoupage as D25
from d3dash import figures as F
from d3dash.config import Config
from d3dash.app import creer_app
from d3dash.meta import DECOUPAGE_2025, nom_propre
from d3dash.pages import implantation as I


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
def page(donnees):
    return texte(I.layout())


def test_structure_plan_de_travail(page):
    """En-tête, phrase de résumé, barre de filtres sans cadre, rangée carte + liste, deux légendes,
    deux lectures."""
    assert "travail-tete" in page and "Où implanter de nouvelles écoles ?" in page
    assert "className='constat'" in page and "imp-resume" in page
    assert "className='rangee'" in page and "bloc-carte" in page
    assert "Sites candidats" in page and "Exporter en CSV" in page
    assert page.count("className='legende'") == 1 and page.count("legende-marqueurs") == 1
    assert page.count("className='leg-case'") == 5 and page.count("className='lecture'") == 2
    # barre de filtres sans cadre : ni panneau de contrôles, ni ligne d'outils
    assert "barre-filtres" in page and "ligne-outils" not in page
    assert page.count("className='panneau'") == 1 and page.count("panneau bloc-carte") == 1
    # les identifiants des callbacks ne changent pas
    for id_ in ("imp-province", "imp-sites", "imp-table", "imp-carte", "imp-titre-carte",
                "imp-export-btn", "imp-download"):
        assert id_ in page


def test_le_tableau_n_a_pas_de_ligne_de_filtres_native(page):
    """Dans des colonnes de 46 à 118 px, le champ de filtre natif n'affiche même pas son libellé
    (« filtr ») : la page garde ses deux filtres et le tri par en-tête."""
    assert "filter_action='none'" in page and "sort_action='native'" in page
    assert "filter_options" not in page and "style_filter" not in page
    assert "Province" in page and "Sites affichés" in page


def test_carte_dans_la_colonne_large_et_liste_ensuite(page, donnees):
    """La carte occupe la colonne principale, la liste l'autre côté. L'ordre des enfants de la
    rangée est la seule chose qui le décide (le CSS lit `:first-child`)."""
    rangee = [e for e in I.layout().children if getattr(e, "className", "") == "pile zone-contenu"][0]
    rangee = [e for e in rangee.children if getattr(e, "className", "") == "rangee"][0]
    gauche, droite = rangee.children
    assert "bloc-carte" in gauche.className and "imp-carte" in texte(gauche)
    assert "imp-table" in texte(droite) and "Sites candidats" in texte(droite)
    # la légende de la rampe tient en 5 colonnes : la carte n'est pas dans un panneau étroit
    assert "leg-rampe-colonne" not in page


def test_carte_zoomable_hors_ligne(page):
    """La carte se déplace et zoome, sans barre d'outils Plotly ni tuile en ligne."""
    assert "'scrollZoom': True" in page and "'displayModeBar': False" in page
    for id_ in ("imp-zoom-plus", "imp-zoom-moins", "imp-recadrer"):
        assert id_ in page, id_
    assert "Agrandir" in page and "Réduire" in page and "Recadrer" in page
    assert "outils-carte" in page and "mapbox" not in page.lower() and "http" not in page


def test_une_seule_icone_aide_sur_la_fiabilite(page):
    """Cette page porte une seule des 4 icônes « i » du site : la fiabilité des sites."""
    assert page.count("className='aide'") == 1 and "Aide : Fiabilité des sites" in page


def test_aucune_classe_heritee(page):
    """Les classes de la section « Compatibilité » de style.css ont disparu de cette page."""
    for legacy in ("titre-page", "sous-titre", "carte-bloc", "bloc-entete", "ligne-principale",
                   "ligne-implantation", "filtres-compacts", "filtres-implantation", "filtre-2col",
                   "legende-carte", "btn-outline-primary", "bloc-plein", "bloc-liste"):
        assert legacy not in page, legacy


def test_legende_classee_porte_les_bornes_et_l_unite(page):
    """La rampe ocre est écrite en 5 classes avec leur unité (jamais une barre continue)."""
    for lib in ("moins de 20 %", "20 % à 40 %", "40 % à 60 %", "60 % à 80 %", "80 % et plus"):
        assert lib in page.replace("\\u202f", " ").replace(" ", " "), lib


def test_statut_du_site_ecrit_en_toutes_lettres(app, donnees):
    """La fiabilité est un texte lisible, jamais une couleur seule ; l'accent ne sert pas de statut."""
    data, tips, resume, fig, titre, *_ = cb(app, "imp-table.data")("", "tous")
    statuts = {r["fiabilite"] for r in data}
    assert statuts <= {I.FIABLE, I.A_VERIFIER} and I.A_VERIFIER in statuts
    assert "#1d3f6e" not in texte(I._tableau()).lower()
    # chaque ligne garde une infobulle qui explique son statut
    assert len(tips) == len(data) and all("fiabilite" in t for t in tips)


def test_resume_reprend_les_memes_comptes(app, donnees):
    """La phrase cite exactement les comptes de `calculs.sites` (aucun chiffre inventé)."""
    from d3dash.meta import fmt_nombre
    _, _, resume, *_ = cb(app, "imp-table.data")("", "tous")
    tous = C.sites(donnees)
    fia = tous[tous.sites_fiables == 1]
    t = mots(resume)
    assert f"{fmt_nombre(len(tous))} sites candidats" in t
    assert f"{fmt_nombre(len(fia))} fiables" in t
    assert f"{fmt_nombre(fia.enfants_6_11_2030_desservis.sum())} enfants" in t
    assert "className='chiffre'" in texte(resume)


def test_resume_accorde_le_singulier_et_le_cas_zero(donnees):
    """Pires cas de la phrase : un seul site, aucun site fiable, aucun site du tout."""
    tous = C.sites(donnees)
    un = tous.head(1)
    t = mots(I._resume("Province Fictive 05", un, un))
    assert "1 site candidat est à plus de 3 km" in t and "Ce site fiable servirait" in t
    sans_fiable = mots(I._resume("Province Fictive 05", un, un.iloc[0:0]))
    assert "dont 0 fiable." in sans_fiable and "Aucun site n'est fiable ici" in sans_fiable
    vide = mots(I._resume("Province Fictive 05", tous.iloc[0:0], tous.iloc[0:0]))
    assert vide == "Province Fictive 05 : aucune localité candidate à plus de 3 km d'une école connue."


def test_etat_vide_dit_quoi_faire(app):
    """Aucun site après filtrage : le tableau est masqué et l'état vide propose une sortie."""
    f = cb(app, "imp-vide.children")
    vide, masque = f([], "fiables", "BF0001")
    assert masque is True and "Aucun site fiable" in mots(vide)
    assert "Tous, y compris à vérifier" in mots(vide)
    rien, masque = f([{"rang": 1}], "tous", "")
    assert rien is None and masque is False


def test_carte_zoome_sur_la_province_choisie(app, donnees):
    """Choisir une province recadre la carte sur elle (et sur elle seule)."""
    f = cb(app, "imp-table.data")
    pcode = donnees["decoupage_sites"].pcode_province_2025.iloc[0]
    _, _, _, national, *_ = f("", "tous")
    _, _, _, zoom, titre, *_ = f(pcode, "tous")
    assert zoom.layout.xaxis.range[0] > national.layout.xaxis.range[0]
    assert zoom.layout.xaxis.range[1] < national.layout.xaxis.range[1]
    assert "·" in titre


# ---- découpage 2025 -----------------------------------------------------------------------------------------
def test_mention_de_decoupage_et_filtre_des_47_provinces(page, donnees):
    """La mention fixe de la page de projection, et un filtre qui liste les 47 provinces de 2025."""
    assert DECOUPAGE_2025 in page and "className='decoupage'" in page
    opts = I._options(donnees)
    assert len(opts) == 48 and list(opts)[0] == ""            # « Toutes les provinces » + 47
    codes = set(D25.provinces_2025(donnees).code)
    assert set(opts) - {""} == codes
    assert set(donnees["decoupage_sites"].pcode_province_2025) <= codes
    # aucun code de l'ancien découpage ne reste dans le filtre
    assert not (codes & set(donnees["priorite"].pcode_province))


def test_liste_des_sites_sur_le_decoupage_2025_sans_perte(app, donnees):
    """Le rattachement change, la liste non : sans filtre, exactement les mêmes sites qu'avant, et la
    somme des provinces 2025 redonne la liste complète (aucun site perdu ni compté deux fois)."""
    f = cb(app, "imp-table.data")
    data, tips, *_ = f("", "tous")
    ref = C.sites(donnees)
    assert len(data) == len(ref) == len(donnees["implantation"])
    assert {r["rang"] for r in data} == {int(x) for x in ref.rang_national}
    s25 = D25.sites_2025(donnees)
    communes_2025 = set(s25.commune_2025.map(str))
    assert all(r["commune"] in communes_2025 for r in data)
    total = 0
    for code in sorted(set(s25.pcode_province_2025)):
        total += len(f(code, "tous")[0])
    assert total == len(ref)
    # la province 2025 et, s'il y en a un, le nom d'avant 2025 restent lisibles dans l'infobulle
    anciens = {a for a in s25.anciennement.dropna()}
    assert anciens, "le jeu de démonstration doit contenir une province renommée"
    tips_commune = " ".join(t["commune"]["value"] for t in tips)
    for a in anciens:
        assert f"anciennement : {a}" in tips_commune


def test_resume_nomme_la_province_2025_et_son_nom_d_avant(app, donnees):
    """Une province renommée ou scindée en 2025 : la phrase de résumé porte « anciennement : X »."""
    s25 = D25.sites_2025(donnees)
    renommee = s25[s25.anciennement.notna()].iloc[0]
    _, _, resume, _, titre, *_ = cb(app, "imp-table.data")(renommee.pcode_province_2025, "tous")
    t = mots(resume)
    assert f"anciennement : {renommee.anciennement}" in t
    assert renommee.province_2025 in t and renommee.province_2025 in titre


def test_carte_dessine_les_contours_locaux_de_2025(app, donnees):
    """Communes et régions du découpage 2025, et rien d'autre : aucune tuile, aucune couche distante."""
    _, _, _, fig, *_ = cb(app, "imp-table.data")("", "tous")
    assert not any(t.type.endswith("mapbox") for t in fig.data)
    assert fig.layout.dragmode == "pan"
    assert fig.layout.xaxis.fixedrange is False and fig.layout.yaxis.fixedrange is False
    assert fig.layout.uirevision == "BF"
    # l'emprise tracée est celle des communes 2025
    rx, _ry = F.emprise(D25.communes_carte_2025(donnees).geometrie)
    assert list(fig.layout.xaxis.range) == pytest.approx(rx)


def test_les_trois_boutons_changent_les_bornes_de_la_carte(donnees):
    """« Agrandir », « Réduire » et « Recadrer » : chemin clavier du zoom."""
    ex, ey = I._emprise(donnees, "")
    large = ex[1] - ex[0]
    # la vue mémorisée (magasin `imp-vue`) sert de référence quand aucun geste n'a eu lieu : la figure
    # n'est jamais demandée au navigateur
    memo = {"x": list(ex), "y": list(ey), "p": ""}
    rx, ry = I.bornes_zoom("imp-zoom-plus", None, memo, ex, ey, "")
    assert rx[1] - rx[0] == pytest.approx(large * I.ZOOM_PLUS)
    assert (rx[0] + rx[1]) / 2 == pytest.approx((ex[0] + ex[1]) / 2)   # le centre est conservé
    # une vue mémorisée sur une **autre** province est ignorée (on repart de l'emprise affichée)
    autre = {"x": [ex[0], ex[0] + 0.2], "y": [ey[0], ey[0] + 0.2], "p": "BF25P005"}
    assert I.bornes_zoom("imp-zoom-plus", None, autre, ex, ey, "")[0] == pytest.approx(rx)
    # « Réduire » part des bornes réellement affichées (dernière interaction) et ne dépasse jamais
    # l'emprise initiale ; « Recadrer » y revient exactement
    geste = {"xaxis.range[0]": rx[0], "xaxis.range[1]": rx[1], "yaxis.range[0]": ry[0], "yaxis.range[1]": ry[1]}
    rx2, _ = I.bornes_zoom("imp-zoom-moins", geste, None, ex, ey, "")
    assert (rx[1] - rx[0]) < (rx2[1] - rx2[0]) <= large
    # « Recadrer » ne vise aucune borne : il rend la main au cadrage automatique (le callback écrit
    # `autorange`, seul moyen mesuré de recadrer après un zoom à la molette)
    assert I.bornes_zoom("imp-recadrer", geste, memo, ex, ey, "") == (None, None)
    # un double-clic (Plotly renvoie `xaxis.autorange`) laisse repartir de l'emprise
    assert list(I.bornes_zoom("imp-zoom-moins", {"xaxis.autorange": True}, memo, ex, ey, "")[0]) \
        == pytest.approx(ex)


def test_tables_du_decoupage_absentes_bloc_erreur(app, source, monkeypatch):
    """Tout ce qu'affiche cette page vient du découpage 2025 : si ses tables manquent, la page entière
    passe sur le bloc « données indisponibles » du kit, en-tête comme callback."""
    from test_decoupage_2025 import SourceDegradee

    from d3dash import db
    d = db.Donnees(SourceDegradee(source), ttl_s=3600)
    monkeypatch.setattr(I, "donnees", lambda: d)
    assert "bloc-erreur" in texte(I.layout())
    data, _tips, _resume, _fig, _titre, err, cache = cb(app, "imp-table.data")("", "tous")
    assert data == [] and "bloc-erreur" in texte(err) and cache is True


def test_le_callback_des_boutons_publie_des_bornes(app, donnees):
    """Le callback ne renvoie que des bornes (la figure n'est pas reconstruite) ; « Recadrer » rend
    l'emprise initiale de la province affichée."""
    from dash._callback_context import context_value
    from dash._utils import AttributeDict
    context_value.set(AttributeDict(triggered_inputs=[{"prop_id": "imp-recadrer.n_clicks"}]))
    f = cb(app, "imp-cadre.data")
    pcode = donnees["decoupage_sites"].pcode_province_2025.iloc[0]
    ex, ey = I._emprise(donnees, pcode)
    cadre = f(0, 0, 1, None, None, pcode)
    assert list(cadre["x"]) == pytest.approx(ex) and list(cadre["y"]) == pytest.approx(ey)
    assert cadre["p"] == pcode
    national = f(0, 0, 1, None, None, "")
    assert national["x"][0] < cadre["x"][0] and national["x"][1] > cadre["x"][1]


def test_la_province_est_nommee_meme_sans_site_candidat(app, donnees):
    """« anciennement » vient de la table de passage, pas du premier site : une province sans aucun
    site candidat garde son nom 2025 et son nom d'avant."""
    pas = D25.passage(donnees)
    renommee = pas[pas.type_passage.isin(D25.PASSAGES_AVEC_ANCIEN_NOM)].iloc[0]
    nom, avant = I._nom_province(donnees, renommee.pcode_province_2025)
    assert nom == renommee.province_2025 and avant and avant.lower() == renommee.province.lower()
    # aucune mention là où le nom n'a pas changé
    inchangee = pas[pas.type_passage == "inchangee"].iloc[0]
    assert I._nom_province(donnees, inchangee.pcode_province_2025)[1] is None
    # une province dont aucun site n'est candidat est quand même nommée
    s = I._sites(donnees)
    sans_site = [c for c in pas.pcode_province_2025 if not (s.pcode_province_2025 == c).any()]
    for code in sans_site[:1]:
        assert I._nom_province(donnees, code)[0] not in ("", None, code)


def test_site_sans_rattachement_2025_reste_lisible(app, donnees):
    """Un site absent de `decoupage_sites` ne doit jamais afficher « nan » : mention neutre dans la
    cellule, et l'infobulle garde la commune d'avant 2025."""
    import pandas as pd
    s = I._sites(donnees).copy()
    orphelin = s.iloc[[0]].copy()
    for col in ("pcode_commune_2025", "commune_2025", "pcode_province_2025", "province_2025",
                "region_2025", "methode_rattachement", "anciennement"):
        orphelin[col] = pd.Series([None], index=orphelin.index, dtype=object)
    r = next(orphelin.itertuples())
    assert I._nom_2025(r.commune_2025) == I.NON_RENSEIGNE
    tip = I._tip_commune(r)
    assert "nan" not in tip.lower() and I.NON_RENSEIGNE in tip
    assert nom_propre(orphelin.commune.iloc[0]) in tip


def test_la_lecture_nomme_les_traits_gris(page):
    """La phrase « Lecture : » nomme les traits gris, avant la phrase sur le
    déplacement, et elle est **unique** — les deux niveaux de limites sont tracés dans les deux vues,
    donc aucun callback ne la réécrit."""
    assert "Traits gris : limites de province et de région (découpage 2025)." in I.LECTURE_CARTE
    assert I.LECTURE_CARTE.index("Traits gris") < I.LECTURE_CARTE.index("Déplacez la carte")
    assert "Traits gris : limites de province et de région" in page
    assert "imp-lecture-carte" not in page


def test_la_molette_est_rappelee_dans_les_bornes(app, donnees):
    """La molette obéit aux mêmes bornes que les boutons : jamais plus large que
    l'emprise initiale, jamais plus étroite que 0,05° — le callback repose les bornes quand le geste
    en sort, et ne dit rien quand il y reste (aucun aller-retour inutile)."""
    from dash._callback_context import context_value
    from dash._utils import AttributeDict
    context_value.set(AttributeDict(triggered_inputs=[{"prop_id": "imp-carte.relayoutData"}]))
    f = cb(app, "imp-cadre.data")
    ex, ey = I._emprise(donnees, "")
    cx, cy = (ex[0] + ex[1]) / 2, (ey[0] + ey[1]) / 2
    large = ex[1] - ex[0]

    def geste(fx):
        """Molette : étendue multipliée par `fx` autour du centre, telle que Plotly la renvoie."""
        hy = (ey[1] - ey[0]) * fx / 2
        return {"xaxis.range[0]": cx - large * fx / 2, "xaxis.range[1]": cx + large * fx / 2,
                "yaxis.range[0]": cy - hy, "yaxis.range[1]": cy + hy}

    # trop large : rappelé à l'emprise
    rappel = f(0, 0, 0, geste(2.5), None, "")
    assert (rappel["x"][1] - rappel["x"][0]) == pytest.approx(large)
    # trop étroit : rappelé au zoom maximal (0,05° de longitude)
    serre = f(0, 0, 0, geste(0.001), None, "")
    assert (serre["x"][1] - serre["x"][0]) == pytest.approx(F.ZOOM_MINI_DEG)
    # dans les bornes : aucun ordre n'est envoyé au navigateur
    with pytest.raises(Exception):
        f(0, 0, 0, geste(0.5), None, "")


def test_la_vue_memorisee_suit_les_gestes_de_l_utilisateur(app, donnees):
    """La molette et le glissement sont mémorisés (bornes de `relayoutData`) ; un double-clic efface."""
    f = cb(app, "imp-vue.data")
    vue = f({"xaxis.range[0]": -3.0, "xaxis.range[1]": -1.0, "yaxis.range[0]": 11.0, "yaxis.range[1]": 12.0}, "")
    assert vue == {"x": [-3.0, -1.0], "y": [11.0, 12.0], "p": ""}
    assert f({"xaxis.autorange": True}, "BF25P005") is None
    with pytest.raises(Exception):   # un survol ou un redimensionnement ne mémorise rien
        f({"hovermode": "closest"}, "")


def test_un_cadrage_memorise_est_repris_sur_la_meme_province_seulement(app, donnees):
    """Changer « Sites affichés » garde la vue courante ; changer de province la jette."""
    f = cb(app, "imp-table.data")
    pcode = donnees["decoupage_sites"].pcode_province_2025.iloc[0]
    ex, ey = I._emprise(donnees, "")
    serre = {"x": [ex[0] + 1, ex[1] - 1], "y": [ey[0] + 1, ey[1] - 1], "p": ""}
    garde = f("", "fiables", serre)[3]
    assert list(garde.layout.xaxis.range) == pytest.approx(serre["x"])
    autre = f(pcode, "tous", serre)[3]
    assert list(autre.layout.xaxis.range) != pytest.approx(serre["x"])


def test_le_zoom_survit_au_changement_d_un_autre_filtre(app, donnees):
    """`uirevision` ne bouge pas quand « Sites affichés » change (le déplacement et le zoom de
    l'utilisateur sont gardés), mais change quand la province change : là, le recadrage est voulu."""
    f = cb(app, "imp-table.data")
    pcode = donnees["decoupage_sites"].pcode_province_2025.iloc[0]
    a = f("", "tous")[3].layout.uirevision
    b = f("", "fiables")[3].layout.uirevision
    c = f(pcode, "tous")[3].layout.uirevision
    assert a == b == "BF" and c == pcode


def test_la_carte_porte_les_limites_de_province_2025(app, donnees):
    """La carte d'implantation trace les limites de **province** 2025 (`--trait-region`, 0,8 px),
    tout le pays compris quand une seule province est affichée — c'est ce qui situe un site par
    rapport à ses voisines. Les limites de **région** (1,4 px) sont tracées dans les **deux** vues,
    pour que la ligne « Lecture : » unique reste vraie."""
    f = cb(app, "imp-table.data")
    pcode = donnees["decoupage_sites"].pcode_province_2025.iloc[0]
    n_provinces = len(D25.geoms_provinces_2025(donnees))
    for choix_province in ("", pcode):
        fig = f(choix_province, "tous")[3]
        prov = [t for t in fig.data
                if t.mode == "lines" and t.line.color == F.TRAIT_REGION and t.line.width == 0.8]
        assert len(prov) == 1, choix_province
        # toutes les provinces, et pas seulement celle qui est affichée
        assert prov[0].x.count(None) >= n_provinces, choix_province
        reg = [t for t in fig.data
               if t.mode == "lines" and t.line.color == F.TRAIT_REGION and t.line.width == 1.4]
        assert len(reg) == 1, choix_province


def test_le_double_clic_recadre_comme_le_bouton(app, donnees):
    """Le recadrage automatique de Plotly revient aux bornes du **premier** tracé (le pays entier) :
    la page le reconnaît et rend exactement les bornes de « Recadrer »."""
    # signature mesurée dans Chromium : tableau entier ou autorange = double-clic ; bornes indicées
    # = glissement, molette, ou nos propres boutons
    assert I.est_recadrage({"xaxis.range": [-5.0, 2.0], "yaxis.range": [9.0, 15.0]})
    assert I.est_recadrage({"xaxis.autorange": True, "yaxis.autorange": True})
    assert not I.est_recadrage({"xaxis.range[0]": -5.0, "xaxis.range[1]": 2.0})
    assert not I.est_recadrage({"autosize": True})       # redimensionnement : le zoom est gardé
    assert not I.est_recadrage({}) and not I.est_recadrage(None)
    from dash._callback_context import context_value
    from dash._utils import AttributeDict
    f = cb(app, "imp-cadre.data")
    pcode = donnees["decoupage_sites"].pcode_province_2025.iloc[0]
    ex, ey = I._emprise(donnees, pcode)
    context_value.set(AttributeDict(triggered_inputs=[{"prop_id": "imp-carte.relayoutData"}]))
    double = f(0, 0, 0, {"xaxis.autorange": True, "yaxis.autorange": True}, None, pcode)
    context_value.set(AttributeDict(triggered_inputs=[{"prop_id": "imp-recadrer.n_clicks"}]))
    bouton = f(0, 0, 1, None, None, pcode)
    assert double == bouton
    assert list(double["x"]) == pytest.approx(ex) and list(double["y"]) == pytest.approx(ey)
    # un geste de l'utilisateur ne recadre pas (sinon la molette annulerait le zoom qu'elle vient de faire)
    context_value.set(AttributeDict(triggered_inputs=[{"prop_id": "imp-carte.relayoutData"}]))
    with pytest.raises(Exception):
        f(0, 0, 0, {"xaxis.range[0]": -4.0, "xaxis.range[1]": -3.0}, None, pcode)
