"""Implantation : communes (part des enfants à plus de 3 km d'une école) et sites candidats pour de nouvelles
écoles, avec leur fiabilité ; carte des communes et des sites dans la colonne large, liste des sites et export
dans la colonne latérale.

Écran « plan de travail » : en-tête → phrase de résumé → barre de filtres sans
cadre → rangée (carte | liste). Tous les blocs viennent du kit (`d3dash/composants.py`).

Page de **projection** : communes, provinces, régions et rattachement des
sites viennent du découpage administratif de 2025 (17 régions, 47 provinces, `d3dash/decoupage.py`) ; la
liste des sites, elle, est toujours la même (aucun site perdu ni dupliqué). La carte se déplace et zoome
sur des contours **locaux** — aucune tuile, aucune ressource en ligne (CSP `default-src 'self'`).
"""
import io

from dash import Input, Output, State, callback_context, dash_table, dcc, html
from dash.exceptions import PreventUpdate

from .. import aides as A
from .. import composants as K
from .. import decoupage as D25
from .. import figures as F
from ..db import donnees
from ..libelles import pluriel as _pl
from ..meta import DECOUPAGE_2025, fmt_nombre, manque, nom_propre

CHOIX_SITES = {"fiables": "Sites fiables seulement", "tous": "Tous, y compris à vérifier"}
# Statut écrit en toutes lettres dans le tableau : l'information ne repose jamais sur la couleur seule.
# « À vérifier sur le terrain » faisait 150 px dans une colonne de 78 : la phrase entière reste dans
# l'infobulle de la cellule, dans la légende de la carte et dans la ligne « Lecture : ».
FIABLE = "Fiable"
A_VERIFIER = "À vérifier"
A_VERIFIER_LONG = "À vérifier sur le terrain"
# Colonnes exportées : le rattachement 2025 d'abord (c'est le découpage de la page), puis les colonnes
# d'avant 2025, conservées pour retrouver une ligne dans les annuaires.
EXPORT = ["rang_national", "pcode_province_2025", "province_2025", "region_2025", "pcode_commune_2025",
          "commune_2025", "localite_site", "longitude", "latitude", "distance_ecole_actuelle_km",
          "villages_desservis", "enfants_6_11_2030_desservis", "classes_a_prevoir", "fiabilite_osm_province",
          "chef_lieu_probable", "sites_fiables", "methode_rattachement", "pcode_province", "province",
          "pcode_commune", "commune"]

# Le DataTable ne lit pas les variables CSS : ses valeurs sont littérales (seule dérogation à
# « aucune couleur en dur »). Elles sont reprises des constantes de `figures.py`,
# qui valent exactement les jetons de `assets/tokens.css`.
POLICE_UI = F.POLICE_UI
POLICE_CHIFFRE = F.POLICE_CHIFFRE
COLONNES_NUM = ("rang", "enfants", "distance")
# facteurs des boutons « Agrandir » et « Réduire »
ZOOM_PLUS, ZOOM_MOINS = 0.7, 1.4
# écart d'étendue en degrés sous lequel on ne corrige pas une vue (≈ 10 cm) : sans cette tolérance,
# un aller-retour d'arrondi entre le navigateur et le serveur ferait vibrer la carte
TOLERANCE_DEG = 1e-6

# Une **seule** phrase pour les deux vues (pays ou province) : les deux niveaux de limites sont
# toujours tracés, donc aucun callback n'a à la réécrire.
LECTURE_CARTE = ("plus une commune est foncée, plus la part de ses enfants de 6-11 ans qui habitent à plus de "
                 "3 km d'une école est grande. Chaque point est un site proposé : plus il est gros, plus il "
                 "servirait d'enfants. Sur les communes hachurées, la carte des écoles est incomplète, donc la "
                 "distance y est sans doute surestimée. Traits gris : limites de province et de région "
                 "(découpage 2025). Déplacez la carte en la faisant glisser ; utilisez « Agrandir », « Réduire » "
                 "et « Recadrer » pour situer un site.")
LECTURE_LISTE = ("une ligne = une localité où une nouvelle école servirait les enfants qui marchent aujourd'hui "
                 "plus de 3 km, à vol d'oiseau. « Fiable » : la carte des écoles de la province est assez "
                 "complète pour se fier à cette distance. « À vérifier » : une école existe peut-être déjà sans "
                 "être cartographiée, le site est à vérifier sur le terrain. Cliquez sur un en-tête de colonne "
                 "pour trier.")
# Note du panneau du tableau : elle tient sur **une** ligne à côté du titre dans un panneau de
# 520 px — une version plus longue y passe sur deux lignes et double la hauteur de la tête.
NOTE_TRI = "Triés : les fiables d'abord, puis du plus grand nombre d'enfants."
# Rattachement 2025 manquant pour un site (ligne absente de `decoupage_sites`) : jamais « nan » à
# l'écran, une mention neutre à la place.
NON_RENSEIGNE = "non renseignée"


# ---- valeurs dérivées, gardées jusqu'au prochain rafraîchissement des données ---------------------------------
_CACHE = {"_t": None}


def _en_cache(cle, calcul):
    """Mémoïse une valeur dérivée coûteuse (centroïdes des communes, survols des sites, emprises).

    Le cache est remplacé dès que `db.Donnees` a rechargé (son horodatage change) : aucune valeur
    périmée ne peut survivre à un rafraîchissement. Sur les volumes réels (351 communes et plusieurs
    milliers de sites), les centroïdes et les textes de survol ne sont ainsi calculés qu'une fois, et
    non à chaque callback (mesuré : 0,37 s pour les sites au premier appel, puis 0 s).
    Un **nouveau** dictionnaire plutôt qu'un `clear()` : les callbacks de Dash s'exécutent dans
    plusieurs fils, et le rebranchement d'un nom de module est atomique, là où un cache vidé en place
    peut être lu entre son effacement et son remplissage.
    """
    global _CACHE
    c = _CACHE
    t = donnees().horodatage
    if c.get("_t") != t:
        c = _CACHE = {"_t": t}
    if cle not in c:
        c[cle] = calcul()
    return c[cle]


def _communes(d):
    return _en_cache("communes", lambda: D25.communes_carte_2025(d))


def _sites(d):
    """Tous les sites rattachés au découpage 2025 (survol compris) : le filtrage se fait ensuite sur
    cette table, sans refaire le rattachement ni réécrire plusieurs milliers de textes de survol."""
    return _en_cache("sites", lambda: D25.sites_2025(d))


def _passage(d):
    """Table de passage « ancienne province → province 2025 » : elle nomme les 47 provinces même celles
    où aucun site n'est candidat."""
    return _en_cache("passage", lambda: D25.passage(d))


def _regions(d):
    return _en_cache("regions", lambda: D25.geoms_regions_2025(d))


def _provinces(d):
    return _en_cache("provinces", lambda: D25.provinces_2025(d))


def _geoms_provinces(d):
    """Contours des 47 provinces 2025 : tracés sur **chaque** figure, pays entier compris quand une
    seule province est affichée (c'est ce qui situe un site par rapport à ses voisines). Mémoïsés
    comme le reste : la table n'est relue et reconvertie à aucun clic."""
    return _en_cache("geoms_provinces", lambda: D25.geoms_provinces_2025(d))


def _cadre(d, pcode):
    """Géométries qui cadrent la carte : les communes de la province choisie, ou tout le pays."""
    com = _communes(d)
    return com[com.pcode_province_2025 == pcode].geometrie if pcode else com.geometrie


def _emprise(d, pcode):
    """Emprise initiale de la carte (bornes du zoom), calculée une fois par province et par chargement."""
    return _en_cache(("emprise", pcode or ""), lambda: F.emprise(_cadre(d, pcode)))


def _options(d):
    p = _provinces(d)
    return {"": "Toutes les provinces", **{r.code: nom_propre(r.label) for r in p.itertuples()}}


def _tableau():
    """Tableau des sites candidats : mêmes jetons que le tableau statique `.tab` du kit."""
    return dash_table.DataTable(
        # `filter_action="none"` : dans des colonnes de 46 à 118 px, le champ de
        # filtre natif n'affiche même pas son propre libellé (« filtr » mesuré). La page a déjà ses
        # deux filtres — Province et Sites affichés — et le tri par en-tête. Le Classement, lui, garde
        # sa ligne de filtres : ses colonnes sont assez larges.
        id="imp-table", sort_action="native", filter_action="none", page_action="none",
        fixed_rows={"headers": True},
        # Ordre de lecture d'un téléphone : le critère du tri (enfants servis) juste après le nom du
        # site, pour qu'il tienne dans la largeur du bloc à 390 px ; la commune, qui
        # situe le site, vient ensuite. Aucune colonne n'est masquée, aucune n'est perdue.
        # En-têtes raccourcis : la colonne latérale fait 480-520 px et
        # aucun en-tête ne dépasse 2 lignes. Le nom complet reste dans la ligne « Lecture : ».
        columns=[{"name": "Rang", "id": "rang", "type": "numeric"},
                 {"name": "Localité", "id": "localite"},
                 {"name": "Enfants 2030", "id": "enfants", "type": "numeric",
                  "format": {"locale": {"group": " "}, "specifier": ",.0f"}},
                 {"name": "Commune", "id": "commune"},
                 # « École la plus proche (km) » tenait sur trois lignes ; la ligne « Lecture : »
                 # dit déjà qu'il s'agit de la distance à vol d'oiseau
                 {"name": "Distance (km)", "id": "distance", "type": "numeric",
                  "format": {"locale": {"decimal": ","}, "specifier": ".1f"}},
                 {"name": "Fiabilité", "id": "fiabilite"}],
        style_table={"height": "100%", "maxHeight": "100%", "overflowY": "auto", "overflowX": "auto"},
        # Aucun texte tronqué : un nom de localité ou de commune trop long passe à la ligne.
        # Des points de suspension rendraient 275 communes illisibles, sans équivalent au clavier.
        style_cell={"fontFamily": POLICE_UI, "fontSize": 13, "padding": "4px 8px", "textAlign": "left",
                    "color": F.ENCRE, "border": "none", "borderBottom": f"1px solid {F.BORDURE_FAIBLE}",
                    "whiteSpace": "normal", "lineHeight": "1.25", "overflow": "visible",
                    "textOverflow": "clip"},
        style_header={"fontFamily": POLICE_UI, "fontWeight": 600, "fontSize": 12, "color": F.GRIS,
                      "backgroundColor": F.BLANC, "border": "none", "borderBottom": f"1px solid {F.BORDURE}",
                      "padding": "0 8px 4px", "whiteSpace": "normal", "height": "auto", "lineHeight": "1.2",
                      "verticalAlign": "bottom"},
        # un nombre ne passe jamais à la ligne et ne se tronque pas
        style_cell_conditional=[{"if": {"column_id": c}, "textAlign": "right", "fontFamily": POLICE_CHIFFRE,
                                 "fontVariantNumeric": "tabular-nums", "letterSpacing": "-0.02em",
                                 "whiteSpace": "nowrap", "textOverflow": "clip"} for c in COLONNES_NUM]
        # Largeurs explicites. Seul leur **rapport** compte : le composant les met à l'échelle de
        # son conteneur. Leur somme (494 px) tient dans le panneau latéral le plus étroit (504 px
        # utiles à 1366), et aucune cellule ne porte de « … ».
        # Mesuré dans le navigateur : l'en-tête d'une colonne a besoin de son mot le plus long + 16 px
        # de remplissage + l'icône de tri — « Distance » en demande 66 à elle seule.
        + [{"if": {"column_id": "rang"}, "width": "46px", "minWidth": "46px"},
           {"if": {"column_id": "localite"}, "width": "118px", "minWidth": "118px"},
           {"if": {"column_id": "enfants"}, "width": "78px", "minWidth": "78px"},
           {"if": {"column_id": "commune"}, "width": "108px", "minWidth": "108px"},
           {"if": {"column_id": "distance"}, "width": "68px", "minWidth": "68px"},
           {"if": {"column_id": "fiabilite"}, "width": "76px", "minWidth": "76px"}],
        # le statut est déjà écrit ; la couleur ne fait que rappeler le marqueur de la carte
        style_data_conditional=[{"if": {"filter_query": f'{{fiabilite}} = "{A_VERIFIER}"',
                                        "column_id": "fiabilite"}, "color": F.ATTENTION}],
        tooltip_delay=300, tooltip_duration=None)


def _legendes():
    """Légende classée des communes (rampe ocre, unité écrite) puis légende des marqueurs de sites."""
    bornes = [haut for _, haut in F.CLASSES_ACCES[:-1]]
    # `libelles_classes` accole déjà l'unité par une espace fine insécable (règle de langue) :
    # le nombre et son unité ne sont jamais séparés en fin de ligne, même dans une colonne étroite
    libelles = F.libelles_classes(bornes, unite="%")
    return [
        # 5 colonnes : la carte occupe la colonne principale (614 px à 1366) — la variante de
        # légende en colonne n'a pas lieu d'être ici
        K.legende_rampe("Enfants de 6-11 ans habitant à plus de 3 km d'une école", libelles),
        K.legende_marqueurs(
            ("leg-rond leg-fiable", "site fiable"),
            ("leg-rond leg-verifier", K.avec_aide("site à vérifier sur le terrain", A.FIABILITE,
                                                  "Fiabilité des sites")),
            ("leg-case-carte leg-hachure", "carte des écoles incomplète")),
    ]


def layout(pcode=None, sites=None, **_):
    try:
        d = donnees()
        d.get()
        # liste des 47 provinces de 2025 : si les tables du découpage manquent (étape additive du
        # pipeline), cette page de projection affiche le bloc « données indisponibles » du kit
        opts = _options(d)
    except Exception:
        return K.erreur_donnees()
    pcode = pcode if pcode in opts else ""
    sites = sites if sites in CHOIX_SITES else "tous"
    return html.Div([
        K.entete("Où implanter de nouvelles écoles ?",
                 "Burkina Faso · primaire · localités situées à plus de 3 km d'une école connue",
                 decoupage=DECOUPAGE_2025),
        # panne de données survenue après l'affichage : un seul bloc rouge, le contenu disparaît
        html.Div(id="imp-erreur"),
        html.Div([
            K.constat(id="imp-resume"),
            # Barre de filtres sans cadre : un panneau et une ligne d'outils coûteraient 67 px de
            # hauteur sur cet écran, qui doit tenir dans une fenêtre de 768 px.
            K.barre_filtres(
                K.filtre("Province", K.menu("imp-province", opts, pcode, searchable=True), cls="filtre-large"),
                K.filtre("Sites affichés", K.menu("imp-sites", CHOIX_SITES, sites),
                         cls="filtre-moyen filtre-sites"),
                action=K.bouton("Exporter en CSV", id_="imp-export-btn")),
            K.rangee(
                # La carte occupe la colonne large : c'est l'objet avec lequel on situe un site.
                # Elle y reçoit la hauteur restante par la règle du kit
                # `.racine-ecran .rangee > :first-child .zone-carte`.
                K.panneau(None,
                          html.Div([html.Div(html.H2(id="imp-titre-carte"), className="panneau-tete"),
                                    K.outils_carte("imp-zoom-plus", "imp-zoom-moins", "imp-recadrer")],
                                   className="carte-outils"),
                          html.Div(dcc.Graph(id="imp-carte", config=F.CONFIG_CARTE_ZOOM, responsive=True,
                                             style={"height": "100%", "width": "100%"}), className="zone-carte"),
                          *_legendes(),
                          K.lecture(LECTURE_CARTE),
                          cls="bloc-carte"),
                K.panneau("Sites candidats",
                          html.Div(id="imp-vide"),
                          html.Div(_tableau(), className="zone-liste", id="imp-liste"),
                          K.lecture(LECTURE_LISTE),
                          note_=NOTE_TRI),
            ),
        ], id="imp-contenu", className="pile zone-contenu"),
        dcc.Download(id="imp-download"),
        # bornes demandées par les trois boutons de carte, posées sur la figure côté navigateur
        dcc.Store(id="imp-cadre"),
        html.Div(id="imp-cadre-fait", hidden=True),
        # vue affichée (molette, glissement, boutons) : relue quand un autre filtre refait la figure
        dcc.Store(id="imp-vue"),
    ], className="pile p-implantation")


def _filtrer(d, pcode, choix):
    """Sites affichés : filtrage de la table déjà rattachée au découpage 2025 (aucun recalcul)."""
    s = _sites(d)
    if pcode:
        s = s[s.pcode_province_2025 == pcode]
    if choix == "fiables":
        s = s[s.sites_fiables == 1]
    return s


def _nom_2025(valeur):
    """Nom 2025 d'une commune ou d'une province, ou une mention neutre si le site n'a pas été rattaché.

    Un site absent de `decoupage_sites` (jamais attendu : l'outil de contrôle vérifie que tous le sont)
    garde sa ligne, sa localité et ses chiffres ; seul son rattachement 2025 manque — et il s'écrit,
    plutôt que d'afficher « nan ».
    """
    return NON_RENSEIGNE if manque(valeur) else nom_propre(valeur)


def _nom_province(d, pcode):
    """Nom 2025 de la province choisie et son nom d'avant 2025 (None si le nom n'a pas changé).

    Lu dans la **table de passage**, et non dans les sites : une province où aucun site n'est candidat
    garde son nom et sa mention « anciennement ».
    """
    p = _passage(d)
    sel = p[p.pcode_province_2025 == pcode]
    if not len(sel):
        return pcode, None
    r = sel.iloc[0]
    avant = nom_propre(r.province) if r.type_passage in D25.PASSAGES_AVEC_ANCIEN_NOM else None
    return nom_propre(r.province_2025), avant


def _tip_commune(r):
    """Infobulle de la colonne « Commune » : commune et province 2025, le nom d'avant 2025 quand il a
    changé, et — si le rattachement manque — la commune d'avant 2025, qui situe quand même le site."""
    if manque(r.province_2025):
        return (f"Province 2025 {NON_RENSEIGNE} · avant 2025 : {nom_propre(r.commune)} "
                f"({nom_propre(r.province)})")
    avant = "" if manque(r.anciennement) else f" · anciennement : {r.anciennement}"
    return f"{_nom_2025(r.commune_2025)} · {nom_propre(r.province_2025)}{avant}"


def _resume(nom, tous, fiables, anciennement=None):
    """Phrase de résumé : mêmes comptes qu'avant, les nombres en police chiffrée (`chiffre()`).

    Une province renommée ou scindée en 2025 porte son nom d'avant 2025, ici comme dans le survol de
    la carte : c'est le seul endroit de l'écran où la province choisie est nommée en entier.
    """
    n, nf = len(tous), len(fiables)
    avant = f" (anciennement : {anciennement})" if anciennement else ""
    if not n:
        return [f"{nom}{avant} : aucune localité candidate à plus de 3 km d'une école connue."]
    enfants = fiables.enfants_6_11_2030_desservis.sum()
    phrase = [f"{nom}{avant} : ",
              K.chiffre(f"{fmt_nombre(n)} {_pl(n, 'site candidat', 'sites candidats')}"),
              f" {_pl(n, 'est', 'sont')} à plus de 3 km d'une école connue, dont ",
              K.chiffre(f"{fmt_nombre(nf)} {_pl(nf, 'fiable', 'fiables')}"), ". "]
    if nf:
        phrase += [f"{_pl(nf, 'Ce site fiable servirait', 'Ces sites fiables serviraient')} ",
                   K.chiffre(f"{fmt_nombre(enfants)} enfants"), " de 6-11 ans en 2030."]
    else:
        phrase.append("Aucun site n'est fiable ici : tous sont à vérifier sur le terrain.")
    return phrase


def revision(pcode):
    """`uirevision` de la carte : le code de la province filtrée, ou « BF » pour tout le pays.

    Tant que le jeton ne change pas, Plotly **garde** le déplacement et le zoom de l'utilisateur :
    changer « Sites affichés » ne recadre donc pas la carte. Il change quand la province change —
    là, le recadrage est voulu.
    """
    return pcode or "BF"


def _ranges_courants(relayout, vue=None, pcode=None):
    """Bornes d'axes réellement affichées : celles de la dernière interaction (`relayoutData`), sinon
    la vue mémorisée dans `imp-vue` **pour la même province**, sinon rien (l'appelant retombe sur
    l'emprise).

    La figure n'est jamais demandée au navigateur : elle pèse des dizaines de kilo-octets (contours des
    communes, 47 provinces, 17 régions, un texte de survol par site) et repasserait par le réseau à
    chaque glissement et à chaque cran de molette. Le magasin, lui, ne porte
    que quatre nombres et un code de province.
    """
    r = relayout or {}
    if "xaxis.range[0]" in r and "yaxis.range[0]" in r:
        return ([r["xaxis.range[0]"], r["xaxis.range[1]"]], [r["yaxis.range[0]"], r["yaxis.range[1]"]])
    if r.get("xaxis.autorange") or r.get("autosize"):
        return None, None
    if vue and vue.get("p") == (pcode or ""):
        return vue.get("x"), vue.get("y")
    return None, None


def est_recadrage(relayout):
    """Vrai si l'événement vient du **double-clic** de Plotly (son recadrage automatique).

    Mesuré dans Chromium : le double-clic écrit `xaxis.range` / `yaxis.range` — le tableau entier —
    ou `xaxis.autorange`, là où un glissement, la molette et nos trois boutons écrivent
    `xaxis.range[0]` et `xaxis.range[1]`. La signature est donc sans ambiguïté.
    `autosize` seul n'en est pas un : c'est un redimensionnement de fenêtre, qui ne doit pas
    jeter le zoom de l'utilisateur.
    Pourquoi corriger : le recadrage de Plotly revient aux bornes du **premier** tracé (le pays
    entier) même quand une seule province est affichée. Le double-clic rend donc exactement ce que
    rend « Recadrer » : les deux passent par les mêmes bornes (`_emprise`).
    """
    r = relayout or {}
    return bool(r) and ("xaxis.range" in r or bool(r.get("xaxis.autorange")))


def bornes_zoom(bouton, relayout, vue, emprise_x, emprise_y, pcode=None):
    """Bornes d'axes après un clic sur « Agrandir » ou « Réduire ».

    L'étendue courante (celle de `relayoutData`, sinon la vue mémorisée, sinon l'emprise) est
    multipliée par `ZOOM_PLUS` ou `ZOOM_MOINS` autour du centre affiché, dans les bornes de
    `figures.zoomer` (jamais plus large que l'emprise initiale, jamais plus étroit que 0,05° de
    longitude). « Recadrer » rend `(None, None)` : il ne vise pas des bornes, il redonne la main au
    cadrage automatique (voir le callback).
    """
    if bouton == "imp-recadrer":
        return None, None
    rx, ry = _ranges_courants(relayout, vue, pcode)
    facteur = ZOOM_PLUS if bouton == "imp-zoom-plus" else ZOOM_MOINS
    return F.zoomer(rx or emprise_x, ry or emprise_y, facteur, emprise_x, emprise_y)


def register(app):
    @app.callback(Output("imp-table", "data"), Output("imp-table", "tooltip_data"), Output("imp-resume", "children"),
                  Output("imp-carte", "figure"), Output("imp-titre-carte", "children"),
                  Output("imp-erreur", "children"), Output("imp-contenu", "hidden"),
                  Input("imp-province", "value"), Input("imp-sites", "value"),
                  State("imp-vue", "data"))
    def maj(pcode, choix, vue=None):
        try:
            d = donnees()
            d.get()
            # Tout ce que cette page affiche vient du découpage 2025 : une table absente
            # (`decoupage.DecoupageIndisponible`) donne le même bloc rouge qu'une base injoignable.
            s = _filtrer(d, pcode, choix)
            tous = _filtrer(d, pcode, "tous")
            com = _communes(d)
            regions = _regions(d)
            provinces = _geoms_provinces(d)
        except Exception:
            # un seul bloc rouge : ni phrase de résumé en panne, ni « Données indisponibles » sur la carte
            return ([], [], "", F.figure_vide("Données indisponibles", hauteur=None),
                    "Communes et sites candidats", K.erreur_donnees(), True)
        nom, avant = "Burkina Faso", None
        if pcode:
            com = com[com.pcode_province_2025 == pcode]
            nom, avant = _nom_province(d, pcode)
        # Contours tracés : communes 2025 (filet blanc du kit), limites de **province** 2025 (0,8 px)
        # et de **région** 2025 (1,4 px) — les deux niveaux, tout le pays, même quand une seule
        # province est affichée : les limites voisines restent visibles au zoom, et la ligne
        # « Lecture : » qui les nomme reste vraie dans les deux vues.
        # Sur une province, ses propres communes cadrent la carte.
        fig = F.carte_implantation(com, s, contours_regions=regions, contours_provinces=provinces,
                                   cadre=com.geometrie,
                                   montrer_a_verifier=(choix != "fiables"), taille_max=18 if pcode else 7,
                                   zoomable=True, revision=revision(pcode))
        if vue and vue.get("p") == (pcode or ""):
            # La vue courante (molette, glissement ou boutons) est reprise telle quelle quand un autre
            # filtre rafraîchit la figure. Mesuré : `uirevision` ne suffit pas ici — la figure porte des
            # bornes explicites, et Plotly leur redonne la priorité au rafraîchissement. Au changement
            # de province, la vue mémorisée ne correspond plus : la carte se recadre, comme voulu.
            fig.update_xaxes(range=vue["x"])
            fig.update_yaxes(range=vue["y"])
        fia = tous[tous.sites_fiables == 1]
        resume = _resume(nom, tous, fia, avant)
        data = [{"rang": int(r.rang_national), "localite": nom_propre(r.localite_site),
                 "commune": _nom_2025(r.commune_2025), "enfants": r.enfants_6_11_2030_desservis,
                 "distance": round(r.distance_ecole_actuelle_km, 1),
                 "fiabilite": FIABLE if r.sites_fiables == 1 else A_VERIFIER} for r in s.itertuples()]
        # L'infobulle garde ce que la cellule n'écrit plus : la phrase entière de la fiabilité, la
        # province 2025 et, quand elle a changé de nom en 2025, son nom d'avant.
        tips = [{"localite": {"value": f"{nom_propre(r.localite_site)} ({_nom_2025(r.province_2025)})",
                              "type": "text"},
                 "commune": {"value": _tip_commune(r), "type": "text"},
                 "enfants": {"value": f"{fmt_nombre(r.classes_a_prevoir)} classes à prévoir", "type": "text"},
                 "fiabilite": {"value": "Site fiable : la carte des écoles de la province est assez complète"
                               if r.sites_fiables == 1 else
                               (f"{A_VERIFIER_LONG} · chef-lieu probable : une école y existe sans doute déjà"
                                if r.chef_lieu_probable == 1
                                else f"{A_VERIFIER_LONG} · carte des écoles peu fiable dans cette province"),
                               "type": "text"}}
                for r in s.itertuples()]
        titre = "Communes et sites candidats" + (f" · {nom}" if pcode else "")
        return data, tips, resume, fig, titre, "", False

    @app.callback(Output("imp-cadre", "data"),
                  Input("imp-zoom-plus", "n_clicks"), Input("imp-zoom-moins", "n_clicks"),
                  Input("imp-recadrer", "n_clicks"), Input("imp-carte", "relayoutData"),
                  State("imp-vue", "data"),
                  State("imp-province", "value"), prevent_initial_call=True)
    def zoomer(n_plus, n_moins, n_recadrer, relayout, vue, pcode):
        """« Agrandir » · « Réduire » · « Recadrer » : le chemin clavier du zoom,
        le **double-clic**, qui rend exactement ce que rend « Recadrer », et le rappel des bornes
        quand la molette sort de l'emprise.

        Le callback ne calcule que les **bornes** (règle de `figures.zoomer`, vérifiée par les tests) ;
        elles sont posées sur la carte par la fonction côté navigateur ci-dessous. La figure n'est ni
        reconstruite ni relue : elle ne repasse par le réseau dans aucun sens, ni au clic, ni au
        glissement, ni à la molette — seuls quatre nombres circulent.
        """
        bouton = callback_context.triggered_id
        geste = bouton == "imp-carte"
        if geste and est_recadrage(relayout):
            bouton = "imp-recadrer"   # double-clic : même résultat que le bouton « Recadrer »
        try:
            d = donnees()
            d.get()
            ex, ey = _emprise(d, pcode)
        except Exception:
            raise PreventUpdate  # la carte porte déjà le bloc « données indisponibles »
        if geste and bouton != "imp-recadrer":
            # Glissement, molette ou pincement : Plotly ne sait pas borner un zoom lui-même
            # (`minallowed`/`maxallowed` transforment un glissement contre le bord en zoom, mesuré).
            # On laisse donc faire, et on ne rappelle les bornes de `figures.zoomer` que si l'étendue
            # obtenue sort de la règle — plus large que l'emprise initiale ou plus étroite que 0,05°.
            rx, ry = _ranges_courants(relayout, vue, pcode)
            if not rx or not ry:
                raise PreventUpdate
            bx, by = F.zoomer(rx, ry, 1.0, ex, ey)
            if abs((bx[1] - bx[0]) - (rx[1] - rx[0])) < TOLERANCE_DEG:
                raise PreventUpdate  # étendue déjà dans les bornes : rien à poser
            return {"x": list(bx), "y": list(by), "p": pcode or ""}
        rx, ry = bornes_zoom(bouton, relayout, vue, ex, ey, pcode)
        # la province est mémorisée avec les bornes : un cadrage ne se reporte jamais sur une autre
        return {"x": list(rx or ex), "y": list(ry or ey), "p": pcode or ""}

    @app.callback(Output("imp-vue", "data"), Input("imp-carte", "relayoutData"),
                  State("imp-province", "value"), prevent_initial_call=True)
    def memoriser_vue(relayout, pcode):
        """Mémorise la vue affichée (molette, glissement, boutons) pour qu'elle survive au
        rafraîchissement de la figure par un autre filtre. N'affiche rien et ne redessine rien."""
        if est_recadrage(relayout) or (relayout or {}).get("autosize"):
            return None  # double-clic ou redimensionnement : retour au cadrage de la figure
        rx, ry = _ranges_courants(relayout, None)
        if not rx or not ry:
            raise PreventUpdate
        return {"x": list(rx), "y": list(ry), "p": pcode or ""}

    # Pose les bornes sur la carte par le chemin des outils natifs de Plotly (`relayout` avec les
    # bornes indicées, la forme qu'emploie sa propre boîte de zoom). Aucune règle métier ici : les
    # bornes viennent du callback Python ci-dessus.
    # Pourquoi pas une mise à jour de la propriété `figure` : elle passe par `Plotly.react`, qui, à
    # `uirevision` inchangé, donne la priorité à l'état de l'utilisateur et ignore les nouvelles
    # bornes ; et changer `uirevision` à chaque clic ferait perdre le zoom à la molette dès qu'un
    # autre filtre rafraîchit la figure. Mesuré dans le navigateur (Chromium, 1366×768).
    app.clientside_callback(
        """function(cadre) {
            var rien = window.dash_clientside.no_update;
            if (!cadre) { return rien; }
            var g = document.getElementById('imp-carte');
            var p = g && g.querySelector('.js-plotly-plot');
            if (!p || !window.Plotly) { return rien; }
            window.Plotly.relayout(p, {'xaxis.range[0]': cadre.x[0], 'xaxis.range[1]': cadre.x[1],
                                       'yaxis.range[0]': cadre.y[0], 'yaxis.range[1]': cadre.y[1]});
            return rien;
        }""",
        Output("imp-cadre-fait", "children"), Input("imp-cadre", "data"), prevent_initial_call=True)

    @app.callback(Output("imp-vide", "children"), Output("imp-liste", "hidden"),
                  Input("imp-table", "data"), Input("imp-sites", "value"), Input("imp-province", "value"))
    def etat_vide(data, choix, pcode):
        """Aucun site après filtrage : dire ce qui manque et quoi faire (jamais un tableau vide)."""
        if data:
            return None, False
        ou = "dans cette province" if pcode else "dans cette sélection"
        if choix == "fiables":
            return K.vide(f"Aucun site fiable {ou}.",
                          "Affichez « Tous, y compris à vérifier » pour voir les sites à contrôler sur le "
                          "terrain."), True
        return K.vide(f"Aucun site candidat {ou}.",
                      "Choisissez « Toutes les provinces » pour revoir la liste complète."), True

    @app.callback(Output("imp-download", "data"), Input("imp-export-btn", "n_clicks"),
                  State("imp-province", "value"), State("imp-sites", "value"), prevent_initial_call=True)
    def exporter(n, pcode, choix):
        try:
            s = _filtrer(donnees(), pcode, choix)[EXPORT]
        except Exception:
            raise PreventUpdate  # rien à exporter : la page affiche déjà son bloc d'erreur
        buf = io.StringIO()
        s.to_csv(buf, sep=";", decimal=",", index=False)
        # BOM UTF-8 en échappement (cf. classement.py) : mêmes octets, source lisible
        return dcc.send_string("﻿" + buf.getvalue(), f"sites_implantation_{pcode or 'BF'}.csv")
