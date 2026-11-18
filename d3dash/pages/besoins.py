"""Besoins 2030 : scénario, variante de population, normes (sensibilité) et secteur ; chiffres nationaux,
comparaison des scénarios, carte et liste des provinces (besoins recalculés pour les normes choisies).

Page de **projection** : tout ce qui est par province vient du découpage administratif de 2025
(17 régions, 47 provinces, `d3dash/decoupage.py`) ; les totaux nationaux, eux, sont ceux de
`calculs.py` — ils sont identiques dans les deux découpages par construction (test de conservation
dans `tests/test_decoupage_2025.py`).

Page « qui défile » : en-tête, barre de filtres sans cadre (5 champs sur une
rangée), bande de 4 chiffres, puis deux rangées 5/7. Tous les blocs viennent du kit
(`composants.py`, `figures.py`) ; seules les règles de mise en page propres à l'écran vivent dans
`assets/page-besoins.css` (préfixe `.p-besoins`).
"""
from dash import Input, Output, dcc, html

from .. import aides as A
from .. import calculs as C
from .. import composants as K
from .. import decoupage as D25
from .. import figures as F
from ..db import donnees
from ..libelles import SCENARIOS_CLAIRS
from ..meta import (DECOUPAGE_2025, NORMES_CLASSE, NORMES_ENSEIGNANT, POPULATIONS, SCENARIO_CENTRAL, SCENARIOS,
                    fmt_nombre, fmt_signe, manque)

# Libellés en mots simples pour des lecteurs non initiés ; le code du scénario reste entre
# parenthèses. Une seule source pour tout le site (`d3dash/libelles.py`) : le filtre, le tableau de
# la Fiche et l'axe du graphique disaient trois choses différentes du même scénario.
# Les **valeurs** (clés) restent celles de meta.py : les callbacks, les tests et
# outils/verifier_d3.py continuent de choisir les mêmes options.
LIB_SCENARIOS = SCENARIOS_CLAIRS
# « 50 (norme officielle) » faisait 131 px et était coupé dans un champ de 184 px (les 5 filtres sur
# une rangée) : « norme officielle » et les variantes restent écrits dans l'icône « i »
# « Élèves par classe » (`A.NORMES`) — aucune information perdue.
LIB_NORMES_CLASSE = {50: "50 (norme)", 60: "60", 65: "65 (ancien plafond)"}
LIB_NORMES_ENSEIGNANT = {45: "45", 50: "50 (norme)", 55: "55"}
STATUTS_2030 = {"TOTAL": "Public + privé", "PUBLIC": "Public seulement"}

TITRE_PAGE = "Besoins en 2030 (nouveau découpage 2025)"
PERIMETRE = ("Ce qu'il faut construire et recruter d'ici l'année scolaire 2030-2031, "
             "selon la scolarisation attendue et la norme visée.")
NB_PROVINCES = 47
LECTURE_CARTE = ("plus la province est foncée, plus il faut y construire de salles d'ici 2030. "
                 "Les traits gris sont les limites des 17 régions de 2025.")
# Une seule phrase dit d'où viennent les chiffres d'une province créée en 2025 : sans elle, un
# lecteur qui connaît l'ancienne province croirait à un chiffre nouveau.
LECTURE_PROVINCES = ("les 10 provinces où il faut construire le plus de salles, avec le scénario et les normes "
                     "choisis ci-dessus. Une province issue du découpage d'une ancienne province reçoit une part "
                     "du total de celle-ci, au prorata de sa population et de ses écoles géolocalisées : le total "
                     "national est inchangé. Le lien ouvre la fiche de l'ancienne province (découpage d'avant 2025).")
TITRE_CARTE = "Salles à construire d'ici 2030"
MESURE_CARTE = "salles_a_construire_2030"
# `None` : cette mesure n'a pas de norme écrite, ses bornes suivent la distribution affichée. Elles
# sont donc calculées **une fois** par rafraîchissement et passées telles quelles à la carte et à
# la légende.
BORNES_CARTE = F.bornes_mesure(MESURE_CARTE)


def _options(base, libelles):
    """Options d'un sélecteur : libellés en mots simples, valeurs inchangées."""
    return {cle: libelles.get(cle, defaut) for cle, defaut in base.items()}


def _options_normes(normes, libelles):
    return {n: libelles.get(n, f"{n}") for n in normes}


def _kpis_squelette():
    """Première peinture : la géométrie et les libellés définitifs, les valeurs en aplat."""
    return [K.kpi("Élèves en 2030", K.valeur_sk("000 000"), variation=K.valeur_sk("en 2024-2025")),
            K.kpi("Salles à construire", K.valeur_sk("00 000"), variation=K.valeur_sk("par classe")),
            K.kpi("Enseignants en plus", K.valeur_sk("00 000"), variation=K.valeur_sk("par enseignant")),
            K.kpi("Salles fermées supposées rouvertes", K.valeur_sk("0 000"), variation=K.valeur_sk("déduites"))]


def layout(scenario=None, **_):
    scenario = scenario if scenario in SCENARIOS else SCENARIO_CENTRAL
    return html.Div([
        K.entete(TITRE_PAGE, PERIMETRE, decoupage=DECOUPAGE_2025),
        # panne de données : un seul bloc rouge, le contenu disparaît
        html.Div(id="bes-erreur"),
        html.Div([

        # Pas de panneau autour des filtres : 26 px gagnés. La grille des
        # 5 champs sur une rangée reste propre à cet écran (`assets/page-besoins.css`).
        html.Div([
            K.filtre("Scénario", K.menu("bes-scenario", _options(SCENARIOS, LIB_SCENARIOS), scenario),
                     A.SCENARIOS, cls="filtre-large"),
            K.filtre("Population 6-11 ans en 2030", K.menu("bes-pop", POPULATIONS, "moyen")),
            K.filtre("Élèves par classe",
                     K.menu("bes-nc", _options_normes(NORMES_CLASSE, LIB_NORMES_CLASSE), 50), A.NORMES),
            K.filtre("Élèves par enseignant",
                     K.menu("bes-nm", _options_normes(NORMES_ENSEIGNANT, LIB_NORMES_ENSEIGNANT), 50)),
            K.filtre("Secteur", K.menu("bes-statut", STATUTS_2030, "TOTAL")),
        ], className="filtres"),

        K.bande_kpi(_kpis_squelette(), colonnes=4, id="bes-kpis"),

        K.grille(
            K.panneau("Selon le scénario",
                      # zone du kit : la figure occupe la hauteur laissée par la carte d'en face
                      html.Div(dcc.Graph(id="bes-scenarios", config=F.CONFIG, responsive=True,
                                         style={"height": "100%", "width": "100%"}),
                               className="zone-graphique"),
                      html.Div(id="bes-lecture-scenarios"),
                      note_="avec les normes choisies"),
            K.panneau(None,
                      html.Div(html.Div([html.H2("Salles à construire par province"),
                                         K.note(f"{NB_PROVINCES} provinces")],
                                        className="panneau-tete"), className="carte-outils"),
                      html.Div(dcc.Graph(id="bes-carte", config=F.CONFIG_CARTE, responsive=True,
                                         style={"height": "100%", "width": "100%"}), className="zone-carte"),
                      html.Div(id="bes-legende"),
                      cls="bloc-carte"),
            inverse=True, id="bes-rangee-figures"),

        K.grille(
            K.panneau("Effet de la norme", html.Div(id="bes-normes"),
                      note_="scénario et population choisis"),
            K.panneau("Provinces où il faut le plus construire", html.Div(id="bes-provinces"),
                      note_=f"10 sur {NB_PROVINCES}"),
            inverse=True),
        ], id="bes-contenu", className="pile zone-contenu"),
    ], className="pile p-besoins")


def _tab_norme(lib_colonne, lib_valeur, serie, normes, choisi, libelles, resume):
    """Petit tableau de sensibilité : une norme par ligne, la norme choisie en valeur mise en avant.

    Mise en avant **neutre** (`.ligne-centrale`, fond `--muted`) et jamais par la couleur seule :
    la ligne porte aussi `aria-current` et la mention « · choisi ».
    """
    lignes = []
    for n in normes:
        sel = n == choisi
        lignes.append(html.Tr([
            html.Td([libelles.get(n, f"{n}"), html.Span(" · choisi", className="note") if sel else None]),
            html.Td(fmt_nombre(serie.get(float(n))), className="c-num"),
        ], className="ligne-centrale" if sel else None, **({"aria-current": "true"} if sel else {})))
    return html.Table([html.Caption(resume, className="sr-only"),
                       html.Thead(html.Tr([html.Th(lib_colonne, scope="col"),
                                           html.Th(lib_valeur, className="c-num", scope="col")])),
                       html.Tbody(lignes)], className="tab")


def _tables_normes(d, scenario, pop, statut, nc, nm):
    s = d["sensibilite_2030"]
    s = s[(s.scenario == scenario) & (s.variante_population == pop) & (s.statut == statut)]
    sal = s[s.norme_eleves_par_enseignant == nm].set_index("norme_eleves_par_classe").salles_a_construire_2030
    ens = s[s.norme_eleves_par_classe == nc].set_index("norme_eleves_par_enseignant").enseignants_supplementaires_2030
    return [html.Div([
        _tab_norme("Élèves par classe", "Salles à construire", sal, NORMES_CLASSE, nc, LIB_NORMES_CLASSE,
                   "Salles à construire d'ici 2030 selon le nombre d'élèves par classe"),
        _tab_norme("Élèves par enseignant", "Enseignants en plus", ens, NORMES_ENSEIGNANT, nm,
                   LIB_NORMES_ENSEIGNANT,
                   "Enseignants à recruter d'ici 2030 selon le nombre d'élèves par enseignant"),
    ], className="pile"),
        K.lecture(f"à 60 élèves par classe au lieu de 50, il faudrait {fmt_nombre(sal.get(60.0))} salles au lieu de "
                  f"{fmt_nombre(sal.get(50.0))}, avec des classes plus chargées ; la norme officielle reste 50.")]


def _survol(r):
    """Survol d'une province de la carte : les noms de 2025, et le nom d'avant 2025 après la région.

    Texte simple, sans balise de couleur ; la ligne n'apparaît que si le nom a
    changé en 2025.
    """
    avant = "" if manque(r.anciennement) else f"anciennement : {r.anciennement}<br>"
    return (f"<b>{r.province_nom}</b> · {r.region_nom}<br>{avant}"
            f"Salles à construire : {fmt_nombre(r.salles_a_construire_2030)} "
            f"(≈ {fmt_nombre(r.salles_par_an)} par an)<br>"
            f"Enseignants en plus : {fmt_nombre(r.enseignants_supplementaires_2030)}<br>"
            f"Élèves : {fmt_nombre(r.eleves_2024_25)} → {fmt_nombre(r.eleves_2030)}")


def _titre_lien(r):
    """Titre du lien vers la Fiche, qui reste sur l'ancien découpage : il nomme la province **ouverte**.

    Une province créée ou renommée en 2025 n'a pas de fiche : le lien ouvre celle de l'ancienne
    province (sa province mère pour une province scindée). Le titre le dit, sinon le lecteur croirait
    ouvrir la fiche de la province 2025.
    """
    if manque(r.anciennement):
        return f"Fiche de {r.province_nom}"
    return f"Fiche de l'ancienne province {r.anciennement}"


def _tableau_provinces(top):
    lignes = [html.Tr([
        html.Td([dcc.Link(r.province_nom, href=f"/fiche?pcode={r.pcode_province}", title=_titre_lien(r)),
                 # seconde ligne « anciennement : X » quand le nom a changé en 2025
                 K.anciennement(None if manque(r.anciennement) else r.anciennement),
                 html.Span(r.region_nom, className="reg-ligne", title=r.region_nom)], className="c-prov"),
        html.Td(fmt_nombre(r.salles_a_construire_2030), className="c-num"),
        html.Td(fmt_nombre(r.salles_par_an), className="c-num"),
        html.Td(fmt_nombre(r.enseignants_supplementaires_2030), className="c-num"),
        html.Td(fmt_nombre(r.eleves_2030), className="c-num"),
    ]) for r in top.itertuples()]
    tete = html.Thead(html.Tr([html.Th("Province", scope="col"),
                               html.Th("Salles", className="c-num", scope="col"),
                               html.Th("Par an", className="c-num", scope="col"),
                               html.Th("Enseignants", className="c-num", scope="col"),
                               html.Th("Élèves 2030", className="c-num", scope="col")]))
    tab = html.Table([html.Caption("Les 10 provinces du découpage 2025 où il faut construire le plus de salles "
                                   "d'ici 2030", className="sr-only"), tete, html.Tbody(lignes)],
                     className="tab tab-top10")
    return [html.Div(tab, className="table-defile"), K.lecture(LECTURE_PROVINCES)]


def register(app):
    @app.callback(Output("bes-kpis", "children"), Output("bes-scenarios", "figure"),
                  Output("bes-lecture-scenarios", "children"), Output("bes-carte", "figure"),
                  Output("bes-legende", "children"),
                  Output("bes-normes", "children"), Output("bes-provinces", "children"),
                  Output("bes-erreur", "children"), Output("bes-contenu", "hidden"),
                  Input("bes-scenario", "value"), Input("bes-pop", "value"), Input("bes-nc", "value"),
                  Input("bes-nm", "value"), Input("bes-statut", "value"))
    def maj(scenario, pop, nc, nm, statut):
        nc, nm = int(nc), int(nm)
        try:
            d = donnees()
            d.get()
            # Découpage 2025 lu tout de suite : si ses tables manquent (étape additive du pipeline,
            # `decoupage.DecoupageIndisponible`), cette page de projection affiche le même bloc rouge
            # que pour une base injoignable — jamais une moitié de page sur l'ancien découpage.
            b25 = D25.besoins_province_2025(d, scenario, pop, statut, nc, nm)
            geoms, regions = D25.geoms_provinces_2025(d), D25.geoms_regions_2025(d)
        except Exception:
            # un seul bloc rouge au-dessus : les 4 chiffres, les deux figures et les tableaux
            # disparaissent plutôt que d'afficher trois fois « Données indisponibles »
            v = F.figure_vide("Données indisponibles")
            return (_kpis_squelette(), v, None, v, None, None, None, K.erreur_donnees(), True)
        # Chiffres nationaux : l'ancien découpage, source inchangée de la page (les totaux sont
        # identiques dans les deux découpages, cf. tests/test_decoupage_2025.py).
        b = C.besoins_province(d, scenario, pop, statut, nc, nm)
        el24, el30 = b.eleves_2024_25.sum(), b.eleves_2030.sum()
        sal, ens = b.salles_a_construire_2030.sum(), b.enseignants_supplementaires_2030.sum()
        reouv = b.salles_reouvrables.sum()
        var = 100 * (el30 / el24 - 1) if el24 else None
        secteur = STATUTS_2030.get(statut, statut).lower()
        kp = [K.kpi("Élèves en 2030", fmt_nombre(el30), evolution=html.Span(
                  f"{fmt_signe(var, 0)} % par rapport à 2024-2025", className="tendance t-neutre"),
                  variation=f"{fmt_nombre(el24)} élèves en 2024-2025"),
              K.kpi("Salles à construire", fmt_nombre(sal), evolution=html.Span(
                  f"≈ {fmt_nombre(sal / 6)} par an pendant 6 ans", className="tendance t-neutre"),
                  variation=f"à {nc} élèves par classe",
                  aide_kpi=A.texte(
                      f"Salles qu'il reste à bâtir entre 2025 et 2030 : le besoin de 2030 (élèves de 2030 divisés "
                      f"par {nc}, arrondi au-dessus) moins les salles existantes en 2024-2025 et les salles fermées "
                      f"supposées rouvertes. Calcul fait province par province ({secteur}) : un excédent ne comble "
                      "jamais le manque d'une autre province.",
                      source="projections INSD, annuaires DGESS ; calcul de l'équipe")),
              K.kpi("Enseignants en plus", fmt_nombre(ens), evolution=html.Span(
                  f"≈ {fmt_nombre(ens / 6)} par an pendant 6 ans", className="tendance t-neutre"),
                  variation=f"à {nm} élèves par enseignant",
                  aide_kpi=A.texte(
                      f"Enseignants à recruter entre 2025 et 2030 : le besoin de 2030 (élèves de 2030 divisés par "
                      f"{nm}, arrondi au-dessus) moins les enseignants en poste en 2024-2025. Calcul fait province "
                      f"par province ({secteur}) : un excédent ne comble jamais le manque d'une autre province.",
                      source="projections INSD, annuaires DGESS ; calcul de l'équipe")),
              K.kpi("Salles fermées supposées rouvertes", fmt_nombre(reouv),
                  variation="déduites des salles à construire" if reouv else
                  "aucune réouverture dans ce scénario")]
        sc = C.besoins_par_scenario(d, pop, statut, nc, nm)
        fig_s = F.barres_scenarios(sc, scenario)
        c = sc.set_index("scenario")
        lec = None
        if {"S1_tendanciel", "S3_universel"} <= set(c.index):
            lec = K.lecture(
                f"de {fmt_nombre(c.loc['S1_tendanciel', 'salles_a_construire_2030'])} salles si rien ne change "
                f"(S1) à {fmt_nombre(c.loc['S3_universel', 'salles_a_construire_2030'])} si tous les enfants "
                "vont à l'école (S3). Contour noir : scénario choisi.")
        # Carte, tableau et listes : découpage 2025 (47 provinces, 17 régions). `b25` répartit `b` par
        # la table de passage — ses totaux sont donc exactement ceux des 4 chiffres ci-dessus.
        vals = {r.pcode_province_2025: (r.salles_a_construire_2030, _survol(r)) for r in b25.itertuples()}
        # légende HTML classée (5 cases écrites) plutôt que la barre de couleur de Plotly ; l'unité est
        # portée par le titre de la légende — la répéter dans chaque classe les ferait passer sur deux
        # lignes (le kit fait de même sur la Vue d'ensemble)
        # Bornes calculées **une fois** : cette mesure n'a pas de norme écrite (F.bornes_mesure vaut
        # None), ses classes suivent la distribution affichée — la carte et la légende doivent lire
        # la même liste, sinon la légende décrirait d'autres classes que la carte.
        bornes = F.classes(list(b25.salles_a_construire_2030), bornes_classes=BORNES_CARTE)
        fig_c = F.carte(geoms, vals, TITRE_CARTE, contours_regions=regions, legende=False,
                        bornes_classes=bornes)
        leg = [K.legende_rampe(TITRE_CARTE, F.libelles_classes(bornes, 0)), K.lecture(LECTURE_CARTE)]
        return (kp, fig_s, lec, fig_c, leg, _tables_normes(d, scenario, pop, statut, nc, nm),
                _tableau_provinces(b25.head(10)), "", False)
