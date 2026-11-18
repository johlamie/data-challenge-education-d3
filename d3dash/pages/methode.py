"""À propos et méthode (`/a-propos` et `/methode`) : l'équipe, l'outil expliqué en mots simples, puis
le détail de la méthode (définitions, découpages, normes, score, besoins 2030, accès, limites,
contrôles, sources).

Seul écran de texte du site : aucune icône « i », aucune infobulle — les quatre
icônes du site vivent sur les autres pages, ici l'explication est écrite dans le texte.
Les valeurs calculées (corrélation de rang, comptes de contrôles) et les tables affichées (normes,
hypothèses, contrôles, passages d'un découpage à l'autre) sont lues dans la base : aucune n'est
retapée ici. Les libellés des clés techniques, eux, sont traduits en français par les tables de
libellés de ce module, avec un repli lisible pour une clé inconnue.
"""
import json
import re
from pathlib import Path

from dash import html

from .. import __version__
from .. import decoupage as D25
from ..composants import (entete, erreur_donnees, grille, grille_equipe, lecture, liste, membre_equipe,
                          note_limite, panneau, texte)
from ..db import donnees
from ..libelles import pluriel
from ..meta import EQUIPE, fmt_nombre, manque, nom_propre

# (ancre, titre) dans l'ordre du DOM : colonne de gauche, puis colonne de droite.
SECTIONS = (("s-definitions", "Définitions"), ("s-normes", "Normes"), ("s-score", "Score de priorité"),
            ("s-besoins", "Besoins 2030"), ("s-acces", "Accès et implantation"),
            ("s-decoupages", "Découpages administratifs"), ("s-limites", "Limites"),
            ("s-hypotheses", "Hypothèses de projection"), ("s-controles", "Contrôles de qualité"),
            ("s-sources", "Sources"))
# sections dont le contenu vient de la base : absentes quand la base ne répond pas
SECTIONS_BASE = ("s-normes", "s-hypotheses", "s-controles")

LIBELLES_NORMES = {"eleves_par_classe": "Élèves par classe", "eleves_par_enseignant": "Élèves par enseignant",
                   "distance_ecole_km": "Distance à l'école (km)"}
USAGES_NORMES = {"retenue": "retenue", "sensibilite": "sensibilité", "retenue_hypothese": "hypothèse retenue",
                 "reference": "contexte"}
ORDRES_NORMES = {"primaire": "primaire", "post_primaire": "post-primaire", "secondaire": "secondaire"}
# Les 10 clés écrites par l'étape d'analyse `d3a_03_projection_2030.py` (table `projection_2030_hypotheses`).
# Une clé absente de cette table est rendue par `_libelle_cle` : jamais un identifiant technique brut.
LIBELLES_HYPOTHESES = {
    "annee_reference": "Année de référence",
    "horizon": "Horizon de projection",
    "ecart_max_pop_annuaire_vs_projection_2024": "Écart maximal population annuaire / projection (2024)",
    "population": "Source de population",
    "facteur_pop_bas": "Facteur de population basse en 2030",
    "facteur_pop_haut": "Facteur de population haute en 2030",
    "scenario_central": "Scénario central",
    "part_public": "Part du public dans les élèves",
    "deficits": "Agrégation des manques",
    "rythme_annuel": "Rythme annuel",
}

DEFINITIONS = (
    ("Élèves par maître", "élèves inscrits / maîtres titulaires d'une classe"),
    ("Élèves par salle", "élèves inscrits / salles de classe utilisées"),
    ("Enseignants (salles) manquants",
     "pour chaque province, ce qui manque pour respecter 50 élèves par enseignant (par salle) ; somme des "
     "provinces en manque, sans compensation par les excédents d'autres provinces"),
    ("Enseignants redéployables",
     "excédents des provinces sous la norme, plafonnés au manque total : ce qu'un redéploiement parfait couvrirait"),
    ("Taux brut de scolarisation (TBS)",
     "élèves du primaire / enfants de 6 à 11 ans (population INSD) ; peut dépasser 100 %"),
    ("Secteur", "« Public » ou « Public + privé » ; les normes et les manques sont calculés sur le public"),
)

LIMITES = (
    "Les annuaires ne donnent pas les données par école : les ratios moyens d'une province masquent des écarts "
    "entre écoles et entre communes.",
    "Les fermetures liées à l'insécurité évoluent vite ; les salles « réouvrables » supposent un retour de la "
    "sécurité.",
    "Les projections de population datent du recensement 2019, avant les grands déplacements de population.",
    "La carte des écoles OSM est incomplète (voir fiabilité) ; les distances sont à vol d'oiseau.",
    "Le découpage administratif de 2025 (17 régions, 47 provinces) est utilisé sur les pages de projection "
    "(Besoins 2030, Implantation) ; les pages de constat restent sur le découpage des annuaires (13 régions, "
    "45 provinces). Les totaux nationaux sont identiques dans les deux découpages.",
    "Dans les deux provinces scindées en 2025, la répartition interne des salles et des enseignants déjà en "
    "place est indicative : elle suit la carte des écoles (OpenStreetMap), qui décrit surtout le réseau "
    "d'avant la crise.",
)

SOURCES = (
    "Annuaires statistiques de l'enseignement primaire, DGESS/MENAPLN, 2017-2018 à 2024-2025 (classeur du Data "
    "Challenge).",
    "Normes : arrêté 2020-186/MENAPLN/SG/DGESS (manuel des normes éducatives) ; DGESS, tableau de bord du primaire "
    "(CNS565) ; Kaboré-Idany, RICS 2014 (ancien plafond de 65).",
    "Population : INSD, RGPH 2019 et projections 2020-2035 par province.",
    "Crise : rapports du Secrétariat technique de l'éducation en situation d'urgence (ST-ESU, 2021-2022 et février "
    "2026 : écoles fermées, réouvertes, délocalisées, élèves déplacés internes) ; personnes déplacées internes "
    "(CONASUR).",
    "Géographie : limites administratives et localités OCHA/BNDT (HDX) ; écoles OpenStreetMap.",
    "Découpage administratif de 2025 : limites officielles COD-AB Burkina Faso v03 (17 régions, 47 provinces, "
    "351 communes, HDX).",
)


# ---- petits blocs de texte (blocs du kit : texte(), liste(), note_limite()) ------------------------------------
ESPACES_FINES = (" ;", " :", " %", " ?", " !", " »")


def _typo(t):
    """Espaces insécables du français (règles de langue) : avant « ; : % ? ! » et à
    l'intérieur des guillemets. Posé au rendu sur les chaînes écrites dans ce module, pour que le
    texte des sources reste lisible tel quel dans le code ; aucune valeur de la base n'y passe."""
    if not isinstance(t, str):
        return t
    for avant in ESPACES_FINES:
        t = t.replace(avant, " " + avant[1:])
    return t.replace("« ", "« ")


def _p(*contenu):
    """Paragraphe du corps de texte : bloc `texte()` du kit (mesure de ligne et rythme)."""
    return texte(*[_typo(c) for c in contenu])


def _intro(titre_gras, suite):
    return _p(html.Strong(_typo(titre_gras) + " "), suite)


def _liste(items):
    return liste([_typo(t) for t in items])


def _scenario(code, definition):
    """Entrée « code : définition » d'une liste (scénario 2030, classe de priorité)."""
    return html.Span([html.Strong(code), _typo(" : " + definition)])


def _tableau(legende, entetes, lignes, num=()):
    """Tableau statique du kit (`.tab`), qui défile dans son bloc plutôt que de faire défiler la page."""
    tete = html.Thead(html.Tr([html.Th(e, scope="col", className="c-num" if i in num else None)
                               for i, e in enumerate(entetes)]))
    corps = html.Tbody([html.Tr([html.Td(c, className="c-num" if i in num else None)
                                 for i, c in enumerate(ligne)]) for ligne in lignes])
    return html.Div(html.Table([html.Caption(legende, className="sr-only"), tete, corps], className="tab"),
                    className="table-defile")


def _cellule_detaillee(principal, precision):
    """Cellule à deux lignes : le libellé, puis la précision que la base donne à côté (12 px, atténuée).
    Une colonne de plus serait illisible dans une colonne de 475 px (`.table-defile` défilerait)."""
    if not precision:
        return principal
    return [principal, html.Div(precision, className="note")]


def _texte_base(v):
    """Valeur texte venant de la base : une valeur absente reste vide, jamais « 0 » ni « nan »."""
    return "" if manque(v) else str(v).strip()


def _nombre_fr(v):
    """Nombre de la base écrit à la française, texte gardé tel quel.

    Les colonnes `valeur` (normes) et `valeur` (hypothèses) sont du texte côté base : « 50 » y
    côtoie « 0.9939 » et « 2030-2031 ». Le nombre de décimales est celui de la source, zéros de
    fin retirés : arrondir un facteur de population à l'unité le rendrait faux, et une norme
    chargée en flottant (« 50.0 ») ne doit pas s'afficher « 50,0 ».
    """
    s = _texte_base(v)
    try:
        x = float(s)
    except ValueError:
        return s
    return fmt_nombre(x, len(s.partition(".")[2].rstrip("0")))


def _libelle_cle(cle):
    """Repli pour une clé technique absente des tables de libellés : « rythme_annuel » →
    « Rythme annuel ». Jamais un identifiant brut avec ses soulignés à l'écran."""
    s = _texte_base(cle).replace("_", " ")
    return s[:1].upper() + s[1:]


def _minuscule(s):
    return s[:1].lower() + s[1:]


def _detail_lisible(v):
    """Rend lisible le `detail` d'un contrôle **sans réécrire ses valeurs**.

    L'étape d'analyse écrit ce champ comme un `repr` Python (nombre, dictionnaire ou liste de
    dictionnaires) tronqué à 500 caractères : affiché tel quel, il se termine par une accolade
    ouverte au milieu d'un mot. Les cas d'une liste sont donc comptés et les trois premiers écrits
    en clair ; tout autre contenu est rendu inchangé.
    """
    t = _texte_base(v)
    if t in ("", "[]", "{}", "None"):
        return None
    if not t.startswith("["):
        return t
    cas = [", ".join(x.strip().strip("'\"") for x in re.findall(r":\s*('[^']*'|[^,}]+)", bloc))
           for bloc in re.findall(r"\{[^{}]*\}", t)]
    if not cas:
        return t
    tete = ("au moins " if not t.endswith("]") else "") + f"{len(cas)} {pluriel(len(cas), 'cas relevé')}"
    # la phrase (« au moins 4 cas relevés : … ») est écrite ici : elle porte les espaces fines du
    # français, comme tout texte de ce module ; les valeurs listées ne sont pas réécrites
    return _typo(tete + " : " + " ; ".join(cas[:3]) + (" ; …" if len(cas) > 3 else ""))


def _section(ancre, titre_section, *enfants):
    return panneau(titre_section, *enfants, id=ancre)


def _sommaire(ancres):
    """Sommaire d'ancres : la page est longue, chaque section est atteignable en un clic."""
    liens = [html.A(lib, href=f"#{a}", className="lien-suite") for a, lib in SECTIONS if a in ancres]
    return panneau("Aller à une section",
                   html.Nav(liens, className="sommaire", **{"aria-label": "Sections de la page"}))


# ---- sections ------------------------------------------------------------------------------------------------
def _equipe():
    """Bloc « L'équipe » : premier bloc de la page, pleine largeur.

    Deux cases de même poids : portrait rond, nom, rôle, une ligne de texte. Aucune coordonnée. Le
    nom de famille garde les capitales données par la personne, et un nom long passe à la ligne — il
    n'est jamais tronqué. Les portraits ne sont pas livrés avec le code :
    sans le fichier, la case se rend sans image (`composants.photo_presente`). « Unica Labs » est la
    **société** de John, pas le nom de l'équipe : c'est un lien externe, et le nom de l'équipe vient
    de `meta.EQUIPE`, écrit seulement dans la ligne de périmètre de l'en-tête.
    """
    return panneau(
        "L'équipe",
        grille_equipe(
            membre_equipe("Melissa Bénéwendé Sougrinoma Djelika OUEDRAOGO",
                          "Data analyst et data engineer",
                          bio=_typo("Ingénieure de l'eau et des aménagements hydro-agricoles, Institut 2iE."),
                          photo="equipe/melissa.jpg"),
            membre_equipe("John Lamien", "Architecte et data scientist",
                          bio=[_typo("Ingénieur en intelligence artificielle, gérant d'"),
                               html.A("Unica Labs", href="https://unicalabs.bf", target="_blank",
                                      rel="noopener noreferrer"),
                               _typo(", société de conseil informatique et de solutions d'ingénierie.")],
                          photo="equipe/john.jpg")))


def _en_bref():
    return panneau(
        "En bref",
        _intro("Ce que montre ce tableau de bord.",
               "Il répond au défi 3 du Data Challenge Éducation : comment mieux répartir les salles de classe et "
               "les enseignants du primaire au Burkina Faso ? Il compare les 45 provinces (ancien découpage, celui "
               "des annuaires) de 2017-2018 à 2024-2025, estime les besoins à l'horizon 2030-2031 et propose des "
               "localités où une nouvelle école servirait le plus d'enfants."),
        _intro("D'où viennent les chiffres.",
               "Des annuaires statistiques du primaire (DGESS/MENAPLN), des projections de population de l'INSD, "
               "des rapports sur les écoles fermées pendant la crise (ST-ESU, CONASUR) et des données "
               "géographiques ouvertes (OCHA/BNDT, OpenStreetMap). La liste complète est dans « Sources » ; "
               "aucun chiffre n'est inventé ni complété."),
        _intro("Comment une province devient « prioritaire ».",
               "Chaque province reçoit un score de 0 à 100 : la moyenne de cinq mesures qui comptent toutes autant "
               "(poids égaux) — élèves par salle, élèves par enseignant, salles à construire d'ici 2030, salles "
               "perdues pendant la crise et enfants hors de l'école. Le classement est ensuite rejoué avec "
               "5 000 pondérations tirées au hasard pour vérifier qu'il tient. P1 : la province est dans les dix "
               "premières et y reste pour au moins 60 % des tirages. P2 : elle est au rang 15 ou mieux, ou dans "
               "les dix premières pour au moins 25 % des tirages. P3 : à surveiller."),
        _intro("Ce que veulent dire les scénarios 2030.",
               "Le nombre d'élèves en 2030 n'est pas connu, il est estimé : enfants de 6 à 11 ans projetés par "
               "l'INSD, multipliés par un taux de scolarisation supposé. S1 : le taux d'aujourd'hui se maintient. "
               "S2 (central) : le taux revient à son niveau d'avant la crise et les salles fermées rouvrent. "
               "S2b : même taux, sans réouverture. S3 : tous les enfants sont scolarisés."),
        _intro("Ce que cet outil ne sait pas faire.",
               "Il raisonne par province, jamais par école : une moyenne provinciale masque les écarts entre "
               "écoles et entre communes. La carte des écoles OpenStreetMap est incomplète, donc la part d'enfants "
               "éloignés d'une école est surestimée dans certaines provinces. Les projections de population "
               "datent du recensement de 2019. Toutes les limites sont écrites dans « Limites »."))


def _definitions():
    return _section(
        "s-definitions", "Définitions",
        _p("Les mots employés sur tout le site, et le calcul exact qu'il y a derrière."),
        _tableau("Définition des indicateurs du tableau de bord", ["Indicateur", "Définition"],
                 [[_typo(nom), _typo(definition)] for nom, definition in DEFINITIONS]),
        lecture(_typo("un indicateur affiché ailleurs sur le site est toujours calculé comme écrit ici.")))


def _decoupages(pas=None):
    """Les deux découpages administratifs : pourquoi, ce qui change, et comment les chiffres passent
    de l'un à l'autre. Les renommages et les scissions sont lus dans la table de passage ; la page
    n'en retape aucun nom. Sans base, les deux paragraphes de méthode restent lisibles."""
    return _section(
        "s-decoupages", "Découpages administratifs",
        _intro("Deux cartes administratives, et deux seulement.",
               "Le Burkina Faso a redécoupé ses régions et ses provinces en 2025. Les pages de constat (vue "
               "d'ensemble, classement, fiche province) restent sur le découpage des annuaires statistiques, "
               "13 régions et 45 provinces : un chiffre observé ne doit pas changer de carte en route. Les deux "
               "pages tournées vers l'avenir (Besoins 2030, Implantation) sont présentées sur le découpage de "
               "2025, 17 régions et 47 provinces (limites officielles COD-AB v03) : une décision d'investissement "
               "se prend sur la carte en vigueur."),
        _passages(pas),
        _intro("Comment les chiffres passent sur la carte de 2025.",
               "Le rattachement des communes et des écoles est recalculé à partir de leurs coordonnées. Les "
               "valeurs d'une province scindée sont ensuite réparties entre ses deux provinces filles, jamais "
               "dupliquées : la population et les élèves au prorata des enfants de 6 à 11 ans, les salles et les "
               "enseignants au prorata des écoles géolocalisées. Le résultat est enfin calé sur le total de "
               "l'ancienne province, si bien que les totaux nationaux sont identiques dans les deux découpages."),
        lecture(_typo("un total national (salles à construire, enseignants supplémentaires) est le même sur les "
                      "deux cartes ; seule sa répartition entre provinces change.")))


def _passages(pas):
    """Phrase des renommages et des scissions, construite sur la table de passage du découpage 2025.

    Sans cette table (étape d3a_09b absente, droit SELECT manquant, base injoignable), la section
    garde ses paragraphes de méthode et une note dit ce qui manque : aucun nom n'est inventé.
    """
    if pas is None or not len(pas) or not {"province", "province_2025", "type_passage"} <= set(pas.columns):
        return html.P(_typo("La liste des provinces renommées et scindées est lue dans la table de passage du "
                            "découpage 2025 ; elle n'est pas disponible pour le moment."), className="note")
    noms = {}
    for r in pas.itertuples():
        noms.setdefault(_texte_base(r.type_passage), {}).setdefault(nom_propre(_texte_base(r.province)),
                                                                    []).append(_texte_base(r.province_2025))
    ren, sci = noms.get("renommee", {}), noms.get("scindee", {})
    inchangees = len(noms.get("inchangee", {}))
    clauses = []
    if ren:
        clauses.append(f"{len(ren)} {pluriel(len(ren), 'province')} {pluriel(len(ren), 'a', 'ont')} été "
                       + pluriel(len(ren), "renommée") + " ("
                       + " ; ".join(f"{a} devient {b[0]}" for a, b in ren.items()) + ")")
    if sci:
        clauses.append(f"{len(sci)} {pluriel(len(sci), 'a', 'ont')} été " + pluriel(len(sci), "scindée")
                       + " en deux (" + " ; ".join(f"{a} donne {' et '.join(b)}" for a, b in sci.items()) + ")")
    if not clauses:
        return None
    suite = f" Les {inchangees} autres provinces passent d'une carte à l'autre sans changement." if inchangees else ""
    # les noms viennent de la base : ils sont rendus dans un `Span`, hors des substitutions de `_typo`
    return _p(html.Strong("Ce qui change d'une carte à l'autre. "), html.Span(" et ".join(clauses) + "."), suite)


def _normes(no):
    """Normes : le tableau ne montre que le primaire (seul niveau du tableau de bord) ; une norme
    d'un autre ordre d'enseignement est citée à part, sinon elle se lit comme une norme du primaire
    (ainsi la ligne post-primaire, à 70 élèves par classe)."""
    niveau = no.niveau.map(lambda v: _texte_base(v).lower())
    prim, hors = no[niveau.isin(("", "primaire"))], no[~niveau.isin(("", "primaire"))]
    return _section(
        "s-normes", "Normes",
        _p("Une norme est le nombre d'élèves à ne pas dépasser, par classe ou par enseignant. C'est elle qui "
           "transforme un effectif en « manque » de salles ou d'enseignants. Toutes les normes ci-dessous sont "
           "celles du primaire."),
        _tableau("Normes du primaire retenues et variantes de sensibilité",
                 ["Indicateur", "Valeur", "Usage", "Source"],
                 [[r.indicateur, r.valeur, r.usage, _texte_base(r.source)] for r in prim.itertuples()], num=(1,)),
        lecture(_typo("les lignes « retenue » sont les valeurs utilisées partout sur le site ; les lignes "
                      "« sensibilité » servent seulement à montrer ce qui change avec une autre norme.")),
        _p("Pour mémoire, hors primaire : ",
           html.Span(" ; ".join(f"{r.valeur} {_minuscule(r.indicateur)} ({_niveau(r.niveau)})"
                                for r in hors.itertuples())),
           ". Ces valeurs ne servent à aucun calcul de ce tableau de bord, qui ne porte que sur le primaire.")
        if len(hors) else None)


def _niveau(v):
    return ORDRES_NORMES.get(_texte_base(v).lower()) or _minuscule(_libelle_cle(v))


def _score(rho):
    return _section(
        "s-score", "Score de priorité",
        _p("Le ", html.Strong("score de priorité"), " (0 à 100) est la moyenne de 5 composantes, chacune convertie "
           "en rang parmi les 45 provinces (poids égaux) : élèves par salle, élèves par enseignant (2024-2025), "
           "salles à construire d'ici 2030 rapportées au parc actuel (scénario central), salles perdues pendant "
           "la crise (par rapport au maximum 2017-2021) et enfants hors de l'école (100 − TBS)."),
        _intro("Robustesse.",
               "Pour vérifier que le classement ne dépend pas d'un choix de calcul, il est recalculé avec "
               "5 000 pondérations tirées au hasard et 10 variantes (une composante retirée, normalisation "
               "min-max, besoins S1 ou S3, accès OSM ou pression des déplacés ajoutés)."),
        _liste([_scenario("P1", "dans le top 10 et dans le top 10 pour au moins 60 % des tirages."),
                _scenario("P2", "rang ≤ 15 ou top 10 dans au moins 25 % des tirages."),
                _scenario("P3", "à surveiller.")]),
        html.P(_typo(f"Corrélation de rang minimale entre le classement central et les variantes : "
                     f"{fmt_nombre(rho, 2)} (1,00 = classement identique)."),
               className="note") if rho is not None and rho == rho else None)


def _besoins():
    return _section(
        "s-besoins", "Besoins 2030",
        _p("Le nombre d'élèves en 2030 est estimé, pas observé. Élèves 2030 = enfants de 6-11 ans projetés par "
           "l'INSD pour 2030 (variante basse, moyenne ou haute) × TBS supposé. Le privé garde sa part des élèves."),
        _liste([_scenario("S1", "le TBS de 2024-2025 se maintient."),
                _scenario("S2 (central)", "retour au TBS d'avant-crise (meilleur de 2017-2018 et 2018-2019) et "
                                          "réouverture des salles fermées."),
                _scenario("S2b", "même TBS sans réouverture."),
                _scenario("S3", "TBS d'au moins 100 % (scolarisation universelle).")]),
        _p("Salles à construire = élèves 2030 / norme, arrondi au supérieur, moins les salles existantes (et "
           "réouvrables) ; enseignants supplémentaires = élèves 2030 / norme moins les enseignants actuels. Les "
           "besoins nationaux sont la somme des besoins provinciaux (pas de compensation entre provinces), à "
           "étaler sur 6 années scolaires."))


def _acces():
    return _section(
        "s-acces", "Accès et implantation",
        _p("Les localités (OCHA/BNDT, population 6-11 ans estimée) sont rapprochées des écoles cartographiées dans "
           "OpenStreetMap ; la distance est mesurée à vol d'oiseau. Une localité à ", html.Strong("plus de 3 km"),
           " d'une école connue est jugée mal desservie (hypothèse : il n'existe pas de norme officielle de "
           "distance pour le primaire ; 5 km en sensibilité)."),
        _p("Dans chaque commune, les sites candidats sont choisis pour servir le plus d'enfants (au moins 150 en "
           "2030), sans double compte."),
        _p("La carte OSM est très incomplète dans certaines provinces : la part d'enfants éloignés y est ",
           html.Strong("surestimée"), ". Un site est « fiable » si sa province est couverte à au moins 50 % par "
           "OSM (écoles OSM / écoles de l'annuaire) et s'il n'est pas un chef-lieu probable ; sinon, il est à "
           "vérifier sur le terrain."))


def _limites():
    # note de limite du kit : bloc encadré neutre, jamais une alerte (ce n'est pas une panne)
    return _section("s-limites", "Limites",
                    note_limite(_typo("Ce que les données ne permettent pas de dire, et qu'il faut garder en "
                                      "tête avant de décider.")),
                    _liste(LIMITES))


def _hypotheses(hy):
    """Hypothèses : chaque clé de la table est libellée en français et son commentaire est affiché
    sous le libellé ; sans ce libellé, 7 des 10 clés de la table sortiraient en identifiants bruts."""
    return _section(
        "s-hypotheses", "Hypothèses de projection",
        _tableau("Hypothèses des projections 2030", ["Hypothèse", "Valeur"],
                 [[_cellule_detaillee(r.hypothese, r.commentaire), r.valeur] for r in hy.itertuples()]),
        lecture(_typo("ces réglages sont ceux utilisés par défaut pour toutes les projections 2030 du site ; "
                      "la ligne grise est le commentaire écrit par l'étape d'analyse.")))


def phrase_controles(nb, ok, alertes, echecs):
    """Résumé des contrôles **compté sur la table** : jamais une promesse écrite à l'avance.
    Accord en nombre du français (0 et 1 au singulier) et aucune catégorie vide énumérée."""
    clauses = [f"{ok} {pluriel(ok, 'conforme')}"]
    if alertes:
        clauses.append(f"{alertes} {pluriel(alertes, 'alerte')} {pluriel(alertes, 'non bloquante')}")
    if echecs:
        clauses.append(f"{echecs} {pluriel(echecs, 'échec')}")
    enum = clauses[0] if len(clauses) == 1 else ", ".join(clauses[:-1]) + " et " + clauses[-1]
    return f"{nb} {pluriel(nb, 'contrôle automatique', 'contrôles automatiques')} : {enum}."


def _controles(ct):
    ok = int((ct.resultat == "OK").sum())
    alertes = int((ct.resultat == "ALERTE").sum())
    lignes = [[_cellule_detaillee(_texte_base(r.controle),
                                  None if r.resultat == "OK" else _detail_lisible(getattr(r, "detail", None))),
               _texte_base(r.resultat)] for r in ct.itertuples()]
    return _section(
        "s-controles", "Contrôles de qualité",
        _p(phrase_controles(len(ct), ok, alertes, len(ct) - ok - alertes)),
        _tableau("Contrôles automatiques de qualité des données", ["Contrôle", "Résultat"], lignes),
        lecture(_typo("« OK » signifie que le contrôle est passé ; une « ALERTE » est un écart relevé qui ne "
                      "bloque pas la publication, et son détail est écrit sous le libellé ; un « ÉCHEC » "
                      "arrêterait la chaîne de traitement.")))


_SOURCE_GEO_DEMO = []     # cache : le fichier de contours fait 190 Ko, on n'en lit la source qu'une fois


def source_fond_de_carte(d):
    """Attribution du fond de carte **de la démonstration**, lue dans `d3dash/demo_geo.json`.

    Le fichier porte lui-même sa source : rien n'est réécrit ici. En production, la géométrie vient
    de la base et la section « Sources » la cite déjà (limites administratives OCHA/BNDT) : la ligne
    n'est alors pas affichée. Renvoie None si la source active n'est pas une source de démonstration
    ou si le fichier est absent.
    """
    nom = type(getattr(d, "source", None)).__name__
    if "Demo" not in nom and "Synthetique" not in nom:
        return None
    if not _SOURCE_GEO_DEMO:
        chemin = Path(__file__).resolve().parent.parent / "demo_geo.json"
        try:
            with chemin.open(encoding="utf-8") as f:
                _SOURCE_GEO_DEMO.append(json.load(f).get("source") or "")
        except (OSError, ValueError):
            _SOURCE_GEO_DEMO.append("")
    return _SOURCE_GEO_DEMO[0] or None


def _sources(source_geo=None):
    """Sources du site ; en démonstration, le fond de carte cite sa propre provenance."""
    items = list(SOURCES)
    if source_geo:
        items.append("Fond de carte de la démonstration : " + source_geo)
    return _section("s-sources", "Sources", _liste(items))


# ---- préparation des tables de la base -----------------------------------------------------------------------
def _table_passage(d):
    """Table de passage du découpage 2025, ou None si l'étape d3a_09b n'est pas chargée.

    Les tables `decoupage_2025_*` peuvent manquer sans que les vues de constat en souffrent
    (`decoupage.DecoupageIndisponible`) : cette page est une page de texte, elle ne tombe pas pour
    autant — seule la phrase construite sur la table laisse la place à une note.
    """
    try:
        return D25.passage(d)
    except D25.DecoupageIndisponible:
        return None


def preparer_normes(no):
    """Normes lisibles : libellé d'indicateur, valeur à la française, usage, niveau d'enseignement.
    Une ligne dont le code, le statut ou l'ordre est inconnu reste affichée, en clair."""
    t = no.copy()
    t["valeur"] = t.valeur.map(_nombre_fr)
    t["indicateur"] = [LIBELLES_NORMES.get(c) or _libelle_cle(c) for c in t.code]
    t["usage"] = [USAGES_NORMES.get(s) or _minuscule(_libelle_cle(s)) for s in t.statut]
    t["niveau"] = t.ordre if "ordre" in t.columns else "primaire"
    return t


def preparer_hypotheses(hy):
    """Hypothèses lisibles : libellé français de la clé, valeur à la française, commentaire de la base."""
    t = hy.copy()
    t["hypothese"] = [LIBELLES_HYPOTHESES.get(c) or _libelle_cle(c) for c in t.hypothese]
    t["valeur"] = t.valeur.map(_nombre_fr)
    t["commentaire"] = t.commentaire.map(_texte_base) if "commentaire" in t.columns else ""
    return t


# ---- page ----------------------------------------------------------------------------------------------------
def layout(**_):
    tete = entete("À propos et méthode",
                  f"Équipe {EQUIPE} · version {__version__} · données 2017-2018 à 2024-2025, "
                  f"projections 2030-2031")
    try:
        d = donnees()
        d.get()
    except Exception:
        # Le texte reste lisible : seules les sections alimentées par la base disparaissent.
        ancres = [a for a, _ in SECTIONS if a not in SECTIONS_BASE]
        return html.Div([tete, _equipe(), grille(
            html.Div([_en_bref(), _definitions(), _score(None), _besoins(), _acces()], className="pile"),
            html.Div([_sommaire(ancres), erreur_donnees(), _decoupages(), _limites(), _sources()],
                     className="pile"))],
            className="p-methode pile")

    no = preparer_normes(d["normes"])
    hy = preparer_hypotheses(d["hypotheses_2030"])
    ct = d["controles"]
    ro = d["robustesse"]
    rho = ro[ro.variante != "central"].spearman_vs_central.min() if len(ro) else None

    # Le bloc « L'équipe » est le premier bloc de la page, pleine largeur.
    # Ensuite, une seule rangée 7/5 pour tout le reste : « En bref » et le sommaire sont en **tête des
    # deux piles**, jamais dans une rangée à part — un panneau de 240 px en face d'un panneau de 475 px
    # creusait 225 px de vide dans la colonne de droite.
    return html.Div([
        tete,
        _equipe(),
        grille(html.Div([_en_bref(), _definitions(), _normes(no), _score(rho), _besoins(), _acces()],
                        className="pile"),
               # « Découpages administratifs » ouvre la colonne de droite, juste au-dessus de
               # « Limites » qui s'y réfère : les deux piles se terminent presque à la même hauteur
               # (mesuré 2 411 et 2 322 px à 1440 ; dans la colonne de gauche, l'écart dépassait
               # 1 000 px et la colonne de droite s'arrêtait au milieu de la page).
               html.Div([_sommaire([a for a, _ in SECTIONS]), _decoupages(_table_passage(d)),
                         _limites(), _hypotheses(hy), _controles(ct), _sources(source_fond_de_carte(d))],
                        className="pile")),
    ], className="p-methode pile")


def register(app):
    return None
