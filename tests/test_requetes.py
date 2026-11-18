"""Requêtes : uniquement des SELECT sur les vues v_d3_dashboard_* et les tables decoupage_2025_* du schéma
d3_analyse."""
from d3dash import db


def test_requetes_lecture_seule():
    for cle in db.RELATIONS:
        sql = db.sql_relation(cle)
        prefixe = 'v_d3_dashboard_' if cle in db.VUES else 'decoupage_2025_'
        assert sql.startswith(f'SELECT * FROM "d3_analyse".{prefixe}')
        assert ";" not in sql
    assert set(db.VUES) | set(db.TABLES) == set(db.RELATIONS)


def test_schema_synthetique_complet(source):
    brut = source.charger()
    assert set(brut) == set(db.RELATIONS)
    d = db.preparer(brut)
    for k in db.AVEC_GEOMETRIE:
        assert "geometrie" in d[k] and d[k].geometrie.notna().all()


def test_preparation_sans_les_tables_du_decoupage(source):
    """Découpage 2025 illisible : les vues de constat restent préparables (géométries comprises)."""
    brut = {k: v for k, v in source.charger().items() if k not in db.TABLES}
    d = db.preparer(brut)
    assert set(d) == set(db.VUES)
    for k in db.AVEC_GEOMETRIE:
        if k in db.VUES:
            assert d[k].geometrie.notna().all()
