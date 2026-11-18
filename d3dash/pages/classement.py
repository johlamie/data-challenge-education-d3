"""Classement : contrôles, tableau des 45 provinces (gauche) et carte de la même mesure (droite).

Écran « plan de travail » : le tableau est l'objet principal, la carte
illustre la même mesure. Aucune icône « i » ici : le score et les classes P1/P2/P3 sont expliqués
en toutes lettres sous le tableau.
"""
import io

from dash import Input, Output, State, dash_table, dcc, html
from dash.exceptions import PreventUpdate

from .. import calculs as C
from .. import composants as K
from .. import figures as F
from ..db import donnees
from ..meta import (ANNEE_REF, ANNEES, DECOUPAGE_CONSTAT, MESURES, MESURES_ANNUELLES, STATUTS,
                    annee_scolaire, fmt_mesure)
from ..navigation import aller_a_la_fiche

# Le DataTable ne lit pas les variables CSS : ses valeurs s'écrivent en clair ici, mais jamais
# retapées — polices et couleurs viennent des constantes de figures.py.
POLICE = F.POLICE_UI
POLICE_CHIFFRE = F.POLICE_CHIFFRE
FOND_FILTRE = F.MUTED

EXPORT = {"rang": "rang", "province_nom": "province", "region_nom": "region", "pcode_province": "pcode_province",
          "valeur": "valeur_mesure", "score_priorite": "score_priorite", "rang_priorite": "rang_priorite",
          "classe": "classe_priorite", "eleves_par_maitre": "eleves_par_maitre", "eleves_par_salle": "eleves_par_salle",
          "deficit_enseignants": "enseignants_manquants", "deficit_salles": "salles_manquantes",
          "salles_a_construire_2030": "salles_a_construire_2030_S2", "enseignants_2030": "enseignants_supplementaires_2030_S2",
          "acces_part_hors_3km": "part_enfants_hors_3km_pct", "fiabilite_osm_province": "fiabilite_carte_ecoles"}

# mesures déjà portées par une colonne fixe du tableau : pas de colonne « valeur » en double
MESURES_SANS_COLONNE = ("score_priorite", "eleves_par_maitre", "eleves_par_salle")
COLONNES_NUM = ("rang", "valeur", "score", "epm", "eps")

STYLE_CELLULE = {"fontFamily": POLICE, "fontSize": 13, "padding": "4px 8px", "textAlign": "left",
                 "border": "none", "borderBottom": f"1px solid {F.BORDURE_FAIBLE}", "whiteSpace": "nowrap",
                 "color": F.ENCRE, "backgroundColor": F.BLANC, "textOverflow": "clip", "overflow": "visible"}
# `style_header` et `style_filter` passent devant `style_cell_conditional` : l'en-tête reste en
# police d'interface même au-dessus d'une colonne de chiffres (sinon il hérite du monospace).
STYLE_ENTETE = {"fontFamily": POLICE, "fontWeight": 600, "backgroundColor": F.BLANC, "color": F.GRIS,
                "fontSize": 12, "padding": "4px 8px", "borderBottom": f"1px solid {F.BORDURE}",
                "whiteSpace": "normal", "height": "auto", "lineHeight": "1.25", "verticalAlign": "bottom",
                "letterSpacing": "normal"}
STYLE_FILTRE = {"fontFamily": POLICE, "backgroundColor": FOND_FILTRE, "color": F.GRIS, "fontSize": 12,
                "letterSpacing": "normal", "borderBottom": f"1px solid {F.BORDURE}"}
# Largeurs explicites : un nombre ne se coupe jamais (colonne assez large pour « 70 568 »), un nom
# passe à la ligne plutôt que d'être tronqué (le DataTable n'a pas d'attribut `title`), et rien n'est
# jamais rendu avec des points de suspension.
#
# Le composant **n'agrandit** les largeurs déclarées que pour remplir son conteneur ; il ne les
# réduit jamais. Leur somme doit donc tenir dans le panneau le plus étroit, **colonne de mesure
# comprise** : à 1366 px le panneau du tableau offre 692 px, moins la barre de défilement verticale
# du corps, soit **≈ 682 px** utiles. Somme déclarée : **676 px**. Avec un jeu plus large (762 px),
# la colonne « Région » était rognée — en-tête « Régio » — dès qu'un critère ajoutait sa colonne, et
# le `.dash-spreadsheet-inner` est en `overflow-x: hidden`, donc sans défilement possible.
# Minimum d'une colonne = mot le plus long de l'en-tête + 8 px de flèche de tri + 16 px de
# remplissage (mesuré) : Rang 55, Province 76, mesure **97** (« Enseignants »), Score 57,
# Priorité 69, Élèves par maître 87 (deux lignes), Région 66.
LARGEURS_NUM = {"rang": 56, "valeur": 98, "score": 56, "epm": 86, "eps": 86}
LARGEURS = [{"if": {"column_id": c}, "textAlign": "right", "width": f"{px}px", "minWidth": f"{px}px"}
            for c, px in LARGEURS_NUM.items()]
LARGEURS += [{"if": {"column_id": "classe"}, "width": "68px", "minWidth": "68px"},
             {"if": {"column_id": "province"}, "width": "130px", "minWidth": "130px",
              "whiteSpace": "normal", "lineHeight": "1.25"},
             {"if": {"column_id": "region"}, "width": "96px", "minWidth": "96px",
              "whiteSpace": "normal", "lineHeight": "1.25"}]
# somme des largeurs de la configuration la plus large (8 colonnes) : vérifiée par un test
LARGEUR_TOTALE_MAX = sum(LARGEURS_NUM.values()) + 68 + 130 + 96
# la police chiffrée ne s'applique qu'aux cellules : l'en-tête reste en police d'interface
CHIFFRES = [{"if": {"column_id": c}, "fontFamily": POLICE_CHIFFRE, "letterSpacing": "-0.02em"}
            for c in LARGEURS_NUM]


def _fmt(dec):
    return {"locale": {"decimal": ",", "group": " "}, "specifier": f",.{dec}f"}


def titre_mesure(mesure):
    """Libellé complet de la mesure, avec son unité en toutes lettres (titre de carte et de légende)."""
    m = MESURES[mesure]
    unite = {"%": " (en %)", "/ 100": " (sur 100)"}.get(m["unite"], "")
    return m["label"] + unite


def colonnes(mesure):
    """Colonnes du tableau, dans l'ordre de lecture d'un téléphone.

    La mesure qui **fait** le classement vient juste après le nom : à 390 px, les trois premières
    colonnes tiennent dans la largeur du bloc et donnent le classement sans défiler.
    La région, métadonnée secondaire, passe en dernier — elle reste écrite sur la Fiche et dans le
    panneau « Provinces prioritaires » de la Vue d'ensemble.
    En-têtes courts : l'échelle 0-100 du score et la définition de P1/P2/P3 sont déjà dans la ligne
    « Lecture : » sous le tableau, un en-tête sur trois lignes ne les répète pas utilement.
    """
    cols = [{"name": "Rang", "id": "rang", "type": "numeric"},
            {"name": "Province", "id": "province", "presentation": "markdown"}]
    if mesure not in MESURES_SANS_COLONNE:
        m = MESURES[mesure]
        cols.append({"name": titre_mesure(mesure), "id": "valeur", "type": "numeric", "format": _fmt(m["dec"])})
    cols += [{"name": "Score", "id": "score", "type": "numeric", "format": _fmt(0)},
             {"name": "Priorité", "id": "classe"},
             {"name": "Élèves par maître", "id": "epm", "type": "numeric", "format": _fmt(1)},
             {"name": "Élèves par salle", "id": "eps", "type": "numeric", "format": _fmt(1)},
             {"name": "Région", "id": "region"}]
    return cols


def _r(v, n):
    return None if v is None or v != v else round(float(v), n)


def lignes(t, mesure, annee, statut):
    return [{"rang": None if r["rang"] != r["rang"] else int(r["rang"]),
             "province": f"[{r['province_nom']}](/fiche?pcode={r['pcode_province']}&annee={annee}&statut={statut})",
             "region": r["region_nom"], "valeur": _r(r["valeur"], MESURES[mesure]["dec"]),
             "score": _r(r["score_priorite"], 0), "epm": _r(r["eleves_par_maitre"], 1),
             "eps": _r(r["eleves_par_salle"], 1), "classe": r["classe"]} for _, r in t.iterrows()]


def tableau():
    """DataTable restylé sur les jetons du tableau statique `.tab`."""
    return dash_table.DataTable(
        id="cla-table", sort_action="native", filter_action="native", page_action="none",
        # `fixed_columns` n'est pas repris : il casse le rendu du tableau dans ce panneau (essayé, DataTable 4.5)
        fixed_rows={"headers": True}, markdown_options={"link_target": "_self"},
        # le tableau défile dans son bloc (jamais la page) quand les 8 colonnes dépassent le panneau
        style_table={"height": "100%", "maxHeight": "100%", "overflowY": "auto", "overflowX": "auto"},
        style_cell=STYLE_CELLULE, style_header=STYLE_ENTETE, style_filter=STYLE_FILTRE,
        style_cell_conditional=LARGEURS,
        # P1 porte le code **et** la graisse : l'information ne repose jamais sur la couleur seule
        style_data_conditional=CHIFFRES + [{"if": {"filter_query": '{classe} = "P1"', "column_id": "classe"},
                                            "fontWeight": 700, "color": F.BLEU}],
        filter_options={"case": "insensitive", "placeholder_text": "filtre"})


def layout(mesure=None, annee=None, statut=None, **_):
    mesure = mesure if mesure in MESURES else "score_priorite"
    try:
        annee = int(annee) if annee else ANNEE_REF
    except ValueError:
        annee = ANNEE_REF
    annee = annee if annee in ANNEES else ANNEE_REF
    statut = statut if statut in STATUTS else "PUBLIC"
    return html.Div([
        K.entete("Classement des provinces", "Burkina Faso · primaire · 45 provinces",
                 decoupage=DECOUPAGE_CONSTAT),
        # Panne de données : un **seul** bloc rouge, et `.zone-contenu` disparaît — jamais un état
        # vide, un bouton d'export actif et un « Données indisponibles » en même temps.
        html.Div(id="cla-erreur"),
        html.Div([
            K.constat(id="cla-resume"),
            # Filtres **sans cadre** : l'export est sur la même rangée, aligné à droite et sur le
            # bas des champs. Ni panneau de contrôles, ni ligne d'outils : 67 px de hauteur rendus
            # au tableau et à la carte.
            K.barre_filtres(
                K.filtre("Classer selon",
                         K.menu("cla-mesure", {k: m["label"] for k, m in MESURES.items()}, mesure),
                         cls="filtre-large"),
                K.filtre("Année scolaire",
                         K.menu("cla-annee", {a: annee_scolaire(a) for a in ANNEES[::-1]}, annee),
                         cls="filtre-moyen"),
                K.filtre("Secteur", K.menu("cla-statut", STATUTS, statut), cls="filtre-moyen"),
                action=K.bouton("Exporter en CSV", id_="cla-export-btn",
                                title="Télécharge la liste telle qu'elle est filtrée")),
            K.rangee(
                K.panneau("Les 45 provinces", html.Div(id="cla-vide", className="zone-vide"),
                          html.Div(tableau(), className="zone-liste"),
                          K.lecture("cliquez sur un nom de province pour ouvrir sa fiche. Le score de priorité va "
                                    "de 0 à 100 : il résume cinq retards (élèves par salle, élèves par maître, "
                                    "salles à construire d'ici 2030, salles perdues pendant la crise, enfants hors "
                                    "de l'école). P1 = priorité robuste, P2 = priorité probable, P3 = à surveiller. "
                                    "Région : découpage des annuaires, à 45 provinces."),
                          # La note du panneau porte le contexte de la mesure **et** l'affordance de tri
                          # (vraie : toute la cellule d'en-tête trie, au clic comme au clavier) ; elle
                          # est écrite par le callback, qui remplit les deux cas.
                          note_=html.Span(id="cla-note", className="note")),
                K.panneau(None,
                          html.Div(html.Div([html.H2(id="cla-titre-carte"), K.note("45 provinces, 5 classes")],
                                            className="panneau-tete"), className="carte-outils"),
                          html.Div(dcc.Graph(id="cla-carte", config=F.CONFIG_CARTE, responsive=True,
                                             style={"height": "100%", "width": "100%"}), className="zone-carte"),
                          html.Div(id="cla-legende"),
                          html.Div(id="cla-lecture"),
                          dcc.Location(id="cla-aller", refresh="callback-nav"),
                          cls="bloc-carte"),
            ),
        ], id="cla-contenu", className="pile zone-contenu"),
        dcc.Download(id="cla-download"),
    ], className="pile p-classement")


def register(app):
    @app.callback(Output("cla-table", "data"), Output("cla-table", "columns"), Output("cla-resume", "children"),
                  Output("cla-carte", "figure"), Output("cla-titre-carte", "children"), Output("cla-lecture", "children"),
                  Output("cla-note", "children"), Output("cla-annee", "disabled"), Output("cla-statut", "disabled"),
                  Output("cla-legende", "children"),
                  Output("cla-erreur", "children"), Output("cla-contenu", "hidden"),
                  Input("cla-mesure", "value"), Input("cla-annee", "value"), Input("cla-statut", "value"))
    def maj(mesure, annee, statut):
        try:
            d = donnees()
            d.get()
        except Exception:
            # un seul bloc rouge, le contenu disparaît : ni tableau vide, ni export actif, ni
            # second message sur la carte
            return ([], [], "", F.figure_vide("Données indisponibles", hauteur=None), "Carte", "",
                    "", False, False, None, K.erreur_donnees(), True)
        mesure = mesure if mesure in MESURES else "score_priorite"
        annuelle = mesure in MESURES_ANNUELLES
        a = annee if annuelle else ANNEE_REF
        t = C.classement(d, mesure, a, statut)
        m = MESURES[mesure]
        lib_sect = STATUTS[statut].lower()
        ctx = (f"année scolaire {annee_scolaire(a)}, secteur {lib_sect}" if annuelle
               else f"année scolaire {annee_scolaire(ANNEE_REF)}")
        resume = (f"Les 45 provinces classées selon : {m['label'].lower()} ({ctx}). "
                  "La province en tête est celle où la valeur est la plus élevée.")
        top = set(t.head(10).pcode_province)
        vals = {r["pcode_province"]: (r["valeur"], C.survol_province(r, mesure)) for _, r in t.iterrows()}
        # Les bornes sont calculées **une fois** et passées à la carte comme à la légende : les deux
        # ne peuvent pas diverger. Une mesure cartographiée sur plusieurs pages garde partout la même
        # légende (F.BORNES_MESURE) ; un pourcentage est plafonné à 100, sinon la dernière classe
        # annoncerait « 100 % et plus », une valeur que la mesure ne peut pas atteindre.
        pct = m["unite"] == "%"
        bornes_classes = F.classes(list(t["valeur"]), bornes_classes=F.bornes_mesure(mesure),
                                   plafond=100 if pct else None)
        fig = F.carte(C.geoms_provinces(d), vals, titre_mesure(mesure), gras=top,
                      contours_regions=d["geo_region"], fmt=".0f" if m["dec"] == 0 else ".1f", legende=False,
                      bornes_classes=bornes_classes)
        # légende écrite en HTML (5 classes + unité) plutôt que la barre de couleurs de Plotly ;
        # en colonne, car la carte est ici dans un panneau latéral de moins de 480 px
        legende = K.legende_rampe(titre_mesure(mesure),
                                  F.libelles_classes(bornes_classes, m["dec"], "%" if pct else ""),
                                  colonne=True)
        p1 = t.iloc[0]
        lecture = K.lecture(f"{p1['province_nom']} arrive en tête ({fmt_mesure(p1['valeur'], mesure)}). Plus une "
                            "province est foncée, plus la valeur y est élevée. Contour noir : les 10 premières du "
                            "classement. Traits gris : limites de région.")
        # Note du panneau du tableau : l'affordance de tri dans les deux cas, précédée du contexte
        # de la mesure quand l'année et le secteur n'y changent rien (les deux menus sont alors
        # désactivés : la note dit pourquoi).
        # mesurée : la note du bandeau tient sur **une** ligne à 1366 px (sinon le titre du panneau
        # tombe lui aussi sur deux lignes) — 95 caractères au maximum
        note = ("cliquez sur un en-tête pour trier" if annuelle else
                f"mesure de {annee_scolaire(ANNEE_REF)}, l'année et le secteur n'y changent rien · "
                "cliquez sur un en-tête pour trier")
        return (lignes(t, mesure, a, statut), colonnes(mesure), resume, fig, m["label"], lecture, note,
                not annuelle, not annuelle, legende, "", False)

    @app.callback(Output("cla-vide", "children"), Input("cla-table", "derived_virtual_data"))
    def etat_vide(visibles):
        """Filtre de colonne sans résultat : dire ce qui manque et quoi faire, jamais un tableau vide."""
        if visibles is None or len(visibles):
            return None
        return html.Div([K.vide("Aucune province ne correspond à ce filtre.",
                                "Effacez les filtres du tableau pour revoir les 45 provinces."),
                         html.Div(K.bouton("Effacer les filtres", id_="cla-effacer"), className="ligne-outils")],
                        className="pile")

    @app.callback(Output("cla-table", "filter_query"), Input("cla-effacer", "n_clicks"), prevent_initial_call=True)
    def effacer(n):
        # le bouton naît avec l'état vide : son apparition ne doit pas effacer le filtre toute seule
        if not n:
            raise PreventUpdate
        return ""

    @app.callback(Output("cla-download", "data"), Input("cla-export-btn", "n_clicks"),
                  State("cla-mesure", "value"), State("cla-annee", "value"), State("cla-statut", "value"),
                  State("cla-table", "derived_virtual_data"), prevent_initial_call=True)
    def exporter(n, mesure, annee, statut, visibles):
        d = donnees()
        mesure = mesure if mesure in MESURES else "score_priorite"
        a = annee if mesure in MESURES_ANNUELLES else ANNEE_REF
        t = C.classement(d, mesure, a, statut)
        if visibles is not None:
            gardes = [str(v.get("province", "")).split("pcode=")[-1].split("&")[0] for v in visibles]
            t = t.set_index("pcode_province").loc[[g for g in gardes if g]].reset_index()
        t = t[list(EXPORT)].rename(columns=EXPORT)
        t.insert(0, "mesure", mesure)
        t.insert(1, "annee_scolaire", annee_scolaire(a))
        t.insert(2, "secteur", statut if mesure in MESURES_ANNUELLES else "")
        buf = io.StringIO()
        t.to_csv(buf, sep=";", decimal=",", index=False)
        # BOM UTF-8 écrit en échappement : le caractère U+FEFF, invisible dans un éditeur, se perd
        # ou se duplique au moindre copier-coller du fichier source. Octets du CSV inchangés.
        return dcc.send_string("\ufeff" + buf.getvalue(),
                               f"classement_provinces_{mesure}_{annee_scolaire(a)}.csv")

    @app.callback(Output("cla-aller", "href"), Input("cla-carte", "clickData"), prevent_initial_call=True)
    def ouvrir(clic):
        return aller_a_la_fiche(clic)
