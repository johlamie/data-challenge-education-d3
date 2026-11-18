"""Ouverture d'une fiche province depuis une carte Plotly (partagé par les pages à carte).

Vit dans le kit plutôt que dans une page : la Vue d'ensemble et le Classement ouvrent la même
fiche depuis le même `clickData`, et une page n'importe jamais une autre page.
"""
from dash.exceptions import PreventUpdate


def code_clique(clic):
    """Code de la province cliquée, à partir du `clickData` de Plotly.

    Un clic sur un **remplissage** (`hoveron="fills"`, le cas de toutes les provinces) ne désigne
    aucun point : Plotly renvoie `pointNumber: null` et Dash transmet alors tout le tableau
    `customdata` du tracé (le même code répété) au lieu d'une valeur. La fiche ne s'ouvrait donc
    jamais. On prend la première valeur ; `lien_fiche` valide ensuite le code, inchangé."""
    try:
        code = clic["points"][0]["customdata"]
    except (TypeError, KeyError, IndexError):
        return None
    if isinstance(code, (list, tuple)):
        code = code[0] if code else None
    return code


def lien_fiche(clic):
    """Adresse de la fiche de la province cliquée, ou `PreventUpdate` si le clic ne désigne rien."""
    try:
        code = clic["points"][0]["customdata"]
    except (TypeError, KeyError, IndexError):
        raise PreventUpdate
    if not isinstance(code, str) or not code.startswith("BF"):
        raise PreventUpdate
    return f"/fiche?pcode={code}"


def aller_a_la_fiche(clic):
    """Callback complet d'un clic sur une carte de provinces : code lu, puis adresse de la fiche."""
    return lien_fiche({"points": [{"customdata": code_clique(clic)}]})
