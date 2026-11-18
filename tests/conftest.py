"""Jeu de données SYNTHÉTIQUE (aucune donnée réelle) reproduisant le schéma des vues v_d3_dashboard_*."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from d3dash import db  # noqa: E402

from d3dash.demo import SourceSynthetique  # noqa: E402,F401  (jeu synthétique partagé avec le mode démo)


@pytest.fixture(scope="session")
def source():
    return SourceSynthetique()


@pytest.fixture()
def donnees(source):
    d = db.Donnees(source, ttl_s=3600)
    db.installer(d)
    return d
