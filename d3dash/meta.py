"""Libellés, listes de choix et formats d'affichage (français)."""
from .config import EQUIPE  # noqa: F401  (nom d'équipe : paramètre unique défini dans config.py)

ANNEES = list(range(2017, 2025))
ANNEE_REF = 2024
NORME_CLASSE = 50       # élèves par classe (arrêté 2020-186/MENAPLN/SG/DGESS)
NORME_ENSEIGNANT = 50   # élèves par enseignant (DGESS, CNS565 p. 34)
NORMES_CLASSE = [50, 60, 65]
NORMES_ENSEIGNANT = [45, 50, 55]
DISTANCE_KM = 3

# Mentions de découpage administratif : deux textes, et deux seulement.
# Les pages de constat lisent les annuaires (45 provinces), les pages de projection le découpage
# de 2025 (47 provinces) ; une page n'en écrit jamais un troisième.
# L'apostrophe est typographique (U+2019) : la mention est un texte fixe, repris mot pour mot et
# caractère pour caractère.
DECOUPAGE_CONSTAT = "Données 2017-2025 · découpage d’avant 2025 (45 provinces)"
DECOUPAGE_2025 = "Projection 2030 · découpage 2025 (47 provinces)"

STATUTS = {"PUBLIC": "Public", "TOTAL": "Public + privé"}
SCENARIOS = {"S1_tendanciel": "S1 · tendanciel",
             "S2_retour_avant_crise": "S2 · retour à l'avant-crise (central)",
             "S2b_retour_sans_reouverture": "S2b · retour sans réouverture des salles",
             "S3_universel": "S3 · scolarisation universelle"}
SCENARIOS_COURTS = {"S1_tendanciel": "S1", "S2_retour_avant_crise": "S2", "S2b_retour_sans_reouverture": "S2b",
                    "S3_universel": "S3"}
SCENARIO_CENTRAL = "S2_retour_avant_crise"
POPULATIONS = {"bas": "Basse", "moyen": "Moyenne (centrale)", "haut": "Haute"}
CLASSES = {"P1 priorite robuste": ("P1", "Priorité robuste"),
           "P2 priorite probable": ("P2", "Priorité probable"),
           "P3 a surveiller": ("P3", "À surveiller")}
FIABILITES = {"bonne": "Bonne", "moyenne": "Moyenne", "faible": "Faible"}

# mesures de classement et de carte (province) : libellé, format, sens (1 = plus haut = plus préoccupant)
MESURES = {
    "score_priorite": dict(label="Score de priorité", court="Score", dec=0, unite="/ 100", sens=1),
    "eleves_par_maitre": dict(label="Élèves par maître", court="Élèves/maître", dec=1, unite="", sens=1),
    "eleves_par_salle": dict(label="Élèves par salle", court="Élèves/salle", dec=1, unite="", sens=1),
    "deficit_enseignants": dict(label="Enseignants manquants", court="Ens. manquants", dec=0, unite="", sens=1),
    "deficit_salles": dict(label="Salles manquantes", court="Salles manquantes", dec=0, unite="", sens=1),
    "salles_a_construire_2030": dict(label="Salles à construire d'ici 2030", court="Salles 2030", dec=0, unite="",
                                     sens=1),
    "acces_part_hors_3km": dict(label="Enfants à plus de 3 km d'une école", court="> 3 km", dec=0, unite="%", sens=1),
}
# mesures qui dépendent de l'année et du statut (les autres sont calculées pour 2024-2025)
MESURES_ANNUELLES = ("eleves_par_maitre", "eleves_par_salle", "deficit_enseignants", "deficit_salles")


def annee_scolaire(a):
    a = int(a)
    return f"{a}-{a + 1}"


def nom_propre(s):
    """« BOUCLE DU MOUHOUN » → « Boucle du Mouhoun » (les noms déjà en casse mixte sont gardés)."""
    if not isinstance(s, str) or not s.isupper():
        return s
    t = s.title()
    for w in (" Du ", " De ", " Des ", " La ", " Le ", " Les ", " Et ", " En "):
        t = t.replace(w, w.lower())
    return t


def manque(v):
    return v is None or v != v


def fmt_nombre(v, dec=0):
    if manque(v):
        return "n.d."
    return format(float(v), f",.{dec}f").replace(",", "\u202f").replace(".", ",")


def fmt_signe(v, dec=0):
    if manque(v):
        return "n.d."
    return ("+" if v > 0 else ("−" if v < 0 else "")) + fmt_nombre(abs(v), dec)


def fmt_pct(v, dec=0, fraction=False):
    if manque(v):
        return "n.d."
    return fmt_nombre(100 * v if fraction else v, dec) + "\u202f%"


def fmt_mesure(v, cle):
    m = MESURES.get(cle, {})
    if m.get("unite") == "%":
        return fmt_pct(v, m.get("dec", 0))
    return fmt_nombre(v, m.get("dec", 0))


def classe_courte(c):
    return CLASSES.get(c, ("–", "n.d."))[0]
