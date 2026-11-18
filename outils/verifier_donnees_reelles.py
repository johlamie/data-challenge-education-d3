"""Contrôle sur la base réelle (à lancer sur le serveur, avec l'environnement du service) : connexion par le
pooler avec le rôle lecture seule, présence de toutes les colonnes attendues par l'application (celles du
jeu synthétique),
recalcul des besoins 2030 identique à la vue de sensibilité, passage au découpage 2025 identique à la table
calculée par le pipeline (d3a_09), rendu de chaque page et appel de chaque callback principal. N'imprime que des
comptes, des booléens et des types d'erreur (aucune valeur de données, aucun secret).

Code de sortie : 0 si tout va bien, sinon le nombre d'anomalies. Les contrôles qui ne demandent pas la connexion
sont dans `controler(d)` : `tests/test_verifier_donnees_reelles.py` les rejoue sur le jeu synthétique.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from d3dash import calculs as C  # noqa: E402
from d3dash import db  # noqa: E402
from d3dash import decoupage as D  # noqa: E402
from d3dash.app import ROUTES, creer_app  # noqa: E402
from d3dash.config import Config  # noqa: E402
from d3dash.demo import SourceSynthetique  # noqa: E402
from d3dash.meta import ANNEE_REF, SCENARIO_CENTRAL  # noqa: E402

SCENARIOS = ("S1_tendanciel", "S2_retour_avant_crise", "S2b_retour_sans_reouverture", "S3_universel")
POPULATIONS = ("bas", "moyen", "haut")
STATUTS = ("TOTAL", "PUBLIC")
NORMES_CLASSE, NORMES_ENSEIGNANT = (50, 60, 65), (45, 50, 55)
COMMUNES_2025 = 351  # découpage 2025 de la base réelle (le jeu de démonstration en a moins)


def _lire(src, table):
    """Un SELECT de plus, hors cache : la table de contrôle du pipeline n'est pas chargée par l'application."""
    with src._connexion() as cx, cx.cursor() as cur:
        cur.execute(f'SELECT * FROM "d3_analyse".{table}')
        return db._normaliser(pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description]))


def _controler_besoins(d):
    """Recalcul des besoins 2030 pour toutes les normes = vue de sensibilité."""
    ecarts = 0
    for sc in SCENARIOS:
        for pop in POPULATIONS:
            for st in STATUTS:
                for nc in NORMES_CLASSE:
                    for nm in NORMES_ENSEIGNANT:
                        b = C.besoins_province(d, sc, pop, st, nc, nm)
                        s = C.sensibilite(d, sc, pop, st, nc, nm)
                        ecarts += int(b.salles_a_construire_2030.sum() != s.salles_a_construire_2030)
                        ecarts += int(b.enseignants_supplementaires_2030.sum() != s.enseignants_supplementaires_2030)
    print("recalcul besoins 2030 = vue de sensibilite (216 combinaisons x 2) : ecarts =", ecarts)
    return ecarts


def _controler_decoupage_2025(d, src=None, communes_attendues=COMMUNES_2025):
    """Découpage 2025 : tables chargées, totaux nationaux conservés pour les 216 combinaisons, sites tous
    rattachés, et — si `src` est fourni — répartition identique à projection_2030_province_2025 (50/50)."""
    if not d.decoupage_disponible:
        print("decoupage 2025 : tables indisponibles (erreur :", d.erreur_decoupage, ") - lancer "
              "d3a_09b_geo_decoupage_2025.sql puis d3a_09_decoupage_2025.py, et verifier le GRANT SELECT "
              "a dc_edu_d3_ro. Les pages de constat, elles, fonctionnent.")
        return 1
    anomalies = 0
    attendu = {"decoupage_passage": 47, "decoupage_geo_provinces": 47, "decoupage_geo_regions": 17,
               "decoupage_communes": communes_attendues, "decoupage_sites": len(d["implantation"])}
    conforme = all(len(d[k]) == n for k, n in attendu.items())
    print("decoupage 2025 - lignes :", {k: len(d[k]) for k in attendu}, "| attendu :", attendu,
          "| conforme :", conforme)
    anomalies += int(not conforme)
    geo = {k: bool(d[k].geometrie.notna().all())
           for k in ("decoupage_geo_provinces", "decoupage_geo_regions", "decoupage_communes")}
    print("decoupage 2025 - geometries presentes :", geo)
    anomalies += int(not all(geo.values()))
    b25 = D.besoins_province_2025(d)
    print("decoupage 2025 - provinces :", b25.pcode_province_2025.nunique(), "| regions :",
          b25.region_2025.nunique(), "| anciennement renseigne :", int(b25.anciennement.notna().sum()))
    if src is not None:
        p25 = _lire(src, "projection_2030_province_2025")
        manquantes = sorted(set(D.COLS_ADDITIVES + ["pcode_province_2025", "type_passage"]) - set(p25.columns))
        print("projection_2030_province_2025 - lignes :", len(p25), "| colonnes attendues manquantes :",
              manquantes or "aucune")
        anomalies += len(manquantes)
        cellules = comparees = 0
        for sc in SCENARIOS:
            for pop in POPULATIONS:
                for st in STATUTS:
                    a = D.besoins_province_2025(d, sc, pop, st, 50, 50).set_index("pcode_province_2025").sort_index()
                    r = p25[(p25.scenario == sc) & (p25.variante_population == pop) & (p25.statut == st)]
                    r = r.set_index("pcode_province_2025").sort_index()
                    if not len(r) or list(a.index) != list(r.index):
                        print("  combinaison non comparable :", sc, pop, st, "| lignes :", len(r))
                        anomalies += 1
                        continue
                    ecart = (a[D.COLS_ADDITIVES] - r[D.COLS_ADDITIVES]).abs() > 0.5
                    cellules += int(ecart.to_numpy().sum())
                    comparees += int(ecart.size)
        print("decoupage 2025 = pipeline (24 combinaisons x 11 colonnes additives x 47 provinces) : cellules "
              "differentes =", cellules, "/", comparees)
        anomalies += cellules
    ecarts = 0
    for sc in SCENARIOS:
        for pop in POPULATIONS:
            for st in STATUTS:
                for nc in NORMES_CLASSE:
                    for nm in NORMES_ENSEIGNANT:
                        a = D.besoins_province_2025(d, sc, pop, st, nc, nm)
                        o = C.besoins_province(d, sc, pop, st, nc, nm)
                        ecarts += int(a.salles_a_construire_2030.sum() != o.salles_a_construire_2030.sum())
                        ecarts += int(a.enseignants_supplementaires_2030.sum()
                                      != o.enseignants_supplementaires_2030.sum())
                        ecarts += int((a[D.COLS_ADDITIVES] < 0).to_numpy().any())
    print("totaux nationaux 47 provinces = 45 provinces (216 combinaisons x 2) : ecarts =", ecarts)
    anomalies += ecarts
    s25, s45 = D.sites_2025(d), C.sites(d)
    rattaches = len(s25) == len(s45) and bool(s25.pcode_province_2025.notna().all())
    print("sites rattaches au decoupage 2025 :", len(s25), "/", len(s45), "| tous rattaches :", rattaches,
          "| communes 2025 sans code ancien :", int(d["decoupage_communes"].pcode_commune.isna().sum()))
    return anomalies + int(not rattaches)


def _callbacks(app):
    """Les callbacks **Python** de l'application. Un callback côté navigateur (`clientside_callback`, par
    exemple la pose des bornes de zoom de la page Implantation) a une entrée dans `callback_map` sans clé
    `callback` : il n'y a rien à appeler ici, il est ignoré."""
    return {k: v["callback"].__wrapped__ for k, v in app.callback_map.items() if "callback" in v}


def _fonction(cbs, cle):
    for k, f in cbs.items():
        if cle in k:
            return f
    raise KeyError(cle)


def _controler_pages(app):
    """Rendu de chaque route par le callback de routage."""
    cbs = _callbacks(app)
    try:
        routeur = _fonction(cbs, "page.children")
    except KeyError:
        print("pages rendues : callback de routage introuvable")
        return 1
    ok = 0
    for chemin in ROUTES:
        try:
            if routeur(chemin, "")[0] is None:
                print("  page vide :", chemin)
            else:
                ok += 1
        except Exception as e:
            print("  page en erreur :", chemin, "|", type(e).__name__)
    print("pages rendues :", ok, "/", len(ROUTES))
    return len(ROUTES) - ok


def _contexte_dash(declencheur):
    """Contexte de callback minimal : Dash ne l'installe que dans une requête, et le callback de recadrage
    de la carte lit le bouton déclencheur. Rend la fonction qui rétablit le contexte précédent, ou None si
    l'API interne de Dash a changé."""
    try:
        from dash._callback_context import context_value
        from dash._utils import AttributeDict
        jeton = context_value.set(AttributeDict(triggered_inputs=[{"prop_id": f"{declencheur}.n_clicks"}]))
        return lambda: context_value.reset(jeton)
    except Exception:
        return None


def _controler_callbacks(d, app):
    """Appelle chaque callback principal avec des arguments pris dans les données et rend compte par
    callback : « ok », « bloc d'erreur » (le callback a affiché « Données indisponibles ») ou le type de
    l'exception. Les filtres de province suivent le découpage de leur page : ancien pour les pages de
    constat, 2025 pour Besoins 2030 et Implantation."""
    cbs = _callbacks(app)
    etats = []

    def essayer(libelle, cle, *args, affiche=False):
        """`affiche` : les deux dernières sorties du callback sont (bloc d'erreur, contenu masqué) ; un
        callback qui a rattrapé une panne de données ne compte pas comme un succès."""
        try:
            r = _fonction(cbs, cle)(*args)
            if affiche and not (r[-1] is False and not r[-2]):
                etats.append((libelle, "bloc d'erreur"))
                return None
            etats.append((libelle, "ok"))
            return r
        except Exception as e:
            etats.append((libelle, type(e).__name__))
            return None

    pcode = d["priorite"].pcode_province.iloc[0]  # province d'avant 2025 : pages de constat
    pcode25 = d["decoupage_sites"].pcode_province_2025.iloc[0] if d.decoupage_disponible else ""
    essayer("Vue d'ensemble - carte", "acc-carte.figure", "score_priorite")
    essayer("Classement - tableau et carte", "cla-table.data", "score_priorite", ANNEE_REF, "PUBLIC", affiche=True)
    essayer("Classement - export CSV", "cla-download.data", 1, "score_priorite", ANNEE_REF, "PUBLIC", None)
    essayer("Fiche province", "fic-identite.children", pcode, ANNEE_REF, "PUBLIC")
    essayer("Besoins 2030 - decoupage 2025", "bes-kpis.children", SCENARIO_CENTRAL, "moyen", 50, 50, "TOTAL",
            affiche=True)
    imp = essayer("Implantation - tout le pays", "imp-table.data", "", "tous", affiche=True)
    imp25 = essayer("Implantation - une province 2025", "imp-table.data", pcode25, "tous", affiche=True)
    essayer("Implantation - liste vide", "imp-vide.children", imp[0] if imp else [], "tous", "")
    essayer("Implantation - export CSV", "imp-download.data", 1, pcode25, "tous")
    rendre_contexte = _contexte_dash("imp-recadrer")
    if rendre_contexte:
        try:
            essayer("Implantation - recadrage de la carte", "imp-cadre.data", 1, None, None, None, None, pcode25)
        finally:
            rendre_contexte()  # le contexte posé ne survit pas à ce contrôle
    else:
        print("  Implantation - recadrage de la carte : ignore (contexte Dash indisponible)")
    for libelle, etat in etats:
        print("  ", libelle, ":", etat)
    echecs = [libelle for libelle, etat in etats if etat != "ok"]
    print("callbacks principaux :", len(etats) - len(echecs), "/", len(etats),
          "| sites listes :", len(imp[0]) if imp else 0,
          "| sites de la province 2025 :", len(imp25[0]) if imp25 else 0,
          "| en echec :", echecs or "aucun")
    return len(echecs)


def controler(d, src=None, communes_attendues=COMMUNES_2025):
    """Tous les contrôles qui travaillent sur des données déjà chargées. Rend le nombre d'anomalies.
    `src` : source Postgres, seulement pour la comparaison avec la table calculée par le pipeline."""
    anomalies = _controler_besoins(d)
    anomalies += _controler_decoupage_2025(d, src, communes_attendues)
    app = creer_app(Config(auth_active=False, code_hash="", secret_key=""), d)
    anomalies += _controler_pages(app)
    return anomalies + _controler_callbacks(d, app)


def main():
    cfg = Config()
    src = db.SourcePostgres(cfg)
    with src._connexion() as cx, cx.cursor() as cur:
        cur.execute("select current_user, current_setting('transaction_read_only')")
        user, ro = cur.fetchone()
        cur.execute("select has_schema_privilege(current_user, 'public', 'CREATE'), "
                    "has_schema_privilege(current_user, 'd3_analyse', 'CREATE')")
        cree_public, cree_d3 = cur.fetchone()
    print("connexion pooler :", "ok", "| role :", user, "| lecture seule :", ro,
          "| droit CREATE public/d3_analyse :", cree_public, cree_d3)
    brut = src.charger()
    synth = SourceSynthetique().charger()
    manquantes = {k: sorted(set(synth[k].columns) - set(brut[k].columns)) for k in synth if k in brut}
    manquantes = {k: v for k, v in manquantes.items() if v}
    absentes = sorted(set(synth) - set(brut))
    print("relations chargees :", len(brut), "| lignes :", {k: len(v) for k, v in brut.items()})
    print("colonnes attendues manquantes :", manquantes or "aucune", "| relations absentes :", absentes or "aucune")
    d = db.Donnees(src, ttl_s=3600)
    d.get()
    anomalies = len(manquantes) + len(absentes) + controler(d, src)
    print("anomalies :", anomalies)
    return anomalies


if __name__ == "__main__":
    sys.exit(main())
