"""Configuration lue depuis l'environnement (fichier d'environnement systemd en production).

Aucun secret n'a de valeur par défaut. Les secrets ne sont jamais journalisés.
"""
import os
from dataclasses import dataclass, field

# Nom d'équipe affiché partout (bandeau, navigation, pied de page, exports) : SEUL paramètre à remplacer.
# Nom de l'équipe du Data Challenge, à ne pas confondre avec la société d'un membre (voir « À propos »).
EQUIPE = "EduPrioriteBurkina_MelissaJohn"


def _bool(nom, defaut):
    v = os.environ.get(nom)
    if v is None:
        return defaut
    return v.strip().lower() in ("1", "true", "oui", "yes", "on")


@dataclass(frozen=True)
class Config:
    pg_host: str = field(default_factory=lambda: os.environ.get("DC_EDU_PG_HOST", "127.0.0.1"))
    pg_port: int = field(default_factory=lambda: int(os.environ.get("DC_EDU_PG_PORT", "5432")))
    pg_db: str = field(default_factory=lambda: os.environ.get("DC_EDU_PG_DB", "data_challenge_edu"))
    pg_user: str = field(default_factory=lambda: os.environ.get("DC_EDU_PG_USER", "dc_edu_d3_ro.your-tenant-id"))
    pg_password: str = field(default_factory=lambda: os.environ.get("DC_EDU_PG_PASSWORD", ""), repr=False)
    cache_ttl_s: int = field(default_factory=lambda: int(os.environ.get("DC_EDU_CACHE_TTL", "900")))
    # authentification par code d'accès partagé
    auth_active: bool = field(default_factory=lambda: _bool("DC_EDU_AUTH", True))
    code_hash: str = field(default_factory=lambda: os.environ.get("DC_EDU_CODE_HASH", ""), repr=False)
    # second code, facultatif (accès du jury) : révocable sans toucher au premier ; vide = fonction inactive
    code_hash_jury: str = field(default_factory=lambda: os.environ.get("DC_EDU_CODE_HASH_JURY", ""), repr=False)
    secret_key: str = field(default_factory=lambda: os.environ.get("DC_EDU_SECRET_KEY", ""), repr=False)
    # adresses des proxys inverses locaux dont X-Forwarded-For est cru (vide : aucun, l'en-tête est ignoré)
    proxys_confiance: tuple = field(default_factory=lambda: tuple(
        a.strip() for a in os.environ.get("DC_EDU_PROXYS_CONFIANCE", "").split(",") if a.strip()))
    session_heures: int = field(default_factory=lambda: int(os.environ.get("DC_EDU_SESSION_HEURES", "12")))
    cookie_secure: bool = field(default_factory=lambda: _bool("DC_EDU_COOKIE_SECURE", False))
    max_essais: int = field(default_factory=lambda: int(os.environ.get("DC_EDU_MAX_ESSAIS", "5")))
    # mode démo : données SYNTHÉTIQUES clairement fictives (bandeau « Données fictives »), jamais en production
    demo: bool = field(default_factory=lambda: _bool("DC_EDU_DEMO", False))
    demo_geo: str = field(default_factory=lambda: os.environ.get("DC_EDU_DEMO_GEO", ""))
    fenetre_essais_s: int = field(default_factory=lambda: int(os.environ.get("DC_EDU_FENETRE_ESSAIS", "900")))
