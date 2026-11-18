"""Géographie du jeu de démonstration : contours administratifs réels, noms et chiffres fictifs."""
import json

from d3dash.demo import TAILLES_REGIONS, SourceSynthetique, _anneaux, _dedans, _point_garanti


def _geoms(df):
    return [json.loads(t) for t in df.geometrie_geojson]


def _sommets(geom):
    return [p for anneau in _anneaux(geom) for p in anneau]


def test_provinces_contours_reels_et_noms_fictifs(source):
    d = source.charger()
    prov = d["priorite"]
    assert len(prov) == 45 == sum(TAILLES_REGIONS)
    assert prov.province.str.match(r"^PROVINCE FICTIVE \d{2}$").all()
    assert prov.pcode_province.str.match(r"^BF00\d{2}$").all()
    geoms = _geoms(prov)
    # 45 contours distincts, et plus détaillés qu'un rectangle (5 sommets)
    assert len({json.dumps(g, sort_keys=True) for g in geoms}) == 45
    assert min(len(_sommets(g)) for g in geoms) > 10
    xs = [p[0] for g in geoms for p in _sommets(g)]
    ys = [p[1] for g in geoms for p in _sommets(g)]
    # emprise du pays (lon -5,5 à 2,4 ; lat 9,4 à 15,1)
    assert -5.6 < min(xs) < -5.3 and 2.2 < max(xs) < 2.6
    assert 9.3 < min(ys) < 9.6 and 14.9 < max(ys) < 15.2


def test_regions_sont_des_contours_dissous(source):
    d = source.charger()
    reg, prov = d["geo_region"], d["priorite"]
    assert len(reg) == len(TAILLES_REGIONS) == 13
    assert reg.region.str.match(r"^REGION FICTIVE \d{2}$").all()
    geoms = {c: g for c, g in zip(reg.code_region, _geoms(reg))}
    # dissous : nettement moins d'anneaux que de provinces (pas une frontière interne par province)
    assert sum(len(_anneaux(g)) for g in geoms.values()) < 20
    # chaque province est bien dans le contour de sa région
    for code_region, geom_prov in zip(prov.code_region, _geoms(prov)):
        x, y = _point_garanti(_anneaux(geom_prov))
        assert _dedans(x, y, _anneaux(geoms[code_region])), code_region


def test_communes_dans_leur_province_et_sites_dans_leur_commune(source):
    d = source.charger()
    prov = {c: json.loads(t) for c, t in zip(d["priorite"].pcode_province, d["priorite"].geometrie_geojson)}
    com = {r.pcode_commune: (json.loads(r.geometrie_geojson), r.pcode_province) for r in d["communes"].itertuples()}
    assert len(com) == 4 * len(prov)
    for geom, pcode in com.values():
        x, y = _point_garanti(_anneaux(geom))
        assert _dedans(x, y, _anneaux(prov[pcode])), pcode
    sites = d["implantation"]
    assert len(sites)
    for s in sites.itertuples():
        geom = com[s.pcode_commune][0]
        assert _dedans(s.longitude, s.latitude, _anneaux(geom)), s.pcode_commune


def test_coordonnees_des_sites_deterministes():
    a = SourceSynthetique().charger()["implantation"]
    b = SourceSynthetique().charger()["implantation"]
    assert a.longitude.tolist() == b.longitude.tolist()
    assert a.latitude.tolist() == b.latitude.tolist()
