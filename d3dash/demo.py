"""Jeu de données SYNTHÉTIQUE (aucune donnée réelle) reproduisant le schéma des vues v_d3_dashboard_* et des
tables decoupage_2025_*.

Sert aux tests automatiques et au mode démo (DC_EDU_DEMO=1, bandeau « Données fictives »). Les noms et les
chiffres sont explicitement fictifs (« Province fictive 07 ») ; seule la géographie est réelle : les contours
administratifs du pays (45 provinces, 13 régions) sont lus dans demo_geo.json, les « communes » étant quatre
zones fictives par province. La province fictive n° k reçoit le k-ième contour réel : aucun nom réel n'est
exposé, la carte a seulement la bonne forme.

Le découpage 2025 fictif (17 régions, 47 provinces) est dérivé de ces mêmes contours, sans tirage aléatoire :
43 provinces reprises 1 pour 1 (dont 3 renommées) et 2 scindées en deux provinces filles.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ANNEES = list(range(2017, 2025))
SCENARIOS = ["S1_tendanciel", "S2_retour_avant_crise", "S2b_retour_sans_reouverture", "S3_universel"]
POP = {"bas": 0.994, "moyen": 1.0, "haut": 1.009}
NC, NM = [50, 60, 65], [45, 50, 55]
# 13 régions, 45 provinces : tailles réelles, dans l'ordre des contours de demo_geo.json
TAILLES_REGIONS = [1, 6, 2, 3, 3, 4, 3, 5, 3, 4, 3, 4, 4]
ZONES_PAR_PROVINCE = 4
# découpage 2025 fictif : 17 régions pour 47 provinces (dans l'ordre des provinces 2025)
TAILLES_REGIONS_2025 = [1, 4, 2, 3, 3, 2, 3, 3, 2, 3, 3, 2, 3, 3, 2, 4, 4]
PROVINCES_RENOMMEES = (5, 21, 38)   # numéros de provinces fictives (1-45) renommées en 2025
PROVINCES_SCINDEES = (16, 29)       # scindées en deux : zones 0-1 au « nord », zones 2-3 au « sud »
SUFFIXES_SCINDEES = ("nord", "sud")

_CHEMIN_GEO = Path(__file__).with_name("demo_geo.json")
_CONTOURS = None


def _contours():
    """Contours réels (lon/lat), chargés une seule fois : (provinces, zones par province, régions)."""
    global _CONTOURS
    if _CONTOURS is None:
        with _CHEMIN_GEO.open(encoding="utf-8") as f:
            g = json.load(f)
        zones = {}
        for c in g["communes"]:
            zones.setdefault(c["province"], {})[int(c["i"])] = c["geometrie"]
        _CONTOURS = (
            [p["geometrie"] for p in g["provinces"]],
            [[zones[p["code"]][i] for i in range(ZONES_PAR_PROVINCE)] for p in g["provinces"]],
            [r["geometrie"] for r in g["regions"]],
        )
    return _CONTOURS


def _anneaux(geom):
    """Anneaux (extérieurs et trous) d'une géométrie GeoJSON Polygon ou MultiPolygon."""
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    return [anneau for poly in polys for anneau in poly]


def _polygones(geom):
    """Polygones d'une géométrie GeoJSON Polygon ou MultiPolygon (chaque polygone = liste d'anneaux)."""
    return list(geom["coordinates"]) if geom["type"] == "MultiPolygon" else [geom["coordinates"]]


def _multipolygone(geoms):
    """Réunion approchée de géométries voisines : un MultiPolygon de tous leurs polygones (pas de dissolution,
    les frontières internes ne sont pas effacées — suffisant pour une carte de démonstration)."""
    return {"type": "MultiPolygon", "coordinates": [p for g in geoms for p in _polygones(g)]}


def _dedans(x, y, anneaux):
    """Point dans polygone par lancer de rayon, règle pair-impair (les trous sont donc exclus)."""
    dedans = False
    for anneau in anneaux:
        for i in range(len(anneau)):
            x1, y1 = anneau[i - 1][0], anneau[i - 1][1]
            x2, y2 = anneau[i][0], anneau[i][1]
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                dedans = not dedans
    return dedans


def _point_garanti(anneaux):
    """Repli déterministe : milieu du plus long segment intérieur d'une ligne de balayage horizontale."""
    ys = sorted({p[1] for anneau in anneaux for p in anneau})
    meilleur, point = 0.0, None
    for ya, yb in zip(ys, ys[1:]):
        y = (ya + yb) / 2
        xs = []
        for anneau in anneaux:
            for i in range(len(anneau)):
                xa, y1 = anneau[i - 1][0], anneau[i - 1][1]
                xb, y2 = anneau[i][0], anneau[i][1]
                if (y1 > y) != (y2 > y):
                    xs.append(xa + (y - y1) * (xb - xa) / (y2 - y1))
        xs.sort()
        for a, b in zip(xs[0::2], xs[1::2]):
            if b - a > meilleur:
                meilleur, point = b - a, ((a + b) / 2, y)
    if point is not None:
        return point
    pts = [p for anneau in anneaux for p in anneau]  # géométrie dégénérée : centre des sommets
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def _point_dans(geom, rng, essais=200):
    """Un point à l'intérieur de geom : tirage rejeté dans la boîte englobante, puis repli déterministe."""
    anneaux = _anneaux(geom)
    xs = [p[0] for anneau in anneaux for p in anneau]
    ys = [p[1] for anneau in anneaux for p in anneau]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    for _ in range(essais):
        x, y = float(rng.uniform(x0, x1)), float(rng.uniform(y0, y1))
        if _dedans(x, y, anneaux):
            return x, y
    return _point_garanti(anneaux)


def _decoupage_2025(P, C, SI):
    """Les cinq tables decoupage_2025_* du jeu fictif, dérivées des 45 provinces, des 180 zones et des sites.

    Aucun tirage aléatoire (le flux principal de `charger` reste inchangé) : le découpage est fixe et les poids
    de répartition viennent des chiffres fictifs des communes, donc ne sont pas ronds. Contours : une province
    fille et une région 2025 sont des MultiPolygon faits des contours de leurs communes / provinces.
    Chaque province scindée reçoit aussi une commune 2025 sans équivalent d'avant 2025 (`pcode_commune` nul),
    comme la base réelle, pour que les indicateurs d'accès hérités soient parfois manquants.
    """
    _, contours_zones, _ = _contours()
    zones_src = C.set_index("pcode_commune")  # chiffres fictifs des communes : poids de la table de passage
    pop_com, eco_com = zones_src.pop_6_11_villages, zones_src.villages
    enfants, communes = [], []
    m_prov = m_com = 0
    for n, p in enumerate(P.itertuples(), start=1):
        zones = contours_zones[p.k]
        scindee = n in PROVINCES_SCINDEES
        groupes = list(zip(SUFFIXES_SCINDEES, ([0, 1], [2, 3]))) if scindee else [(None, list(range(len(zones))))]
        decoupe = next((j for j in range(len(zones)) if len(_polygones(zones[j])) > 1), None) if scindee else None
        for suffixe, js in groupes:
            m_prov += 1
            code = f"BF25P{m_prov:03d}"
            if suffixe:
                nom, passage = f"Province fictive {n:02d} {suffixe}", "scindee"
            elif n in PROVINCES_RENOMMEES:
                nom, passage = f"Province refondue {n:02d}", "renommee"
            else:
                nom, passage = f"Province fictive {n:02d}", "inchangee"
            mes_communes = []
            for j in js:
                ancien = f"BF{(n - 1) * ZONES_PAR_PROVINCE + j + 1:06d}"
                polys = _polygones(zones[j])
                if j == decoupe:  # premier morceau détaché : commune 2025 sans code d'avant 2025
                    m_com += 1
                    mes_communes.append(dict(pcode_commune_2025=f"BF25C{m_com:03d}",
                                             commune_2025=f"Commune fictive 2025 {m_com:03d}", pcode_commune=None,
                                             geom={"type": "MultiPolygon", "coordinates": polys[:1]}))
                    polys = polys[1:]
                m_com += 1
                mes_communes.append(dict(pcode_commune_2025=f"BF25C{m_com:03d}",
                                         commune_2025=f"Commune fictive {int(ancien[2:]):03d}", pcode_commune=ancien,
                                         geom={"type": "MultiPolygon", "coordinates": polys}))
            for c in mes_communes:
                communes.append(dict(c, pcode_province_2025=code, ancienne_province=p.pcode_province))
            anciens = [c["pcode_commune"] for c in mes_communes if c["pcode_commune"]]
            enfants.append(dict(pcode_province_2025=code, province_2025=nom, type_passage=passage,
                                pcode_province=p.pcode_province, province=p.province, nb_communes=len(mes_communes),
                                pop_6_11=float(pop_com[anciens].sum()), ecoles=int(eco_com[anciens].sum()),
                                geom=_multipolygone([c["geom"] for c in mes_communes]) if scindee else p.geom))

    # régions 2025 : des groupes de provinces 2025 consécutives (l'ordre des contours est géographique)
    i = 0
    for ir, taille in enumerate(TAILLES_REGIONS_2025, start=1):
        for _ in range(taille):
            enfants[i]["code_region_2025"] = f"BF25R{ir:02d}"
            enfants[i]["region_2025"] = f"Région fictive 2025 {ir:02d}"
            i += 1

    E = pd.DataFrame(enfants)
    GP = E[["pcode_province_2025", "province_2025", "code_region_2025", "region_2025"]].copy()
    GP["geometrie_geojson"] = [json.dumps(g) for g in E.geom]
    GR = E.groupby(["code_region_2025", "region_2025"], as_index=False).agg(geoms=("geom", list))
    GR["geometrie_geojson"] = [json.dumps(_multipolygone(g)) for g in GR.geoms]
    GR = GR.drop(columns=["geoms"])

    ref = E.set_index("pcode_province_2025")
    CO = pd.DataFrame(communes)
    for c in ("province_2025", "code_region_2025", "region_2025"):
        CO[c] = CO.pcode_province_2025.map(ref[c])
    CO["geometrie_geojson"] = [json.dumps(g) for g in CO.geom]
    COLS_CO = ["pcode_commune_2025", "commune_2025", "pcode_province_2025", "province_2025", "code_region_2025",
               "region_2025", "pcode_commune", "geometrie_geojson"]

    # table de passage : deux poids de somme 1 dans chaque ancienne province (égaux à 1 si elle n'est pas scindée)
    lignes = []
    for pcode, grp in E.groupby("pcode_province", sort=False):
        g = grp.sort_values("pcode_province_2025")
        if len(g) == 1:
            wp, we = [1.0], [1.0]
            source = "province inchangée (poids = 1)"
        else:
            wp = list(g.pop_6_11 / g.pop_6_11.sum())
            we = list(g.ecoles / g.ecoles.sum())
            wp[-1], we[-1] = 1.0 - sum(wp[:-1]), 1.0 - sum(we[:-1])  # somme exactement égale à 1
            source = "population 6-11 et écoles fictives"
        for (_, e), a, b in zip(g.iterrows(), wp, we):
            lignes.append(dict(pcode_province=pcode, province=e.province, pcode_province_2025=e.pcode_province_2025,
                               province_2025=e.province_2025, code_region_2025=e.code_region_2025,
                               region_2025=e.region_2025, type_passage=e.type_passage, nb_communes=e.nb_communes,
                               pop_6_11_2030_communes=int(round(e.pop_6_11 * 1.12)), ecoles_geolocalisees=e.ecoles,
                               part_population=a, part_ecoles=b, source_poids=source))
    PAS = pd.DataFrame(lignes).sort_values(["pcode_province", "pcode_province_2025"]).reset_index(drop=True)

    # rattachement des sites : point dans une commune 2025 de leur ancienne province, sinon code de commune ancien
    candidats, ancien_vers_2025 = {}, {}
    for c in communes:
        candidats.setdefault(c["ancienne_province"], []).append((c["pcode_commune_2025"], _anneaux(c["geom"])))
        if c["pcode_commune"]:
            ancien_vers_2025[c["pcode_commune"]] = c["pcode_commune_2025"]
    cref = CO.set_index("pcode_commune_2025")
    lignes = []
    for s in SI.itertuples():
        trouve = next((code for code, anneaux in candidats[s.pcode_province]
                       if _dedans(s.longitude, s.latitude, anneaux)), None)
        methode = "point_dans_commune" if trouve else "commune_ancienne"
        r = cref.loc[trouve or ancien_vers_2025[s.pcode_commune]]
        lignes.append(dict(rang_national=s.rang_national, pcode_commune_2025=r.name, commune_2025=r.commune_2025,
                           pcode_province_2025=r.pcode_province_2025, province_2025=r.province_2025,
                           code_region_2025=r.code_region_2025, region_2025=r.region_2025,
                           methode_rattachement=methode))
    ST = pd.DataFrame(lignes).sort_values("rang_national").reset_index(drop=True)
    return {"decoupage_passage": PAS,
            "decoupage_geo_provinces": GP.sort_values("pcode_province_2025").reset_index(drop=True),
            "decoupage_geo_regions": GR.sort_values("code_region_2025").reset_index(drop=True),
            "decoupage_communes": CO.sort_values("pcode_commune_2025")[COLS_CO].reset_index(drop=True),
            "decoupage_sites": ST}


class SourceSynthetique:
    def __init__(self, graine=7):
        self.graine = graine

    def charger(self):
        rng = np.random.default_rng(self.graine)
        provs = []
        k = 0
        for ir, n in enumerate(TAILLES_REGIONS):
            for _ in range(n):
                provs.append(dict(pcode_province=f"BF{k + 1:04d}", province=f"PROVINCE FICTIVE {k + 1:02d}",
                                  code_region=f"BF{ir + 1:02d}", region=f"REGION FICTIVE {ir + 1:02d}", k=k))
                k += 1
        P = pd.DataFrame(provs)
        # contours réels : la province fictive n° k prend le k-ième contour, la région fictive le ir-ième
        contours_prov, contours_zones, contours_reg = _contours()
        P["geom"] = [contours_prov[k] for k in P.k]
        P["eleves_2024"] = rng.integers(25000, 140000, len(P))
        P["epm"] = rng.uniform(38, 66, len(P))
        P["eps"] = rng.uniform(36, 64, len(P))
        P["tbs"] = rng.uniform(45, 110, len(P))
        P["tbs_av"] = P.tbs + rng.uniform(0, 25, len(P))
        P["perte"] = rng.choice([0, 0, 0, 0.05, 0.2, 0.5], len(P))

        # ---- province x année x statut
        rows = []
        for _, p in P.iterrows():
            for a in ANNEES:
                f = 0.85 + 0.02 * (a - 2017)
                crise = (1 - p.perte) if a >= 2022 else 1
                for st, part in (("TOTAL", 1.0), ("PUBLIC", 0.82), ("PRIVE", 0.18)):
                    el = round(p.eleves_2024 * f * crise * part)
                    epm = p.epm * (0.95 + 0.008 * (a - 2017)) * (1 if st != "PRIVE" else 0.85)
                    eps = p.eps * (0.95 + 0.008 * (a - 2017)) * (1 if st != "PRIVE" else 0.85)
                    maitres, salles = max(1, round(el / epm)), max(1, round(el / eps))
                    gp = max(1, round(el / (eps * 0.97)))
                    pop = p.eleves_2024 / (p.tbs / 100) * (0.9 + 0.015 * (a - 2017))
                    bs, be = int(np.ceil(el / 50)), int(np.ceil(el / 50))
                    rows.append(dict(annee_scolaire=f"{a}-{a + 1}", annee_debut=a, code_region=p.code_region,
                                     region=p.region, pcode_province=p.pcode_province, province=p.province, statut=st,
                                     province_nouvelle=p.province, region_nouvelle=p.region, ecoles=round(salles / 4.5),
                                     salles_classe=salles, groupes_pedagogiques=gp, maitres=maitres, eleves=el,
                                     eleves_par_salle=el / salles, eleves_par_classe=el / gp, eleves_par_maitre=el / maitres,
                                     classes_par_salle=gp / salles, salles_par_ecole=4.5, gp_multigrades=round(gp * 0.1),
                                     part_classes_multigrades=10.0, gp_double_flux=0, part_classes_double_flux=0.0,
                                     classes_sans_salle=max(0, gp - salles) if st == "PRIVE" else 0,
                                     effectif_f=el * 0.49, effectif_g=el * 0.51, pop_6_11_t=pop,
                                     tbs_t=(100 * el / pop) if st == "TOTAL" else None, tbs_f=None, tbs_g=None,
                                     besoin_salles=bs, deficit_salles=max(0, bs - salles) if st != "PRIVE" else None,
                                     excedent_salles=max(0, salles - bs) if st != "PRIVE" else None,
                                     taux_deficit_salles=None, besoin_enseignants=be,
                                     deficit_enseignants=max(0, be - maitres) if st != "PRIVE" else None,
                                     excedent_enseignants=max(0, maitres - be) if st != "PRIVE" else None,
                                     taux_deficit_enseignants=None, valeur_imputee=False))
        PA = pd.DataFrame(rows)

        # ---- national et régional (sommes)
        nat = []
        for niveau, cles in (("national", []), ("region", ["code_region", "region"])):
            g = PA.groupby(["annee_scolaire", "annee_debut", "statut"] + cles, as_index=False)[
                ["ecoles", "salles_classe", "groupes_pedagogiques", "maitres", "eleves", "pop_6_11_t", "classes_sans_salle",
                 "deficit_salles", "excedent_salles", "deficit_enseignants", "excedent_enseignants"]].sum(min_count=1)
            g["niveau_geo"] = niveau
            if not cles:
                g["code_region"], g["region"] = None, None
            nat.append(g)
        N = pd.concat(nat, ignore_index=True)
        N["eleves_par_salle"] = N.eleves / N.salles_classe
        N["eleves_par_classe"] = N.eleves / N.groupes_pedagogiques
        N["eleves_par_maitre"] = N.eleves / N.maitres
        N["part_classes_multigrades"], N["part_classes_double_flux"] = 10.0, 0.0
        N["tbs_t"] = np.where(N.statut == "TOTAL", 100 * N.eleves / N.pop_6_11_t, np.nan)
        N["tbs_f"], N["tbs_g"] = np.nan, np.nan
        N["taux_deficit_salles"] = 100 * N.deficit_salles / N.salles_classe
        N["taux_deficit_enseignants"] = 100 * N.deficit_enseignants / N.maitres
        N.loc[N.statut == "PRIVE", ["deficit_salles", "deficit_enseignants"]] = np.nan

        pub = PA[PA.statut == "PUBLIC"].groupby(["annee_scolaire", "annee_debut"], as_index=False).agg(
            deficit_enseignants=("deficit_enseignants", "sum"), excedent_enseignants=("excedent_enseignants", "sum"),
            deficit_salles=("deficit_salles", "sum"),
            provinces_en_deficit=("deficit_enseignants", lambda s: int((s > 0).sum())),
            provinces_en_excedent=("excedent_enseignants", lambda s: int((s > 0).sum())))
        pub["enseignants_redeployables"] = pub[["deficit_enseignants", "excedent_enseignants"]].min(axis=1)
        pub["part_deficit_couvert_par_redeploiement"] = (100 * pub.enseignants_redeployables /
                                                         pub.deficit_enseignants.clip(lower=1)).round(1).astype(str)
        pub["recrutement_net_necessaire"] = pub.deficit_enseignants - pub.enseignants_redeployables
        pub["statut"] = "PUBLIC"

        # ---- 2030
        ref = PA[PA.annee_debut == 2024].pivot(index="pcode_province", columns="statut",
                                                values=["eleves", "salles_classe", "maitres"])
        smax = PA[(PA.annee_debut <= 2021)].groupby(["pcode_province", "statut"]).salles_classe.max().unstack()
        rows, sens = [], []
        for sc in SCENARIOS:
            for vp, fp in POP.items():
                for _, p in P.iterrows():
                    tbs30 = {"S1_tendanciel": p.tbs, "S3_universel": 100.0}.get(sc, p.tbs_av)
                    pop30 = p.eleves_2024 / (p.tbs / 100) * 1.12 * fp
                    el_tot = pop30 * tbs30 / 100
                    for st in ("TOTAL", "PUBLIC"):
                        part = ref.loc[p.pcode_province, ("eleves", st)] / ref.loc[p.pcode_province, ("eleves", "TOTAL")]
                        s24 = ref.loc[p.pcode_province, ("salles_classe", st)]
                        reouv = max(0, smax.loc[p.pcode_province, st] - s24) if sc in ("S2_retour_avant_crise", "S3_universel") else 0
                        rows.append(dict(pcode_province=p.pcode_province, province=p.province, code_region=p.code_region,
                                         region=p.region, scenario=sc, variante_population=vp, tbs_t=p.tbs,
                                         tbs_avant_crise=p.tbs_av, tbs_2030=tbs30, pop_6_11_t=round(pop30 / 1.12),
                                         pop_6_11_2030=round(pop30), statut=st,
                                         eleves_2024_25=ref.loc[p.pcode_province, ("eleves", st)],
                                         salles_2024_25=s24, enseignants_2024_25=ref.loc[p.pcode_province, ("maitres", st)],
                                         salles_reouvrables=reouv, eleves_2030=round(el_tot * part)))
        R = pd.DataFrame(rows)

        def besoins(R, nc, nm):
            b = R.copy()
            b["norme_eleves_par_classe"], b["norme_eleves_par_enseignant"] = float(nc), float(nm)
            b["besoin_salles_2030"] = np.ceil(b.eleves_2030 / nc)
            b["besoin_enseignants_2030"] = np.ceil(b.eleves_2030 / nm)
            b["salles_a_construire_2030"] = (b.besoin_salles_2030 - b.salles_2024_25 - b.salles_reouvrables).clip(lower=0)
            b["enseignants_supplementaires_2030"] = (b.besoin_enseignants_2030 - b.enseignants_2024_25).clip(lower=0)
            return b
        B = besoins(R, 50, 50)
        B["salles_par_an_2025_2030"] = (B.salles_a_construire_2030 / 6).round(1)
        B["enseignants_par_an_2025_2030"] = (B.enseignants_supplementaires_2030 / 6).round(1)
        B["variation_eleves_pct"] = ((B.eleves_2030 / B.eleves_2024_25 - 1) * 100).round(1)
        for nc in NC:
            for nm in NM:
                g = besoins(R, nc, nm).groupby(["scenario", "variante_population", "statut", "norme_eleves_par_classe",
                                                "norme_eleves_par_enseignant"], as_index=False)[
                    ["eleves_2024_25", "eleves_2030", "salles_2024_25", "salles_reouvrables", "besoin_salles_2030",
                     "salles_a_construire_2030", "enseignants_2024_25", "besoin_enseignants_2030",
                     "enseignants_supplementaires_2030"]].sum()
                sens.append(g)
        S = pd.concat(sens, ignore_index=True)
        S["normes_retenues"] = (S.norme_eleves_par_classe == 50) & (S.norme_eleves_par_enseignant == 50)
        S["scenario_central"] = (S.scenario == "S2_retour_avant_crise") & (S.variante_population == "moyen")

        # ---- priorité
        ref24 = PA[(PA.annee_debut == 2024) & (PA.statut == "TOTAL")].set_index("pcode_province")
        b2 = B[(B.scenario == "S2_retour_avant_crise") & (B.variante_population == "moyen") & (B.statut == "TOTAL")].set_index("pcode_province")
        Q = P.set_index("pcode_province")[["code_region", "region", "province"]].copy()
        Q["eleves"] = ref24.eleves
        Q["salles_classe"] = ref24.salles_classe
        Q["maitres"] = ref24.maitres
        Q["eleves_par_salle"] = ref24.eleves_par_salle
        Q["eleves_par_maitre"] = ref24.eleves_par_maitre
        Q["tbs_t"] = ref24.tbs_t
        Q["salles_max_2017_2021"] = smax["TOTAL"]
        Q["c1_eleves_par_salle"] = Q.eleves_par_salle
        Q["c2_eleves_par_enseignant"] = Q.eleves_par_maitre
        Q["c3_besoin_salles_2030"] = b2.salles_a_construire_2030 / Q.salles_classe
        Q["salles_a_construire_2030_S2"] = b2.salles_a_construire_2030
        Q["enseignants_supplementaires_2030_S2"] = b2.enseignants_supplementaires_2030
        Q["v_besoin_2030_S1"] = Q.c3_besoin_salles_2030 * 0.6
        Q["v_besoin_2030_S3"] = Q.c3_besoin_salles_2030 * 1.5
        Q["c4_salles_perdues_crise"] = P.set_index("pcode_province").perte
        Q["c5_enfants_hors_ecole"] = (100 - Q.tbs_t).clip(lower=0)
        Q["v_acces_hors_3km"] = rng.uniform(0.2, 0.9, len(Q))
        Q["v_pression_edi"] = rng.uniform(0, 0.3, len(Q))
        comps = ["c1_eleves_par_salle", "c2_eleves_par_enseignant", "c3_besoin_salles_2030", "c4_salles_perdues_crise",
                 "c5_enfants_hors_ecole"]
        for c in comps:
            Q["rang_centile_" + c] = Q[c].rank(pct=True)
        Q["score_priorite"] = 100 * Q[["rang_centile_" + c for c in comps]].mean(axis=1)
        Q["score_priorite"] = 100 * (Q.score_priorite - Q.score_priorite.min()) / (Q.score_priorite.max() - Q.score_priorite.min())
        Q["rang_priorite"] = Q.score_priorite.rank(ascending=False, method="first").astype(int)
        Q["rang_median_mc"] = Q.rang_priorite
        Q["rang_p05_mc"] = (Q.rang_priorite - 4).clip(lower=1)
        Q["rang_p95_mc"] = (Q.rang_priorite + 6).clip(upper=45)
        Q["freq_top10_mc"] = np.clip(1.1 - Q.rang_priorite / 14, 0, 1).round(3)
        Q["rang_pire_variante"] = (Q.rang_priorite + 5).clip(upper=45)
        Q["rang_meilleur_variante"] = (Q.rang_priorite - 3).clip(lower=1)
        Q["nb_variantes_top10"] = np.clip(12 - Q.rang_priorite, 0, 11)
        Q["classe_priorite"] = np.where((Q.rang_priorite <= 10) & (Q.freq_top10_mc >= 0.6), "P1 priorite robuste",
                                        np.where((Q.rang_priorite <= 15) | (Q.freq_top10_mc >= 0.25),
                                                 "P2 priorite probable", "P3 a surveiller"))
        Q["acces_part_hors_3km"] = Q.v_acces_hors_3km * 100
        cov = pd.Series(rng.uniform(0.2, 1.1, len(Q)), index=Q.index)
        Q["fiabilite_osm_province"] = np.where(cov < 0.5, "faible", np.where(cov < 0.8, "moyenne", "bonne"))
        Q["geometrie_geojson"] = [json.dumps(g) for g in P.set_index("pcode_province").geom]
        Q = Q.reset_index().sort_values("rang_priorite")

        ROB = []
        for v in ["central", "sans_c1_eleves_par_salle", "normalisation_minmax", "besoin_2030_scenario_S3"]:
            sc_ = Q.score_priorite + (0 if v == "central" else rng.normal(0, 6, len(Q)))
            rk = sc_.rank(ascending=False, method="first").astype(int)
            ROB.append(pd.DataFrame(dict(variante=v, pcode_province=Q.pcode_province, province=Q.province, score=sc_,
                                         rang=rk, spearman_vs_central=1.0 if v == "central" else 0.95)))
        ROB = pd.concat(ROB, ignore_index=True)

        # ---- communes (4 zones par province) et sites
        # Les points de site sont tirés dans un flux aléatoire séparé pour ne pas déplacer le flux principal.
        rng_pts = np.random.default_rng(self.graine + 1000)
        com, sites = [], []
        nc_ = 0
        for _, p in P.iterrows():
            for j in range(ZONES_PAR_PROVINCE):
                nc_ += 1
                zone = contours_zones[p.k][j]
                ph3 = float(rng.uniform(0.1, 0.9))  # fraction ; les parts sont exportées en %
                popc = int(rng.integers(3000, 20000))
                fia = Q.set_index("pcode_province").loc[p.pcode_province, "fiabilite_osm_province"]
                com.append(dict(pcode_province=p.pcode_province, pcode_commune=f"BF{nc_:06d}",
                                villages=int(rng.integers(10, 60)), villages_geolocalises=40, pop_6_11_villages=popc,
                                pop_6_11_geolocalisee=popc, pop_6_11_hors_3km=int(popc * ph3),
                                pop_6_11_hors_5km=int(popc * ph3 * 0.5), pop_6_11_2030_hors_3km=popc * ph3 * 1.1,
                                villages_hors_3km=10, distance_mediane_km=float(rng.uniform(1, 8)),
                                distance_moyenne_ponderee_km=float(rng.uniform(1, 8)), part_pop_geolocalisee=0.97,
                                part_hors_3km=100 * ph3, part_hors_5km=50 * ph3, couverture_osm_vs_annuaire_2024_25=0.6,
                                fiabilite_osm_province=fia, commune_ancienne=f"COMMUNE FICTIVE {nc_:03d}",
                                province_ancienne=p.province, region_ancienne=p.region,
                                pcode_commune_nouveau=f"BF{nc_:06d}", commune_nouvelle=f"COMMUNE FICTIVE {nc_:03d}",
                                province_nouvelle=p.province, region_nouvelle=p.region, rang_national_part_hors_3km=0,
                                geometrie_geojson=json.dumps(zone)))
                for r in range(int(rng.integers(0, 4))):
                    chef = bool(rng.random() < 0.15)
                    verif = chef or fia == "faible"
                    rng.uniform(0.05, 0.38)  # anciennes coordonnées de la grille : tirages conservés pour
                    rng.uniform(0.05, 0.49)  # garder le flux principal (donc tous les chiffres) inchangé
                    lon, lat = _point_dans(zone, rng_pts)
                    sites.append(dict(pcode_province=p.pcode_province, pcode_commune=f"BF{nc_:06d}",
                                      commune=f"COMMUNE FICTIVE {nc_:03d}", rang_dans_commune=r + 1,
                                      id_localite=len(sites) + 1, localite_site=f"LOCALITE FICTIVE {len(sites) + 1:04d}",
                                      longitude=lon, latitude=lat,
                                      geolocalisation="nom_exact", distance_ecole_actuelle_km=float(rng.uniform(3, 12)),
                                      villages_desservis=int(rng.integers(1, 6)),
                                      enfants_6_11_2030_desservis=int(rng.integers(150, 1500)),
                                      classes_a_prevoir=int(rng.integers(1, 7)), chef_lieu_probable=chef,
                                      villages_desservis_liste="LOCALITE FICTIVE", province=p.province,
                                      couverture_osm_vs_annuaire_2024_25=0.6, fiabilite_osm_province=fia,
                                      a_verifier_sur_terrain=verif, sites_fiables=not verif))
        C = pd.DataFrame(com)
        C["rang_national_part_hors_3km"] = C.part_hors_3km.rank(ascending=False, method="first").astype(int)
        SI = pd.DataFrame(sites).sort_values(["sites_fiables", "enfants_6_11_2030_desservis"], ascending=[False, False])
        SI["rang_national"] = range(1, len(SI) + 1)

        CR = P[["pcode_province", "province", "region"]].copy()
        CR["fermees_2022_05"] = (P.perte * 300).astype(int)
        CR["eleves_affectes_2022_05"] = (P.perte * 40000).astype(int)
        CR["ecoles_primaires_rouvertes_cumul_2026_02"] = (P.perte * 100).astype(int)
        CR["ecoles_primaires_delocalisees_cumul_2026_02"] = (P.perte * 20).astype(int)
        CR["edi_primaire_total_2026_02"] = (P.perte * 5000).astype(int)
        CR["pdi_2024"] = P.perte * 50000
        CR["salles_max_2017_2021"] = smax["TOTAL"].values
        CR["salles_2024_25"] = ref[("salles_classe", "TOTAL")].values
        CR["part_salles_perdues"] = 100 * (1 - CR.salles_2024_25 / CR.salles_max_2017_2021)  # en %

        NO = pd.DataFrame([
            ("eleves_par_classe", "primaire", 50.0, "retenue", "Effectif maximal par classe (fictif)", "Source fictive", ""),
            ("eleves_par_classe", "primaire", 60.0, "sensibilite", "Variante (fictif)", "Choix d'analyse", ""),
            ("eleves_par_classe", "primaire", 65.0, "sensibilite", "Ancien plafond (fictif)", "Source fictive", ""),
            ("eleves_par_enseignant", "primaire", 50.0, "retenue", "Élèves par enseignant (fictif)", "Source fictive", ""),
            ("eleves_par_enseignant", "primaire", 45.0, "sensibilite", "Variante (fictif)", "Choix d'analyse", ""),
            ("eleves_par_enseignant", "primaire", 55.0, "sensibilite", "Variante (fictif)", "Choix d'analyse", ""),
            ("distance_ecole_km", "primaire", 3.0, "retenue_hypothese", "Distance (fictif)", "Hypothèse", ""),
        ], columns=["code", "ordre", "valeur", "statut", "libelle", "source", "reference"])
        HY = pd.DataFrame([("annee_reference", "2024-2025", "Fictif"), ("horizon", "2030-2031", "Fictif"),
                           ("scenario_central", "S2_retour_avant_crise / moyen / normes 50-50", "Fictif")],
                          columns=["hypothese", "valeur", "commentaire"])
        CT = pd.DataFrame([("contrôle fictif 1", "OK", True, ""), ("contrôle fictif 2", "OK", True, ""),
                           ("contrôle fictif 3", "ALERTE", False, "")],
                          columns=["controle", "resultat", "bloquant", "detail"])
        GR = []
        for ir, (cr, rn) in enumerate(P[["code_region", "region"]].drop_duplicates().itertuples(index=False)):
            GR.append(dict(code_region=cr, region=rn, geometrie_geojson=json.dumps(contours_reg[ir])))
        SI = SI.reset_index(drop=True)
        return {"province_annee": PA, "national": N, "redeploiement": pub, "priorite": Q, "robustesse": ROB,
                "province_2030": B, "sensibilite_2030": S, "hypotheses_2030": HY, "crise": CR, "communes": C,
                "implantation": SI, "normes": NO, "controles": CT, "geo_region": pd.DataFrame(GR),
                **_decoupage_2025(P, C, SI)}


SourceDemo = SourceSynthetique
