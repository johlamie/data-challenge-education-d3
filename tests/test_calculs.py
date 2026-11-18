"""Calculs : chiffres clés, classement, recalcul des besoins 2030 pour d'autres normes."""
import numpy as np
import pytest

from d3dash import calculs as C


def test_kpis(donnees):
    k = C.kpis(donnees)
    assert k["epm"] > 0 and k["def_ens"] >= 0 and k["s2030"] > 0
    assert 0 <= k["prov_def_salles"] <= 45


@pytest.mark.parametrize("nc,nm", [(50, 50), (60, 45), (65, 55)])
@pytest.mark.parametrize("statut", ["TOTAL", "PUBLIC"])
def test_besoins_recalcules_egalent_la_sensibilite(donnees, nc, nm, statut):
    for sc in ("S1_tendanciel", "S2_retour_avant_crise", "S3_universel"):
        b = C.besoins_province(donnees, sc, "moyen", statut, nc, nm)
        s = C.sensibilite(donnees, sc, "moyen", statut, nc, nm)
        assert b.salles_a_construire_2030.sum() == pytest.approx(s.salles_a_construire_2030)
        assert b.enseignants_supplementaires_2030.sum() == pytest.approx(s.enseignants_supplementaires_2030)


def test_besoins_normes_de_base_egalent_la_vue_province(donnees):
    b = C.besoins_province(donnees).set_index("pcode_province")
    p = donnees["province_2030"]
    p = p[(p.scenario == "S2_retour_avant_crise") & (p.variante_population == "moyen") & (p.statut == "TOTAL")]
    p = p.set_index("pcode_province")
    assert np.allclose(b.loc[p.index, "salles_a_construire_2030"], p.salles_a_construire_2030)


def test_classement_ordre(donnees):
    t = C.classement(donnees, "score_priorite")
    assert list(t.rang_priorite.head(5)) == sorted(t.rang_priorite.head(5))
    t = C.classement(donnees, "acces_part_hors_3km")
    v = t.valeur.dropna().tolist()
    assert v == sorted(v, reverse=True)


def test_communes_et_sites(donnees):
    c = C.communes_carte(donnees)
    assert c.cx.notna().all() and c.part100.between(0, 100).all()
    s = C.sites(donnees, fiables_seulement=True)
    assert (s.sites_fiables == 1).all()
