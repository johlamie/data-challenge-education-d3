"""Page de démonstration du kit (`/_kit`, mode données fictives uniquement).

Tous les blocs du kit avec leurs états (plein, chargement, obsolète, erreur, vide)
sur les données de démonstration — y compris les pires cas : nom le plus long, rang ex æquo, valeur à
six chiffres, comparaison absente, valeur non disponible. Aucune page métier n'en dépend.
"""
from dash import Input, Output, dash_table, dcc, html

from .. import aides as A
from .. import calculs as C
from .. import composants as K
from .. import figures as F
from ..db import donnees
from ..meta import DECOUPAGE_2025, DECOUPAGE_CONSTAT, fmt_nombre
from .classement import STYLE_CELLULE, STYLE_ENTETE

MESURES_CARTE = {"score_priorite": "Score de priorité", "eleves_par_maitre": "Élèves par maître",
                 "salles_a_construire_2030": "Salles à construire 2030"}
NORMES_CARTE = {"eleves_par_maitre": 50}
TITRES = {"score_priorite": "Score de priorité (0 à 100)",
          "eleves_par_maitre": "Élèves par maître, public 2024-2025 — norme : 50",
          "salles_a_construire_2030": "Salles à construire d'ici 2030 (scénario central)"}


def _dec(mesure):
    return 1 if mesure == "eleves_par_maitre" else 0


def _bornes(d, mesure):
    """Les 4 bornes, calculées **une fois** pour la carte et pour la légende (même règle que
    `accueil.bornes_carte`) : deux chemins de code donneraient deux légendes possibles."""
    return F.classes(list(C.classement(d, mesure)[mesure]), norme=NORMES_CARTE.get(mesure),
                     bornes_classes=F.bornes_mesure(mesure), dec=_dec(mesure))


def _figure(d, mesure):
    t = C.classement(d, mesure)
    top = C.classement(d, "score_priorite").head(10)
    rangs = {r.pcode_province: int(r.rang) for r in top.itertuples()}
    vals = {r["pcode_province"]: (r[mesure], C.survol_province(r, mesure)) for _, r in t.iterrows()}
    return F.carte(C.geoms_provinces(d), vals, TITRES[mesure], gras=set(rangs), rangs=rangs,
                   selection=top.pcode_province.iloc[0], contours_regions=d["geo_region"],
                   legende=False, bornes_classes=_bornes(d, mesure),
                   fmt=".1f" if mesure == "eleves_par_maitre" else ".0f")


def _legende(d, mesure):
    return K.legende_rampe(TITRES[mesure], F.libelles_classes(_bornes(d, mesure), _dec(mesure)))


def _tableau_top(d, n=10):
    t = C.classement(d, "score_priorite").head(n)
    lignes = []
    for i, (_, r) in enumerate(t.iterrows()):
        lignes.append(html.Tr([
            html.Td(int(r["rang"]), className="c-rang"),
            html.Td([dcc.Link(r["province_nom"], href=f"/fiche?pcode={r['pcode_province']}"),
                     html.Span(r["region_nom"], className="reg-ligne", title=r["region_nom"])],
                    className="c-prov"),
            html.Td(K.barre_score(r["score_priorite"], fmt_nombre(r["score_priorite"])), className="c-num"),
            html.Td(K.badge_classe(r["classe_priorite"], court=True), className="c-stat"),
        ], className="ligne-sel" if i == 0 else None, **({"aria-current": "true"} if i == 0 else {})))
    tete = html.Thead(html.Tr([
        html.Th("#", className="c-rang", scope="col"), html.Th("Province", scope="col"),
        html.Th(["Score", K.aide(A.SCORE, "Score de priorité")], className="c-num", scope="col"),
        html.Th("Priorité", className="c-stat", scope="col")]))
    return html.Table([html.Caption("Les 10 provinces les plus prioritaires sur 45", className="sr-only"),
                       tete, html.Tbody(lignes)], className="tab tab-top10")


def _kpis(d):
    k = C.kpis(d)
    return [
        K.kpi("Élèves par maître", fmt_nombre(k["epm"], 1),
              evolution=K.tendance(k["epm_delta"], f"+{fmt_nombre(k['epm_delta'], 1)} en un an"),
              variation="norme : 50"),
        # chaque ligne tient sur une ligne : « comparaison absente » se dit en deux mots
        K.kpi("Élèves par salle", fmt_nombre(k["eps"], 1), variation="norme : 50 · sans comparaison"),
        K.kpi("Enseignants manquants", fmt_nombre(k["def_ens"]),
              evolution=K.tendance(k["def_ens_delta"], f"+{fmt_nombre(k['def_ens_delta'])} en un an"),
              variation=f"dont {fmt_nombre(k['redeployables'])} redéployables", aide_kpi=A.KPI_DEFICIT_ENS),
        K.kpi("Salles manquantes", fmt_nombre(k["def_salles"]),
              variation=f"dans {k['prov_def_salles']} provinces sur 45", aide_kpi=A.KPI_DEFICIT_SALLES),
        K.kpi("Salles à construire 2030", fmt_nombre(k["s2030"]),
              evolution=html.Span(f"≈ {fmt_nombre((k['s2030'] or 0) / 6)} par an d'ici 2030",
                                  className="tendance t-neutre"),
              variation=f"+ {fmt_nombre(k['e2030'])} enseignants", aide_kpi=A.KPI_2030),
        K.kpi("Taux de scolarisation", fmt_nombre(k["tbs"], 1) + " %",
              evolution=K.tendance(k["tbs_delta"], f"+{fmt_nombre(k['tbs_delta'], 1)} pt en un an",
                                   mauvais_si_hausse=False),
              variation=f"{fmt_nombre(k['tbs_2017'], 1)} % en 2017-2018", aide_kpi=A.KPI_TBS),
    ]


# ---- pires données -------------------------------------------------------------------------------------------
# Contenu hostile **passé directement aux composants** : le jeu de démonstration n'est pas touché
# (ses chiffres sont figés par contrat), mais chaque bloc doit tenir avec ces valeurs-là.
NOM_LONG = "Province Fictive de la Boucle du Mouhoun Septentrionale"     # 54 caractères
REGION_LONGUE = "Région Fictive des Hauts-Bassins et des Cascades réunies"  # 56 caractères
COURRIEL_LONG = "direction.provinciale.education@province-fictive-septentrionale.bf"
CONTEXTE_LONG = ("norme : 50 élèves par enseignant · dont 3 954 couverts en déplaçant des enseignants "
                 "d'autres provinces · au plus haut depuis l'année scolaire 2017-2018")


def _ligne_pire(rang, nom, region, score, classe):
    return html.Tr([
        html.Td(rang, className="c-rang"),
        html.Td([dcc.Link(nom, href="/fiche"), html.Span(region, className="reg-ligne", title=region)],
                className="c-prov"),
        html.Td(K.barre_score(score, fmt_nombre(score)), className="c-num"),
        html.Td(K.badge_classe(classe, court=True), className="c-stat"),
    ])


def _tableau_pire():
    """Tableau top 10 avec les pires données : nom et région de plus de 45 caractères, rang
    ex æquo, score 0 et score 100. Le nom passe à la ligne, la région se tronque avec son `title`,
    le nombre ne se coupe jamais."""
    return html.Table([
        html.Caption("Pires données : noms longs, rang ex æquo, valeurs extrêmes", className="sr-only"),
        html.Thead(html.Tr([html.Th("#", className="c-rang", scope="col"), html.Th("Province", scope="col"),
                            html.Th("Score", className="c-num", scope="col"),
                            html.Th("Priorité", className="c-stat", scope="col")])),
        html.Tbody([_ligne_pire(9, NOM_LONG, REGION_LONGUE, 100, "P1 priorite robuste"),
                    _ligne_pire(9, "Province Fictive 05", REGION_LONGUE, 0, "P3 a surveiller"),
                    _ligne_pire(11, NOM_LONG, "Région Fictive 02", 1, "P2 priorite probable")]),
    ], className="tab tab-top10")


def _datatable_pire():
    """Même `DataTable` que les écrans Classement et Implantation, avec des noms de 54 caractères :
    à 390 px, les trois premières colonnes restent lisibles et le tableau défile dans son bloc."""
    return dash_table.DataTable(
        id="kit-pire-table", sort_action="native", page_action="none", fixed_rows={"headers": True},
        columns=[{"name": "Rang", "id": "rang", "type": "numeric"},
                 {"name": "Province", "id": "province"},
                 {"name": "Score", "id": "score", "type": "numeric"},
                 {"name": "Région", "id": "region"}],
        data=[{"rang": 9, "province": NOM_LONG, "score": 100, "region": REGION_LONGUE},
              {"rang": 9, "province": "Province Fictive 05", "score": 0, "region": REGION_LONGUE},
              {"rang": 11, "province": NOM_LONG, "score": None, "region": "Région Fictive 02"}],
        style_table={"overflowX": "auto"}, style_cell=STYLE_CELLULE, style_header=STYLE_ENTETE,
        style_cell_conditional=[{"if": {"column_id": "rang"}, "width": "56px", "minWidth": "56px",
                                 "textAlign": "right"},
                                {"if": {"column_id": "province"}, "width": "170px", "minWidth": "170px",
                                 "whiteSpace": "normal", "lineHeight": "1.25"},
                                {"if": {"column_id": "score"}, "width": "72px", "minWidth": "72px",
                                 "textAlign": "right"},
                                {"if": {"column_id": "region"}, "width": "120px", "minWidth": "120px",
                                 "whiteSpace": "normal", "lineHeight": "1.25"}])


def _nouveautes():
    """Mention de découpage, barre de filtres sans cadre, ligne « anciennement », outils de carte
    et bloc équipe, chacun avec son pire cas. Les pages les composent, elles n'en inventent aucun."""
    return html.Div([
        # Les deux mentions sont montrées **à la largeur d'un en-tête de page**, le seul endroit
        # où elles vivent : dans un panneau, la plus longue dépasserait son bloc à 390 px.
        html.Div([K.note("Mentions de découpage :"),
                  K.mention_decoupage(DECOUPAGE_CONSTAT), K.mention_decoupage(DECOUPAGE_2025)],
                 className="tete-droite"),
        K.panneau(
            "13 · Mention de découpage, filtres, « anciennement », outils de carte, équipe",
            K.texte("Les deux seules mentions de découpage du site (ci-dessus, à la largeur d'un "
                    "en-tête de page), la barre de filtres sans cadre dont l'action est sur la même "
                    "ligne alignée à droite, la seconde ligne du nom d'une province renommée, les "
                    "trois boutons de la carte d'implantation et le bloc de l'équipe. Pire cas : le "
                    "plus long nom d'avant 2025 et une barre de trois filtres dont une valeur de "
                    "54 caractères."),
            K.barre_filtres(
                K.filtre("Province", K.menu("kit-bf-province", {"a": f"{NOM_LONG} ({REGION_LONGUE})",
                                                                "b": "Province Fictive 05"}, "a"),
                         cls="filtre-large"),
                K.filtre("Année scolaire", K.menu("kit-bf-annee", {"2024": "2024-2025"}, "2024"),
                         cls="filtre-moyen"),
                K.filtre("Sites", K.menu("kit-bf-sites", {"tous": "Tous les sites",
                                                          "fiables": "Sites fiables seulement"}, "tous"),
                         cls="filtre-moyen"),
                action=K.bouton("Exporter en CSV", id_="kit-bf-export")),
            html.Div([
                K.panneau("Nom de province renommée",
                          html.Table([html.Tbody([
                              html.Tr([html.Td([dcc.Link(NOM_LONG, href="/fiche"), K.anciennement(NOM_LONG),
                                                html.Span(REGION_LONGUE, className="reg-ligne",
                                                          title=REGION_LONGUE)], className="c-prov"),
                                       html.Td(fmt_nombre(1234567), className="c-num")]),
                              html.Tr([html.Td([dcc.Link("Province Fictive 05", href="/fiche"),
                                                html.Span("Région Fictive 02", className="reg-ligne")],
                                               className="c-prov"),
                                       html.Td(fmt_nombre(0), className="c-num")]),
                          ])], className="tab tab-top10"),
                          K.lecture("la ligne « anciennement » n'apparaît que si le nom a changé ; "
                                    "elle passe à la ligne, elle n'est jamais tronquée.")),
                # même composition que le bloc carte de l'Implantation : titre à gauche, outils à droite
                K.panneau(None,
                          html.Div([html.Div(html.H2("Sites candidats et communes"),
                                             className="panneau-tete"),
                                    K.outils_carte("kit-zoom-plus", "kit-zoom-moins", "kit-recadrer")],
                                   className="carte-outils"),
                          K.lecture("trois verbes à l'infinitif, aucune icône : ils sont le chemin "
                                    "clavier du zoom que la molette et le pincement font aussi.")),
            ], className="pile"),
            K.panneau("L'équipe",
                      # mêmes cases que « À propos et méthode » : deux membres de même poids
                      K.grille_equipe(
                          K.membre_equipe("Melissa Bénéwendé Sougrinoma Djelika OUEDRAOGO",
                                          "Data analyst et data engineer",
                                          bio="Ingénieure de l'eau et des aménagements "
                                              "hydro-agricoles, Institut 2iE.",
                                          photo="equipe/melissa.jpg"),
                          K.membre_equipe("John Lamien", "Architecte et data scientist",
                                          bio="Ingénieur en intelligence artificielle, gérant "
                                              "d'Unica Labs, société de conseil informatique et de "
                                              "solutions d'ingénierie.",
                                          photo="equipe/john.jpg")),
                      K.lecture("portrait rond de 72 px (64 px sous 621 px), puis le nom, le rôle et "
                                "une ligne. Sans fichier de portrait, la case se rend sans image, "
                                "jamais avec une initiale ou un avatar ; un nom long passe à la "
                                "ligne, il n'est jamais tronqué.")),
        ),
    ], className="pile")


def _pires_donnees():
    return K.panneau(
        "12 · Pires données",
        K.texte("Les blocs ci-dessous reçoivent le contenu le plus hostile prévu par "
                "« design/components.md » : un nom de province et une région de plus de 45 caractères, "
                "un rang ex æquo, une valeur manquante, un zéro, un nombre à sept chiffres, une "
                "évolution négative, une ligne de contexte très longue et une adresse insécable."),
        K.bande_kpi([
            # Une ligne de contexte plus longue que sa cellule est coupée : elle porte alors son
            # texte entier en infobulle de titre — une métadonnée tronquée garde toujours un moyen
            # d'être lue.
            K.kpi("Élèves déplacés internes", fmt_nombre(1234567),
                  variation=html.Span(CONTEXTE_LONG, title=CONTEXTE_LONG),
                  evolution=K.tendance(12345, "+12 345 en un an")),
            K.kpi("Enseignants manquants", "n.d.",
                  variation=html.Span("comparaison absente : aucune ligne n'est rendue",
                                      title="comparaison absente : aucune ligne n'est rendue")),
            K.kpi("Salles manquantes", fmt_nombre(0),
                  evolution=K.tendance(-1234, "−1 234 en un an"), variation="aucune salle ne manque ici"),
            K.kpi("Taux de scolarisation", fmt_nombre(100.0, 1) + " %",
                  evolution=K.tendance(0, "stable en un an"), variation="norme : 100 %"),
        ], colonnes=4),
        html.Div([
            K.panneau("Tableau statique", _tableau_pire(),
                      K.lecture("le nom passe à la ligne, la région se tronque avec son infobulle de "
                                "titre, le nombre ne se coupe jamais.")),
            K.panneau("Tableau de données", html.Div(_datatable_pire(), className="zone-liste"),
                      K.lecture("à 390 px, Rang, Province et Score tiennent dans le bloc ; le reste défile "
                                "dans le bloc, jamais la page.")),
        ], className="pile"),
        html.Div([
            K.filtre("Province (valeur longue)",
                     K.menu("kit-pire-province", {"a": f"{NOM_LONG} ({REGION_LONGUE})",
                                                  "b": "Province Fictive 05 (Région Fictive 02)"}, "a"),
                     cls="filtre-large"),
            K.filtre("Scénario (valeur longue)",
                     K.menu_natif("kit-pire-scenario",
                                  {"s2": "Retour au taux d'avant-crise (S2, central)",
                                   "s1": "Si rien ne change (S1)"}, "s2"), cls="filtre-moyen"),
        ], className="filtres"),
        K.liste_chiffres([
            ("Fiabilité de la carte des écoles dans cette province et ses communes voisines", "n.d."),
            ("Courriel de la direction provinciale", html.Span(COURRIEL_LONG, className="valeur-insecable")),
            ("Élèves déplacés internes (février 2026)", fmt_nombre(1234567)),
            ("Sites d'école proposés", "0"),
        ]),
        K.legende_rampe("Enfants de 6-11 ans habitant à plus de 3 km d'une école (en %)",
                        F.libelles_classes([20, 40, 60, 80], 0, "%"), colonne=True),
        K.lecture("aucun nombre n'est tronqué, aucun bloc ne déborde : un nom long passe à la ligne, "
                  "une adresse insécable est coupée au besoin, une valeur absente s'écrit « n.d. »."))


def layout(**_):
    try:
        d = donnees()
        d.get()
    except Exception:
        return K.erreur_donnees()
    p = C.classement(d, "score_priorite")
    premiere = p.iloc[0]
    k = C.kpis(d)
    ev = d["province_annee"]
    ev = ev[(ev.pcode_province == premiere["pcode_province"]) & (ev.statut == "PUBLIC")].sort_values("annee_debut")
    comp = [("Élèves par salle", 82), ("Élèves par enseignant", 98), ("Salles à construire 2030", 100),
            ("Salles perdues (crise)", 62), ("Enfants hors de l'école", 84)]
    return html.Div([
        K.entete("Kit d'interface", "Page de démonstration · mode données fictives · tous les blocs et leurs états"),
        K.constat("Le primaire public compte ", K.chiffre(f"{fmt_nombre(k['epm'], 1)} élèves par maître"),
                  " pour une norme de 50. Il manque ", K.chiffre(f"{fmt_nombre(k['def_ens'])} enseignants"),
                  " et ", K.chiffre(f"{fmt_nombre(k['def_salles'])} salles de classe"), "."),

        K.panneau("1 · Bande de chiffres", K.bande_kpi(_kpis(d)),
                  K.lecture("une seule surface découpée en cellules ; les 4 cellules soulignées ouvrent une "
                            "infobulle au survol, au toucher et au clavier, sans icône.")),

        K.rangee(
            K.panneau(None, html.Div([
                html.Div([html.H2("2 · Bloc carte"), K.note("45 provinces")], className="panneau-tete"),
                K.controle_segmente("kit-mesure", MESURES_CARTE, "score_priorite",
                                    "Mesure affichée sur la carte"),
            ], className="carte-outils"),
                html.Div(dcc.Graph(id="kit-carte", config=F.CONFIG_CARTE, responsive=True,
                                   style={"height": "100%", "width": "100%"}), className="zone-carte"),
                html.Div(_legende(d, "score_priorite"), id="kit-legende"),
                K.lecture(html.Span([
                    "plus la province est foncée, plus elle cumule de retard. Contour noir et numéro : les 10 "
                    "provinces prioritaires. Anneau bleu : la province choisie. Traits gris : limites de région."]),
                    id="kit-lecture"),
                cls="bloc-carte"),
            K.panneau("3 · Bloc liste", _tableau_top(d), note_="10 sur 45",
                      pied=K.panneau_pied(K.lien_suite("Classement complet des 45 provinces", "/classement"),
                                          K.note("rang 9 ex æquo"))),
        ),

        K.grille(
            K.panneau("4 · Bloc graphique",
                      html.P([html.Span([html.Span(className="trait"), "Élèves par maître"]),
                              html.Span([html.Span(className="trait trait-2"), "Élèves par salle"])],
                             className="legende-serie"),
                      dcc.Graph(figure=F.evolution(ev, {"eleves_par_maitre": "Élèves par maître",
                                                        "eleves_par_salle": "Élèves par salle"},
                                                   norme=50, hauteur=240, legende=False),
                                config=F.CONFIG, style={"height": "240px", "width": "100%"}, responsive=True),
                      K.lecture("la norme de 50 n'a jamais été atteinte sur la période."),
                      note_="primaire public"),
            K.panneau("5 · Barres de composantes",
                      K.barres_composantes(comp),
                      K.lecture("chaque barre situe la province parmi les 45 (100 = la plus en difficulté).")),
        ),

        K.grille(
            K.panneau("6 · Carte de situation",
                      # la zone du kit porte le format réel du pays : la figure la remplit
                      html.Div(dcc.Graph(figure=F.carte_localisation(C.geoms_provinces(d),
                                                                     premiere["pcode_province"],
                                                                     premiere["code_region"], d["geo_region"]),
                                         config=F.CONFIG_CARTE, responsive=True,
                                         style={"height": "100%", "width": "100%"}),
                               className="zone-carte"),
                      K.lecture("la province choisie est en bleu foncé, les autres provinces de sa région en "
                                "bleu clair."),
                      note_=K.legende_situation()),
            K.panneau("7 · Liste clé-valeur",
                      K.liste_chiffres([("Écoles fermées (mai 2022)", "15"),
                                        ("Salles perdues depuis 2017-2021", "18 (1 %)"),
                                        ("Élèves déplacés internes", "70 568"),
                                        ("Enfants à plus de 3 km d'une école", "76 %"),
                                        ("Fiabilité de la carte des écoles", "n.d."),
                                        ("Sites d'école proposés", "7 dont 6 fiables")]),
                      K.lecture("une valeur absente s'écrit « n.d. », jamais « 0 ».")),
            inverse=True),

        K.panneau("8 · Contrôles",
                  html.Div([
                      K.filtre("Province", K.menu("kit-province", {"a": "Province Fictive 05 (Region Fictive 02)",
                                                                   "b": "Province Fictive 37 (Region Fictive 11)"},
                                                  "a"), cls="filtre-large"),
                      K.filtre("Année scolaire", K.menu("kit-annee", {"2024": "2024-2025", "2023": "2023-2024"},
                                                        "2024"), cls="filtre-moyen"),
                      K.filtre("Secteur (désactivé)", K.menu("kit-statut", {"PUBLIC": "Public"}, "PUBLIC",
                                                             disabled=True), cls="filtre-moyen"),
                      K.filtre("Élèves par classe", K.menu_natif("kit-norme", {"50": "50 (norme)", "60": "60"},
                                                                 "50"), A.NORMES, cls="filtre-moyen"),
                  ], className="filtres"),
                  html.Div([K.bouton("Exporter en CSV"), K.bouton("Réessayer", plein=True),
                            K.lien_suite("Voir les sites proposés", "/implantation"),
                            html.Span([K.badge_classe("P1 priorite robuste"), " ",
                                       K.badge_classe("P2 priorite probable"), " ",
                                       K.badge_classe("P3 a surveiller")])],
                           className="ligne-outils"),
                  K.lecture("une seule action pleine par zone ; les libellés sont à l'infinitif.")),

        K.panneau("9 · États",
                  K.bande_obsolete("14 h 05", "12 novembre 2025 à 09 h 30"),
                  html.Div([
                      K.vide("Aucune province ne correspond à ce filtre.",
                             "Effacez les filtres pour revoir les 45 provinces."),
                      K.erreur_donnees("12 novembre 2025 à 09 h 30"),
                      K.page_introuvable(),
                  ], className="pile"),
                  K.lecture("un état obsolète n'est jamais rendu comme un état frais ; une adresse inconnue "
                            "n'est pas une panne de données.")),

        K.panneau("10 · Chargement",
                  K.bande_kpi([K.kpi("Élèves par maître", K.valeur_sk(fmt_nombre(k["epm"], 1)),
                                     variation=K.valeur_sk("norme : 50")),
                               K.kpi("Salles manquantes", K.valeur_sk(fmt_nombre(k["def_salles"])),
                                     variation=K.valeur_sk("dans 25 provinces sur 45")),
                               K.kpi("Salles à construire 2030", K.valeur_sk(fmt_nombre(k["s2030"])),
                                     variation=K.valeur_sk("+ enseignants")),
                               K.kpi("Taux de scolarisation", K.valeur_sk(fmt_nombre(k["tbs"], 1) + " %"),
                                     variation=K.valeur_sk("72,7 % en 2017-2018"))], colonnes=4),
                  # état de chargement d'une carte : l'aplat occupe la zone, qui garde le format 1000/733
                  K.zone_squelette(cls="zone-carte"),
                  K.lecture("aplat uni, sans dégradé ni animation ; la géométrie finale est conservée et les "
                            "libellés restent lisibles.")),

        K.panneau("11 · Bloc de texte, liste et note de limite",
                  K.texte("Le corps de texte de l'écran « À propos et méthode » : mesure de ligne de "
                          "72 caractères, 13 px, interligne 1,5, et 8 px entre deux blocs."),
                  K.liste(["Un élément de liste, aligné sur la même mesure que le texte.",
                           "Le rythme intérieur d'une liste est de 4 px entre deux éléments.",
                           "Aucune puce décorative, aucune icône : c'est du texte."]),
                  K.note_limite("Note de limite : bloc encadré neutre (fond gris doux, filet 1 px), sans "
                                "barre latérale et sans couleur de statut — une limite de méthode n'est ni "
                                "une alerte ni une panne."),
                  K.lecture("le seul écran de texte du site compose ces trois blocs ; aucune page n'écrit "
                            "sa propre mise en forme de texte.")),

        _pires_donnees(),
        _nouveautes(),
    ], className="pile")


def register(app):
    @app.callback(Output("kit-carte", "figure"), Output("kit-legende", "children"),
                  Input("kit-mesure", "value"))
    def maj(mesure):
        d = donnees()
        mesure = mesure if mesure in MESURES_CARTE else "score_priorite"
        return _figure(d, mesure), _legende(d, mesure)
