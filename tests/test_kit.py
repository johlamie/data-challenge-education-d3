"""Kit d'interface : coque, composants, états, et point intérieur des cartes."""
import pytest

from d3dash import composants as K
from d3dash import figures as F
from d3dash.app import creer_app
from d3dash.config import Config
from d3dash.demo import _anneaux as _anneaux_demo
from d3dash.demo import _dedans


@pytest.fixture()
def app_demo(donnees):
    return creer_app(Config(auth_active=False, code_hash="", secret_key="", demo=True), donnees)


def texte(x):
    return str(x)


def cb(app, sortie):
    for k, v in app.callback_map.items():
        if sortie in k:
            return v["callback"].__wrapped__
    raise KeyError(sortie)


def test_coque_rail_et_bandeau_demo(app_demo):
    """La coque porte le rail, les identifiants de navigation et le bandeau « Données fictives » complet."""
    lay = texte(app_demo.layout)
    assert "className='rail'" in lay and "className='coque'" in lay
    for id_ in ("nav-accueil", "nav-classement", "nav-fiche", "nav-besoins-2030", "nav-implantation",
                "nav-a-propos", "nav-bascule", "nav-menu", "racine", "page"):
        assert id_ in lay
    assert "Données fictives" in lay and "aucun chiffre, nom ou classement affiché n'est réel" in lay
    assert "bandeau-demo" in lay


def test_liens_actifs_et_aria_current(app_demo):
    sorties = cb(app_demo, "nav-accueil.className")("/classement")
    assert sorties[0] == "nav-item" and sorties[1] == "nav-item actif"
    aria = sorties[12:18]
    assert aria == [None, "page", None, None, None, None]
    # menu mobile : classe vide au repos (jamais " "), « actif » sur la page courante
    assert sorties[6:12] == ["", "actif", "", "", "", ""]


def test_aucun_item_actif_au_premier_rendu(app_demo):
    """Le gabarit est construit sans chemin connu : aucun item n'est marqué actif avant que
    le callback `actif` n'ait répondu (sinon « Vue d'ensemble » clignote sur toutes les pages)."""
    lay = texte(app_demo.layout)
    assert "nav-item actif" not in lay and "aria-current" not in lay
    assert texte(K.rail(chemin="/classement")).count("nav-item actif") == 1


def _liens(noeud, trouves=None):
    """Tous les <a> d'un arbre de composants Dash."""
    trouves = [] if trouves is None else trouves
    if getattr(noeud, "_type", None) == "A":
        trouves.append(noeud)
    enfants = getattr(noeud, "children", None)
    for c in (enfants if isinstance(enfants, (list, tuple)) else [enfants]):
        if hasattr(c, "children") or hasattr(c, "_type"):
            _liens(c, trouves)
    return trouves


def test_liens_de_navigation_interceptables():
    """Les liens du rail et du menu portent data-nav (assets/nav.js) ; « Se déconnecter » non."""
    for bloc in (K.rail(auth_active=True), K.tete_mobile(auth_active=True)):
        liens = _liens(bloc)
        navigables = [a for a in liens if getattr(a, "data-nav", None) == "1"]
        assert len(navigables) == len(K.PAGES)
        assert sorted(a.href for a in navigables) == sorted(h for h, _, _ in K.PAGES)
        sortie = [a for a in liens if a.href == "/deconnexion"]
        assert len(sortie) == 1 and getattr(sortie[0], "data-nav", None) is None


def test_infobulle_sans_aria_expanded():
    """`aria-expanded` sur un élément générique est invalide : seul aria-describedby relie la bulle."""
    assert "aria-expanded" not in texte(K.kpi("Scolarisation", "66,4 %", aide_kpi="définition"))
    assert "aria-expanded" not in texte(K.aide("définition", "Score"))
    assert "aria-expanded" in texte(K.tete_mobile())  # le bouton « Pages » le garde : il est valide


def test_page_kit_rend_tous_les_blocs(app_demo):
    """La page de démonstration /_kit rend chaque bloc du kit avec ses états."""
    page, classe = cb(app_demo, "page.children")("/_kit", "")
    lay = texte(page)
    for classe_css in ("bande-kpi", "kpi-aide", "panneau", "tab tab-top10", "badge badge-p1", "cell-score",
                       "legende", "lecture", "choix choix-segment", "liste-chiffres", "comp-ligne",
                       "bande-obsolete", "bloc-erreur", "bloc-introuvable", "vide", "sk-zone",
                       "btn-plein", "btn-contour", "lien-suite", "filtre-lib",
                       # mention de découpage, filtres, « anciennement », outils de carte, équipe
                       "decoupage", "barre-filtres", "anciennement", "outils-carte", "eq-grille"):
        assert classe_css in lay, classe_css
    assert "kpi-icone" not in lay  # aucune icône sur un chiffre clé
    assert classe == "racine"


def test_kit_absent_hors_demo(donnees):
    app = creer_app(Config(auth_active=False, code_hash="", secret_key="", demo=False), donnees)
    page, _ = cb(app, "page.children")("/_kit", "")
    assert "Page introuvable" in texte(page)


def test_kpi_sans_icone():
    """Aucune icône ni couleur de valeur sur un chiffre clé : les anciens paramètres décoratifs
    (`icone`, `critique`, `titre_info`) ont disparu de la signature."""
    import inspect
    c = texte(K.kpi("Élèves par maître", "50,1", variation="norme : 50"))
    assert "Img" not in c and "icone" not in c
    assert "kpi-lib" in c and "kpi-val" in c and "kpi-ctx" in c
    params = inspect.signature(K.kpi).parameters
    assert not {"icone", "critique", "titre_info"} & set(params)
    assert all(p.kind is not inspect.Parameter.VAR_KEYWORD for p in params.values())


def test_kpi_unite_et_infobulle():
    c = texte(K.kpi("Scolarisation (TBS)", "66,4 %", aide_kpi="définition"))
    assert "kpi-unite" in c and "kpi kpi-aide" in c and "data-aide" in c


def test_tendance_absente_n_affiche_rien():
    assert K.tendance(None, "+3 en un an") is None
    assert "▲" in texte(K.tendance(3.0, "+3 en un an"))


def test_classes_et_libelles_de_legende():
    assert F.classes([0, 100], norme=50) == [45, 50, 55, 60]
    libs = F.libelles_classes([45, 50, 55, 60], dec=0)
    assert libs[0] == "moins de 45" and libs[-1] == "60 et plus" and libs[2] == "50 à 55"
    assert len(F.classes([0, 20, 100])) == 4


def test_centroide_est_un_point_interieur(source):
    """Le point rendu est intérieur : la moyenne des sommets, elle, tombe hors des contours
    concaves (16 communes sur 180)."""
    d = source.charger()
    import json
    for table in ("priorite", "communes"):
        for geojson in d[table].geometrie_geojson:
            geom = json.loads(geojson)
            x, y = F.centroide(geom)
            assert _dedans(x, y, _anneaux_demo(geom))


def test_carte_rangs_et_selection(donnees):
    """Carte choroplèthe : 45 polygones, 5 classes, pastilles de rang et anneau de sélection."""
    from d3dash import calculs as C
    t = C.classement(donnees, "score_priorite")
    rangs = {r.pcode_province: int(r.rang) for r in t.head(10).itertuples()}
    vals = {r["pcode_province"]: (r["score_priorite"], r["province_nom"]) for _, r in t.iterrows()}
    fig = F.carte(C.geoms_provinces(donnees), vals, "Score", gras=set(rangs), rangs=rangs,
                  selection=t.pcode_province.iloc[0], contours_regions=donnees["geo_region"])
    remplis = [tr for tr in fig.data if tr.fill == "toself"]
    assert len(remplis) == 45
    assert set(tr.fillcolor for tr in remplis) <= set(F.RAMPE) | {F.GRIS_ND}
    pastilles = [tr for tr in fig.data if tr.mode == "markers+text"]
    assert len(pastilles) == 1 and len(pastilles[0].text) == 10
    assert any(tr.line.color == F.BLEU and tr.line.width == 2.5 for tr in fig.data)


# ---- règles portées par le kit : ce qu'une page ne refait pas chez elle -------------------------
def test_bornes_imposees_seulement_quand_la_norme_est_ecrite(donnees):
    """Seules les mesures qui ont une **norme écrite** gardent des bornes figées : élèves par
    maître et par salle, calées sur 50 (45/50/55/60) sur la Vue d'ensemble **comme** sur le
    Classement. Les autres mesures suivent la distribution de leurs valeurs."""
    from d3dash import calculs as C
    for mesure in ("eleves_par_maitre", "eleves_par_salle"):
        assert F.bornes_mesure(mesure) == [45, 50, 55, 60], mesure
    assert F.bornes_mesure("salles_a_construire_2030") is None
    assert F.bornes_mesure("deficit_enseignants") is None
    # les bornes imposées passent devant la norme et devant la règle automatique
    assert F.classes([0, 10 ** 6], norme=50, bornes_classes=[200, 500, 800, 1200]) == [200, 500, 800, 1200]
    libs = F.libelles_classes(F.bornes_mesure("eleves_par_maitre"))
    assert libs[0] == "moins de 45" and libs[-1] == "60 et plus"
    # carte et légende lisent la **même** liste : la page la calcule une fois (accueil.bornes_carte)
    t = C.classement(donnees, "salles_a_construire_2030")
    bc = F.classes(list(t["salles_a_construire_2030"]))
    vals = {r["pcode_province"]: (r["salles_a_construire_2030"], "") for _, r in t.iterrows()}
    fig = F.carte(C.geoms_provinces(donnees), vals, "Salles", legende=True, bornes_classes=bc)
    echelle = [tr for tr in fig.data if tr.marker.showscale]
    assert list(echelle[0].marker.colorbar.ticktext) == [F.fmt_nombre(b) for b in bc]


def test_bornes_de_quantiles_lisibles_et_non_vides():
    """Les bornes d'une mesure sans norme écrite viennent des **quantiles** des valeurs affichées :
    des classes peuplées malgré un extrême isolé et malgré beaucoup de zéros, et des nombres
    ronds. Déterministe : même série, mêmes bornes."""
    # série inventée, de la forme d'une mesure très dissymétrique : beaucoup de zéros, un extrême isolé.
    # La règle d'étendue (max − min) / 5 donnerait 5 classes régulières dont 4 presque vides.
    serie = [0] * 11 + [10, 25, 40, 60, 80, 100, 110, 140, 200, 300, 400, 900, 1800]
    b = F.classes(serie)
    assert len(b) == 4 and all(a < c for a, c in zip(b, b[1:]))
    assert all(x in F._echelle_lisible(x) for x in b), b             # toutes « rondes »
    effectifs = [sum(1 for v in serie if F._classe(v, b) == i) for i in range(5)]
    assert all(n >= 1 for n in effectifs), (b, effectifs)            # aucune classe vide
    assert F.classes(serie) == b                                     # déterministe
    assert F.classes(list(reversed(serie))) == b                     # indépendant de l'ordre
    # un extrême isolé ne décide plus des 5 classes
    assert b[-1] < 1791 / 2
    # un pourcentage : aucune borne n'atteint le plafond (« 100 % et plus » serait impossible)
    assert F.classes([0, 10, 50, 90, 100], plafond=100)[-1] < 100
    # série dégénérée ou vide : la règle d'étendue reprend la main, sans exception
    assert len(F.classes([0, 0, 0])) == 4 and len(F.classes([])) == 4


def test_unite_collee_au_nombre_par_une_insecable():
    """Un nombre n'est jamais séparé de son unité en fin de ligne : fine (U+202F) avant « % »,
    insécable normale (U+00A0) pour les autres unités."""
    assert F.libelles_classes([20, 40, 60, 80], unite="%")[1] == "20 % à 40 %"
    assert F.libelles_classes([1, 2, 3, 4], unite="km")[0] == "moins de 1 km"
    assert F.libelles_classes([1, 2, 3, 4])[0] == "moins de 1"


def test_rangs_portent_un_uid_stable():
    """Les deux tracés des rangs portent un `uid` : Plotly en fait la classe du groupe SVG, seule
    prise du CSS pour les masquer sous 961 px."""
    import re
    css = open("assets/style.css", encoding="utf-8").read()
    for uid in (F.UID_RANGS_TRAITS, F.UID_RANGS_PASTILLES):
        assert f".trace{uid}" in css
    masquage = re.search(r"@media \(max-width: 960px\).*?\n\}", css, re.S).group(0)
    assert f".trace{F.UID_RANGS_PASTILLES} {{ display: none" in masquage.replace("\n  ", " ")


def test_blocs_de_texte_du_kit():
    """`texte()`, `liste()` et `note_limite()` existent dans le kit : une page n'écrit plus sa
    propre mise en forme de texte. La note de limite est neutre, sans couleur de statut."""
    assert "className='texte'" in texte(K.texte("Un paragraphe."))
    lst = texte(K.liste(["un", "deux"]))
    assert "className='liste'" in lst and lst.count("Li(") == 2
    assert "className='note-limite'" in texte(K.note_limite("Une limite."))
    css = open("assets/style.css", encoding="utf-8").read()
    bloc = css.split("\n.note-limite {")[1].split("}")[0]
    assert "var(--muted)" in bloc and "border-left" not in bloc and "statut" not in bloc


def test_le_kit_neutralise_la_classe_tab_de_dash():
    """La collision avec la classe `.tab` des onglets de Dash est traitée une fois dans le kit
    (spécificité `table.tab`), jamais recopiée dans une feuille de page."""
    import glob
    css = open("assets/style.css", encoding="utf-8").read()
    assert "table.tab {" in css
    for f in glob.glob("assets/page-*.css"):
        contenu = open(f, encoding="utf-8").read()
        assert ".p-" + f.split("page-")[1][:-4] + " .tab {" not in contenu, f
        assert "--accent" not in contenu and "dash-cell" not in contenu, f


def test_style_css_sans_classes_de_compatibilite():
    """La feuille du kit ne garde aucune classe d'une version antérieure des pages."""
    css = open("assets/style.css", encoding="utf-8").read()
    for mort in ("Compatibilité", ".carte-bloc", ".titre-page", ".sous-titre", ".table-dc",
                 ".table-top10", ".ligne-principale", ".ligne-kpi {", ".btn-outline-primary",
                 ".alert-danger", ".markdown-methode", ".zone-top10", ".carte .prov", ".carte .rangs",
                 ".carte .sit", ".legende-carte", ".cellule-score", ".badge-statut"):
        assert mort not in css, mort


# ---- pires données, libellés partagés, évitement du rail ------------------------------------------------------
def _plat(noeud, sortie=None):
    """Tout le contenu d'un arbre de composants Dash, à plat (le `repr` d'un gros arbre abrège)."""
    sortie = [] if sortie is None else sortie
    if noeud is None:
        return "".join(sortie)
    if isinstance(noeud, (list, tuple)):
        for n in noeud:
            _plat(n, sortie)
        return "".join(sortie)
    if isinstance(noeud, (str, int, float)):
        sortie.append("|" + str(noeud) + "|")
        return "".join(sortie)
    for attr in ("children", "className", "style", "title"):
        v = getattr(noeud, attr, None)
        if v is not None:
            _plat(v if attr == "children" else str(v), sortie)
    return "".join(sortie)


def test_page_kit_montre_les_pires_donnees(app_demo):
    """`/_kit` rend les blocs avec le contenu le plus hostile, sans toucher au jeu de
    démonstration : nom et région de plus de 45 caractères, rang ex æquo, valeur manquante, zéro,
    nombre à sept chiffres, évolution négative, contexte long, valeur de sélecteur longue."""
    from d3dash.pages import kit
    page = _plat(cb(app_demo, "page.children")("/_kit", "")[0])
    assert "Pires données" in page
    assert len(kit.NOM_LONG) > 45 and len(kit.REGION_LONGUE) > 45
    assert page.count(kit.NOM_LONG) >= 2 and kit.REGION_LONGUE in page
    # le tableau de données et le sélecteur reçoivent eux aussi le nom le plus long
    table = kit._datatable_pire()
    assert sum(1 for r in table.data if r["province"] == kit.NOM_LONG) == 2
    assert any(r["score"] is None for r in table.data)          # valeur manquante
    assert [r["rang"] for r in table.data].count(9) == 2         # rang ex æquo
    pires = _plat(kit._pires_donnees())
    assert "1 234 567" in pires          # sept chiffres, jamais tronqués
    assert "n.d." in pires                         # valeur manquante
    assert "t-mieux" in pires and "▼" in pires     # évolution négative : flèche **et** texte
    assert pires.count("|9|") == 2                 # rang ex æquo (deux lignes au rang 9)
    assert kit.COURRIEL_LONG in pires and "valeur-insecable" in pires
    assert len(kit.CONTEXTE_LONG) > 100            # ligne de contexte très longue


def test_libelles_de_scenario_viennent_d_un_seul_endroit():
    """Fiche, filtre « Scénario » et axe du graphique nomment les scénarios depuis `libelles.py`."""
    from d3dash import figures as Fg
    from d3dash import libelles as L
    from d3dash.meta import SCENARIOS
    from d3dash.pages import besoins, fiche
    assert set(L.SCENARIOS_CLAIRS) == set(SCENARIOS) == set(L.SCENARIOS_AXE)
    assert fiche.SCENARIOS_CLAIRS is L.SCENARIOS_CLAIRS and besoins.LIB_SCENARIOS is L.SCENARIOS_CLAIRS
    assert Fg.SCENARIOS_AXE is L.SCENARIOS_AXE
    # la variante d'axe porte le même code que le libellé complet (S1, S2, S2b, S3)
    for cle, court in L.SCENARIOS_AXE.items():
        code = L.code_scenario(cle)
        assert code and court.startswith(code), (cle, court)
        assert len(max(court.split("<br>"), key=len)) <= 16, court   # tient sous une barre étroite
    assert L.SCENARIOS_CLAIRS["S1_tendanciel"] == "Si rien ne change (S1)"


def test_axe_du_graphique_de_scenarios_en_mots_simples(donnees):
    """Les étiquettes de l'axe sont les variantes courtes partagées, pas « S1 tendanciel »."""
    from d3dash import calculs as C
    from d3dash import libelles as L
    sc = C.besoins_par_scenario(donnees, "moyen", "TOTAL", 50, 50)
    fig = F.barres_scenarios(sc, "S2_retour_avant_crise")
    attendu = [L.SCENARIOS_AXE[s] for s in sc.scenario]
    assert list(fig.data[0].x) == attendu
    assert not any("tendanciel" in x for x in fig.data[0].x)


def test_lien_d_evitement_premier_element_focalisable(app_demo):
    """« Aller au contenu » est le premier élément focalisable de la coque et vise `#page`."""
    lay = texte(app_demo.layout)
    assert "Aller au contenu" in lay and "lien-evitement" in lay
    assert lay.index("Aller au contenu") < lay.index("bandeau-demo")
    assert "href='#page'" in lay and "tabIndex='-1'" in lay
    css = open("assets/style.css", encoding="utf-8").read()
    assert ".lien-evitement:focus { left: 8px" in css      # visible seulement au clavier


def test_legende_de_rampe_en_colonne():
    """Variante `.leg-rampe-colonne` du kit, activée par un paramètre."""
    libelles = ["moins de 20 %", "20 % à 40 %", "40 % à 60 %", "60 % à 80 %", "80 % et plus"]
    large = texte(K.legende_rampe("Titre", libelles))
    colonne = texte(K.legende_rampe("Titre", libelles, colonne=True))
    assert "leg-rampe-colonne" not in large and "leg-rampe leg-rampe-colonne" in colonne
    css = open("assets/style.css", encoding="utf-8").read()
    assert ".leg-rampe-colonne { grid-template-columns: minmax(0, 1fr)" in css


def test_socle_css_autonome_sans_bootstrap():
    """Le kit porte lui-même les règles de socle : aucune feuille tierce n'est chargée."""
    import os
    css = open("assets/style.css", encoding="utf-8").read()
    assert not os.path.exists("assets/bootstrap.min.css"), "feuille Bootstrap inutilisée à supprimer"
    for regle in ("box-sizing: border-box", "h1, h2, h3, h4, h5, h6", "line-height: 1.2",
                  "margin-bottom: 16px"):
        assert regle in css, regle


# ---- découpage, filtres sans cadre, « anciennement », zoom, équipe -----------------------------
def test_mention_de_decoupage_neutre_dans_l_entete():
    """Deux textes et deux seulement (meta), posés à droite du titre dans `.tete-droite`.
    Ce n'est pas une alerte : aucun rôle, aucune couleur de statut, aucune icône."""
    from d3dash.meta import DECOUPAGE_2025, DECOUPAGE_CONSTAT
    # texte fixe, repris caractère pour caractère, apostrophe typographique comprise
    assert DECOUPAGE_CONSTAT == "Données 2017-2025 · découpage d’avant 2025 (45 provinces)"
    assert "'" not in DECOUPAGE_CONSTAT
    assert "47 provinces" in DECOUPAGE_2025 and "Projection 2030" in DECOUPAGE_2025
    tete = texte(K.entete("Vue d'ensemble", "périmètre", decoupage=DECOUPAGE_CONSTAT))
    assert "tete-droite" in tete and "className='decoupage'" in tete
    assert "role" not in tete and "aide" not in tete and "ico" not in tete
    # sans mention, l'en-tête reste celui des pages qui n'en portent pas
    assert "decoupage" not in texte(K.entete("Kit", "périmètre"))
    css = open("assets/style.css", encoding="utf-8").read()
    bloc = css.split("\n.decoupage {")[1].split("}")[0]
    assert "var(--muted)" in bloc and "nowrap" in bloc
    for statut in ("--destructive", "--statut", "--fond-attention"):
        assert statut not in bloc
    # Sous 621 px, la mention quitte la pastille et devient une ligne de texte qui passe à la
    # ligne : à 390 px, la plus longue (358 px) déborderait un en-tête de 343 px. Le texte n'est
    # ni raccourci ni masqué, et rien ne change au-dessus de 621 px.
    import re
    mobile = re.search(r"@media \(max-width: 620px\) \{.*?\n\}", css, re.S).group(0)
    regle = mobile.split(".decoupage {")[1].split("}")[0]
    for attendu in ("background: transparent", "border: 0", "border-radius: 0", "padding: 0",
                    "white-space: normal"):
        assert attendu in regle, attendu
    assert "display: none" not in regle and "ellipsis" not in regle


def test_barre_de_filtres_sans_cadre_et_action_a_droite():
    """`barre_filtres` : aucune surface (pas de `.panneau`), l'action sur la même ligne, à droite ;
    une note éventuelle prend sa propre ligne, jamais la place de l'action."""
    barre = K.barre_filtres(K.filtre("Province", K.menu_natif("x-prov", {"a": "A"}, "a")),
                            action=K.bouton("Exporter en CSV", id_="x-export"),
                            note_="Sites triés par enfants servis.")
    rendu = texte(barre)
    assert "className='barre-filtres'" in rendu and "panneau" not in rendu
    assert "btn-contour" in rendu and "Exporter en CSV" in rendu
    assert "className='note'" in rendu
    css = open("assets/style.css", encoding="utf-8").read()
    bloc = css.split("\n.barre-filtres {")[1].split("}")[0]
    assert "align-items: flex-end" in bloc and "background" not in bloc and "border" not in bloc
    assert ".barre-filtres > .btn-contour, .barre-filtres > .btn-plein { margin-left: auto; }" in css
    assert ".barre-filtres > .note { flex: 1 1 100%; }" in css


def test_ligne_anciennement_sous_le_nom():
    """Seconde ligne « anciennement : X » : même gabarit que la ligne région,
    jamais tronquée, et rien du tout si le nom n'a pas changé."""
    rendu = texte(K.anciennement("Province Fictive de la Boucle du Mouhoun Septentrionale"))
    assert "anciennement : Province Fictive de la Boucle" in rendu
    assert "className='anciennement'" in rendu
    assert K.anciennement(None) is None and K.anciennement("") is None
    css = open("assets/style.css", encoding="utf-8").read()
    bloc = css.split("\n.anciennement {")[1].split("}")[0]
    assert "var(--t-mini)" in bloc and "var(--muted-foreground)" in bloc
    assert "ellipsis" not in bloc and "nowrap" not in bloc
    # dans un DataTable, la ligne est du markdown : la règle `em` lui donne le même rendu
    assert ".dash-table-container .dash-cell em {" in css


def test_outils_de_carte_trois_verbes_sans_icone():
    """Trois boutons de texte : « Agrandir » · « Réduire » · « Recadrer »."""
    rendu = texte(K.outils_carte("imp-zoom-plus", "imp-zoom-moins", "imp-recadrer"))
    assert "className='outils-carte'" in rendu
    for lib in ("Agrandir", "Réduire", "Recadrer"):
        assert lib in rendu
    for id_ in ("imp-zoom-plus", "imp-zoom-moins", "imp-recadrer"):
        assert id_ in rendu
    assert rendu.count("btn-contour") == 3 and "ico" not in rendu and "Img" not in rendu
    assert ".outils-carte { display: flex; gap: 4px; }" in open("assets/style.css", encoding="utf-8").read()


def test_carte_qui_zoome_sans_barre_d_outils_plotly(donnees):
    """La carte d'implantation se déplace et zoome, la barre d'outils de Plotly reste masquée
    (ce serait un second jeu d'icônes) ; les bornes du zoom sont celles du kit."""
    from d3dash import calculs as C
    assert F.CONFIG_CARTE_ZOOM["scrollZoom"] is True
    assert F.CONFIG_CARTE_ZOOM["displayModeBar"] is False
    assert F.CONFIG_CARTE_ZOOM["doubleClick"] == "reset"
    com = C.communes_carte(donnees)
    sites = C.sites(donnees)
    fixe = F.carte_implantation(com, sites)
    zoom = F.carte_implantation(com, sites, zoomable=True, revision="BF5204")
    assert fixe.layout.xaxis.fixedrange is True and fixe.layout.dragmode is False
    assert zoom.layout.xaxis.fixedrange is False and zoom.layout.dragmode == "pan"
    assert zoom.layout.uirevision == "BF5204"
    # le pays ne se déforme pas au zoom (projection conservée)
    assert zoom.layout.xaxis.scaleanchor == "y"
    # bornes : jamais plus large que l'emprise initiale, jamais plus étroit que 0,05° de longitude
    ex, ey = [-6.0, 2.5], [9.0, 15.5]
    assert F.zoomer(ex, ey, 1.4, ex, ey)[0] == ex
    etroit = F.zoomer([0.0, 0.04], [12.0, 12.03], 0.7, ex, ey)[0]
    assert round(etroit[1] - etroit[0], 6) == F.ZOOM_MINI_DEG
    plus = F.zoomer(ex, ey, 0.7, ex, ey)
    assert round(plus[0][1] - plus[0][0], 3) == round((ex[1] - ex[0]) * 0.7, 3)
    assert round(sum(plus[0]) / 2, 6) == round(sum(ex) / 2, 6)   # le centre est conservé


def test_bloc_equipe_portrait_nom_role_une_ligne(monkeypatch):
    """Bloc « L'équipe » : portrait rond, nom, rôle, une ligne de texte court.
    Le portrait n'est rendu que si son fichier existe ; sinon la case tient sans image, jamais avec
    une initiale ou un avatar de remplacement."""
    monkeypatch.setattr(K, "photo_presente", lambda fichier: fichier == "equipe/x.jpg")
    bloc = texte(K.grille_equipe(
        K.membre_equipe("Nom Très Long De La Personne", "Rôle court", bio="Une ligne.",
                        photo="equipe/x.jpg"),
        K.membre_equipe("Sans Portrait", "Rôle court", bio="Une ligne.", photo="equipe/absent.jpg")))
    assert "className='eq-grille'" in bloc and bloc.count("className='eq-membre'") == 2
    for cls in ("eq-nom", "eq-role", "eq-bio", "eq-txt"):
        assert f"className='{cls}'" in bloc, cls
    # un seul portrait : celui dont le fichier existe, nommé par son `alt`, avec ses dimensions
    assert bloc.count("className='eq-photo'") == 1
    assert "src='/assets/equipe/x.jpg'" in bloc and "alt='Nom Très Long De La Personne'" in bloc
    assert "width='72'" in bloc and "height='72'" in bloc
    assert "equipe/absent.jpg" not in bloc and "monogramme" not in bloc
    # la case reste composable sans portrait ni ligne de texte (appel historique à deux arguments)
    court = texte(K.membre_equipe("Sans Rien", "Rôle court"))
    assert "eq-photo" not in court and "eq-bio" not in court and "Sans Rien" in court
    css = open("assets/style.css", encoding="utf-8").read()
    assert ".eq-grille { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr))" in css
    assert ".eq-grille { grid-template-columns: minmax(0, 1fr); }" in css   # une colonne sous 621 px
    assert "border-radius: 50%; object-fit: cover" in css                  # portrait rond, non déformé
    assert ".eq-photo { width: 64px; height: 64px; }" in css               # 64 px sous 621 px
    assert ".eq-txt { min-width: 0; }" in css                              # un nom long passe à la ligne


def test_photo_presente_lit_le_dossier_assets():
    """`photo_presente` répond sur le dossier `assets/` réel et mémorise sa réponse."""
    assert K.photo_presente("style.css") is True
    assert K.photo_presente("equipe/aucun-fichier.jpg") is False
    assert "equipe/aucun-fichier.jpg" in K._PHOTOS_PRESENTES


def test_verrou_un_ecran_dans_le_css():
    """Verrou « un écran » : la coque est verrouillée sur la hauteur de la
    fenêtre en `dvh`, c'est la liste qui défile, et la page ne défile jamais au-dessus de 961 px."""
    import re
    css = open("assets/style.css", encoding="utf-8").read()
    bloc = re.search(r"@media \(min-width: 961px\) \{.*?\n\}", css, re.S).group(0)
    attendus = (".racine-ecran { height: 100dvh; overflow: hidden; }",
                ".racine-ecran .coque { flex: 1 1 auto; min-height: 0; }",
                ".racine-ecran .rail { position: static; height: auto; overflow-y: auto; }",
                ".racine-ecran .travail { min-height: 0; overflow-y: auto; }",
                # la liste **remplit** le panneau et la hauteur en trop va aux lignes du tableau
                # (sans cela, 160 px de vide mesurés à 1440×900)
                ".racine-ecran .zone-liste { flex: 1 1 auto; min-height: 0; overflow-y: auto; }",
                ".racine-ecran .zone-liste > .tab-top10 { height: 100%; }",
                # planchers : sans eux, rien ne déborde, donc rien ne défile, et la carte est
                # écrasée en bandeau illisible sur une fenêtre courte
                ".racine-ecran .rangee { flex: 1 1 auto; min-height: 420px; }",
                "min-height: 240px; }")
    for regle in attendus:
        assert regle in bloc, regle
    # jamais l'unité de fenêtre fixe (Android bas de gamme)
    assert "100vh" not in css
    # le pied suit le contenu : il n'a rien à combler (c'est la liste qui remplit le panneau)
    assert ".panneau-pied { margin-top: auto; }" not in bloc
    assert ".zone-liste { flex: 1 1 auto; min-height: 0; }" in css
    # phrase-constat d'une vue « un écran » : 14 px et mesure 104 ch **à toute largeur**
    assert ".racine-ecran .constat { font-size: var(--t-corps); max-width: 104ch; }" in css
    assert ".racine-ecran .constat" not in bloc


def test_densite_de_la_mise_en_page():
    """Gouttières et remplissages mesurés : tout est sur l'échelle fermée."""
    import re
    css = open("assets/style.css", encoding="utf-8").read()
    for regle in ("padding: 4px 16px; text-align: center; }",          # bandeaux : 26 px rendus
                  "gap: 8px; padding: 12px 16px; }",                   # .travail
                  ".pile { display: flex; flex-direction: column; gap: 8px; }",
                  "grid-template-columns: minmax(0, 1fr) minmax(380px, 440px); gap: 8px; }",
                  "padding: 8px 12px; }",                              # .panneau, cellule de chiffre
                  ".panneau-pied { margin-top: 4px; padding-top: 4px;",
                  ".bloc-carte .legende { margin-top: 8px; }"):
        assert regle in css, regle
    # une ligne du top 10 : lien 13 px/600, ligne mesurée 41 px
    assert "font-size: var(--t-petit); line-height: 1.25;\n  font-weight: 600;" in css
    # quatre lignes d'une ligne chacune dans une cellule de chiffre, **au-dessus de 1280 px
    # seulement** : plus bas, une cellule de 160 px coupait le contexte sans recours
    assert ".kpi-tend, .kpi-tend .tendance, .kpi-ctx { display: block; }" in css
    coupure = css.split("@media (min-width: 1281px) {")[1].split("}")[0]
    assert "white-space: nowrap" in coupure and "text-overflow: ellipsis" in coupure
    sous_961 = re.search(r"@media \(max-width: 960px\).*?\n\}", css, re.S).group(0)
    assert "white-space" not in sous_961


def test_lignes_de_chiffre_jamais_tronquees_en_silence():
    """Une ligne secondaire écrite en toutes lettres porte son texte en `title` : au-dessus de
    1280 px elle tient sur une ligne et pourrait être coupée par une valeur plus longue que prévu
    — une métadonnée tronquée garde toujours un moyen d'être lue."""
    cellule = K.kpi("Enseignants manquants", "4 067", variation="dont 3 954 redéployables",
                    evolution="▲ +306 en un an")
    rendu = texte(cellule)
    assert rendu.count("title='dont 3 954 redéployables'") == 1
    assert rendu.count("title='▲ +306 en un an'") == 1
    # un composant porte déjà son propre titre : le kit ne le double pas, et ce titre reprend le
    # texte **en entier** avant d'en donner le sens (sinon la ligne coupée resterait illisible)
    avec_tendance = texte(K.kpi("Élèves par maître", "50,1", evolution=K.tendance(0.4, "+0,4 en un an")))
    assert "title='+0,4 en un an · évolution défavorable sur un an'" in avec_tendance
    assert avec_tendance.count("title=") == 1
    assert K.tendance(-2.0, "−2 en un an", mauvais_si_hausse=True).title.endswith("favorable sur un an")
    assert K.tendance(0.0, "stable en un an").title == "stable en un an · stable sur un an"
    # et aucune cellule vide ne fabrique de ligne
    assert "kpi-ctx" not in texte(K.kpi("Sans contexte", "0"))


def test_bornes_entieres_pour_une_mesure_sans_decimale():
    """Une mesure écrite sans décimale ne peut pas afficher « moins de 0 » ni « 0 à 0 » : ses
    bornes sont des entiers distincts, même sur une série entièrement sous 1."""
    serie = [0.0, 0.1, 0.25, 0.4, 0.5, 0.6, 0.8, 0.95]
    b = F.classes(serie, dec=0)
    assert b == [1.0, 2.0, 3.0, 4.0]
    libs = F.libelles_classes(b, 0)
    assert libs[0] == "moins de 1" and len(set(libs)) == 5
    assert "0 à 0" not in " ".join(libs)
    # une mesure à une décimale garde ses bornes fines, et une série normale ne bouge pas
    assert F.classes(serie, dec=1)[0] < 1
    assert F.classes([0] * 11 + [10, 60, 96, 200, 420, 1791], dec=0) == F.classes([0] * 11 + [10, 60, 96, 200, 420, 1791])


def test_couche_des_limites_de_province_sur_la_carte_d_implantation(donnees):
    """Ordre de tracé : communes (filet blanc 0,4) · limites de **province**
    (`--trait-region`, 0,8) · limites de **région** (1,4) · marqueurs de site. Le paramètre est
    facultatif : sans lui, la carte ne porte aucune des deux couches de limites."""
    from d3dash import calculs as C
    com, sites = C.communes_carte(donnees), C.sites(donnees)
    prov = C.geoms_provinces(donnees)
    sans = F.carte_implantation(com, sites)
    avec = F.carte_implantation(com, sites, contours_provinces=prov,
                                contours_regions=donnees["geo_region"])

    def traits(fig, largeur):
        return [i for i, t in enumerate(fig.data)
                if t.mode == "lines" and t.line.color == F.TRAIT_REGION and t.line.width == largeur]

    assert traits(sans, 0.8) == []                       # rien de nouveau sans le paramètre
    assert len(traits(avec, 0.8)) == 1 and len(traits(avec, 1.4)) == 1
    i_prov, i_reg = traits(avec, 0.8)[0], traits(avec, 1.4)[0]
    communes = [i for i, t in enumerate(avec.data) if t.fill == "toself"]
    marqueurs = [i for i, t in enumerate(avec.data) if t.mode == "markers" and t.marker.opacity != 0]
    # sous les marqueurs, au-dessus des communes, et la province sous la région (trait plus fort)
    assert max(communes) < i_prov < i_reg < min(marqueurs)
    # une seule couleur de limite : aucune couleur nouvelle sur la carte
    assert avec.data[i_prov].line.color == avec.data[i_reg].line.color == F.TRAIT_REGION
    # le tracé couvre **toutes** les provinces, pas seulement celle qui est affichée
    assert avec.data[i_prov].x.count(None) >= len(prov)
    assert avec.data[i_prov].hoverinfo == "skip"         # une limite ne vole pas le survol d'une commune


def test_controle_segmente_et_alignement_des_chiffres():
    """Deux réglages mesurés : le contrôle segmenté qui dépasserait son panneau à 1024×600, et les
    valeurs de chiffres désalignées quand un libellé passe sur deux lignes."""
    import re
    css = open("assets/style.css", encoding="utf-8").read()
    opts = css.split("\n.choix-segment .choix-opts {")[1].split("}")[0]
    radios = css.split("\n.choix-segment .choix-radios {")[1].split("}")[0]
    assert "flex-wrap: wrap" in opts and "flex-wrap: wrap" in radios
    # l'option elle-même n'est jamais coupée : elle garde `nowrap`
    assert "white-space: nowrap" in css.split("\n.choix-segment .opt-txt {")[1].split("}")[0]
    bande = re.search(r"@media \(min-width: 961px\) and \(max-width: 1320px\) \{.*?\n\}", css, re.S)
    assert bande and ".bande-kpi .kpi-lib { min-height: 34px; }" in bande.group(0)
