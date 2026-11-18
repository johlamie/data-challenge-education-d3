"""Fiche province : identité, chiffres clés et carte de situation (la région en bleu), puis évolution,
besoins 2030 par scénario, composantes du score, crise et accès.

La page compose les blocs du kit (`d3dash/composants.py`) : aucun composant local, aucune couleur
en ligne, aucune icône « i » (les deux seuls chiffres non évidents ouvrent leur infobulle au survol
de la cellule entière).
"""
from dash import Input, Output, dcc, html

from .. import aides as A
from .. import calculs as C
from .. import figures as F
from ..composants import (badge_classe, barre_filtres, entete, erreur_donnees, filtre, grille, kpi, lecture,
                          legende_situation, lien_suite, liste_chiffres, menu, note, panneau, panneau_pied,
                          tendance, vide)
from ..db import donnees
from ..libelles import SCENARIOS_CLAIRS, pluriel as _pluriel
from ..meta import (ANNEE_REF, ANNEES, DECOUPAGE_CONSTAT, SCENARIOS, STATUTS, annee_scolaire, fmt_nombre,
                    fmt_pct, fmt_signe, nom_propre)

COMPOSANTES = {"rang_centile_c1_eleves_par_salle": "Élèves par salle",
               "rang_centile_c2_eleves_par_enseignant": "Élèves par enseignant",
               "rang_centile_c3_besoin_salles_2030": "Salles à construire 2030",
               "rang_centile_c4_salles_perdues_crise": "Salles perdues (crise)",
               "rang_centile_c5_enfants_hors_ecole": "Enfants hors de l'école"}

CENTRAL = "S2_retour_avant_crise"
HAUTEUR_EVOL = 240       # 240 px pour une courbe, 200 px pour des barres
HAUTEUR_COMP = 200


def _options(d):
    p = d["priorite"].sort_values("province")
    return {r.pcode_province: f"{nom_propre(r.province)} ({nom_propre(r.region)})" for r in p.itertuples()}


def layout(pcode=None, annee=None, statut=None, **_):
    try:
        d = donnees()
        d.get()
    except Exception:
        return erreur_donnees()
    opts = _options(d)
    if pcode not in opts:
        pcode = d["priorite"].sort_values("rang_priorite").pcode_province.iloc[0]
    try:
        annee = int(annee) if annee else ANNEE_REF
    except ValueError:
        annee = ANNEE_REF
    annee = annee if annee in ANNEES else ANNEE_REF
    statut = statut if statut in STATUTS else "PUBLIC"
    return html.Div([
        entete("Fiche province",
               "Ce qui manque aujourd'hui dans une province, et ce qu'il faudra y construire d'ici 2030.",
               decoupage=DECOUPAGE_CONSTAT),
        # Filtres **sans cadre** : les champs portent déjà leur filet, un panneau autour coûterait
        # 26 px de hauteur et éloignerait les menus du titre.
        barre_filtres(
            filtre("Province", menu("fic-province", opts, pcode, searchable=True), cls="filtre-large"),
            filtre("Année scolaire", menu("fic-annee", {a: annee_scolaire(a) for a in ANNEES[::-1]}, annee),
                   cls="filtre-moyen"),
            filtre("Secteur", menu("fic-statut", STATUTS, statut), cls="filtre-moyen"),
        ),
        html.Div([
            panneau(None,
                    html.Div(id="fic-identite", className="fiche-identite"),
                    html.Div(id="fic-kpis", className="fiche-kpis")),
            panneau("Situation",
                    html.Div(dcc.Graph(id="fic-carte", config=F.CONFIG_CARTE, responsive=True,
                                       style={"width": "100%", "height": "100%"}),
                             className="zone-carte"),
                    # une seule ligne : chaque ligne de plus ici allonge le panneau « Situation »
                    # et ouvre un blanc en face, dans la première rangée. La légende à pastilles
                    # juste au-dessus dit déjà « province » et « sa région ».
                    lecture("province en bleu foncé, sa région en bleu clair."),
                    note_=legende_situation()),
        ], className="fiche-haut"),
        grille(
            panneau(None,
                    html.Div(id="fic-titre-evol", className="panneau-tete"),
                    dcc.Graph(id="fic-evol", config=F.CONFIG, responsive=True,
                              style={"height": f"{HAUTEUR_EVOL}px", "width": "100%"}),
                    html.Div(id="fic-lecture-evol")),
            panneau("Pourquoi cette priorité ?",
                    dcc.Graph(id="fic-composantes", config=F.CONFIG, responsive=True,
                              style={"height": f"{HAUTEUR_COMP}px", "width": "100%"}),
                    html.Div(id="fic-robustesse")),
        ),
        grille(
            panneau("Besoins en 2030 selon le scénario", html.Div(id="fic-2030"), note_="public + privé"),
            panneau("Crise et accès à l'école", html.Div(id="fic-crise")),
        ),
    ], className="pile p-fiche")


def _identite(r, pa):
    """En-tête de fiche : nom, région (et découpage 2025 si la province a été redécoupée), puis
    la classe de priorité, le rang et le score.

    La clause « découpage 2025 » n'apparaît que si un nom a **changé** : la répéter à l'identique
    donnait « Région Region Fictive 02 · découpage 2025 : province Province Fictive 05, région
    Region Fictive 02 », trois fois la même information. Aucun calcul nouveau, même donnée lue.
    """
    region = f"Région {nom_propre(r['region'])}"
    if pa is not None and isinstance(pa.get("province_nouvelle"), str):
        nouvelle_p, nouvelle_r = pa["province_nouvelle"], pa["region_nouvelle"]
        change = (str(nouvelle_p).strip().casefold() != str(r["province"]).strip().casefold()
                  or str(nouvelle_r).strip().casefold() != str(r["region"]).strip().casefold())
        if change:
            region += (f" · découpage 2025 : province {nom_propre(nouvelle_p)}, "
                       f"région {nom_propre(nouvelle_r)}")
    return [html.H2(nom_propre(r["province"])),
            html.P(region, className="f-region"),
            html.P([badge_classe(r["classe_priorite"]),
                    html.Span(f"rang {int(r['rang_priorite'])} sur 45 · "
                              f"score {fmt_nombre(r['score_priorite'])} / 100")],
                   className="f-rang")]


def _kpis(d, pcode, annee, statut):
    """4 chiffres clés de l'année choisie. Infobulle (sans icône) sur les deux seuls libellés qui ne
    se comprennent pas seuls : les manques d'enseignants et de salles — au périmètre de la
    province, jamais le texte national « somme, province par province… »."""
    pa = d["province_annee"]
    cur = pa[(pa.pcode_province == pcode) & (pa.statut == statut) & (pa.annee_debut == annee)]
    prev = pa[(pa.pcode_province == pcode) & (pa.statut == statut) & (pa.annee_debut == annee - 1)]
    r = cur.iloc[0] if len(cur) else None
    p = prev.iloc[0] if len(prev) else None

    def dlt(c):
        if r is None or p is None or r[c] != r[c] or p[c] != p[c]:
            return None
        return float(r[c]) - float(p[c])

    def v(c):
        return None if r is None else r[c]
    epm, eps = v("eleves_par_maitre"), v("eleves_par_salle")
    return r, [
        kpi("Élèves par maître", fmt_nombre(epm, 1),
            evolution=tendance(dlt("eleves_par_maitre"), f"{fmt_signe(dlt('eleves_par_maitre'), 1)} en un an"),
            variation="norme : 50"),
        kpi("Élèves par salle", fmt_nombre(eps, 1),
            evolution=tendance(dlt("eleves_par_salle"), f"{fmt_signe(dlt('eleves_par_salle'), 1)} en un an"),
            variation="norme : 50"),
        # l'infobulle suit le **secteur choisi** : devant un chiffre « public + privé », elle ne
        # peut pas dire « dans le public »
        kpi("Enseignants manquants", fmt_nombre(v("deficit_enseignants")) if statut != "PRIVE" else "n.d.",
            evolution=tendance(dlt("deficit_enseignants"), f"{fmt_signe(dlt('deficit_enseignants'))} en un an"),
            variation=f"excédent : {fmt_nombre(v('excedent_enseignants'))}",
            aide_kpi=A.deficit_ens_province(statut)),
        kpi("Salles manquantes", fmt_nombre(v("deficit_salles")),
            evolution=tendance(dlt("deficit_salles"), f"{fmt_signe(dlt('deficit_salles'))} en un an"),
            variation=f"{fmt_nombre(v('salles_classe'))} salles, {fmt_nombre(v('eleves'))} élèves",
            aide_kpi=A.deficit_salles_province(statut)),
    ]


def _table_2030(d, pcode):
    """Tableau des 4 scénarios (toujours public + privé, comme le dit la note du panneau).
    Si la province n'a pas de scénario calculé, le bloc affiche l'état vide du kit."""
    p = d["province_2030"]
    s = p[(p.pcode_province == pcode) & (p.statut == "TOTAL") & (p.variante_population == "moyen")]
    s = s.set_index("scenario").reindex(list(SCENARIOS)).reset_index()
    if not len(s) or s["eleves_2030"].isna().all():
        return vide("Les scénarios 2030 ne sont pas calculés pour cette province.",
                    "Choisissez une autre province, ou ouvrez « Besoins 2030 » pour les chiffres du pays.")
    tete = html.Thead(html.Tr([html.Th("Scénario", scope="col"),
                               html.Th("Élèves 2030", className="c-num", scope="col"),
                               html.Th("Salles à construire", className="c-num", scope="col"),
                               html.Th("Enseignants en plus", className="c-num", scope="col")]))
    corps = [html.Tr([html.Td(SCENARIOS_CLAIRS.get(r.scenario, SCENARIOS.get(r.scenario, r.scenario))),
                      html.Td(fmt_nombre(r.eleves_2030), className="c-num"),
                      html.Td(fmt_nombre(r.salles_a_construire_2030), className="c-num"),
                      html.Td(fmt_nombre(r.enseignants_supplementaires_2030), className="c-num")],
                     className="ligne-centrale" if r.scenario == CENTRAL else None)
             for r in s.itertuples()]
    c = s[s.scenario == CENTRAL]
    lec = None
    if len(c):
        c = c.iloc[0]
        lec = lecture(f"dans le scénario central, la province passerait de {fmt_nombre(c.eleves_2024_25)} à "
                      f"{fmt_nombre(c.eleves_2030)} élèves (public et privé) ; il faudrait construire "
                      f"{fmt_nombre(c.salles_a_construire_2030)} salles, soit ≈ {fmt_nombre(c.salles_a_construire_2030 / 6)} "
                      "par an, à 50 élèves par classe.")
    return [html.Div(html.Table([html.Caption("Besoins en 2030 selon le scénario, public et privé",
                                              className="sr-only"), tete, html.Tbody(corps)], className="tab"),
                     className="table-defile"), lec]


def _crise(d, pcode, r):
    cr = d["crise"]
    cr = cr[cr.pcode_province == pcode]
    s = d["implantation"]
    s = s[s.pcode_province == pcode]
    fiables = int((s.sites_fiables == 1).sum())
    items = []
    if len(cr):
        c = cr.iloc[0]
        items += [("Écoles fermées (mai 2022)", fmt_nombre(c.fermees_2022_05)),
                  ("Salles perdues depuis 2017-2021", f"{fmt_nombre(max(0, c.salles_max_2017_2021 - c.salles_2024_25))}"
                                                      f" ({fmt_pct(max(0, c.part_salles_perdues), 0)})"),
                  ("Élèves déplacés internes (févr. 2026)", fmt_nombre(c.edi_primaire_total_2026_02))]
    items += [("Enfants à plus de 3 km d'une école", fmt_pct(r["acces_part_hors_3km"], 0)),
              ("Fiabilité de la carte des écoles", str(r["fiabilite_osm_province"] or "n.d.").capitalize()),
              ("Sites d'école proposés", f"{len(s)} dont {fiables} {_pluriel(fiables, 'fiable')}")]
    return [liste_chiffres(items),
            panneau_pied(lien_suite("Voir les sites proposés", f"/implantation?pcode={pcode}"),
                         note(f"{fiables} {_pluriel(fiables, 'site')} {_pluriel(fiables, 'fiable')}"))]


def register(app):
    @app.callback(Output("fic-identite", "children"), Output("fic-kpis", "children"), Output("fic-carte", "figure"),
                  Output("fic-titre-evol", "children"), Output("fic-evol", "figure"),
                  Output("fic-lecture-evol", "children"), Output("fic-composantes", "figure"),
                  Output("fic-robustesse", "children"), Output("fic-2030", "children"), Output("fic-crise", "children"),
                  Input("fic-province", "value"), Input("fic-annee", "value"), Input("fic-statut", "value"))
    def maj(pcode, annee, statut):
        try:
            d = donnees()
            d.get()
        except Exception:
            e = erreur_donnees()
            v = F.figure_vide("Données indisponibles")
            return e, None, v, "", v, None, v, None, None, None
        pr = d["priorite"]
        r = pr[pr.pcode_province == pcode].iloc[0]
        pa_row, kp = _kpis(d, pcode, annee, statut)
        carte = F.carte_localisation(C.geoms_provinces(d), pcode, r["code_region"], d["geo_region"])
        pa = d["province_annee"]
        ev = pa[(pa.pcode_province == pcode) & (pa.statut == statut)].sort_values("annee_debut")
        fig = F.evolution(ev, {"eleves_par_maitre": "Élèves par maître", "eleves_par_salle": "Élèves par salle"},
                          norme=50, hauteur=HAUTEUR_EVOL)
        lec = None
        if len(ev) >= 2:
            a, b = ev.iloc[0], ev.iloc[-1]
            lec = lecture(f"de {a.annee_scolaire} à {b.annee_scolaire}, le nombre d'élèves par maître est passé de "
                          f"{fmt_nombre(a.eleves_par_maitre, 1)} à {fmt_nombre(b.eleves_par_maitre, 1)} "
                          f"({STATUTS[statut].lower()}).")
        comp = [(lib, 100 * float(r[c])) for c, lib in COMPOSANTES.items() if r[c] == r[c]]
        # piste claire de 0 à 100 derrière chaque barre et valeurs alignées à droite ;
        # les libellés gardent leur air avant la piste
        fig_c = F.barres_h([x[0] for x in comp], [x[1] for x in comp], hauteur=HAUTEUR_COMP, marge_g=170,
                           piste=100,
                           survol=[f"{lib} : plus élevé que {v:.0f} % des provinces" for lib, v in comp])
        rob = lecture(f"chaque barre situe la province parmi les 45 (100 = la plus en difficulté). Avec 5 000 "
                      f"pondérations tirées au hasard, son rang varie de {fmt_nombre(r['rang_p05_mc'])} à "
                      f"{fmt_nombre(r['rang_p95_mc'])} ; elle est dans le top 10 dans "
                      f"{fmt_pct(r['freq_top10_mc'], 0, fraction=True)} des cas.")
        tete_evol = [html.H2(f"Évolution de {annee_scolaire(ANNEES[0])} à {annee_scolaire(ANNEES[-1])}"),
                     note(f"primaire {STATUTS[statut].lower()}")]
        return (_identite(r, pa_row), kp, carte, tete_evol, fig, lec, fig_c, rob,
                _table_2030(d, pcode), _crise(d, pcode, r))
