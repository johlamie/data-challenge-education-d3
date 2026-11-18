"""Page « À propos et méthode » (`/a-propos`, `/methode`) : structure, sommaire, tableaux, états.

Le contenu de méthode (chiffres, poids, seuils, sources) n'est pas testé mot à mot ici.
Ces tests gardent la **structure** du kit et les règles d'écran de texte.
"""
import re

import pandas as pd
import pytest

from d3dash import db
from d3dash.pages import methode


def texte(x):
    return str(x)


@pytest.fixture()
def page(donnees):
    return texte(methode.layout())


def test_racine_et_entete(page):
    """Racine de page préfixée, en-tête du kit, aucune mention d'un identifiant Dash perdu."""
    assert "className='p-methode pile'" in page
    assert "className='travail-tete'" in page and "À propos et méthode" in page
    assert "className='perimetre'" in page and "projections 2030-2031" in page


def test_sections_et_sommaire(page):
    """Les 10 sections sont rendues en panneaux du kit et le sommaire pointe sur elles, sans lien mort."""
    ancres = [a for a, _ in methode.SECTIONS]
    for ancre, titre in methode.SECTIONS:
        assert f"id='{ancre}'" in page, f"section absente : {ancre}"
        assert titre in page
    cibles = set(re.findall(r"href='#([a-z-]+)'", page))
    assert cibles == set(ancres)
    # les 10 sections + « L'équipe » + « En bref » + « Aller à une section » : aucune surface hors du kit
    assert page.count("className='panneau'") == len(ancres) + 3


# Liste de référence des sections de méthode, dans l'ordre de lecture. Toute section ajoutée,
# retirée, renommée ou déplacée fait échouer le test ci-dessous.
SECTIONS_ATTENDUES = (
    ("s-definitions", "Définitions"),
    ("s-normes", "Normes"),
    ("s-score", "Score de priorité"),
    ("s-besoins", "Besoins 2030"),
    ("s-acces", "Accès et implantation"),
    ("s-decoupages", "Découpages administratifs"),
    ("s-limites", "Limites"),
    ("s-hypotheses", "Hypothèses de projection"),
    ("s-controles", "Contrôles de qualité"),
    ("s-sources", "Sources"),
)


def test_sections_exactement_celles_attendues(page):
    """La page rend exactement les sections de référence, dans cet ordre, et aucune autre."""
    assert tuple(methode.SECTIONS) == SECTIONS_ATTENDUES
    attendues = [a for a, _ in SECTIONS_ATTENDUES]
    assert re.findall(r"id='(s-[a-z0-9-]+)'", page) == attendues
    assert set(re.findall(r"href='#([a-z0-9-]+)'", page)) == set(attendues)


def test_equipe_premier_bloc_pleine_largeur(page):
    """Le cadre « L'équipe » est le premier bloc de la page, avant la rangée 7/5 : les deux membres
    dans l'ordre, deux cases de même poids — portrait, nom, rôle, une ligne."""
    racine = methode.layout()
    equipe = racine.children[1]
    assert equipe.children[0].children[0].children == "L'équipe"
    cases = equipe.children[1]
    assert cases.className == "eq-grille"
    assert [c.className for c in cases.children] == ["eq-membre", "eq-membre"]
    for cls in ("eq-nom", "eq-role", "eq-bio"):
        assert page.count(f"className='{cls}'") == 2, cls
    # ordre imposé : la coéquipière d'abord, John Lamien ensuite
    assert page.index("OUEDRAOGO") < page.index("John Lamien")
    assert "Melissa Bénéwendé Sougrinoma Djelika OUEDRAOGO" in page
    assert "Data analyst et data engineer" in page and "Architecte et data scientist" in page
    assert methode._typo("Ingénieure de l'eau et des aménagements hydro-agricoles, Institut 2iE.") in page
    assert "Ingénieur en intelligence artificielle, gérant d'" in page
    assert "société de conseil informatique et de solutions d'ingénierie." in page
    # le bloc est hors de la grille 7/5 : il tient toute la largeur
    assert getattr(racine.children[2], "className", "") == "grille-fiche"


# Contenu attendu, mot pour mot, des deux cases : nom, rôle, une ligne. L'égalité stricte garantit
# qu'aucune autre ligne ne peut subsister dans une case.
EQUIPE_ATTENDUE = (
    ("Melissa Bénéwendé Sougrinoma Djelika OUEDRAOGO", "Data analyst et data engineer",
     "Ingénieure de l'eau et des aménagements hydro-agricoles, Institut 2iE."),
    ("John Lamien", "Architecte et data scientist",
     "Ingénieur en intelligence artificielle, gérant d'Unica Labs, société de conseil informatique "
     "et de solutions d'ingénierie."),
)


def _mots(x):
    """Texte visible d'un arbre de composants Dash, liens compris."""
    if isinstance(x, str):
        return x
    if isinstance(x, (list, tuple)):
        return "".join(_mots(i) for i in x)
    enfants = getattr(x, "children", None)
    return _mots(enfants) if enfants is not None else ""


def test_equipe_textes_courts_et_exacts(page):
    """Chaque case dit exactement trois choses — nom, rôle, **une** ligne — et rien d'autre.

    L'égalité stricte ligne à ligne : tout texte en plus dans une case fait échouer ce test.
    """
    cases = methode._equipe().children[1].children
    assert len(cases) == len(EQUIPE_ATTENDUE)
    for case, attendu in zip(cases, EQUIPE_ATTENDUE):
        lignes = case.children[1].children       # .eq-txt : nom, rôle, une ligne
        assert [p.className for p in lignes] == ["eq-nom", "eq-role", "eq-bio"]
        assert tuple(_mots(p) for p in lignes) == tuple(methode._typo(t) for t in attendu)
        # une ligne de biographie, pas un paragraphe : elle tient en une phrase
        assert _mots(lignes[2]).count(".") == 1
    # la seule société nommée dans le bloc est celle qui est liée, et une seule fois
    bloc = _mots(methode._equipe())
    assert bloc.count("Unica Labs") == 1
    assert texte(methode._equipe()).count("href=") == 1


def test_equipe_societe_en_lien_externe(page):
    """« Unica Labs » est la société de John, pas l'équipe : lien externe sûr, et le nom d'équipe
    reste le paramètre unique de `config.py`, lu par `meta.EQUIPE`."""
    assert "href='https://unicalabs.bf'" in page
    assert "target='_blank'" in page and "rel='noopener noreferrer'" in page
    assert f"Équipe {methode.EQUIPE} ·" in page
    assert "Unica Labs" not in page.replace("'Unica Labs'", "", 1)  # cité une seule fois, dans le lien
    assert methode.EQUIPE != "Unica Labs"


def test_equipe_sans_coordonnee_personnelle(page):
    """Aucun état provisoire sur la page, aucune coordonnée : la case ne porte que le nom, le rôle,
    une ligne, et le lien vers la société."""
    for provisoire in ("à compléter", "provisoire", "Coéquipière", "className='vide'", "sera ajouté"):
        assert provisoire not in page, f"mention provisoire encore présente : {provisoire}"
    equipe = texte(methode._equipe())
    assert not re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", equipe)        # aucune adresse électronique
    assert not re.search(r"(\+226|\b0[0-9]{2}[\s.-]?[0-9]{2})[\s.-]?[0-9]{2}[\s.-]?[0-9]{2}\b", equipe)
    assert equipe.count("href=") == 1 and "unicalabs.bf" in equipe     # un seul lien : la société
    assert "avatar" not in equipe.lower() and "initiale" not in equipe.lower()


def test_portraits_ronds_et_repli_sans_fichier(page, monkeypatch):
    """Les portraits sont servis depuis `assets/equipe/` avec un `alt` qui nomme la personne et des
    dimensions explicites ; sans le fichier (clone du dépôt, autre machine), la case se rend
    **sans** `<img>` — jamais une image cassée."""
    import d3dash.composants as K
    assert page.count("className='eq-photo'") == 2
    for src in ("/assets/equipe/melissa.jpg", "/assets/equipe/john.jpg"):
        assert f"src='{src}'" in page
    assert "alt='John Lamien'" in page and "alt='Melissa Bénéwendé Sougrinoma Djelika OUEDRAOGO'" in page
    assert "width='72'" in page and "height='72'" in page

    monkeypatch.setattr(K, "photo_presente", lambda fichier: False)
    sans = texte(methode._equipe())
    assert "Img(" not in sans and "eq-photo" not in sans
    assert "John Lamien" in sans and "OUEDRAOGO" in sans


def test_tableaux_du_kit_defilent_dans_leur_bloc(page):
    """Les 4 tableaux portent la classe du kit, une légende lisible par lecteur d'écran et leur
    conteneur de défilement : la page ne défile jamais horizontalement."""
    assert page.count("className='tab'") == 4
    assert page.count("className='table-defile'") == 4
    assert page.count("className='sr-only'") == 4
    # 4 lignes « Lecture : » de tableau + celle de la section des découpages
    assert page.count("className='lecture'") == 5
    assert "scope='col'" in page and "className='c-num'" in page


def test_aucune_icone_aide_ni_classe_heritee(page):
    """Écran de texte : aucune icône « i », aucune infobulle, aucune classe d'une version
    antérieure de la page."""
    assert "className='aide'" not in page and "data-aide" not in page
    for heritee in ("carte-bloc", "titre-page", "sous-titre", "markdown-methode", "page-methode",
                    "table-dc", "'limite'", "bloc-entete", "dbc"):
        assert heritee not in page, f"classe héritée encore utilisée : {heritee}"


def test_espaces_insecables_du_francais(page):
    """Les chaînes écrites dans la page portent l'espace fine insécable avant « ; : % ? ! » et
    dans les guillemets : un guillemet fermant ne part jamais seul à la ligne."""
    assert methode._typo("un « mot » utile ; 50 % des cas :") == (
        "un « mot » utile ; 50 % des cas :")
    # le repr des composants Dash échappe l'espace fine : on la cherche sous sa forme échappée
    fine = "\\u202f"
    assert " »" not in page and "« " not in page
    assert fine + "»" in page and "«" + fine in page


def test_valeurs_lues_dans_la_base(page, donnees):
    """Les tables de la base alimentent la page : normes, hypothèses et contrôles, et les
    repères « fictif » du mode démonstration sont conservés."""
    assert "Élèves par classe" in page and "Élèves par enseignant" in page
    ct = donnees["controles"]
    nb_ok = int((ct.resultat == "OK").sum())
    nb_al = int((ct.resultat == "ALERTE").sum())
    # la phrase porte une espace fine (échappée dans le `repr`) : on vérifie l'énumération comptée
    assert methode.phrase_controles(len(ct), nb_ok, nb_al, 0).split(": ")[1] in page
    assert "fictif" in page.lower()  # jeu de démonstration : les repères ne sont pas effacés
    # la valeur d'une norme chargée en flottant (50.0) reste un entier à l'écran
    assert "50,0" not in page and "50.0" not in page
    # la phrase des renommages et des scissions est construite sur la table de passage
    assert "Ce qui change d'une carte à l'autre" in page and "n'est pas disponible" not in page


# ---- formes réelles des trois tables de la base --------------------------------------------------------------
# La démonstration n'a que 3 / 3 / 7 lignes bien rangées : les vraies vues ont 10 hypothèses dont
# 7 clés techniques, 23 contrôles en ASCII dont une alerte détaillée, et 9 normes dont une du
# post-primaire. Les cadres ci-dessous reproduisent ces formes, à l'identique de la base.
HYPOTHESES_REELLES = pd.DataFrame([
    ("annee_reference", "2024-2025", "Derniere annee d'annuaire disponible"),
    ("ecart_max_pop_annuaire_vs_projection_2024", "0", "Controle d'alignement des series (attendu 0)"),
    ("facteur_pop_bas", "0.9939", "Rapport national 6-11 bas/moyen en 2030 applique a chaque province"),
    ("rythme_annuel", "6 annees scolaires (2025-26 a 2030-31)", "salles_par_an_2025_2030 = besoin / 6"),
    ("cle_inconnue_du_tableau_de_bord", "12345.50", ""),
], columns=["hypothese", "valeur", "commentaire"])

CONTROLES_REELS = pd.DataFrame([
    ("45 provinces x 8 annees x 3 statuts", "OK", True, "1080"),
    ("ratios eleves/maitre dans [20 ; 120] (total et public)", "ALERTE", False,
     "[{'province': 'KOMANDJARI', 'annee_scolaire': '2017-2018', 'statut': 'PUBLIC', 'eleves_par_maitre': 18.6}, "
     "{'province': 'LOROUM', 'annee_scolaire': '2022-2023', 'statut': 'PUBLIC', 'eleves_par_maitre': 149.2}, "
     "{'province': 'LOROUM', 'annee_scolaire': '2023-2024', 'statut': 'PUBLIC', 'eleves_par_m"),
    ("priorite : 45 provinces, score dans [0 ; 100]", "ECHEC", True, "score hors bornes : 101,4"),
], columns=["controle", "resultat", "bloquant", "detail"])

NORMES_REELLES = pd.DataFrame([
    ("eleves_par_classe", "primaire", "50", "retenue", "Effectif maximal par classe", "Manuel des normes", ""),
    ("eleves_par_enseignant", "primaire", "50", "retenue", "Ratio eleves/enseignant", "DGESS CNS565", ""),
    ("distance_ecole_km", "primaire", "3", "retenue_hypothese", "Distance a vol d'oiseau", "Hypothese", ""),
    ("eleves_par_classe", "post_primaire", "70", "reference", "Norme du post-primaire", "DGESS CNS564", ""),
], columns=["code", "ordre", "valeur", "statut", "libelle", "source", "reference"])


def plat(bloc):
    """Texte rendu d'un bloc Dash, dans l'ordre du DOM (sans les noms de classes)."""
    if isinstance(bloc, str):
        return bloc
    if isinstance(bloc, (list, tuple)):
        return " ".join(plat(x) for x in bloc)
    enfants = getattr(bloc, "children", None)
    return plat(enfants) if enfants is not None else ""


def test_hypotheses_reelles_libellees_et_chiffrees():
    """10 clés réelles : chacune a un libellé français, une clé inconnue est rendue lisible, les
    nombres sont écrits à la française avec les décimales de la source, le commentaire est affiché."""
    rendu = plat(methode._hypotheses(methode.preparer_hypotheses(HYPOTHESES_REELLES)))
    for brut in ("ecart_max_pop_annuaire_vs_projection_2024", "facteur_pop_bas", "rythme_annuel"):
        assert brut not in rendu, f"clé technique affichée brute : {brut}"
    assert "Écart maximal population annuaire / projection (2024)" in rendu
    assert "Facteur de population basse en 2030" in rendu and "Rythme annuel" in rendu
    assert "Cle inconnue du tableau de bord" in rendu  # repli lisible, jamais les soulignés
    assert "0,9939" in rendu and "0.9939" not in rendu          # virgule décimale
    assert "12 345,5" in rendu                             # fin de milliers + zéro final retiré
    assert "2024-2025" in rendu and "6 annees scolaires (2025-26 a 2030-31)" in rendu
    assert "Controle d'alignement des series (attendu 0)" in rendu  # commentaire de la base affiché


def test_controles_reels_comptes_et_detail_des_non_conformes():
    """La phrase de résumé est comptée sur la table (pas de promesse écrite d'avance) et le détail
    d'une ligne non conforme est affiché, lisible malgré la troncature à 500 caractères."""
    rendu = plat(methode._controles(CONTROLES_REELS))
    assert methode._typo("3 contrôles automatiques : 1 conforme, 1 alerte non bloquante et 1 échec.") in rendu
    assert "les alertes sont expliquées" not in rendu
    # 2 cas entiers et un troisième coupé par la troncature de la base : « au moins »
    assert methode._typo("au moins 2 cas relevés :") in rendu
    assert "KOMANDJARI, 2017-2018, PUBLIC, 18.6" in rendu and "LOROUM, 2022-2023, PUBLIC, 149.2" in rendu
    assert "{'province'" not in rendu and "}" not in rendu      # aucun repr Python à l'écran
    assert "score hors bornes : 101,4" in rendu                 # détail de l'échec aussi
    assert "1080" not in rendu                                  # détail d'une ligne OK : inutile


def test_normes_reelles_sans_confusion_de_niveau():
    """Le tableau ne contient que le primaire ; la norme du post-primaire est citée à part, avec son
    niveau — elle ne peut pas se lire comme une norme du primaire."""
    bloc = methode._normes(methode.preparer_normes(NORMES_REELLES))
    rendu = plat(bloc)
    tableau = plat([e for e in bloc.children if getattr(e, "className", "") == "table-defile"])
    assert "70" not in tableau and "post" not in tableau.lower()
    assert methode._typo("Pour mémoire, hors primaire :") in rendu
    assert "70 élèves par classe (post-primaire)" in rendu
    for retenue in ("Élèves par classe", "Élèves par enseignant", "Distance à l'école (km)"):
        assert retenue in tableau
    assert "retenue" in tableau and "hypothèse retenue" in tableau


def test_normes_sans_colonne_ordre():
    """Une vue qui ne donnerait pas la colonne `ordre` reste affichée (toutes les lignes au
    primaire), sans phrase « hors primaire » et sans exception."""
    bloc = methode._normes(methode.preparer_normes(NORMES_REELLES.drop(columns=["ordre"])))
    rendu = plat(bloc)
    assert "Pour mémoire, hors primaire" not in rendu and "Élèves par classe" in rendu


class SourceSansDecoupage:
    """Source qui sert les vues de constat mais aucune table `decoupage_2025_*` (étape d3a_09b
    absente ou droit SELECT manquant) : les pages de constat continuent de fonctionner."""

    def __init__(self, source):
        self.source = source
        self.derniere_erreur_decoupage = "UndefinedTable"

    def charger(self):
        brut = dict(self.source.charger())
        for cle in db.TABLES:
            brut.pop(cle, None)
        return brut


def test_decoupage_2025_indisponible_la_page_reste_entiere(source, monkeypatch):
    """Sans les tables du découpage 2025, la page de texte se rend quand même : cadre équipe,
    section « Découpages administratifs » avec ses paragraphes, et une note à la place de la
    phrase construite sur la table de passage. Aucun nom inventé, aucune exception."""
    d = db.Donnees(SourceSansDecoupage(source), ttl_s=3600)
    assert d.decoupage_disponible is False
    monkeypatch.setattr(methode, "donnees", lambda: d)
    page = texte(methode.layout())
    assert "John Lamien" in page and "Découpages administratifs" in page
    assert "Deux cartes administratives, et deux seulement." in page
    assert "Comment les chiffres passent sur la carte de 2025." in page
    assert "Ce qui change d'une carte à l'autre" not in page
    assert "elle n'est pas disponible pour le moment" in page
    # les sections alimentées par les vues de constat sont là : seule la table de passage manque
    for ancre in methode.SECTIONS_BASE:
        assert f"id='{ancre}'" in page
    assert "bloc-erreur" not in page


def test_etat_erreur_garde_le_texte(monkeypatch):
    """Base injoignable : le bloc erreur apparaît, le texte de méthode reste lisible et le
    sommaire ne propose pas les sections alimentées par la base."""
    monkeypatch.setattr(methode, "donnees", lambda: (_ for _ in ()).throw(RuntimeError("hors ligne")))
    page = texte(methode.layout())
    assert "bloc-erreur" in page and "Les données ne sont pas disponibles pour le moment" in page
    assert "Score de priorité" in page and "Limites" in page and "En bref" in page
    cibles = set(re.findall(r"href='#([a-z-]+)'", page))
    assert cibles.isdisjoint(set(methode.SECTIONS_BASE))
    for ancre in methode.SECTIONS_BASE:
        assert f"id='{ancre}'" not in page


def _titres(pile):
    """Titres des panneaux d'une pile, dans l'ordre du DOM."""
    titres = []
    for panneau in pile.children:
        tete = panneau.children[0]
        h2 = tete.children[0] if tete is not None else None
        titres.append(h2.children if h2 is not None else None)
    return titres


def test_une_seule_rangee_sept_cinq(donnees):
    """« En bref » et le sommaire sont en tête des deux piles, pas dans une rangée à part : une
    seule `grille()` pour toute la page, donc aucun trou dans la colonne de droite."""
    racine = methode.layout()
    rangees = [e for e in racine.children if getattr(e, "className", "") == "grille-fiche"]
    assert len(rangees) == 1
    gauche, droite = rangees[0].children
    assert _titres(gauche)[0] == "En bref"
    assert _titres(droite)[0] == "Aller à une section"
    assert "Définitions" in _titres(gauche) and "Limites" in _titres(droite)


def test_source_du_fond_de_carte_en_demonstration(donnees):
    """En mode démonstration, la section « Sources » cite la provenance du fond de carte, lue dans
    `d3dash/demo_geo.json` ; rien n'est réécrit dans la page."""
    import json
    from pathlib import Path
    attendu = json.loads((Path(methode.__file__).resolve().parent.parent / "demo_geo.json")
                         .read_text(encoding="utf-8"))["source"]
    assert methode.source_fond_de_carte(donnees) == attendu
    items = methode._sources(attendu).children[1].children[-1].children
    # la page applique seulement ses espaces insécables : le texte de la source n'est pas réécrit
    assert items == methode._typo("Fond de carte de la démonstration : " + attendu)
    assert methode._typo(attendu) in items

    class SourceReelle:
        pass

    class FausseBase:
        source = SourceReelle()
    assert methode.source_fond_de_carte(FausseBase()) is None
