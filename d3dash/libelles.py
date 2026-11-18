"""Libellés d'interface partagés par plusieurs écrans — un seul endroit, aucune dépendance.

`meta.py` garde les libellés **techniques** (clés de la base, valeurs des sélecteurs) ; ce module
porte les formulations **lisibles par un non-initié** qu'au moins deux écrans affichent. Les clés
sont celles de `meta.SCENARIOS` : les valeurs des sélecteurs, les callbacks et les tests ne changent
pas, seule l'étiquette lue change.

Règle : un libellé de scénario ne se réécrit jamais dans une page ni dans une figure ; on importe
`SCENARIOS_CLAIRS` (texte complet) ou `SCENARIOS_AXE` (variante courte sur deux lignes, pour l'axe
d'un graphique où un libellé complet se chevaucherait). Les deux portent le même code (S1, S2,
S2b, S3) et sont vérifiés l'un par rapport à l'autre dans les tests.
"""

# Scénarios 2030 en langage courant, le code technique entre parenthèses.
SCENARIOS_CLAIRS = {
    "S1_tendanciel": "Si rien ne change (S1)",
    "S2_retour_avant_crise": "Retour au taux d'avant-crise (S2, central)",
    "S2b_retour_sans_reouverture": "Même taux, sans réouverture des salles (S2b)",
    "S3_universel": "Tous les enfants scolarisés (S3)",
}

# Variante d'axe : même quatre scénarios, en deux lignes courtes (`<br>` est lu par Plotly).
# Un libellé complet se chevaucherait sous quatre barres groupées dans un panneau de 420 px.
SCENARIOS_AXE = {
    "S1_tendanciel": "S1<br>rien ne change",
    "S2_retour_avant_crise": "S2 central<br>avant-crise",
    "S2b_retour_sans_reouverture": "S2b<br>sans rouvrir",
    "S3_universel": "S3<br>tous scolarisés",
}


def code_scenario(cle):
    """Code technique écrit dans le libellé clair (« S2, central » → « S2 »)."""
    lib = SCENARIOS_CLAIRS.get(cle, "")
    if "(" not in lib:
        return ""
    return lib[lib.rfind("(") + 1:lib.rfind(")")].split(",")[0].strip()


def pluriel(n, singulier, pluriel_=None):
    """Accord du français : 0 et 1 au singulier, 2 et plus au pluriel (catégorie « one » de fr).

    Avec un seul mot, le pluriel est formé en ajoutant « s ».
    """
    if pluriel_ is None:
        pluriel_ = singulier + "s"
    try:
        return singulier if abs(n) < 2 else pluriel_
    except TypeError:
        return pluriel_
