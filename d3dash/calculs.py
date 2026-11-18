"""Calculs purs (sans Dash) à partir des vues chargées : chiffres clés, classement, besoins 2030 recalculés."""
import numpy as np
import pandas as pd

from .meta import (ANNEE_REF, CLASSES, MESURES, MESURES_ANNUELLES, SCENARIO_CENTRAL, SCENARIOS, fmt_mesure,
                   fmt_nombre, nom_propre)


def national(d, annee, statut):
    n = d["national"]
    s = n[(n.niveau_geo == "national") & (n.statut == statut) & (n.annee_debut == annee)]
    return s.iloc[0] if len(s) else None


def _val(r, c):
    return None if r is None or c not in r or r[c] != r[c] else float(r[c])


def delta(d, annee, statut, col):
    a, b = national(d, annee, statut), national(d, annee - 1, statut)
    va, vb = _val(a, col), _val(b, col)
    return None if va is None or vb is None else va - vb


def sensibilite(d, scenario=SCENARIO_CENTRAL, pop="moyen", statut="TOTAL", nc=50, nm=50):
    s = d["sensibilite_2030"]
    s = s[(s.scenario == scenario) & (s.variante_population == pop) & (s.statut == statut)
          & (s.norme_eleves_par_classe == nc) & (s.norme_eleves_par_enseignant == nm)]
    return s.iloc[0] if len(s) else None


def redeploiement(d, annee=ANNEE_REF):
    r = d["redeploiement"]
    r = r[r.annee_debut == annee]
    return r.iloc[0] if len(r) else None


def kpis(d, annee=ANNEE_REF):
    """Six chiffres clés nationaux (public sauf TBS et 2030 : ensemble public + privé)."""
    pub, tot = national(d, annee, "PUBLIC"), national(d, annee, "TOTAL")
    s = sensibilite(d)
    red = redeploiement(d, annee)
    dep = d["province_annee"]
    dep = dep[(dep.annee_debut == annee) & (dep.statut == "PUBLIC")]
    serie = d["national"]
    serie = serie[(serie.niveau_geo == "national") & (serie.statut == "PUBLIC")].sort_values("annee_debut")
    return {
        "epm": _val(pub, "eleves_par_maitre"), "epm_delta": delta(d, annee, "PUBLIC", "eleves_par_maitre"),
        "eps": _val(pub, "eleves_par_salle"), "eps_delta": delta(d, annee, "PUBLIC", "eleves_par_salle"),
        "def_ens": _val(pub, "deficit_enseignants"), "def_ens_delta": delta(d, annee, "PUBLIC", "deficit_enseignants"),
        "def_ens_record": bool(len(serie) and _val(pub, "deficit_enseignants") is not None
                               and _val(pub, "deficit_enseignants") >= serie.deficit_enseignants.max()),
        "def_salles": _val(pub, "deficit_salles"), "def_salles_delta": delta(d, annee, "PUBLIC", "deficit_salles"),
        "prov_def_ens": int((dep.deficit_enseignants > 0).sum()), "prov_def_salles": int((dep.deficit_salles > 0).sum()),
        "redeployables": _val(red, "enseignants_redeployables"), "recrutement": _val(red, "recrutement_net_necessaire"),
        "s2030": _val(s, "salles_a_construire_2030"), "e2030": _val(s, "enseignants_supplementaires_2030"),
        "tbs": _val(tot, "tbs_t"), "tbs_delta": delta(d, annee, "TOTAL", "tbs_t"),
        "tbs_2017": _val(national(d, 2017, "TOTAL"), "tbs_t"),
        "eleves": _val(tot, "eleves"),
    }


def geoms_provinces(d):
    p = d["priorite"]
    return pd.DataFrame({"code": p.pcode_province, "nom": p.province.map(nom_propre), "code_region": p.code_region,
                         "geometrie": p.geometrie})


def table_provinces(d, annee=ANNEE_REF, statut="PUBLIC"):
    """Une ligne par province : priorité (2024-25), ratios et déficits (année et statut choisis), 2030 (S2)."""
    p = d["priorite"].copy()
    pa = d["province_annee"]
    pa = pa[(pa.annee_debut == annee) & (pa.statut == statut)].set_index("pcode_province")
    t = p[["pcode_province", "province", "code_region", "region", "score_priorite", "rang_priorite", "classe_priorite",
           "salles_a_construire_2030_S2", "enseignants_supplementaires_2030_S2", "acces_part_hors_3km",
           "fiabilite_osm_province"]].copy()
    t = t.rename(columns={"salles_a_construire_2030_S2": "salles_a_construire_2030",
                          "enseignants_supplementaires_2030_S2": "enseignants_2030"})
    for c in ("eleves_par_maitre", "eleves_par_salle", "deficit_enseignants", "deficit_salles", "eleves", "maitres",
              "salles_classe", "excedent_enseignants"):
        t[c] = t.pcode_province.map(pa[c]) if c in pa else np.nan
    t["province_nom"] = t.province.map(nom_propre)
    t["region_nom"] = t.region.map(nom_propre)
    t["classe"] = t.classe_priorite.map(lambda c: CLASSES.get(c, ("–", ""))[0])
    return t


def classement(d, mesure="score_priorite", annee=ANNEE_REF, statut="PUBLIC"):
    t = table_provinces(d, annee if mesure in MESURES_ANNUELLES else ANNEE_REF, statut)
    t["valeur"] = t[mesure]
    t["rang"] = t.valeur.rank(ascending=MESURES[mesure]["sens"] < 0, method="min")
    t.loc[t.valeur.isna(), "rang"] = np.nan
    return t.sort_values(["rang", "province"], na_position="last").reset_index(drop=True)


def survol_province(r, mesure=None):
    lignes = [f"<b>{r['province_nom']}</b> · {r['region_nom']}"]
    if mesure and mesure != "score_priorite":
        lignes.append(f"{MESURES[mesure]['label']} : {fmt_mesure(r[mesure], mesure)}")
    lignes.append(f"Score de priorité : {fmt_nombre(r['score_priorite'])} / 100 (rang {fmt_nombre(r['rang_priorite'])}, "
                  f"{r['classe']})")
    lignes.append(f"Élèves par maître : {fmt_nombre(r['eleves_par_maitre'], 1)} · par salle : "
                  f"{fmt_nombre(r['eleves_par_salle'], 1)}")
    return "<br>".join(lignes)


# ---- besoins 2030 -------------------------------------------------------------------------------------------
def besoins_province(d, scenario=SCENARIO_CENTRAL, pop="moyen", statut="TOTAL", nc=50, nm=50):
    """Recalcule les besoins par province pour des normes quelconques, avec les règles de l'analyse :
    besoin = ⌈élèves 2030 / norme⌉ ; à construire = max(0, besoin − salles 2024-25 − salles réouvrables) ;
    enseignants supplémentaires = max(0, ⌈élèves 2030 / norme⌉ − enseignants 2024-25)."""
    p = d["province_2030"]
    b = p[(p.scenario == scenario) & (p.variante_population == pop) & (p.statut == statut)].copy()
    b["norme_eleves_par_classe"], b["norme_eleves_par_enseignant"] = float(nc), float(nm)
    b["besoin_salles_2030"] = np.ceil(b.eleves_2030 / nc)
    b["besoin_enseignants_2030"] = np.ceil(b.eleves_2030 / nm)
    b["salles_a_construire_2030"] = (b.besoin_salles_2030 - b.salles_2024_25 - b.salles_reouvrables).clip(lower=0)
    b["enseignants_supplementaires_2030"] = (b.besoin_enseignants_2030 - b.enseignants_2024_25).clip(lower=0)
    b["salles_par_an"] = b.salles_a_construire_2030 / 6
    b["enseignants_par_an"] = b.enseignants_supplementaires_2030 / 6
    b["province_nom"] = b.province.map(nom_propre)
    b["region_nom"] = b.region.map(nom_propre)
    b["salles_pour_100"] = 100 * b.salles_a_construire_2030 / b.salles_2024_25.where(b.salles_2024_25 > 0)
    return b.sort_values("salles_a_construire_2030", ascending=False).reset_index(drop=True)


def besoins_par_scenario(d, pop="moyen", statut="TOTAL", nc=50, nm=50):
    s = d["sensibilite_2030"]
    s = s[(s.variante_population == pop) & (s.statut == statut) & (s.norme_eleves_par_classe == nc)
          & (s.norme_eleves_par_enseignant == nm)].copy()
    s["ordre"] = s.scenario.map({k: i for i, k in enumerate(SCENARIOS)})
    s["libelle"] = s.scenario.map({"S1_tendanciel": "S1 tendanciel", "S2_retour_avant_crise": "S2 central",
                                   "S2b_retour_sans_reouverture": "S2b sans réouverture",
                                   "S3_universel": "S3 universel"})
    return s.sort_values("ordre").reset_index(drop=True)


# ---- implantation ---------------------------------------------------------------------------------------------
def communes_carte(d):
    from .figures import centroide
    c = d["communes"].copy()
    c["part100"] = c.part_hors_3km  # déjà en % (0-100)
    cxy = c.geometrie.map(centroide)
    c["cx"], c["cy"] = cxy.map(lambda t: t[0]), cxy.map(lambda t: t[1])
    c["survol"] = [f"<b>{nom_propre(a)}</b> · {nom_propre(b)}<br>Enfants de 6-11 ans à plus de 3 km : "
                   f"{fmt_nombre(p, 0)} %<br>Distance médiane à l'école : {fmt_nombre(m, 1)} km<br>"
                   f"Carte des écoles : fiabilité {f}"
                   for a, b, p, m, f in zip(c.commune_ancienne, c.province_ancienne, c.part100, c.distance_mediane_km,
                                            c.fiabilite_osm_province)]
    return c


def sites(d, pcode=None, fiables_seulement=False):
    s = d["implantation"].copy()
    if pcode:
        s = s[s.pcode_province == pcode]
    if fiables_seulement:
        s = s[s.sites_fiables == 1]
    s["survol"] = [f"<b>{nom_propre(l)}</b> · {nom_propre(c)} ({nom_propre(p)})<br>"
                   f"Enfants de 6-11 ans servis en 2030 : {fmt_nombre(e)}<br>Classes à prévoir : {fmt_nombre(k)}<br>"
                   f"École connue la plus proche : {fmt_nombre(dist, 1)} km<br>"
                   + ("Site fiable" if f == 1 else "À vérifier sur le terrain")
                   for l, c, p, e, k, dist, f in zip(s.localite_site, s.commune, s.province, s.enfants_6_11_2030_desservis,
                                                     s.classes_a_prevoir, s.distance_ecole_actuelle_km, s.sites_fiables)]
    return s
