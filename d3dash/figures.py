"""Figures Plotly entièrement hors ligne (partie « kit » du design, avec `composants.py`).

Les cartes sont dessinées comme des polygones remplis sur des axes cartésiens (projection équirectangulaire
corrigée de la latitude) : aucune tuile, aucun topojson ni fichier distant n'est chargé par le navigateur.

Jetons : les valeurs ci-dessous reprennent `assets/tokens.css` (Plotly ne lit pas les variables CSS).
Toute modification doit être faite **des deux côtés**. Une seule rampe séquentielle ocre à 5 classes pour
toutes les cartes ; le bleu `--primary` ne sert qu'à la sélection. Les `dash_table.DataTable`
des pages reprennent eux aussi ces constantes (ENCRE, GRIS, BORDURE, MUTED, POLICE_UI, POLICE_CHIFFRE) :
aucune valeur de jeton n'est retapée dans une page.
"""
import math

import numpy as np
import plotly.graph_objects as go

from .libelles import SCENARIOS_AXE
from .meta import NORME_CLASSE, NORME_ENSEIGNANT, fmt_nombre

# ---- jetons (miroir de assets/tokens.css) --------------------------------------------------------------------
ENCRE = "#16222E"
GRIS = "#53606D"
BLANC = "#FFFFFF"
BORDURE = "#D8DEE6"
BORDURE_FAIBLE = "#E8ECF1"
MUTED = "#F3F5F8"             # --muted : fond de la ligne de filtre d'un DataTable
BLEU = "#1D3F6E"              # --primary : sélection uniquement
BLEU_REGION = "#A8C3E2"       # --primary-region
GRIS_CARTE = "#E4E8ED"        # --gris-carte
TRAIT_REGION = "#46525E"
GRIS_ND = "#DDE2E8"           # --carte-nd
ATTENTION = "#B45309"         # --statut-attention
PISTE = "#E4E9EF"             # --piste : fond de piste d'une barre
PISTE_PLEINE = "#8D99A6"
SERIES = [ENCRE, "#B36C16", GRIS]
# rampe choroplèthe : 5 classes, mono-teinte ocre, luminance strictement décroissante
RAMPE = ["#FBEFDA", "#F0CD93", "#DC9F46", "#B36C16", "#703802"]

# polices (miroir de --police-ui et --police-chiffre) : les composants Dash qui ne lisent pas les
# variables CSS (DataTable) les reprennent ici plutôt que de retaper la pile de polices
POLICE_UI = "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
POLICE_CHIFFRE = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
POLICE = dict(family=POLICE_UI, size=13, color=ENCRE)
CONFIG = {"displaylogo": False, "responsive": True, "scrollZoom": False, "showLink": False, "showSendToCloud": False,
          "showEditInChartStudio": False,
          "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d", "toggleSpikelines",
                                     "hoverClosestCartesian", "hoverCompareCartesian", "sendDataToCloud"],
          "toImageButtonOptions": {"format": "png", "scale": 2}, "locale": "fr"}
# cartes : ni déplacement ni zoom (le pays reste cadré) ; double-clic = recadrage ; survol actif
CONFIG_CARTE = {**CONFIG, "scrollZoom": False, "doubleClick": "reset", "displayModeBar": False}
# carte qui se déplace et qui zoome (Implantation : situer un site) : molette, pincement,
# glissement, double-clic pour recadrer. La barre d'outils Plotly reste **masquée** — ce serait un
# second jeu d'icônes ; les trois boutons du kit sont le chemin visible.
CONFIG_CARTE_ZOOM = {**CONFIG, "scrollZoom": True, "doubleClick": "reset", "displayModeBar": False}
COS_LAT = math.cos(math.radians(12.3))  # latitude moyenne du Burkina Faso
SURVOL = dict(bgcolor=BLANC, bordercolor=BORDURE, font=dict(size=13, color=ENCRE, family=POLICE["family"]),
              namelength=-1, align="left")


# ---- géométrie (pur Python, aucune dépendance géospatiale) ----------------------------------------------------
def _anneaux(geom):
    """Liste des x, y (séparés par None) d'une géométrie Polygon ou MultiPolygon GeoJSON."""
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    xs, ys = [], []
    for poly in polys:
        for ring in poly:
            xs.extend(p[0] for p in ring)
            ys.extend(p[1] for p in ring)
            xs.append(None)
            ys.append(None)
    return xs, ys


def _listes_anneaux(geom):
    """Anneaux (extérieurs et trous) sous forme de listes de points."""
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    return [anneau for poly in polys for anneau in poly]


def _intersections(anneaux, v, axe=1):
    """Abscisses (axe=1 : balayage horizontal à y=v) ou ordonnées (axe=0) des croisements du contour."""
    a, b = (0, 1) if axe == 1 else (1, 0)
    xs = []
    for anneau in anneaux:
        for i in range(len(anneau)):
            p1, p2 = anneau[i - 1], anneau[i]
            u1, u2 = p1[b], p2[b]
            if (u1 > v) != (u2 > v):
                xs.append(p1[a] + (v - u1) * (p2[a] - p1[a]) / (u2 - u1))
    xs.sort()
    return xs


def centroide(geom):
    """Point **intérieur garanti** du polygone (milieu du plus long segment d'une ligne de balayage).

    La moyenne des sommets tombe hors du polygone dès qu'il est concave ou en plusieurs morceaux :
    l'ancre de survol décrivait alors une commune voisine. Repli sur la moyenne des sommets pour une
    géométrie dégénérée. Renvoie (x, y) comme avant.
    """
    anneaux = _listes_anneaux(geom)
    ys = sorted({p[1] for anneau in anneaux for p in anneau})
    meilleur, point = 0.0, None
    for ya, yb in zip(ys, ys[1:]):
        y = (ya + yb) / 2
        xs = _intersections(anneaux, y, axe=1)
        for a, b in zip(xs[0::2], xs[1::2]):
            if b - a > meilleur:
                meilleur, point = b - a, ((a + b) / 2, y)
    if point is not None:
        return point
    pts = [p for anneau in anneaux for p in anneau]
    if not pts:
        return (None, None)
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def _demi_espace(geom, x, y):
    """Demi-largeur et demi-hauteur libres au point intérieur (x, y), dans l'unité des coordonnées."""
    anneaux = _listes_anneaux(geom)
    dl = dh = 0.0
    xs = _intersections(anneaux, y, axe=1)
    for a, b in zip(xs[0::2], xs[1::2]):
        if a <= x <= b:
            dl = max(dl, min(x - a, b - x))
    ys = _intersections(anneaux, x, axe=0)
    for a, b in zip(ys[0::2], ys[1::2]):
        if a <= y <= b:
            dh = max(dh, min(y - a, b - y))
    return dl, dh


def emprise(geoms, marge=0.02):
    """Emprise [xmin, xmax], [ymin, ymax] des géométries (cadrage sur le pays), avec une petite marge."""
    xs, ys = [], []
    for geom in geoms:
        a, b = _anneaux(geom)
        xs += [x for x in a if x is not None]
        ys += [y for y in b if y is not None]
    if not xs:
        return None, None
    dx, dy = (max(xs) - min(xs)) * marge or 0.1, (max(ys) - min(ys)) * marge or 0.1
    return [min(xs) - dx, max(xs) + dx], [min(ys) - dy, max(ys) + dy]


def verrouiller(fig, geoms):
    """Carte fixe : cadrée sur l'emprise du pays, sans glisser ni zoomer (fixedrange), survol conservé."""
    rx, ry = emprise(geoms)
    fig.update_layout(dragmode=False)
    fig.update_xaxes(fixedrange=True, range=rx, autorange=False if rx else True)
    fig.update_yaxes(fixedrange=True, range=ry, autorange=False if ry else True)
    return fig


ZOOM_MINI_DEG = 0.05   # ≈ 5 km de longitude : un niveau de zoom absurde reste impossible


def deverrouiller(fig, geoms, revision="BF"):
    """Carte qui se déplace et qui zoome, cadrée au départ sur l'emprise des géométries.

    `revision` (`uirevision`) : le code de la province filtrée, ou « BF » pour tout le pays — le
    zoom de l'utilisateur survit au rafraîchissement d'un autre contrôle et se recadre quand la
    province change. `scaleanchor`/`scaleratio` restent posés par `_mise_en_page` : le pays ne se
    déforme pas au zoom.
    """
    rx, ry = emprise(geoms)
    fig.update_layout(dragmode="pan", uirevision=revision)
    fig.update_xaxes(fixedrange=False, range=rx, autorange=False if rx else True)
    fig.update_yaxes(fixedrange=False, range=ry, autorange=False if ry else True)
    return fig


def zoomer(rx, ry, facteur, emprise_x, emprise_y):
    """Nouvelles bornes d'axes après « Agrandir » (facteur < 1) ou « Réduire » (facteur > 1).

    Bornes du zoom : jamais plus large que l'emprise initiale, jamais plus
    étroit que ZOOM_MINI_DEG de longitude. Le centre courant est conservé.
    """
    if not (rx and ry and emprise_x and emprise_y):
        return emprise_x, emprise_y
    large = max(min((rx[1] - rx[0]) * facteur, emprise_x[1] - emprise_x[0]), ZOOM_MINI_DEG)
    part = large / (rx[1] - rx[0]) if rx[1] > rx[0] else 1.0
    haut = (ry[1] - ry[0]) * part
    cx, cy = (rx[0] + rx[1]) / 2, (ry[0] + ry[1]) / 2
    return [cx - large / 2, cx + large / 2], [cy - haut / 2, cy + haut / 2]


def figure_vide(message, hauteur=420):
    f = go.Figure()
    f.add_annotation(text=message, showarrow=False, x=0.5, y=0.5, xref="paper", yref="paper",
                     font=dict(size=15, color=GRIS))
    f.update_layout(height=hauteur, autosize=True, xaxis_visible=False, yaxis_visible=False, plot_bgcolor=BLANC,
                    paper_bgcolor=BLANC, font=POLICE, margin=dict(l=8, r=8, t=8, b=8))
    return f


# ---- classes de la rampe --------------------------------------------------------------------------------------
def bornes(vals):
    v = np.asarray([x for x in vals if x is not None and x == x], dtype=float)
    if not len(v):
        return 0.0, 1.0
    lo, hi = float(v.min()), float(v.max())
    return (lo, hi) if hi > lo else (lo, lo + 1)


def _pas_rond(x):
    """Pas « rond » immédiatement supérieur à x (échelle 1 · 2 · 2,5 · 5 · 10)."""
    if x <= 0:
        return 1.0
    exp = math.floor(math.log10(x))
    base = x / (10 ** exp)
    for m in (1, 2, 2.5, 5, 10):
        if base <= m:
            return m * (10 ** exp)
    return 10 ** (exp + 1)


# Nombres « ronds » admis comme borne de légende : 10 · 15 · 20 · 25 · 30 · 40 · 50 · 60 · 80 et
# leurs décades. Toute borne affichée est l'un d'eux : une légende se lit, elle ne se déchiffre pas.
MANTISSES = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0)


def _echelle_lisible(x):
    """Nombres ronds encadrant x (trois décades : celle de x, celle du dessous, celle du dessus)."""
    exp = math.floor(math.log10(x)) if x > 0 else 0
    return sorted(round(m * 10 ** e, 6) for e in (exp - 1, exp, exp + 1) for m in MANTISSES)


def _arrondi_lisible(x):
    """Nombre rond le plus proche de x (à égalité, le plus petit). 0 ou négatif : None."""
    if x is None or x != x or x <= 0:
        return None
    return min(_echelle_lisible(x), key=lambda v: (abs(v - x), v))


def _suivant_lisible(x):
    """Plus petit nombre rond strictement supérieur à x."""
    return next((v for v in _echelle_lisible(max(x, 1e-9)) if v > x), round(x * 2, 6))


def _precedent_lisible(x):
    """Plus grand nombre rond strictement inférieur à x, ou None s'il n'en existe pas d'utile."""
    return next((v for v in reversed(_echelle_lisible(max(x, 1e-9))) if v < x), None)


# Quantiles qui découpent la série en cinq classes d'effectifs comparables.
QUANTILES = (0.2, 0.4, 0.6, 0.8)


def _bornes_quantiles(valeurs, plafond=None):
    """4 bornes rondes tirées des quantiles des valeurs **réellement affichées**, ou None.

    Pourquoi des quantiles et non l'étendue : une seule province extrême (914 enseignants
    manquants quand 60 % des provinces sont sous 80) écrase cinq classes régulières, et la carte
    devient monochrome. Les quantiles garantissent des classes peuplées ; l'arrondi aux nombres
    ronds (`MANTISSES`) garde une légende lisible.
    Robustesse : beaucoup de zéros (scénarios 2030 où rien n'est à construire) écrasent les
    premiers quantiles — les bornes manquantes sont alors remplies vers le bas depuis la première
    borne positive, au lieu d'annoncer une classe « moins de 0 » que personne ne peut atteindre.
    Déterministe : même série, mêmes bornes (aucun tirage, aucun état).
    """
    v = np.asarray([x for x in valeurs if x is not None and x == x], dtype=float)
    if not len(v):
        return None
    # Beaucoup de zéros (scénarios 2030 où plus d'une province sur quatre n'a rien à construire) :
    # les deux premiers quantiles valent 0 et toute la discrimination se perdrait. Les quantiles
    # sont alors pris sur les valeurs **positives** ; la première classe réunit les zéros.
    positives = v[v > 0]
    base = positives if len(positives) >= 4 and float(np.quantile(v, QUANTILES[0])) <= 0 else v
    brutes = [_arrondi_lisible(float(q)) for q in np.quantile(base, QUANTILES)]
    b = [None] * 4
    for i, x in enumerate(brutes):           # vers le haut : chaque borne dépasse la précédente
        if x is None:
            continue
        precedente = next((b[j] for j in range(i - 1, -1, -1) if b[j] is not None), None)
        b[i] = x if precedente is None or x > precedente else _suivant_lisible(precedente)
    for i in range(2, -1, -1):               # vers le bas : les quantiles nuls ou égaux
        if b[i] is None and b[i + 1] is not None:
            b[i] = _precedent_lisible(b[i + 1])
    if plafond is not None:                  # une borne annoncée reste atteignable
        limite = plafond
        for i in range(3, -1, -1):
            if b[i] is not None and b[i] >= limite:
                b[i] = _precedent_lisible(limite)
            limite = b[i] if b[i] is not None else limite
    if any(x is None or x <= 0 for x in b) or any(a >= c for a, c in zip(b, b[1:])):
        return None                          # série dégénérée : la règle d'étendue reprend la main
    return b


# Bornes écrites fixées pour une mesure : seules celles qui viennent d'une **norme écrite**
# (arrêté 2020-186 : 50 élèves par salle, DGESS : 50 élèves par enseignant) restent figées, pour
# que « au-dessus de la norme » se lise de la même façon sur la Vue d'ensemble et sur le Classement.
# Les autres mesures suivent leur distribution (`_bornes_quantiles`) : des bornes fixes
# 200/500/800/1 200 pour « salles à construire » laissaient une classe vide dans la moitié des
# scénarios. Présentation seulement : les valeurs tracées ne changent pas.
NORMES_MESURE = {"eleves_par_maitre": NORME_ENSEIGNANT, "eleves_par_salle": NORME_CLASSE}
BORNES_MESURE = {cle: [n - 5, n, n + 5, n + 10] for cle, n in NORMES_MESURE.items()}


def bornes_mesure(cle):
    """Bornes fixées de la mesure `cle` (norme écrite), ou None si elle suit sa distribution."""
    bc = BORNES_MESURE.get(cle)
    return list(bc) if bc else None


def _bornes_entieres(b):
    """Bornes entières strictement croissantes, pour une mesure écrite **sans décimale**.

    Une série dont toutes les valeurs sont inférieures à 1 (cas limite : une mesure déclarée
    entière qui arrive en fraction) donnerait les libellés « moins de 0 » puis « 0 à 0 » :
    une légende dégénérée, que personne ne peut lire. Chaque borne est arrondie, ramenée à 1 au
    minimum, et poussée d'au moins un pas au-dessus de la précédente.
    """
    sortie = []
    for v in b:
        e = max(1, int(round(float(v))))
        sortie.append(float(e if not sortie or e > sortie[-1] else sortie[-1] + 1))
    return sortie


def classes(valeurs, norme=None, bornes_=None, bornes_classes=None, plafond=None, dec=None):
    """4 bornes écrites qui découpent les valeurs en 5 classes.

    `bornes_classes` : les 4 bornes imposées (une mesure dont la norme est écrite garde la même
    légende partout, cf. BORNES_MESURE).
    Avec une norme (50 élèves par classe, par maître…), les classes sont calées dessus pour que
    « au-dessus de la norme » se lise d'un coup d'œil : n−5, n, n+5, n+10.
    Sinon, bornes rondes tirées des **quantiles des valeurs affichées** (`_bornes_quantiles`), et,
    en dernier recours (série dégénérée, aucune valeur), bornes rondes régulières couvrant
    l'étendue observée. Présentation seulement, jamais un calcul d'indicateur.
    `plafond` : valeur que la mesure ne peut pas dépasser (100 pour un pourcentage). La série est
    décalée d'un pas tant que la dernière borne l'atteint, sinon la légende annoncerait une classe
    impossible (« 100 % et plus ») que personne ne peut atteindre.
    `dec` : nombre de décimales avec lequel la mesure est **écrite** (`meta.MESURES[…]["dec"]`).
    À 0, les bornes sont ramenées à des entiers distincts : une série entièrement sous 1 écrirait
    sinon « moins de 0 » puis « 0 à 0 ».
    """
    if bornes_classes:
        return list(bornes_classes)
    if norme:
        return [norme - 5, norme, norme + 5, norme + 10]
    if bornes_ is None:
        q = _bornes_quantiles(valeurs, plafond=plafond)
        if q is not None:
            return _bornes_entieres(q) if dec == 0 else q
    lo, hi = bornes_ or bornes(valeurs)
    pas = _pas_rond((hi - lo) / 5)
    debut = math.floor(lo / pas) * pas
    b = [round(debut + pas * i, 6) for i in range(1, 5)]
    while plafond is not None and b[-1] >= plafond and b[0] - pas > 0:
        b = [round(v - pas, 6) for v in b]
    return _bornes_entieres(b) if dec == 0 else b


def libelles_classes(bornes_classes, dec=0, unite=""):
    """Libellés écrits des 5 classes (légende HTML `legende_classee`).

    L'unité est accolée au nombre par une espace insécable — **fine** (U+202F) avant « % », comme
    `meta.fmt_pct`, normale (U+00A0) pour les autres unités : un nombre et son unité ne sont jamais
    séparés en fin de ligne, même dans une colonne de légende étroite.
    """
    u = ((" " if unite == "%" else " ") + unite) if unite else ""
    # une borne ronde s'écrit sans décimale (« 45 à 50 », pas « 45,0 à 50,0 »)
    b = [fmt_nombre(v, 0 if float(v).is_integer() else dec) + u for v in bornes_classes]
    return [f"moins de {b[0]}", f"{b[0]} à {b[1]}", f"{b[1]} à {b[2]}", f"{b[2]} à {b[3]}", f"{b[3]} et plus"]


def _classe(v, bornes_classes):
    if v is None or v != v:
        return None
    for i, b in enumerate(bornes_classes):
        if float(v) < b:
            return i
    return len(bornes_classes)


def _legende_classee(fig, bornes_classes, titre, dec=0):
    """Légende de la rampe : 5 blocs pleins et les bornes écrites (jamais un dégradé continu)."""
    echelle = []
    for i, c in enumerate(RAMPE):
        echelle += [[i / 5, c], [(i + 1) / 5, c]]
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode="markers", hoverinfo="skip", showlegend=False,
        marker=dict(colorscale=echelle, cmin=0, cmax=5, color=[0], showscale=True,
                    colorbar=dict(orientation="h", y=-0.01, yanchor="top", x=0.5, xanchor="center", len=0.8,
                                  thickness=10, outlinewidth=0, tickmode="array",
                                  tickvals=[1, 2, 3, 4], ticktext=[fmt_nombre(b, dec) for b in bornes_classes],
                                  tickfont=dict(size=12, color=GRIS),
                                  title=dict(text=titre, side="top", font=dict(size=12, color=GRIS))))))


# ---- mise en page ----------------------------------------------------------------------------------------------
def _mise_en_page(fig, hauteur=None, marge_bas=4):
    # autosize même avec une hauteur fixe : sinon Plotly impose sa largeur par défaut (700 px) et déborde
    fig.update_layout(height=hauteur, autosize=True, margin=dict(l=4, r=4, t=4, b=marge_bas),
                      plot_bgcolor=BLANC, paper_bgcolor=BLANC, font=POLICE, separators=", ",
                      hoverlabel=SURVOL,
                      xaxis=dict(visible=False, scaleanchor="y", scaleratio=COS_LAT, constrain="domain"),
                      yaxis=dict(visible=False), showlegend=False)
    return fig


def _contours(fig, geoms, couleur=TRAIT_REGION, largeur=1.4):
    xs, ys = [], []
    for geom in geoms:
        if geom:
            a, b = _anneaux(geom)
            xs += a
            ys += b
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=couleur, width=largeur), hoverinfo="skip",
                             showlegend=False))


ANGLES = (0.0, 0.6, -0.6, 1.2, -1.2, 1.9, -1.9, 2.6, -2.6)
# identifiants des deux tracés des rangs : repris en classes CSS « .tracerangs-* » (assets/style.css)
UID_RANGS_TRAITS = "rangs-traits"
UID_RANGS_PASTILLES = "rangs-pastilles"


def _pastilles_rangs(fig, rangs, rect):
    """Pastilles numérotées des provinces prioritaires, posées au point intérieur.

    Si la place libre y est plus petite que la pastille, elle est décalée vers l'extérieur du pays
    et reliée au point par un trait de rappel.
    """
    (x0, x1), (y0, y1) = rect
    largeur = x1 - x0
    r = 0.013 * largeur          # rayon de la pastille dans l'unité des coordonnées (≈ 13 px sur 1000)
    d = 0.044 * largeur          # distance de décalage
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    posees, traits_x, traits_y = [], [], []
    px, py, txt = [], [], []
    for rang, x, y, dl, dh in rangs:
        if x is None:
            continue
        bx, by = x, y
        if dl < r or dh < r:
            base = math.atan2(y - cy, x - cx) or 0.0
            for da in ANGLES:
                a = base + da
                cx2, cy2 = x + d * math.cos(a), y + d * math.sin(a)
                if not (x0 + r <= cx2 <= x1 - r and y0 + r <= cy2 <= y1 - r):
                    continue
                if all(math.hypot(cx2 - ax, cy2 - ay) >= 2 * r + 0.008 * largeur for ax, ay in posees):
                    bx, by = cx2, cy2
                    break
            traits_x += [x, bx, None]
            traits_y += [y, by, None]
        posees.append((bx, by))
        px.append(bx)
        py.append(by)
        txt.append(str(rang))
    # `uid` stable : Plotly nomme le groupe SVG du tracé « trace<uid> », ce qui donne au CSS la
    # seule prise possible sur un tracé (les rangs sont masqués sous 961 px, où les pastilles
    # seraient illisibles). Le `uid` fait partie de la figure : il survit à chaque
    # recalcul du callback, sans script ni dépendance à la largeur côté serveur.
    if traits_x:
        fig.add_trace(go.Scatter(x=traits_x, y=traits_y, mode="lines", line=dict(color=ENCRE, width=1),
                                 hoverinfo="skip", showlegend=False, uid=UID_RANGS_TRAITS))
    if px:
        fig.add_trace(go.Scatter(x=px, y=py, mode="markers+text", text=txt, textposition="middle center",
                                 textfont=dict(size=11, color=ENCRE, family=POLICE["family"]),
                                 marker=dict(size=26, color=BLANC, line=dict(color=ENCRE, width=1)),
                                 hoverinfo="skip", showlegend=False, cliponaxis=False,
                                 uid=UID_RANGS_PASTILLES))


def carte(geoms, valeurs, titre_echelle, gras=(), contours_regions=None, bornes_=None, hauteur=None,
          fmt=",.0f", norme=None, rangs=None, selection=None, legende=True, dec=None, bornes_classes=None):
    """Choroplèthe des 45 provinces, rampe ocre à **5 classes** et légende écrite.

    geoms : DataFrame [code, nom, geometrie] ; valeurs : code -> (valeur, survol).
    gras : codes des 10 provinces prioritaires (contour encre) ; rangs : code -> rang (pastilles) ;
    selection : code de la province choisie (halo blanc + anneau accent) ; `bornes_classes` : les
    4 bornes imposées de la légende (`bornes_mesure()`), sinon la norme puis la règle automatique.
    """
    vals = [valeurs.get(c, (None, ""))[0] for c in geoms["code"]]
    bc = classes(vals, norme=norme, bornes_=bornes_, bornes_classes=bornes_classes)
    if dec is None:
        dec = 1 if str(fmt).endswith(".1f") else 0
    fig = go.Figure()
    for code, nom, geom in zip(geoms["code"], geoms["nom"], geoms["geometrie"]):
        v, survol = valeurs.get(code, (None, f"<b>{nom}</b><br>non disponible"))
        i = _classe(v, bc)
        xs, ys = _anneaux(geom)
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", fill="toself",
                                 fillcolor=GRIS_ND if i is None else RAMPE[i], name=nom,
                                 line=dict(color=ENCRE if code in gras else BLANC,
                                           width=1.8 if code in gras else 0.6),
                                 hoveron="fills", hoverinfo="text", text=survol, showlegend=False,
                                 customdata=[code] * len(xs)))
    if contours_regions is not None:
        _contours(fig, contours_regions["geometrie"])
    if selection is not None:
        sel = [g for c, g in zip(geoms["code"], geoms["geometrie"]) if c == selection]
        if sel:
            xs, ys = _anneaux(sel[0])
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=BLANC, width=5),
                                     hoverinfo="skip", showlegend=False))
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=BLEU, width=2.5),
                                     hoverinfo="skip", showlegend=False))
    rect = emprise(geoms["geometrie"])
    if rangs:
        points = []
        for code, geom in zip(geoms["code"], geoms["geometrie"]):
            if code in rangs:
                x, y = centroide(geom)
                dl, dh = _demi_espace(geom, x, y) if x is not None else (0, 0)
                points.append((rangs[code], x, y, dl, dh))
        _pastilles_rangs(fig, sorted(points), rect)
    if legende:
        _legende_classee(fig, bc, titre_echelle, dec)
    _mise_en_page(fig, hauteur, marge_bas=54 if legende else 4)
    return verrouiller(fig, geoms["geometrie"])


def carte_localisation(geoms, code, code_region, contours_regions=None, hauteur=None):
    """Carte de situation : la province choisie en bleu foncé, sa région en bleu clair avec un contour
    accent (la couleur n'est jamais le seul indice), le reste du pays en gris."""
    fig = go.Figure()
    for c, nom, cr, geom in zip(geoms["code"], geoms["nom"], geoms["code_region"], geoms["geometrie"]):
        coul = BLEU if c == code else (BLEU_REGION if cr == code_region else GRIS_CARTE)
        xs, ys = _anneaux(geom)
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", fill="toself", fillcolor=coul,
                                 line=dict(color=BLANC, width=0.6), hoveron="fills", hoverinfo="text",
                                 text=nom, showlegend=False))
    if contours_regions is not None:
        _contours(fig, contours_regions["geometrie"], couleur=TRAIT_REGION, largeur=1.4)
        reg = contours_regions[contours_regions["code_region"] == code_region] \
            if "code_region" in contours_regions else None
        if reg is not None and len(reg):
            _contours(fig, reg["geometrie"], couleur=BLEU, largeur=2)
    _mise_en_page(fig, hauteur)
    return verrouiller(fig, geoms["geometrie"])


CLASSES_ACCES = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 101)]


def carte_implantation(communes, sites, contours_regions=None, cadre=None, hauteur=None, montrer_a_verifier=True,
                       taille_max=12, zoomable=False, revision="BF", contours_provinces=None):
    """Communes colorées par la part des enfants à plus de 3 km (5 classes de la rampe ocre ; hachures =
    carte des écoles peu fiable) et sites proposés (rond plein encre = fiable, rond creux ambre = à
    vérifier), taille ∝ enfants servis.

    Ordre de tracé, du dessous vers le dessus : communes (filet blanc 0,4) ·
    limites de **province** (`contours_provinces`, `--trait-region` 0,8) · limites de **région**
    (`contours_regions`, 1,4) · marqueurs de site. Les deux couches de limites sont facultatives et
    indépendantes : une page qui n'en passe aucune obtient exactement la carte d'avant.
    `zoomable=True` (Implantation) : la carte se déplace et zoome
    (`deverrouiller`), `revision` étant le code de la province filtrée. Par défaut la carte reste
    cadrée, comme toutes les autres cartes du site."""
    fig = go.Figure()
    for i, (a, b) in enumerate(CLASSES_ACCES):
        for faible in (False, True):
            sel = communes[(communes.part100 >= a) & (communes.part100 < b)
                           & ((communes.fiabilite_osm_province == "faible") == faible)]
            if not len(sel):
                continue
            xs, ys = [], []
            for g in sel.geometrie:
                u, v = _anneaux(g)
                xs += u
                ys += v
            tr = dict(x=xs, y=ys, mode="lines", fill="toself", fillcolor=RAMPE[i],
                      line=dict(color=BLANC, width=0.4), hoverinfo="skip", showlegend=False)
            if faible:
                tr["fillpattern"] = dict(shape="/", fgcolor=GRIS, bgcolor=RAMPE[i], size=6, solidity=0.2)
            fig.add_trace(go.Scatter(**tr))
    nd = communes[communes.part100.isna()]
    if len(nd):
        xs, ys = [], []
        for g in nd.geometrie:
            u, v = _anneaux(g)
            xs += u
            ys += v
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", fill="toself", fillcolor=GRIS_ND,
                                 line=dict(color=BLANC, width=0.4), hoverinfo="skip", showlegend=False))
    # survol des communes : points invisibles au point intérieur de chaque commune
    fig.add_trace(go.Scatter(x=communes.cx, y=communes.cy, mode="markers", marker=dict(size=9, opacity=0),
                             hoverinfo="text", text=communes.survol, showlegend=False))
    # Limites administratives, par-dessus les communes et sous les marqueurs : la province d'abord
    # (trait fin), la région ensuite (trait fort) — une limite de région est aussi une limite de
    # province, elle doit rester la plus lisible des deux. Même couleur, deux épaisseurs : aucune
    # couleur nouvelle. Les contours couvrent **tout le pays**, y compris quand une seule province
    # est affichée : c'est ce qui permet de situer un site par rapport à ses voisines.
    if contours_provinces is not None:
        _contours(fig, contours_provinces["geometrie"], largeur=0.8)
    if contours_regions is not None:
        _contours(fig, contours_regions["geometrie"], largeur=1.4)
    taille = lambda s: 4 + (taille_max - 4) * np.sqrt(
        s.clip(lower=0) / max(float(sites.enfants_6_11_2030_desservis.max() or 1), 1))
    if montrer_a_verifier:
        v = sites[sites.sites_fiables != 1]
        if len(v):
            fig.add_trace(go.Scatter(x=v.longitude, y=v.latitude, mode="markers", hoverinfo="text", text=v.survol,
                                     marker=dict(size=taille(v.enfants_6_11_2030_desservis), color=BLANC,
                                                 opacity=0.85, line=dict(color=ATTENTION, width=1.6)),
                                     showlegend=False))
    f = sites[sites.sites_fiables == 1]
    if len(f):
        fig.add_trace(go.Scatter(x=f.longitude, y=f.latitude, mode="markers", hoverinfo="text", text=f.survol,
                                 marker=dict(size=taille(f.enfants_6_11_2030_desservis), color=ENCRE,
                                             line=dict(color=BLANC, width=0.8)), showlegend=False))
    _mise_en_page(fig, hauteur)
    geoms_cadre = cadre if cadre is not None else communes["geometrie"]
    if zoomable:
        return deverrouiller(fig, geoms_cadre, revision)
    return verrouiller(fig, geoms_cadre)


# ---- graphiques ------------------------------------------------------------------------------------------------
def _axes(fig, hauteur=None, legende=True, marge_g=48):
    fig.update_layout(height=hauteur, autosize=True, margin=dict(l=marge_g, r=12, t=8, b=36),
                      plot_bgcolor=BLANC, paper_bgcolor=BLANC, font=POLICE, separators=", ",
                      hoverlabel=SURVOL, showlegend=legende,
                      legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, font=dict(size=12, color=GRIS)))
    fig.update_xaxes(showgrid=False, linecolor=BORDURE, fixedrange=True, zeroline=False)
    fig.update_yaxes(gridcolor=BORDURE_FAIBLE, zeroline=False, fixedrange=True)
    return fig


TRAITS = ("solid", "dot", "longdash")


def evolution(df, colonnes, norme=None, hauteur=280, legende=True):
    """Courbes annuelles (df indexé par année scolaire) ; le trait **et** le motif distinguent les séries.

    Graduations : l'**année de début** (« 2017 »…« 2024 »), jamais la période complète en diagonale —
    à 390 px, huit « 2017-2018 » basculent et se chevauchent. La période entière reste écrite deux
    fois à l'écran, dans le titre du panneau et dans la ligne « Lecture : ».
    """
    fig = go.Figure()
    for i, (col, lib) in enumerate(colonnes.items()):
        fig.add_trace(go.Scatter(x=df["annee_scolaire"], y=df[col], mode="lines+markers", name=lib,
                                 line=dict(color=SERIES[i % 3], width=2, dash=TRAITS[i % 3]),
                                 marker=dict(size=6, color=SERIES[i % 3]),
                                 hovertemplate=f"{lib} : %{{y:.1f}}<extra>%{{x}}</extra>"))
    if norme:
        # « norme : 50 » à droite de la ligne : à gauche, l'étiquette se posait sur la graduation « 50 »
        fig.add_hline(y=norme, line=dict(color=GRIS, dash="dashdot", width=1),
                      annotation_text=f"norme : {norme}", annotation_position="top right",
                      annotation_font=dict(size=11, color=GRIS))
    _axes(fig, hauteur, legende=legende)
    periodes = [str(v) for v in df["annee_scolaire"]]
    if periodes:
        fig.update_xaxes(tickmode="array", tickvals=periodes,
                         ticktext=[p.split("-")[0] for p in periodes], tickangle=0,
                         tickfont=dict(size=12, color=GRIS))
    return fig


def barres_h(libelles, valeurs, couleurs=None, hauteur=260, fmt=",.0f", suffixe="", marge_g=150, survol=None,
             piste=None):
    """Barres horizontales (composantes du score) : remplissage gris neutre, jamais l'accent.

    `piste` : maximum de l'échelle. Donné, il dessine la **piste claire** derrière chaque barre et
    aligne les valeurs sur une colonne unique à droite ; les libellés gardent 8 px d'air avant la piste.
    """
    etiquettes = [fmt_nombre(v) + suffixe for v in valeurs]
    fig = go.Figure()
    if piste:
        fig.add_trace(go.Bar(y=libelles, x=[piste] * len(libelles), orientation="h", marker_color=PISTE,
                             text=etiquettes, textposition="outside", cliponaxis=False,
                             textfont=dict(size=12, color=GRIS), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Bar(y=libelles, x=valeurs, orientation="h", marker_color=couleurs or PISTE_PLEINE,
                         text=None if piste else etiquettes, textposition="outside", cliponaxis=False,
                         textfont=dict(size=12, color=GRIS),
                         hovertext=survol, hoverinfo="text" if survol else "x+y"))
    _axes(fig, hauteur, legende=False, marge_g=marge_g)
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)", ticklabelstandoff=8)
    haut = piste or max([v for v in valeurs if v == v] + [1])
    fig.update_xaxes(showticklabels=False, range=[0, haut * 1.18])
    fig.update_layout(margin=dict(l=marge_g, r=16, t=4, b=4), barmode="overlay", bargap=0.34)
    return fig


def barres_scenarios(df, choisi, hauteur=None):
    """Salles à construire et enseignants supplémentaires par scénario ; contour encre = scénario choisi.

    Les étiquettes d'axe viennent de `libelles.SCENARIOS_AXE` — la même source que les libellés
    écrits en toutes lettres sur la Fiche et dans le filtre « Scénario », en version courte sur deux
    lignes. Présentation seulement : les valeurs tracées et l'ordre des scénarios ne changent pas.
    """
    axe = [SCENARIOS_AXE.get(s, lib) for s, lib in zip(df["scenario"], df["libelle"])]
    fig = go.Figure()
    for col, lib, coul in (("salles_a_construire_2030", "Salles à construire", SERIES[0]),
                           ("enseignants_supplementaires_2030", "Enseignants supplémentaires", SERIES[1])):
        fig.add_trace(go.Bar(x=axe, y=df[col], name=lib, marker_color=coul,
                             marker_line=dict(color=[ENCRE if s == choisi else "rgba(0,0,0,0)" for s in df.scenario],
                                              width=1.6),
                             text=[fmt_nombre(v) for v in df[col]], textposition="outside", cliponaxis=False,
                             textfont=dict(size=12, color=GRIS),
                             hovertemplate=lib + " : %{y:,.0f}<extra>%{x}</extra>"))
    _axes(fig, hauteur)
    fig.update_layout(barmode="group", bargap=0.28, margin=dict(l=8, r=8, t=28, b=30))
    fig.update_yaxes(showticklabels=False, gridcolor="rgba(0,0,0,0)",
                     range=[0, max(df[["salles_a_construire_2030", "enseignants_supplementaires_2030"]].max()) * 1.15])
    return fig
