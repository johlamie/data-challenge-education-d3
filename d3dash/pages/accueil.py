"""Vue d'ensemble (`/`) : phrase-constat, 6 chiffres clés, carte du pays et les 10 provinces en tête.

Plan de travail en deux colonnes : la carte est l'objet principal à gauche, le classement est le
panneau de décision à droite. Tous les blocs viennent du kit (`composants.py`, `figures.py`) ;
aucune valeur n'est calculée ici, seules des valeurs déjà produites par `calculs.py` sont mises
en forme.

**La liste suit la mesure choisie sur la carte** : le même `C.classement(d, mesure)` alimente les
dix lignes, le contour noir de la carte et les pastilles de rang — une seule source, donc aucun
écart possible entre la liste et la carte.
"""
from dash import Input, Output, dcc, html

from .. import aides as A
from .. import calculs as C
from .. import composants as K
from .. import figures as F
from ..db import donnees
from ..meta import (ANNEE_REF, DECOUPAGE_CONSTAT, MESURES, annee_scolaire, fmt_mesure, fmt_nombre, fmt_signe,
                    manque)
from ..navigation import aller_a_la_fiche

MESURES_CARTE = {"score_priorite": "Score de priorité", "eleves_par_maitre": "Élèves par maître",
                 "salles_a_construire_2030": "Salles à construire 2030"}
# normes écrites du manuel (aides.NORMES) : elles calent les classes de la rampe sur « au-dessus / en dessous »
NORMES_CARTE = {"eleves_par_maitre": 50}
TITRES = {"score_priorite": "Score de priorité (0 à 100)",
          "eleves_par_maitre": "Élèves par maître, public 2024-2025 — norme : 50",
          "salles_a_construire_2030": "Salles à construire d'ici 2030 (scénario central)"}
PERIMETRE = f"Burkina Faso · primaire public · année scolaire {annee_scolaire(ANNEE_REF)}"

def _teintes_au_dessus(norme, mesure):
    """Nombre de teintes de la rampe qui valent la norme ou plus, déduit des bornes réellement
    tracées (`F.classes`) : avec les bornes 45/50/55/60, trois des cinq classes sont à 50 ou plus.
    Écrire « les deux teintes les plus foncées » serait faux — et le resterait si la norme changeait."""
    bornes = F.classes([], norme=norme, bornes_classes=F.bornes_mesure(mesure))
    # une classe i (0 à 4) commence à bornes[i-1] ; elle est « à la norme ou au-dessus » dès que
    # sa borne basse atteint la norme
    return sum(1 for b in bornes if b >= norme)


MOTS_NOMBRE = {1: "une", 2: "deux", 3: "trois", 4: "quatre", 5: "cinq"}
_N_AU_DESSUS = _teintes_au_dessus(50, "eleves_par_maitre")
# une phrase « Lecture : » par mesure (obligatoire sous chaque figure)
LECTURES = {
    "score_priorite": "plus la province est foncée, plus elle cumule de retard (salles, maîtres, "
                      "enfants hors de l'école).",
    "eleves_par_maitre": f"les {MOTS_NOMBRE.get(_N_AU_DESSUS, _N_AU_DESSUS)} teintes les plus foncées sont à "
                         "50 élèves par maître ou plus, c'est-à-dire au niveau de la norme ou au-dessus.",
    "salles_a_construire_2030": "plus la province est foncée, plus il faudra y construire de salles d'ici 2030.",
}
# Espaces insécables avant « : » et « ; » (règle de langue du français), écrites en clair ici.
# « à droite » du classement serait faux sous 961 px (la liste passe sous la carte) ; « sur grand
# écran » est vrai aux deux largeurs, contrairement à une affirmation au présent sur les pastilles.
# Le contour noir et les pastilles désignent **les dix provinces de la liste affichée**, quelle
# que soit la mesure : la phrase le dit avec les mots de cette mesure.
RAPPELS = {
    "score_priorite": " Contour noir : les 10 provinces prioritaires de la liste ; sur grand "
                      "écran, chacune porte son rang.",
    "eleves_par_maitre": " Contour noir : les 10 provinces de la liste (le plus d'élèves par "
                         "maître) ; sur grand écran, chacune porte son rang.",
    "salles_a_construire_2030": " Contour noir : les 10 provinces de la liste (le plus de salles "
                                "à construire) ; sur grand écran, chacune porte son rang.",
}
FIN_LECTURE = " Traits gris : limites de région. Sélectionnez une province pour ouvrir sa fiche."

# Titre du panneau de liste : il dit ce que la liste classe — « Provinces prioritaires » mentirait
# sur un classement par élèves par maître. Court : la tête du panneau tient sur **une** ligne à
# 1366 px, à côté de la note « 10 sur 45 ».
TITRES_LISTE = {"score_priorite": "Provinces prioritaires",
                "eleves_par_maitre": "Le plus d'élèves par maître",
                "salles_a_construire_2030": "Le plus de salles à construire"}
# Légende du tableau, lue par un lecteur d'écran : la phrase entière, qui ne coûte aucune place.
LEGENDES_LISTE = {"score_priorite": "Les 10 provinces les plus prioritaires sur 45",
                  "eleves_par_maitre": "Les 10 provinces où il y a le plus d'élèves par maître, sur 45",
                  "salles_a_construire_2030": "Les 10 provinces où il faudra construire le plus de salles "
                                              "d'ici 2030, sur 45"}
# En-tête de la colonne chiffrée : le libellé court de la mesure (`meta.MESURES`), qui tient sans se
# couper dans une colonne de 80 px.
ENTETES_LISTE = {cle: MESURES[cle]["court"] for cle in MESURES_CARTE}


def lien_classement(mesure):
    """Adresse du classement complet, **sur la mesure affichée** (la page Classement lit `?mesure=`)."""
    return "/classement" if mesure == "score_priorite" else f"/classement?mesure={mesure}"


# ---- phrase-constat ------------------------------------------------------------------------------------------
def nb_p1(d):
    """Nombre de provinces classées P1 dans la table de priorité déjà calculée (lecture, pas un calcul)."""
    return int((C.classement(d, "score_priorite")["classe"] == "P1").sum())


def phrase_constat(d):
    """Le constat national en une phrase, à partir des seules valeurs de `C.kpis` et de la table de priorité.

    Une proposition dont la valeur manque disparaît (jamais « — », jamais un chiffre inventé)."""
    k = C.kpis(d)
    debut = []
    if not manque(k["epm"]):
        debut = ["Le primaire public compte ", K.chiffre(f"{fmt_nombre(k['epm'], 1)} élèves par maître"),
                 " pour une norme de 50. "]
    manques = [K.chiffre(f"{fmt_nombre(v)} {lib}")
               for v, lib in ((k["def_ens"], "enseignants"), (k["def_salles"], "salles de classe"))
               if not manque(v)]
    suite = []
    for i, m in enumerate(manques):
        suite += [" et " if i else "Il manque ", m]
    n1 = nb_p1(d)
    if n1:
        # accord singulier/pluriel écrit : la langue d'interface est le français uniquement
        nom, verbe = ("province", " est") if n1 == 1 else ("provinces", " sont")
        if suite:
            suite.append(", et ")
        # P1 (d3a_05_priorite) : dans les dix premières **et** dans les dix premières pour au moins
        # 60 % des 5 000 pondérations tirées. Les deux conditions tiennent en une proposition ;
        # la forme développée (« figurent … et y restent … ») mesure 3 lignes et fait sauter le
        # budget de 2 lignes du constat (mesuré à 1366 et à 1440 px).
        # « quelle que soit la façon de pondérer » serait faux : le seuil est 60 %, pas 100 %.
        suite += [K.chiffre(f"{fmt_nombre(n1)} {nom}"), verbe,
                  " dans les 10 premières pour au moins 60 % des pondérations tirées au hasard"]
    if suite:
        suite.append(".")
    return K.constat(*debut, *suite)


# ---- chiffres clés -------------------------------------------------------------------------------------------
def bloc_kpis(d):
    """Les 6 chiffres clés. Aucune icône ; infobulle (sans icône) sur les 4 indicateurs non évidents.

    Chaque ligne d'une cellule tient sur **une** ligne (budget vertical de la bande : 96 px).
    Ce que la cellule n'écrit plus en entier, l'infobulle le dit : le mot « redéployables » est
    défini dans `A.KPI_DEFICIT_ENS` et la mention de record dans sa variante (aucune perte).
    """
    k = C.kpis(d)
    return [
        K.kpi("Élèves par maître", fmt_nombre(k["epm"], 1),
              evolution=K.tendance(k["epm_delta"], f"{fmt_signe(k['epm_delta'], 1)} en un an"),
              variation="norme : 50"),
        K.kpi("Élèves par salle", fmt_nombre(k["eps"], 1),
              evolution=K.tendance(k["eps_delta"], f"{fmt_signe(k['eps_delta'], 1)} en un an"),
              variation="norme : 50"),
        K.kpi("Enseignants manquants", fmt_nombre(k["def_ens"]),
              evolution=K.tendance(k["def_ens_delta"], f"{fmt_signe(k['def_ens_delta'])} en un an"),
              variation=f"dont {fmt_nombre(k['redeployables'])} redéployables",
              aide_kpi=A.deficit_ens(k["def_ens_record"])),
        K.kpi("Salles manquantes", fmt_nombre(k["def_salles"]),
              evolution=K.tendance(k["def_salles_delta"], f"{fmt_signe(k['def_salles_delta'])} en un an"),
              variation=f"dans {k['prov_def_salles']} provinces sur 45", aide_kpi=A.KPI_DEFICIT_SALLES),
        K.kpi("Salles à construire 2030", fmt_nombre(k["s2030"]),
              # « scénario central » est porté par l'infobulle (A.KPI_2030), la ligne garde l'horizon ;
              # le `title` rend la phrase entière lisible si la cellule devait la couper
              evolution=html.Span(f"≈ {fmt_nombre((k['s2030'] or 0) / 6)} par an d'ici 2030",
                                  className="tendance t-neutre",
                                  title=f"≈ {fmt_nombre((k['s2030'] or 0) / 6)} salles par an d'ici 2030"),
              variation=f"+ {fmt_nombre(k['e2030'])} enseignants", aide_kpi=A.KPI_2030),
        K.kpi("Taux de scolarisation", fmt_nombre(k["tbs"], 1) + " %",
              evolution=K.tendance(k["tbs_delta"], f"{fmt_signe(k['tbs_delta'], 1)} pt en un an",
                                   mauvais_si_hausse=False),
              variation=f"{fmt_nombre(k['tbs_2017'], 1)} % en 2017-2018", aide_kpi=A.KPI_TBS),
    ]


# ---- liste des 10 provinces en tête --------------------------------------------------------------------------
def top10(d, mesure="score_priorite", n=10):
    """Les `n` premières provinces pour la mesure affichée.

    **Source unique** de la liste, du contour noir de la carte et des pastilles de rang : les trois
    lisent cette table, donc aucun écart n'est possible entre ce que la liste écrit et ce que la
    carte dessine. Le tri, les ex æquo (`method="min"`) et les valeurs manquantes (toujours en fin)
    sont ceux de `calculs.classement` — rien n'est recalculé ici.
    """
    return C.classement(d, mesure).head(n)


def _cellule_valeur(r, mesure):
    """Colonne chiffrée : la barre de score sur le score (indice de 0 à 100), le nombre seul sur les
    autres mesures — une piste pleine à 100 n'aurait aucun sens devant « 64,0 élèves par maître »."""
    txt = fmt_mesure(r["valeur"], mesure)
    if mesure == "score_priorite":
        return K.barre_score(r["valeur"], txt)
    return txt


def tableau_top(d, mesure="score_priorite", n=10, t=None):
    """Les 10 provinces en tête pour la mesure affichée : rang, province (+ sa région sur une seconde
    ligne), valeur de la mesure, badge de priorité.

    La colonne « Priorité » reste sur les trois mesures : le lecteur garde le lien avec les classes
    P1/P2/P3, même quand la liste est classée sur autre chose. L'icône « i » appartient au score (le
    site en compte 4 en tout) : elle reste sur sa colonne et n'apparaît pas sur les deux autres.
    """
    t = top10(d, mesure, n) if t is None else t
    lignes = []
    for _, r in t.iterrows():
        lignes.append(html.Tr([
            html.Td("–" if manque(r["rang"]) else int(r["rang"]), className="c-rang"),
            html.Td([dcc.Link(r["province_nom"], href=f"/fiche?pcode={r['pcode_province']}"),
                     html.Span(r["region_nom"], className="reg-ligne", title=r["region_nom"])],
                    className="c-prov"),
            html.Td(_cellule_valeur(r, mesure), className="c-num"),
            html.Td(K.badge_classe(r["classe_priorite"], court=True), className="c-stat"),
        ]))
    entete = ENTETES_LISTE[mesure]
    tete = html.Thead(html.Tr([
        html.Th("#", className="c-rang", scope="col"), html.Th("Province", scope="col"),
        html.Th([entete, K.aide(A.SCORE, "Score de priorité")] if mesure == "score_priorite" else entete,
                className="c-num", scope="col"),
        html.Th("Priorité", className="c-stat", scope="col")]))
    return html.Table([html.Caption(LEGENDES_LISTE[mesure], className="sr-only"),
                       tete, html.Tbody(lignes)], className="tab tab-top10")


# ---- carte ---------------------------------------------------------------------------------------------------
def bornes_carte(d, mesure):
    """Les 4 bornes de la légende, calculées **une fois** pour la carte et pour la légende.

    Une mesure dont la norme est écrite garde ses bornes partout (`F.bornes_mesure`) ; les autres
    suivent les quantiles des valeurs réellement affichées — les deux blocs doivent donc lire la
    même liste, sinon la légende peut décrire d'autres classes que la carte.
    """
    return F.classes(list(C.classement(d, mesure)[mesure]), norme=NORMES_CARTE.get(mesure),
                     bornes_classes=F.bornes_mesure(mesure), dec=MESURES[mesure]["dec"])


def figure_carte(d, mesure, top=None):
    """Carte de la mesure affichée. `top` : les dix provinces de la liste (`top10`) — le contour noir
    et les pastilles numérotées désignent **exactement** ces dix-là, avec les mêmes rangs, ex æquo
    compris. Depuis que la liste suit la mesure, les rangs ont un sens sur les trois mesures."""
    t = C.classement(d, mesure)
    top = top10(d, mesure) if top is None else top
    rangs = {r.pcode_province: int(r.rang) for r in top.itertuples() if not manque(r.rang)}
    vals = {r["pcode_province"]: (r[mesure], C.survol_province(r, mesure)) for _, r in t.iterrows()}
    return F.carte(C.geoms_provinces(d), vals, TITRES[mesure], gras=set(top.pcode_province),
                   rangs=rangs, contours_regions=d["geo_region"], legende=False,
                   bornes_classes=bornes_carte(d, mesure),
                   fmt=".0f" if MESURES[mesure]["dec"] == 0 else ".1f")


def legende_carte(d, mesure):
    """Légende HTML classée : les 5 classes écrites avec leur borne (jamais une barre continue)."""
    return K.legende_rampe(TITRES[mesure], F.libelles_classes(bornes_carte(d, mesure),
                                                              MESURES[mesure]["dec"]))


def lecture_carte(mesure):
    return LECTURES[mesure] + RAPPELS[mesure] + FIN_LECTURE


# ---- page ----------------------------------------------------------------------------------------------------
def layout(**_):
    try:
        d = donnees()
        d.get()
    except Exception:
        return K.erreur_donnees()
    return html.Div([
        K.entete("Vue d'ensemble", PERIMETRE, decoupage=DECOUPAGE_CONSTAT),
        phrase_constat(d),
        K.bande_kpi(bloc_kpis(d)),
        K.rangee(
            K.panneau(
                None,
                html.Div([html.Div(html.H2("Les 45 provinces"), className="panneau-tete"),
                          K.controle_segmente("acc-mesure", MESURES_CARTE, "score_priorite",
                                              "Mesure affichée sur la carte")],
                         className="carte-outils"),
                html.Div(dcc.Graph(id="acc-carte", config=F.CONFIG_CARTE, responsive=True,
                                   style={"height": "100%", "width": "100%"}), className="zone-carte"),
                html.Div(legende_carte(d, "score_priorite"), id="acc-legende"),
                K.lecture(html.Span(lecture_carte("score_priorite"), id="acc-lecture")),
                dcc.Location(id="acc-aller", refresh="callback-nav"),
                cls="bloc-carte"),
            K.panneau(
                # le titre vit dans un span : le callback le remplace quand la mesure change
                html.Span(TITRES_LISTE["score_priorite"], id="acc-titre-liste"),
                html.Div(tableau_top(d), className="zone-liste", id="acc-liste"),
                # Les trois codes de la colonne « Priorité », en une ligne : la définition complète
                # de P1 (seuil de 60 % des tirages) est dans l'icône « i » de l'en-tête « Score »,
                # et « le rang est repris sur la carte » est déjà écrit sous la carte. La phrase ne
                # dépend pas de la mesure : la colonne « Priorité » est la même sur les trois.
                K.lecture("P1 = priorité robuste, P2 = probable, P3 à surveiller."),
                note_="10 sur 45",
                pied=K.panneau_pied(K.lien_suite("Classement complet des 45 provinces", "/classement",
                                                 id="acc-lien-classement"))),
        ),
    ], className="pile p-accueil")


def register(app):
    @app.callback(Output("acc-carte", "figure"), Output("acc-legende", "children"),
                  Output("acc-lecture", "children"), Output("acc-liste", "children"),
                  Output("acc-titre-liste", "children"), Output("acc-lien-classement", "href"),
                  Input("acc-mesure", "value"))
    def maj(mesure):
        """La carte **et** la liste suivent la mesure choisie : un seul `top10`, donc le contour
        noir, les pastilles de rang et les dix lignes désignent toujours les mêmes provinces."""
        mesure = mesure if mesure in MESURES_CARTE else "score_priorite"
        titre, lien = TITRES_LISTE[mesure], lien_classement(mesure)
        try:
            d = donnees()
            d.get()
        except Exception:
            # même état que le bloc d'erreur de la page : aucun chiffre périmé n'est laissé à l'écran
            return (F.figure_vide("Données indisponibles", hauteur=None), None, lecture_carte(mesure),
                    K.vide("Les données ne sont pas disponibles pour le moment.",
                           "Réessayez dans une minute."), titre, lien)
        t = top10(d, mesure)
        return (figure_carte(d, mesure, top=t), legende_carte(d, mesure), lecture_carte(mesure),
                tableau_top(d, mesure, t=t), titre, lien)

    @app.callback(Output("acc-aller", "href"), Input("acc-carte", "clickData"), prevent_initial_call=True)
    def ouvrir(clic):
        return aller_a_la_fiche(clic)
