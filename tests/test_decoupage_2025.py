"""Découpage administratif 2025 (17 régions, 47 provinces) des pages de projection, sur le jeu synthétique :
répartition au plus fort reste, contrat de colonnes des tables decoupage_2025_*, dégradation propre quand ces
tables manquent, et surtout conservation des totaux nationaux entre l'ancien et le nouveau découpage pour
toutes les combinaisons de scénario et de normes.
"""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from d3dash import calculs as C
from d3dash import db
from d3dash import decoupage as D
from d3dash.meta import NORMES_CLASSE, NORMES_ENSEIGNANT, POPULATIONS, SCENARIOS

STATUTS = ("TOTAL", "PUBLIC")
# script de l'étape d'analyse D3, hors dépôt : la comparaison est jouée quand il est là, sautée sinon
CHEMIN_REFERENCE = Path("/home/john/Documents/data-challenge-education-D3/07-ANALYSE/scripts/"
                        "d3a_09_decoupage_2025.py")
# colonnes exactes des tables d3_analyse.decoupage_2025_* de la base réelle (contrat du chargeur)
COLONNES = {
    "decoupage_passage": ["pcode_province", "province", "pcode_province_2025", "province_2025", "code_region_2025",
                          "region_2025", "type_passage", "nb_communes", "pop_6_11_2030_communes",
                          "ecoles_geolocalisees", "part_population", "part_ecoles", "source_poids"],
    "decoupage_geo_provinces": ["pcode_province_2025", "province_2025", "code_region_2025", "region_2025",
                                "geometrie_geojson"],
    "decoupage_geo_regions": ["code_region_2025", "region_2025", "geometrie_geojson"],
    "decoupage_communes": ["pcode_commune_2025", "commune_2025", "pcode_province_2025", "province_2025",
                           "code_region_2025", "region_2025", "pcode_commune", "geometrie_geojson"],
    "decoupage_sites": ["rang_national", "pcode_commune_2025", "commune_2025", "pcode_province_2025",
                        "province_2025", "code_region_2025", "region_2025", "methode_rattachement"],
}


# ---- plus fort reste ------------------------------------------------------------------------------------------
def test_plus_fort_reste_somme_exacte():
    for total in (0, 1, 7, 1000, 100001):
        for parts in ([0.2985, 0.7015], [1 / 3, 1 / 3, 1 / 3], [0.9999, 0.0001]):
            r = D.plus_fort_reste(total, parts, [f"BF25P{i:03d}" for i in range(len(parts))])
            assert int(r.sum()) == total
            assert (r.to_numpy(dtype="int64") >= 0).all()


def test_plus_fort_reste_egalites_tranchees_par_code_croissant():
    assert D.plus_fort_reste(1, [0.5, 0.5], ["BF25P002", "BF25P001"]).tolist() == [0, 1]
    assert D.plus_fort_reste(1, [0.5, 0.5], ["BF25P001", "BF25P002"]).tolist() == [1, 0]


def test_plus_fort_reste_total_nul_poids_nuls_et_total_manquant():
    assert D.plus_fort_reste(0, [0.3, 0.7], ["A", "B"]).tolist() == [0, 0]
    r = D.plus_fort_reste(5, [0.0, 0.0], ["A", "B"])  # poids nuls : répartition égale
    assert int(r.sum()) == 5 and r.tolist() == [3, 2]
    r = D.plus_fort_reste(np.nan, [0.4, 0.6], ["A", "B"])
    assert r.isna().all()


# ---- tables de démonstration ---------------------------------------------------------------------------------
def test_tables_de_demo_ont_les_colonnes_reelles(source):
    brut = source.charger()
    for cle, cols in COLONNES.items():
        assert list(brut[cle].columns) == cols, cle


def test_47_provinces_dans_17_regions(donnees):
    p = D.provinces_2025(donnees)
    assert len(p) == 47 and p.code.nunique() == 47 and p.region.nunique() == 17
    assert list(p.label) == sorted(p.label)
    g = D.geoms_provinces_2025(donnees)
    assert len(g) == 47 and g.geometrie.notna().all()
    r = D.geoms_regions_2025(donnees)
    assert len(r) == 17 and r.geometrie.notna().all()
    pas = donnees["decoupage_passage"]
    assert len(pas) == 47 and pas.pcode_province.nunique() == 45
    assert pas.groupby("pcode_province_2025").pcode_province.nunique().eq(1).all()
    assert pas.type_passage.value_counts().to_dict() == {"inchangee": 40, "scindee": 4, "renommee": 3}


def test_poids_de_somme_1_et_jamais_ronds_sur_les_provinces_scindees(donnees):
    pas = donnees["decoupage_passage"]
    s = pas.groupby("pcode_province")[["part_population", "part_ecoles"]].sum()
    assert (s - 1).abs().to_numpy().max() <= 1e-9
    sc = pas[pas.type_passage == "scindee"]
    assert (sc.part_population != sc.part_ecoles).all()
    # des poids « ronds » (0,5 ou 0,25) ne feraient pas travailler le plus fort reste
    assert ((sc[["part_population", "part_ecoles"]] * 20) % 1).to_numpy().min() > 1e-6


# ---- besoins 2030 sur le découpage 2025 -----------------------------------------------------------------------
def test_une_ligne_par_province_2025(donnees):
    b = D.besoins_province_2025(donnees)
    assert len(b) == 47 and b.pcode_province_2025.nunique() == 47 and b.region_2025.nunique() == 17
    assert list(b.province_nom) == list(b.province_2025) and list(b.region_nom) == list(b.region_2025)
    assert list(b.salles_a_construire_2030) == sorted(b.salles_a_construire_2030, reverse=True)
    assert b[D.COLS_ADDITIVES].notna().all().all()


@pytest.mark.parametrize("nc,nm", [(50, 50), (65, 45)])
def test_provinces_non_scindees_identiques_aux_45_provinces(donnees, nc, nm):
    b = D.besoins_province_2025(donnees, nc=nc, nm=nm)
    o = C.besoins_province(donnees, nc=nc, nm=nm).set_index("pcode_province")
    un = b[b.type_passage != "scindee"].set_index("pcode_province")
    assert len(un) == 43
    for c in D.COLS_ADDITIVES + ["salles_par_an", "enseignants_par_an", "tbs_2030", "variation_eleves_pct"]:
        assert np.allclose(un[c], o.loc[un.index, c], equal_nan=True), c


@pytest.mark.parametrize("nc,nm", [(50, 50), (60, 55)])
def test_provinces_scindees_somment_exactement_au_parent(donnees, nc, nm):
    b = D.besoins_province_2025(donnees, nc=nc, nm=nm)
    o = C.besoins_province(donnees, nc=nc, nm=nm).set_index("pcode_province")
    sc = b[b.type_passage == "scindee"]
    assert sc.pcode_province.nunique() == 2 and len(sc) == 4
    somme = sc.groupby("pcode_province")[D.COLS_ADDITIVES].sum()
    for c in D.COLS_ADDITIVES:
        assert (somme[c] == o.loc[somme.index, c]).all(), c


def test_totaux_nationaux_conserves_entre_decoupages(donnees):
    """Exigence du commanditaire : le total national du découpage 2025 est identique à celui des 45 provinces
    (et à la vue de sensibilité) pour les 216 combinaisons scénario x population x secteur x normes."""
    combinaisons = 0
    for scenario in SCENARIOS:
        for pop in POPULATIONS:
            for statut in STATUTS:
                for nc in NORMES_CLASSE:
                    for nm in NORMES_ENSEIGNANT:
                        combinaisons += 1
                        b = D.besoins_province_2025(donnees, scenario, pop, statut, nc, nm)
                        o = C.besoins_province(donnees, scenario, pop, statut, nc, nm)
                        s = C.sensibilite(donnees, scenario, pop, statut, nc, nm)
                        for c in D.COLS_ADDITIVES:
                            assert b[c].sum() == o[c].sum(), (c, scenario, pop, statut, nc, nm)
                        assert b.salles_a_construire_2030.sum() == pytest.approx(s.salles_a_construire_2030)
                        assert b.enseignants_supplementaires_2030.sum() == pytest.approx(
                            s.enseignants_supplementaires_2030)
                        assert (b[D.COLS_ADDITIVES] >= 0).all().all()
    assert combinaisons == 216


def test_anciennement_seulement_pour_les_provinces_renommees_ou_scindees(donnees):
    b = D.besoins_province_2025(donnees)
    attendu = b.type_passage.isin(("renommee", "scindee"))
    assert list(b.anciennement.notna()) == list(attendu)
    assert b.anciennement.notna().sum() == 7
    assert b.loc[~attendu, "anciennement"].map(lambda v: v is None).all()
    for a, n in zip(b.loc[attendu, "anciennement"], b.loc[attendu, "province_2025"]):
        assert a and a != n and not a.isupper()


# ---- communes et sites ---------------------------------------------------------------------------------------
def test_communes_2025_geometrie_presente_et_indicateurs_herites(donnees):
    c = D.communes_carte_2025(donnees)
    assert len(c) == len(donnees["decoupage_communes"]) == 182
    assert c.geometrie.notna().all() and c.cx.notna().all() and c.cy.notna().all()
    assert c.survol.str.startswith("<b>").all()
    assert c.part100.dropna().between(0, 100).all()
    # un taux est hérité de l'ancienne commune ; une commune sans ancien code reste manquante (jamais zéro)
    src = donnees["communes"].set_index("pcode_commune")
    avec = c[c.pcode_commune.notna()]
    assert np.allclose(avec.part100, src.loc[avec.pcode_commune, "part_hors_3km"])
    sans = c[c.pcode_commune.isna()]
    assert len(sans) == 2 and sans.part100.isna().all() and sans.distance_mediane_km.isna().all()


def test_sites_2025_tous_rattaches_et_sans_perte(donnees):
    s = D.sites_2025(donnees)
    ref = C.sites(donnees)
    assert len(s) == len(ref) and s.rang_national.nunique() == len(ref)
    assert s.pcode_province_2025.notna().all() and s.commune_2025.notna().all()
    assert set(s.pcode_province_2025) <= set(donnees["decoupage_passage"].pcode_province_2025)
    assert s.survol.str.contains("<b>").all()
    fia = D.sites_2025(donnees, fiables_seulement=True)
    assert len(fia) == (ref.sites_fiables == 1).sum() and (fia.sites_fiables == 1).all()
    code = s.pcode_province_2025.iloc[0]
    une = D.sites_2025(donnees, code)
    assert len(une) == int((s.pcode_province_2025 == code).sum()) and (une.pcode_province_2025 == code).all()
    # la somme des provinces 2025 redonne tous les sites : aucun site perdu ni compté deux fois
    assert sum(len(D.sites_2025(donnees, c)) for c in set(s.pcode_province_2025)) == len(ref)


def test_contours_2025_emboites_commune_province_region(donnees):
    """Géographie du jeu de démonstration : un point intérieur de chaque commune 2025 tombe dans sa province
    2025, et un point intérieur de chaque province 2025 dans sa région 2025."""
    from d3dash.demo import _anneaux, _dedans, _point_garanti
    prov = {r.code: _anneaux(r.geometrie) for r in D.geoms_provinces_2025(donnees).itertuples()}
    reg = {r.code_region: _anneaux(r.geometrie) for r in D.geoms_regions_2025(donnees).itertuples()}
    for c in donnees["decoupage_communes"].itertuples():
        x, y = _point_garanti(_anneaux(c.geometrie))
        assert _dedans(x, y, prov[c.pcode_province_2025]), c.pcode_commune_2025
    for p in D.geoms_provinces_2025(donnees).itertuples():
        x, y = _point_garanti(_anneaux(p.geometrie))
        assert _dedans(x, y, reg[p.code_region]), p.code


def test_sites_des_provinces_scindees_reparties_entre_les_filles(donnees):
    s = D.sites_2025(donnees)
    sc = s[s.type_passage == "scindee"]
    assert len(sc)
    for pcode, g in sc.groupby("pcode_province"):
        assert g.pcode_province_2025.nunique() == 2, pcode
        assert set(g.pcode_commune_2025) and g.anciennement.notna().all()
    assert pd.notna(sc.methode_rattachement).all()


def test_repartition_d_un_total_manquant(donnees):
    """Entrée manquante dans la vue de projection : la répartition rend des valeurs manquantes, pas des zéros,
    et ne fait pas tomber les autres colonnes de la même province scindée."""
    pas = donnees["decoupage_passage"]
    g = pas[pas.type_passage == "scindee"].head(2).copy()
    for c in D.COLS_ADDITIVES:
        g[c] = 1000.0
    g["salles_2024_25"] = np.nan                      # stock inconnu pour cette ancienne province
    g["norme_eleves_par_classe"], g["norme_eleves_par_enseignant"] = 50.0, 50.0
    r = D._repartir_groupe(g)
    assert r.salles_2024_25.isna().all()
    assert r.eleves_2030.sum() == 1000 and r.pop_6_11_2030.sum() == 1000
    # besoin brut indécidable (stock manquant) : le résultat publié reste calé sur le total de l'ancienne province
    assert r.salles_a_construire_2030.sum() == 1000 and r.besoin_salles_2030.sum() == 1000


# ---- découpage 2025 indisponible (étape d3a_09b/d3a_09 absente ou droit SELECT manquant) -----------------------
class SourceDegradee:
    """Source qui sert les vues de constat mais pas (ou plus) les tables du découpage 2025."""

    def __init__(self, source, absentes=tuple(db.TABLES), echecs=1):
        self.source = source
        self.absentes = absentes
        self.echecs = echecs
        self.appels = 0
        self.derniere_erreur_decoupage = None

    def charger(self):
        self.appels += 1
        brut = dict(self.source.charger())
        if self.appels <= self.echecs:
            for cle in self.absentes:
                brut.pop(cle, None)
            self.derniere_erreur_decoupage = "UndefinedTable"
        return brut


def _fonctions_2025():
    return [D.besoins_province_2025, D.geoms_provinces_2025, D.geoms_regions_2025, D.provinces_2025,
            D.communes_carte_2025, D.sites_2025]


def test_decoupage_absent_les_pages_de_constat_marchent_toujours(source):
    d = db.Donnees(SourceDegradee(source), ttl_s=3600)
    assert d.decoupage_disponible is False and d.erreur_decoupage == "UndefinedTable"
    assert len(d["priorite"]) == 45 and len(C.besoins_province(d)) == 45
    assert C.kpis(d)["s2030"] > 0 and len(C.sites(d)) and len(C.communes_carte(d)) == 180
    for f in _fonctions_2025():
        with pytest.raises(D.DecoupageIndisponible):
            f(d)


@pytest.mark.parametrize("manquante", list(db.TABLES))
def test_une_seule_table_manquante_leve_l_erreur_typee(source, manquante):
    d = db.Donnees(SourceDegradee(source, absentes=(manquante,)), ttl_s=3600)
    assert d.decoupage_disponible is False
    leves = sum(1 for f in _fonctions_2025() if not _rend_un_resultat(f, d))
    assert leves >= 1
    assert len(C.besoins_province(d)) == 45  # le constat n'est jamais affecté


def _rend_un_resultat(f, d):
    try:
        f(d)
        return True
    except D.DecoupageIndisponible:
        return False


def test_rafraichissement_ulterieur_retrouve_le_decoupage(source):
    degradee = SourceDegradee(source)  # premier chargement dégradé, les suivants complets
    d = db.Donnees(degradee, ttl_s=0)
    with pytest.raises(D.DecoupageIndisponible):
        D.besoins_province_2025(d)
    assert degradee.appels == 1
    assert d.decoupage_disponible is True  # deuxième chargement : les tables sont revenues
    assert len(D.besoins_province_2025(d)) == 47


def test_decoupage_perdu_apres_un_chargement_reussi_garde_le_cache(source):
    """Un rafraîchissement dégradé ne doit pas vider les tables déjà chargées (comme pour les vues)."""
    degradee = SourceDegradee(source, echecs=0)
    d = db.Donnees(degradee, ttl_s=0)
    assert len(D.besoins_province_2025(d)) == 47
    degradee.echecs, degradee.appels = 2, 0  # les chargements suivants perdent le découpage
    assert d.decoupage_disponible is True
    assert len(D.besoins_province_2025(d)) == 47


# ---- comparaison avec le script d'analyse de référence (hors dépôt) -------------------------------------------
def _reference():
    """Charge d3a_09_decoupage_2025.py s'il est présent sur la machine ; le dépôt n'en dépend pas."""
    if not CHEMIN_REFERENCE.exists():
        pytest.skip("script d'analyse d3a_09 absent de cette machine")
    spec = importlib.util.spec_from_file_location("d3a_09_reference", CHEMIN_REFERENCE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_plus_fort_reste_identique_a_la_reference():
    ref = _reference()
    cas = [(1000, [0.2985, 0.7015]), (7, [0.5, 0.5]), (0, [0.3, 0.7]), (5, [0.0, 0.0]),
           (12345, [0.4123, 0.5877]), (3, [1 / 3, 1 / 3, 1 / 3])]
    for total, parts in cas:
        codes = [f"BF25P{i:03d}" for i in range(len(parts))]
        assert D.plus_fort_reste(total, parts, codes).tolist() == ref.plus_fort_reste(total, parts, codes).tolist()


@pytest.mark.parametrize("nc,nm", [(50, 50), (65, 45)])
def test_besoins_2025_identiques_a_la_reference(donnees, nc, nm):
    """Même répartition que l'étape d'analyse, colonne par colonne et province par province."""
    ref = _reference()
    projection = C.besoins_province(donnees, nc=nc, nm=nm)
    attendu = ref.repartir(projection, donnees["decoupage_passage"]).set_index("pcode_province_2025").sort_index()
    obtenu = D.besoins_province_2025(donnees, nc=nc, nm=nm).set_index("pcode_province_2025").sort_index()
    assert list(obtenu.index) == list(attendu.index)
    for c in D.COLS_ADDITIVES:
        assert np.array_equal(obtenu[c].to_numpy(float), attendu[c].astype(float).to_numpy()), c
