"""Accès aux données : les vues v_d3_dashboard_* et les tables decoupage_2025_* du schéma d3_analyse, via le
rôle lecture seule dc_edu_d3_ro (pooler local, mode transaction).

Les vues de constat (ancien découpage : 45 provinces, 13 régions) et les tables du découpage 2025 (47 provinces,
17 régions ; étape additive d3a_09 / d3a_09b, ce sont des tables simples et non des vues) sont petites (≈ 2,5 Mo
au total, géométries simplifiées comprises) : tout est chargé en mémoire dans le même cache et rafraîchi toutes
les `cache_ttl_s` secondes. Si un rafraîchissement échoue, les données précédentes sont gardées.
"""
import json
import logging
import threading
import time

import pandas as pd

log = logging.getLogger("d3dash.db")

SCHEMA = "d3_analyse"
# clé interne -> (vue, ordre)
VUES = {
    "province_annee": ("v_d3_dashboard_province_annee", "annee_debut, statut, pcode_province"),
    "national": ("v_d3_dashboard_national", "niveau_geo, statut, annee_debut, code_region"),
    "redeploiement": ("v_d3_dashboard_redeploiement", "annee_debut"),
    "priorite": ("v_d3_dashboard_priorite", "rang_priorite"),
    "robustesse": ("v_d3_dashboard_robustesse", "variante, rang"),
    "province_2030": ("v_d3_dashboard_province_2030", "scenario, variante_population, statut, pcode_province"),
    "sensibilite_2030": ("v_d3_dashboard_sensibilite_2030",
                         "scenario, variante_population, statut, norme_eleves_par_classe, norme_eleves_par_enseignant"),
    "hypotheses_2030": ("v_d3_dashboard_hypotheses_2030", None),
    "crise": ("v_d3_dashboard_crise", "pcode_province"),
    "communes": ("v_d3_dashboard_communes", "pcode_commune"),
    "implantation": ("v_d3_dashboard_implantation", "rang_national"),
    "normes": ("v_d3_dashboard_normes", "code, valeur"),
    "controles": ("v_d3_dashboard_controles", None),
    "geo_region": ("v_d3_dashboard_geo_region", "code_region"),
}
# découpage administratif 2025 (tables, pas des vues) : seules les pages de projection s'en servent
TABLES = {
    "decoupage_passage": ("decoupage_2025_passage", "pcode_province, pcode_province_2025"),
    "decoupage_geo_provinces": ("decoupage_2025_geo_provinces", "pcode_province_2025"),
    "decoupage_geo_regions": ("decoupage_2025_geo_regions", "code_region_2025"),
    "decoupage_communes": ("decoupage_2025_communes", "pcode_commune_2025"),
    "decoupage_sites": ("decoupage_2025_sites", "rang_national"),
}
RELATIONS = {**VUES, **TABLES}
AVEC_GEOMETRIE = ("priorite", "communes", "geo_region", "decoupage_geo_provinces", "decoupage_geo_regions",
                  "decoupage_communes")
TEXTE = {"pcode_province", "pcode_commune", "code_region", "id_localite", "annee_scolaire", "pcode_commune_nouveau",
         "pcode_province_2025", "pcode_commune_2025", "code_region_2025"}


def sql_relation(cle):
    relation, ordre = RELATIONS[cle]
    return f'SELECT * FROM "{SCHEMA}".{relation}' + (f" ORDER BY {ordre}" if ordre else "")


class SourcePostgres:
    """Exécute les requêtes en lecture seule. Compatible pooler en mode transaction (pas de requêtes préparées)."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.derniere_erreur_decoupage = None  # type de la dernière erreur sur les tables du découpage 2025

    def _connexion(self):
        import psycopg
        return psycopg.connect(host=self.cfg.pg_host, port=self.cfg.pg_port, dbname=self.cfg.pg_db,
                               user=self.cfg.pg_user, password=self.cfg.pg_password, connect_timeout=10,
                               autocommit=True, prepare_threshold=None, application_name="dc-edu-d3-dashboard")

    def _lire(self, cur, cle):
        cur.execute(sql_relation(cle))
        return pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])

    def charger(self):
        """Les vues de constat d'abord, puis les tables du découpage 2025 dans une étape séparée.

        Les tables `decoupage_2025_*` viennent d'une étape additive du pipeline (d3a_09b puis d3a_09) : si
        l'une manque ou n'est pas accordée en SELECT au rôle lecture seule, les cinq sont absentes du résultat
        (tout ou rien : un découpage partiel donnerait des pages incohérentes). Les pages de constat continuent
        de fonctionner ; seules les pages de projection affichent leur bloc « données indisponibles » (via
        `decoupage.DecoupageIndisponible`).
        """
        out = {}
        with self._connexion() as cx, cx.cursor() as cur:
            for cle in VUES:
                out[cle] = self._lire(cur, cle)
        self.derniere_erreur_decoupage = None
        try:
            with self._connexion() as cx, cx.cursor() as cur:  # connexion à part : échec sans effet sur les vues
                for cle in TABLES:
                    out[cle] = self._lire(cur, cle)
        except Exception as e:
            for cle in TABLES:
                out.pop(cle, None)
            self.derniere_erreur_decoupage = type(e).__name__
            log.error("tables du decoupage 2025 indisponibles : %s", type(e).__name__)
        return out


def _normaliser(df):
    """Colonnes numériques (Decimal, entiers nullables, booléens) en float ; identifiants et libellés en texte."""
    df = df.copy()
    for c in df.columns:
        if c in TEXTE or c == "geometrie_geojson":
            continue
        s = df[c]
        if s.dtype == object:
            nn = s.dropna()
            if not len(nn):
                continue
            if isinstance(nn.iloc[0], str):
                conv = pd.to_numeric(nn, errors="coerce")
                if conv.notna().all() and c not in ("valeur", "ordre"):  # textes numériques (types DSS)
                    df[c] = pd.to_numeric(s, errors="coerce").astype(float)
                continue
            df[c] = pd.to_numeric(s.map(lambda x: float(x) if x is not None else None), errors="coerce").astype(float)
        elif pd.api.types.is_bool_dtype(s) or (pd.api.types.is_numeric_dtype(s) and str(s.dtype) != "float64"):
            df[c] = s.astype(float)
    if "annee_debut" in df.columns:
        df["annee_debut"] = df["annee_debut"].astype(int)
    return df


def preparer(brut):
    d = {k: _normaliser(v) for k, v in brut.items()}
    for k in AVEC_GEOMETRIE:
        if k not in d:  # relation absente (découpage 2025 indisponible)
            continue
        g = d[k]
        g["geometrie"] = g["geometrie_geojson"].map(lambda t: json.loads(t) if isinstance(t, str) else None)
        d[k] = g.drop(columns=["geometrie_geojson"])
    return d


class Donnees:
    """Cache mémoire thread-safe des vues et des tables du tableau de bord."""

    def __init__(self, source, ttl_s=900):
        self.source = source
        self.ttl_s = ttl_s
        self._verrou = threading.Lock()
        self._d = None
        self._t = 0.0
        self.derniere_erreur = None

    def _rafraichir(self):
        d = preparer(self.source.charger())
        if self._d is not None:
            # découpage 2025 devenu illisible : on garde les tables déjà chargées, comme pour les vues
            for cle in TABLES:
                if cle not in d and cle in self._d:
                    d[cle] = self._d[cle]
        self._d = d
        self._t = time.time()
        self.derniere_erreur = None

    def get(self):
        if self._d is not None and time.time() - self._t < self.ttl_s:
            return self._d
        with self._verrou:
            if self._d is None or time.time() - self._t >= self.ttl_s:
                try:
                    self._rafraichir()
                except Exception as e:  # garder les données précédentes
                    self.derniere_erreur = type(e).__name__
                    log.error("rafraichissement impossible : %s", type(e).__name__)
                    if self._d is None:
                        raise
                    self._t = time.time() - self.ttl_s + 60  # nouvel essai dans 60 s
        return self._d

    def __getitem__(self, cle):
        return self.get()[cle]

    @property
    def decoupage_disponible(self):
        """Les cinq tables du découpage 2025 sont-elles chargées ? (sinon, seules les pages de projection
        sont en panne : voir `decoupage.DecoupageIndisponible`)."""
        d = self.get()
        return all(cle in d for cle in TABLES)

    @property
    def erreur_decoupage(self):
        """Type de la dernière erreur rencontrée sur les tables du découpage 2025, sans détail (journal)."""
        return getattr(self.source, "derniere_erreur_decoupage", None)

    @property
    def horodatage(self):
        return self._t


_DONNEES = None


def installer(donnees):
    global _DONNEES
    _DONNEES = donnees


def donnees():
    if _DONNEES is None:
        raise RuntimeError("source de données non installée")
    return _DONNEES
