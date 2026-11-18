"""Découpage administratif 2025 (17 régions, 47 provinces) pour les pages de projection : besoins 2030 et
implantation. Calculs purs (sans Dash), mêmes règles que l'étape d3a_09 du pipeline d'analyse.

Les pages de constat restent sur l'ancien découpage (45 provinces, 13 régions), calculé par `calculs.py`.
Ici, chaque ligne de `calculs.besoins_province` (une ancienne province) est répartie entre ses provinces 2025 :
 - 43 anciennes provinces vont 1 pour 1 vers une province 2025 (dont 3 renommées) : valeurs inchangées ;
 - 2 sont scindées en deux : les colonnes entières additives sont réparties au plus fort reste, la population
   et les élèves selon `part_population`, les stocks (salles, enseignants, salles réouvrables) selon
   `part_ecoles`, et les résultats publiés sont CALÉS sur le total de l'ancienne province, au prorata du
   besoin brut recalculé sur les entrées de chaque province fille (repli : `part_population` si tous les
   besoins bruts sont nuls). Les totaux nationaux sont donc identiques à ceux de l'ancien découpage.
Les taux (TBS, variation des effectifs) sont hérités de l'ancienne province, faute de source plus fine ;
les colonnes par an sont recalculées ligne par ligne, comme dans `calculs.besoins_province`.

Les tables `decoupage_2025_*` viennent d'une étape additive du pipeline : elles peuvent manquer sans que les
pages de constat en souffrent. Toutes les fonctions publiques d'ici lèvent alors `DecoupageIndisponible`, que
la page de projection attrape pour afficher son bloc « données indisponibles » habituel.
"""
import numpy as np
import pandas as pd

from .calculs import besoins_province, sites
from .meta import SCENARIO_CENTRAL, fmt_nombre, manque, nom_propre

ANNEES = 6  # 2025-26 à 2030-31
COLS_POPULATION = ["pop_6_11_t", "pop_6_11_2030", "eleves_2024_25", "eleves_2030"]
COLS_ECOLES = ["salles_2024_25", "enseignants_2024_25", "salles_reouvrables"]
COLS_RESULTAT = ["besoin_salles_2030", "besoin_enseignants_2030", "salles_a_construire_2030",
                 "enseignants_supplementaires_2030"]
COLS_ADDITIVES = COLS_POPULATION + COLS_ECOLES + COLS_RESULTAT
COLS_PASSAGE = ["pcode_province", "pcode_province_2025", "province_2025", "code_region_2025", "region_2025",
                "type_passage", "part_population", "part_ecoles"]
PASSAGES_AVEC_ANCIEN_NOM = ("renommee", "scindee")
# indicateurs d'accès hérités de l'ancienne commune : des taux et des libellés seulement, jamais un effectif
# (deux communes 2025 peuvent venir de la même ancienne commune : un effectif serait compté deux fois)
COLS_COMMUNES_HERITEES = ["part_hors_3km", "part_hors_5km", "distance_mediane_km", "distance_moyenne_ponderee_km",
                          "part_pop_geolocalisee", "couverture_osm_vs_annuaire_2024_25", "fiabilite_osm_province",
                          "commune_ancienne", "province_ancienne"]


class DecoupageIndisponible(RuntimeError):
    """Les tables `decoupage_2025_*` ne sont pas chargées (étape d3a_09b / d3a_09 absente, table vide ou droit
    SELECT manquant pour le rôle lecture seule). Les pages de constat, elles, fonctionnent toujours : une page
    de projection attrape cette erreur et affiche son bloc « données indisponibles » habituel."""


def _table(d, cle):
    """Une table du découpage 2025, ou une erreur typée que la page sait transformer en bloc d'erreur."""
    try:
        return d[cle]
    except KeyError as e:
        raise DecoupageIndisponible(f"table du découpage 2025 absente : {cle}") from e


def plus_fort_reste(total, parts, codes):
    """Répartit un entier selon des parts, au plus fort reste : la somme est exactement égale au total.
    Égalités de reste tranchées par code croissant (résultat reproductible)."""
    p = np.asarray(parts, dtype=float)
    if pd.isna(total):
        return pd.array([pd.NA] * len(p), dtype="Int64")
    t = int(total)
    if t < 0:
        return -plus_fort_reste(-t, p, codes)
    if not np.isfinite(p).all() or p.sum() <= 0:
        p = np.ones(len(p))
    p = p / p.sum()
    exact = t * p
    base = np.floor(exact).astype("int64")
    reste = t - int(base.sum())
    if reste > 0:
        ordre = sorted(range(len(p)), key=lambda i: (-(exact[i] - base[i]), str(codes[i])))
        for i in ordre[:reste]:
            base[i] += 1
    return pd.array(base, dtype="Int64")


def _reparti(total, parts, codes):
    """Même répartition, en flottants : les colonnes gardent le type de `calculs.besoins_province`."""
    return plus_fort_reste(total, parts, codes).to_numpy(dtype="float64", na_value=np.nan)


def _anciennement(t):
    """« anciennement : ... » : l'ancienne province en casse d'affichage si elle a été renommée ou scindée,
    None sinon (colonne en `object` : `None` et non `NaN`, pour un test direct au point d'appel)."""
    return pd.Series([nom_propre(a) if p in PASSAGES_AVEC_ANCIEN_NOM else None
                      for a, p in zip(t.province, t.type_passage)], index=t.index, dtype=object)


def _repartir_groupe(g):
    """Répartit une ligne de besoins entre les provinces 2025 issues de la même ancienne province (>= 2 filles)."""
    g = g.sort_values("pcode_province_2025").copy()
    codes = g.pcode_province_2025.tolist()
    wpop, weco = g.part_population.to_numpy(float), g.part_ecoles.to_numpy(float)
    for c in COLS_POPULATION:
        g[c] = _reparti(g[c].iloc[0], wpop, codes)
    for c in COLS_ECOLES:
        g[c] = _reparti(g[c].iloc[0], weco, codes)
    nc, nm = float(g.norme_eleves_par_classe.iloc[0]), float(g.norme_eleves_par_enseignant.iloc[0])
    besoin_s, besoin_e = np.ceil(g.eleves_2030 / nc), np.ceil(g.eleves_2030 / nm)
    brut = {"besoin_salles_2030": besoin_s, "besoin_enseignants_2030": besoin_e,
            "salles_a_construire_2030": np.maximum(0.0, besoin_s - g.salles_2024_25 - g.salles_reouvrables),
            "enseignants_supplementaires_2030": np.maximum(0.0, besoin_e - g.enseignants_2024_25)}
    for c, b in brut.items():
        b = b.to_numpy(float)
        g[c] = _reparti(g[c].iloc[0], b if np.nansum(b) > 0 else wpop, codes)
    # colonnes « par an » de la vue (normes 50/50) : recalculées comme dans d3a_09, sinon chaque province fille
    # hériterait du rythme de l'ancienne province entière. Les pages lisent `salles_par_an`.
    g["salles_par_an_2025_2030"] = (g.salles_a_construire_2030 / ANNEES).round(1)
    g["enseignants_par_an_2025_2030"] = (g.enseignants_supplementaires_2030 / ANNEES).round(1)
    return g


def besoins_province_2025(d, scenario=SCENARIO_CENTRAL, pop="moyen", statut="TOTAL", nc=50, nm=50):
    """Besoins 2030 par province du découpage 2025 (47 lignes) : `calculs.besoins_province` réparti par la
    table de passage. Totaux nationaux identiques à l'ancien découpage, pour toutes les normes.

    Colonnes de `calculs.besoins_province` + pcode_province_2025, province_2025, code_region_2025, region_2025,
    type_passage et `anciennement` (ancienne province en casse d'affichage si elle a été renommée ou scindée).
    `province_nom` / `region_nom` sont les noms 2025 ; `pcode_province` / `province` restent l'ancienne province.
    Lève `DecoupageIndisponible` si la table de passage n'est pas chargée.
    """
    pas = _table(d, "decoupage_passage")[COLS_PASSAGE].sort_values(["pcode_province", "pcode_province_2025"])
    b = besoins_province(d, scenario, pop, statut, nc, nm)
    nb = pas.groupby("pcode_province").size()
    m = b.assign(_ligne=np.arange(len(b))).merge(pas, on="pcode_province", how="left")
    # une ancienne province absente de la table de passage (ne devrait pas arriver) est gardée telle quelle :
    # mieux vaut une ligne sans nom 2025 qu'une ligne perdue, qui casserait le total national
    m["_nb"] = m.pcode_province.map(nb).fillna(1)
    morceaux = [m[m._nb == 1]] + [_repartir_groupe(x) for _, x in m[m._nb > 1].groupby("_ligne", sort=False)]
    out = pd.concat(morceaux, ignore_index=True).drop(columns=["_ligne", "_nb"])
    for c in COLS_ADDITIVES:
        out[c] = out[c].astype(float)
    out["salles_par_an"] = out.salles_a_construire_2030 / ANNEES
    out["enseignants_par_an"] = out.enseignants_supplementaires_2030 / ANNEES
    out["salles_pour_100"] = 100 * out.salles_a_construire_2030 / out.salles_2024_25.where(out.salles_2024_25 > 0)
    out["province_nom"], out["region_nom"] = out.province_2025, out.region_2025
    out["anciennement"] = _anciennement(out)
    return out.sort_values("salles_a_construire_2030", ascending=False).reset_index(drop=True)


def passage(d):
    """Table de passage « ancienne province → province 2025 » (47 lignes, poids compris), pour une page qui
    décrit le changement de découpage. Lève `DecoupageIndisponible` comme les autres fonctions d'ici."""
    return _table(d, "decoupage_passage")


def geoms_provinces_2025(d):
    """Contours des 47 provinces 2025, au format attendu par `figures.carte` : code, nom, code_region, geometrie."""
    p = _table(d, "decoupage_geo_provinces")
    return pd.DataFrame({"code": p.pcode_province_2025, "nom": p.province_2025, "code_region": p.code_region_2025,
                         "geometrie": p.geometrie})


def geoms_regions_2025(d):
    """Contours des 17 régions 2025 (traits de région des cartes) : code_region, region, geometrie."""
    r = _table(d, "decoupage_geo_regions")
    return pd.DataFrame({"code_region": r.code_region_2025, "region": r.region_2025, "geometrie": r.geometrie})


def provinces_2025(d):
    """Les 47 provinces 2025 pour un sélecteur : code, label, region, code_region (triées par nom)."""
    p = _table(d, "decoupage_geo_provinces")
    t = pd.DataFrame({"code": p.pcode_province_2025, "label": p.province_2025, "region": p.region_2025,
                      "code_region": p.code_region_2025})
    return t.sort_values(["label", "code"]).reset_index(drop=True)


def _survol_commune(r):
    if manque(r.part_hors_3km):
        # commune 2025 sans équivalent d'avant 2025 : les indicateurs d'accès ne sont pas hérités
        return (f"<b>{r.commune_2025}</b> · {r.province_2025}<br>Enfants de 6-11 ans à plus de 3 km : n.d."
                "<br>Commune créée par le découpage 2025 : indicateurs d'accès non disponibles")
    return (f"<b>{r.commune_2025}</b> · {r.province_2025}<br>Enfants de 6-11 ans à plus de 3 km : "
            f"{fmt_nombre(r.part_hors_3km, 0)} %<br>Distance médiane à l'école : "
            f"{fmt_nombre(r.distance_mediane_km, 1)} km<br>Carte des écoles : fiabilité "
            f"{r.fiabilite_osm_province}")


def communes_carte_2025(d):
    """Communes du découpage 2025 avec leur contour et les indicateurs d'accès hérités de l'ancienne commune.

    Mêmes colonnes de dessin que `calculs.communes_carte` (geometrie, part100, cx, cy, survol,
    fiabilite_osm_province) + pcode_commune_2025, commune_2025, pcode_province_2025, province_2025,
    code_region_2025, region_2025 et pcode_commune (ancien code, manquant si la commune est nouvelle).
    Une commune 2025 sans ancien code garde des valeurs manquantes — jamais des zéros.
    """
    from .figures import centroide
    c = _table(d, "decoupage_communes").copy()
    src = d["communes"].drop_duplicates("pcode_commune").set_index("pcode_commune")
    for col in COLS_COMMUNES_HERITEES:
        c[col] = c.pcode_commune.map(src[col]) if col in src else np.nan
    c["part100"] = c.part_hors_3km  # déjà en % (0-100)
    cxy = c.geometrie.map(centroide)
    c["cx"], c["cy"] = cxy.map(lambda t: t[0]), cxy.map(lambda t: t[1])
    c["survol"] = [_survol_commune(r) for r in c.itertuples()]
    return c


def sites_2025(d, pcode_2025=None, fiables_seulement=False):
    """Sites candidats (`calculs.sites`) rattachés au découpage 2025, filtrables par province 2025.

    Colonnes de `calculs.sites` (dont pcode_province / commune / province d'avant 2025, conservées pour
    l'export) + pcode_commune_2025, commune_2025, pcode_province_2025, province_2025, code_region_2025,
    region_2025, methode_rattachement, type_passage et `anciennement`. Le survol nomme la commune et la
    province 2025. Sans filtre, exactement les mêmes lignes que `calculs.sites` : aucun site perdu ni dupliqué.
    Lève `DecoupageIndisponible` si les tables du découpage ne sont pas chargées.
    """
    r = _table(d, "decoupage_sites").drop_duplicates("rang_national")
    s = sites(d)
    s = s.merge(r[["rang_national", "pcode_commune_2025", "commune_2025", "pcode_province_2025", "province_2025",
                   "code_region_2025", "region_2025", "methode_rattachement"]], on="rang_national", how="left")
    pas = _table(d, "decoupage_passage").drop_duplicates("pcode_province_2025").set_index("pcode_province_2025")
    s["type_passage"] = s.pcode_province_2025.map(pas.type_passage)
    s["anciennement"] = _anciennement(s)
    if pcode_2025:
        s = s[s.pcode_province_2025 == pcode_2025].copy()
    if fiables_seulement:
        s = s[s.sites_fiables == 1].copy()
    s["survol"] = [f"<b>{nom_propre(r.localite_site)}</b> · {r.commune_2025} ({r.province_2025})<br>"
                   f"Enfants de 6-11 ans servis en 2030 : {fmt_nombre(r.enfants_6_11_2030_desservis)}<br>"
                   f"Classes à prévoir : {fmt_nombre(r.classes_a_prevoir)}<br>"
                   f"École connue la plus proche : {fmt_nombre(r.distance_ecole_actuelle_km, 1)} km<br>"
                   + ("Site fiable" if r.sites_fiables == 1 else "À vérifier sur le terrain")
                   + ("" if manque(r.anciennement) else f"<br>Anciennement : {r.anciennement}")
                   for r in s.itertuples()]
    return s
