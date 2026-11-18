"""Kit d'interface : tous les blocs HTML du tableau de bord.

Index de l'API — à composer dans les pages ; un bloc qui manque s'ajoute ici,
jamais en composant local dans une page :

Coque et navigation
    lien_evitement(cible)                   « Aller au contenu » : premier élément focalisable de la coque
    rail(auth_active, chemin, donnees_)     aside.rail (≥ 961 px) ; ids `nav-*` conservés
    tete_mobile(auth_active, chemin)        barre haute + bouton « Pages » (`nav-bascule`/`nav-menu`)
    classes_nav(chemin)                     6 classes de rail + 6 de menu + 12 `aria-current` (ordre de PAGES)
    id_nav(chemin, prefixe="nav")           identifiant d'un lien de navigation
    fraicheur(donnees_)                     contenu du pied de rail (date de lecture ou état obsolète)

En-tête et texte
    entete(titre_page, perimetre, decoupage=…)  .travail-tete (h1 + périmètre + mention de découpage)
    mention_decoupage(texte)                pastille neutre « découpage … » (meta.DECOUPAGE_*)
    anciennement(nom)                       seconde ligne « anciennement : X » sous un nom de province
    constat(*contenu)                       phrase-constat 16 px (14 px sur une vue « un écran »)
    lecture(txt)                            ligne « Lecture : … » obligatoire sous chaque figure
    note(txt)                               12 px gris, à droite d'un titre de panneau
    texte(*contenu)                         paragraphe de corps de texte (mesure 72 caractères)
    liste(items)                            liste à puces du corps de texte
    note_limite(*contenu)                   bloc encadré neutre (limite de méthode), sans statut

Chiffres clés
    bande_kpi(*cellules, colonnes=6)        UNE surface découpée en cellules (jamais 6 cartes)
    kpi(libelle, valeur, …, aide_kpi=…)     cellule ; infobulle au survol/focus/toucher, sans icône
    tendance(delta, texte, …)               flèche + texte ; None si la comparaison n'existe pas

Aides
    aide(texte, lib)                        icône « i » (4 au maximum sur tout le site)
    terme(contenu, texte)                   libellé survolable sans icône
    avec_aide(contenu, texte, lib)          libellé + icône « i »

Blocs
    panneau(titre, *enfants, note_=…, pied=…, aide_titre=…, cls=…, **kw)
    rangee(gauche, droite)                  plan de travail 2 colonnes
    grille(gauche, droite, inverse=False)   rangée 7/5 (ou 5/7) d'une page qui défile
    panneau_pied(*enfants)                  pied de panneau (lien de suite + note)

Contrôles
    barre_filtres(*filtres, action=…, note_=…)  rangée de filtres sans cadre, action alignée à droite
    outils_carte(id_plus, id_moins, id_recadrer)  « Agrandir · Réduire · Recadrer » (Implantation)
    filtre(lib, composant, texte_aide, cls) libellé au-dessus du champ
    menu(id_, options, valeur, **kw)        dcc.Dropdown restylé
    menu_natif(id_, options, valeur, **kw)  <select> local (page kit, formulaires simples)
    controle_segmente(id_, options, valeur, legende)   dcc.RadioItems en piste segmentée
    bouton(libelle, id_=None, plein=False, href=None)   .btn-plein (une par zone) ou .btn-contour
    lien_suite(txt, href)                   lien de fin de bloc avec sa flèche

Données
    badge_classe(c, court=False)            puce P1/P2/P3 (puces + code, jamais la couleur seule)
    barre_score(valeur, texte=None, max_=100)           piste + valeur alignée
    barres_composantes(items)               barres de composantes (libellé · piste grise · valeur)
    liste_chiffres(items)                   <dl> clé-valeur
    grille_equipe(*cases)                   bloc « L'équipe » (À propos)
    membre_equipe(nom, role, bio=, photo=)  une case : portrait rond (si le fichier existe), nom, rôle, 1 ligne
    legende_rampe(titre, libelles)          légende de carte depuis figures.libelles_classes()
    legende_classee(titre, classes)         idem, à partir de (clé de classe, libellé)
    legende_situation()                     pastilles « province » / « sa région »
    legende_marqueurs(*items, lib=None)     légende de marqueurs (sites fiables / à vérifier)

États
    vide(phrase, suite)                     état vide : ce qui manque et quoi faire
    bande_obsolete(depuis, derniere)        bande ambre datée, au-dessus du contenu
    erreur_donnees(derniere=None)           bloc rouge + « Réessayer » (le contenu disparaît)
    page_introuvable()                      même gabarit, ton neutre
    squelette(hauteur)                      aplat de chargement (sans dégradé ni animation)
    zone_squelette(*enfants, hauteur)       aplat à la place d'une zone
    valeur_sk(valeur)                       valeur recouverte par son aplat
    chargement(enfant)                      dcc.Loading (delay_show=250)

Zones de figure (classes de `assets/style.css`, pas de fonction) :
    .zone-carte       conteneur d'une carte Plotly — porte le format réel du pays (1000 × 733)
    .zone-graphique   conteneur d'un graphique qui occupe la hauteur restante de son panneau

Ailleurs dans le kit : `d3dash/figures.py` (figures Plotly, bornes de classes, jetons des
DataTable) et `d3dash/navigation.py` (ouvrir une fiche depuis un clic sur une carte).

Règles : aucune icône ni « i » sur un chiffre clé ; l'accent ne sert qu'à la sélection ;
une information ne repose jamais sur la couleur seule ; les identifiants Dash ne changent pas.
"""
import datetime as dt

from dash import dcc, html

from .meta import ANNEE_REF, CLASSES, EQUIPE, annee_scolaire

# (chemin, libellé, clé d'icône) ; l'identifiant du lien reste « nav-<chemin> » (callbacks et tests)
PAGES = [("/", "Vue d'ensemble", "accueil"), ("/classement", "Classement", "classement"),
         ("/fiche", "Fiche province", "fiche"), ("/besoins-2030", "Besoins 2030", "besoins"),
         ("/implantation", "Implantation", "implantation"), ("/a-propos", "À propos et méthode", "methode")]
NOM_PRODUIT = "Salles & Maîtres"
SOUS_TITRE_PRODUIT = "Primaire, Burkina Faso"
MOIS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")


def id_nav(chemin, prefixe="nav"):
    return f"{prefixe}-{chemin.strip('/') or 'accueil'}"


def _actif(chemin, courant):
    """`courant is None` = chemin encore inconnu (premier rendu du gabarit, avant le callback
    `actif`) : aucun item n'est marqué, plutôt que marquer « Vue d'ensemble » à tort."""
    if courant is None:
        return False
    courant = courant.rstrip("/") or "/"
    if courant == "/methode":
        courant = "/a-propos"
    return courant == chemin


def classes_nav(chemin):
    """État des liens de navigation : classes des 6 liens du rail, puis des 6 liens du menu mobile,
    puis les 12 valeurs de `aria-current` (ordre de PAGES). L'item actif ne repose pas sur la
    seule couleur : il porte aussi `aria-current="page"` et la graisse 600."""
    return ([("nav-item actif" if _actif(h, chemin) else "nav-item") for h, _, _ in PAGES]
            + [("actif" if _actif(h, chemin) else "") for h, _, _ in PAGES]
            + [("page" if _actif(h, chemin) else None) for h, _, _ in PAGES] * 2)


def lien_evitement(cible="#page"):
    """« Aller au contenu » : premier élément focalisable de la coque, visible seulement au clavier.

    Sans lui, atteindre le tableau d'une page au clavier demande de traverser le rail puis, sur le
    Classement ou l'Implantation, des dizaines de liens de province.
    """
    return html.A("Aller au contenu", href=cible, className="lien-evitement")


def _marque(avec_equipe=False):
    return html.Div([html.Span(className="monogramme", **{"aria-hidden": "true"}),
                     html.Span(NOM_PRODUIT, className="marque-nom"),
                     html.Span(EQUIPE, className="marque-eq") if avec_equipe else None],
                    className="marque")


def _lien_nav(chemin, libelle, icone, courant, prefixe="nav", base="nav-item"):
    """Lien du rail ou du menu.

    `html.A` (et non `dcc.Link`) : l'état actif doit porter `aria-current="page"`, que `dcc.Link`
    refuse en Dash 4.5. `data-nav` laisse `assets/nav.js` intercepter le clic et pousser l'adresse
    dans l'historique : la navigation reste côté client, sans recharger le document.
    `base` est la classe de repos ("nav-item" pour le rail, "" pour le menu mobile)."""
    actif = _actif(chemin, courant)
    classe = (base + " actif").strip() if actif else base
    return html.A([html.Span(className=f"ico ico-{icone}", **{"aria-hidden": "true"}),
                   html.Span(libelle)], href=chemin, id=id_nav(chemin, prefixe),
                  className=classe, **{"data-nav": "1"},
                  **({"aria-current": "page"} if actif else {}))


def fraicheur(donnees_=None):
    """Pied de rail : millésime de l'annuaire et heure de la dernière lecture réussie.
    Si la dernière lecture a échoué, la ligne passe en rouge (l'obsolescence n'est jamais masquée)."""
    base = f"Annuaire {annee_scolaire(ANNEE_REF)}"
    if donnees_ is None:
        return html.Span(base, className="etiq-fraicheur")
    horo = getattr(donnees_, "horodatage", 0) or 0
    if not horo:
        return html.Span(base, className="etiq-fraicheur")
    t = dt.datetime.fromtimestamp(horo)
    quand = f"{t.day} {MOIS[t.month - 1]} {t.year} à {t.hour:02d} h {t.minute:02d}"
    if getattr(donnees_, "derniere_erreur", None):
        return html.Span(f"{base} · base injoignable, chiffres lus le {quand}",
                         className="etiq-fraicheur etiq-fraicheur-obsolete")
    return html.Span(f"{base} · lu le {quand}", className="etiq-fraicheur")


def rail(auth_active=True, chemin=None, donnees_=None):
    """Rail de navigation gauche (≥ 961 px) : marque, 6 pages, pied (fraîcheur, méthode, sortie)."""
    pied = [html.Span(fraicheur(donnees_), id="rail-fraicheur"),
            dcc.Link("Sources et méthode", href="/a-propos")]
    if auth_active:
        pied.append(html.A("Se déconnecter", href="/deconnexion"))
    return html.Aside([
        html.Div([_marque(), html.Span(SOUS_TITRE_PRODUIT, className="marque-sous")], className="rail-marque"),
        html.Nav([_lien_nav(h, t, i, chemin) for h, t, i in PAGES],
                 **{"aria-label": "Pages du tableau de bord"}),
        html.Div(pied, className="rail-pied"),
    ], className="rail")


def tete_mobile(auth_active=True, chemin=None):
    """Barre haute et menu « Pages » (< 961 px) : mêmes liens, cibles de 44 px."""
    liens = [_lien_nav(h, t, i, chemin, prefixe="navm", base="") for h, t, i in PAGES]
    if auth_active:
        liens.append(html.A([html.Span(className="ico ico-methode", **{"aria-hidden": "true"}),
                             html.Span("Se déconnecter")], href="/deconnexion"))
    return html.Div([
        html.Div([_marque(avec_equipe=True),
                  html.Button([html.Span(className="ico ico-pages", **{"aria-hidden": "true"}), "Pages"],
                              id="nav-bascule", className="tm-bouton", n_clicks=0,
                              **{"aria-expanded": "false", "aria-controls": "nav-menu"})],
                 className="tm-haut"),
        html.Nav(liens, id="nav-menu", className="tm-menu", hidden=True,
                 **{"aria-label": "Pages du tableau de bord"}),
    ], className="tete-mobile")


# ---- en-tête, texte ------------------------------------------------------------------------------------------
def mention_decoupage(txt, **kw):
    """Pastille neutre du découpage administratif utilisé par la page.

    Même gabarit que le code équipe du rail (`.marque-eq`) : aucune forme nouvelle. Ce n'est pas
    une alerte — ni rouge, ni ambre, ni icône, ni `role`. Les deux textes possibles sont
    `meta.DECOUPAGE_CONSTAT` et `meta.DECOUPAGE_2025` ; une page n'en écrit jamais un troisième.
    """
    return html.Span(txt, className="decoupage", **kw)


def entete(titre_page, perimetre=None, decoupage=None, **kw):
    """En-tête de page : titre, puis périmètre et mention de découpage groupés à droite.

    Le groupe `.tete-droite` aligne les deux au centre : la pastille n'augmente pas la hauteur de
    l'en-tête (21 px), qui reste dans son budget vertical.
    """
    droite = [html.P(perimetre, className="perimetre") if perimetre else None,
              mention_decoupage(decoupage) if decoupage else None]
    return html.Div([html.H1(titre_page),
                     html.Div(droite, className="tete-droite") if any(droite) else None],
                    className="travail-tete", **kw)


def anciennement(nom, **kw):
    """Seconde ligne « anciennement : X » sous un nom de province.

    À n'afficher que si le nom du découpage 2025 diffère du nom d'avant 2025 : répéter un nom
    identique est du bruit. Jamais tronquée (elle passe à la ligne).
    """
    if not nom:
        return None
    return html.Span(f"anciennement : {nom}", className="anciennement", **kw)


def chiffre(txt):
    """Nombre cité dans une phrase : police chiffrée, insécable, jamais coupé."""
    return html.Span(txt, className="chiffre")


def constat(*contenu, **kw):
    """Phrase-constat : une à deux phrases, les nombres enveloppés dans chiffre()."""
    return html.P(list(contenu), className="constat", **kw)


def note(txt, **kw):
    return html.Span(txt, className="note", **kw)


def lecture(txt, **kw):
    """Courte phrase de lecture sous une carte, un tableau ou un graphique (obligatoire)."""
    return html.P([html.Span("Lecture : ", className="lecture-lib"), txt], className="lecture", **kw)


def texte(*contenu, **kw):
    """Paragraphe de corps de texte : mesure de ligne 72 caractères, rythme de 8 px entre blocs."""
    return html.P(list(contenu), className="texte", **kw)


def liste(items, **kw):
    """Liste à puces du corps de texte (même mesure et même rythme que `texte()`)."""
    return html.Ul([html.Li(t) for t in items], className="liste", **kw)


def note_limite(*contenu, **kw):
    """Note de limite : bloc encadré **neutre** (fond `--muted`, filet 1 px), sans barre latérale
    ni couleur de statut — une limite de méthode n'est ni une alerte ni une panne."""
    return html.P(list(contenu), className="note-limite", **kw)


# ---- aides ---------------------------------------------------------------------------------------------------
def aide(texte_aide, lib=None):
    """Icône « i » (4 au maximum sur tout le site : normes, score, scénarios, fiabilité).
    L'infobulle s'ouvre au survol, au toucher et au clavier ; le texte est inséré par assets/aide.js."""
    if not texte_aide:
        return None
    # Pas d'`aria-expanded` : l'icône n'ouvre pas une région, elle décrit son contexte.
    # `aria-describedby="bulle-aide"` est posé par assets/aide.js tant que la bulle est visible.
    return html.Span("i", className="aide", tabIndex="0", role="button",
                     **{"data-aide": texte_aide,
                        "aria-label": "Aide : " + (lib or texte_aide.split("\n")[0][:80])})


def terme(contenu, texte_aide, **kw):
    """Libellé survolable sans icône (soulignement pointillé discret)."""
    return html.Span(contenu, className="terme-aide", tabIndex="0", **{"data-aide": texte_aide}, **kw)


def avec_aide(contenu, texte_aide, lib=None):
    """Libellé suivi de son icône d'aide (espace sécable : l'icône passe à la ligne, elle ne déborde pas)."""
    return html.Span([contenu, " ", aide(texte_aide, lib or (contenu if isinstance(contenu, str) else None))],
                     className="avec-aide")


# ---- chiffres clés -------------------------------------------------------------------------------------------
FLECHES = {"hausse": "▲", "baisse": "▼", "stable": "▶"}


SENS_TENDANCE = {"pire": "Évolution défavorable sur un an", "mieux": "Évolution favorable sur un an",
                 "neutre": "Stable sur un an"}


def tendance(delta, texte, mauvais_si_hausse=True, seuil=1e-9):
    """Évolution sur un an : flèche ▲/▼ **et** texte (jamais la couleur seule).
    Renvoie None si la comparaison n'existe pas : aucune valeur inventée, jamais « +0 ».

    Le `title` reprend le texte **en entier** avant d'en donner le sens : dans une cellule de
    chiffre, la ligne peut être coupée au-dessus de 1280 px, et une métadonnée tronquée doit
    garder un moyen d'être lue.
    """
    if delta is None or delta != delta:
        return None
    sens = "stable" if abs(delta) <= seuil else ("hausse" if delta > 0 else "baisse")
    if sens == "stable":
        effet = "neutre"
    else:
        effet = "pire" if (sens == "hausse") == mauvais_si_hausse else "mieux"
    lu = texte if isinstance(texte, str) else None
    return html.Span([html.Span(FLECHES[sens], className="fleche", **{"aria-hidden": "true"}), " ", texte],
                     className=f"tendance t-{effet}",
                     title=f"{lu} · {SENS_TENDANCE[effet].lower()}" if lu else SENS_TENDANCE[effet])


UNITES = (" %", " %", "%", " pt", " pt")


def _valeur_unite(valeur):
    """Sépare l'unité de la valeur pour la rendre en gris plus petit (le nombre reste entier)."""
    if isinstance(valeur, str):
        for u in UNITES:
            if valeur.endswith(u) and valeur[: -len(u)]:
                return valeur[: -len(u)], html.Span(u.replace(" ", " "), className="kpi-unite")
    return valeur, None


def _ligne_kpi(contenu, classe):
    """Ligne secondaire d'une cellule de chiffre (tendance, contexte).

    Si c'est du texte écrit en toutes lettres, il porte son propre `title` : au-dessus de 1280 px
    la ligne tient sur une ligne et peut, avec une valeur plus longue que prévu, être coupée —
    une métadonnée tronquée garde toujours un moyen d'être lue. Un composant porte
    le sien : `tendance()` reprend son texte entier dans son `title`, et une page qui fabrique un
    `Span` doit faire de même (c'est ce que vérifie `tests/test_kit.py`).
    """
    if contenu is None:
        return None
    if isinstance(contenu, str):
        return html.Div(contenu, className=classe, title=contenu)
    return html.Div(contenu, className=classe)


def kpi(libelle, valeur, variation=None, id_=None, evolution=None, aide_kpi=None):
    """Cellule de chiffre clé : libellé, valeur (+ unité grise), tendance, ligne de contexte.

    Jamais d'icône sur un chiffre clé. Avec `aide_kpi`, toute la cellule ouvre l'infobulle au
    survol, au toucher et au clavier — sans icône « i ». Aucune couleur de valeur : rouge et vert
    sont des statuts d'évolution, portés par `evolution`.
    """
    val, unite = _valeur_unite(valeur)
    enfants = [html.Div(libelle, className="kpi-lib"),
               html.Div([val, unite], className="kpi-val"),
               _ligne_kpi(evolution, "kpi-tend"),
               _ligne_kpi(variation or None, "kpi-ctx")]
    # pas d'`aria-expanded` ici : la cellule est un élément générique, pas un widget qui s'étend.
    # L'infobulle est rattachée par `aria-describedby` (posé par assets/aide.js à l'ouverture).
    sup = {"data-aide": aide_kpi, "tabIndex": "0"} if aide_kpi else {}
    return html.Div(enfants, className="kpi kpi-aide" if aide_kpi else "kpi",
                    **sup, **({"id": id_} if id_ else {}))


def bande_kpi(*cellules, colonnes=6, **kw):
    """Bande de chiffres : UNE surface découpée en cellules par des filets (jamais N cartes)."""
    enfants = list(cellules[0]) if len(cellules) == 1 and isinstance(cellules[0], (list, tuple)) else list(cellules)
    cls = "bande-kpi" + (" ligne-kpi-4" if colonnes == 4 else "")
    return html.Section(enfants, className=cls, **{"aria-label": "Chiffres clés"}, **kw)


# ---- blocs ---------------------------------------------------------------------------------------------------
def panneau(titre_bloc=None, *enfants, note_=None, pied=None, aide_titre=None, cls="", **kw):
    """Surface unique (fond `--card`, filet 1 px, rayon 8, sans ombre) : tête, contenu, pied."""
    tete = None
    if titre_bloc or note_:
        tete = html.Div([html.H2(avec_aide(titre_bloc, aide_titre) if aide_titre else titre_bloc)
                         if titre_bloc else None,
                         note(note_) if isinstance(note_, str) else note_], className="panneau-tete")
    return html.Section([tete, *enfants, pied], className=("panneau " + cls).strip(), **kw)


def panneau_pied(*enfants, **kw):
    return html.Div(list(enfants), className="panneau-pied", **kw)


def rangee(gauche, droite, **kw):
    """Plan de travail : objet principal à gauche, panneau de décision à droite."""
    return html.Div([gauche, droite], className="rangee", **kw)


def grille(gauche, droite, inverse=False, **kw):
    """Rangée 7/5 (ou 5/7 avec inverse=True) d'une page qui défile."""
    return html.Div([gauche, droite], className="grille-fiche" + (" grille-fiche-57" if inverse else ""), **kw)


# ---- contrôles -----------------------------------------------------------------------------------------------
def _id_champ(composant):
    """Identifiant du champ à étiqueter (le composant lui-même ou le premier enfant qui en porte un)."""
    if getattr(composant, "id", None):
        return composant.id
    enfants = getattr(composant, "children", None) or []
    for c in (enfants if isinstance(enfants, (list, tuple)) else [enfants]):
        if getattr(c, "id", None):
            return c.id
    return None


def filtre(lib, composant, texte_aide=None, cls=""):
    """Sélecteur avec son libellé **au-dessus** du champ (jamais dedans)."""
    return html.Div([html.Label([lib, aide(texte_aide, lib)] if texte_aide else lib,
                                htmlFor=_id_champ(composant), className="filtre-lib"), composant],
                    className=("filtre " + cls).strip())


def barre_filtres(*filtres, action=None, note_=None, **kw):
    """Rangée de filtres **sans cadre**, posée sur le fond de page.

    Les champs portent déjà leur filet : un panneau autour coûtait 26 px de hauteur par page.
    `action` : une seule action, alignée à droite et sur le bas des champs (« Exporter en CSV ») ;
    sous 621 px elle passe en pleine largeur. `note_` occupe sa propre ligne, jamais la place de
    l'action — une note contextuelle vit plutôt dans la note du panneau du tableau.
    """
    enfants = [f for f in filtres if f is not None]
    return html.Div([*enfants, action, note(note_) if isinstance(note_, str) else note_],
                    className="barre-filtres", **kw)


def outils_carte(id_plus, id_moins, id_recadrer, **kw):
    """Trois boutons de carte : « Agrandir » · « Réduire » · « Recadrer ».

    Verbes à l'infinitif, **aucune icône** (la barre d'outils de Plotly reste masquée) : ils sont
    le chemin clavier du zoom, que la molette et le pincement font aussi. Un seul écran les
    utilise : l'Implantation.
    """
    return html.Div([bouton("Agrandir", id_=id_plus, title="Agrandir la carte"),
                     bouton("Réduire", id_=id_moins, title="Réduire la carte"),
                     bouton("Recadrer", id_=id_recadrer, title="Revenir au cadrage initial")],
                    className="outils-carte", **kw)


def menu(id_, options, valeur, **kw):
    return dcc.Dropdown(id=id_, options=[{"label": v, "value": k} for k, v in options.items()], value=valeur,
                        clearable=False, searchable=kw.pop("searchable", False), **kw)


def menu_natif(id_, options, valeur, **kw):
    """Sélecteur natif `<select>` (44 px, chevron local) : formulaires sans callback et page kit."""
    return html.Span([
        html.Select([html.Option(v, value=k, selected=(k == valeur)) for k, v in options.items()],
                    id=id_, className="menu", **kw),
        html.Span(className="ico ico-chevron", **{"aria-hidden": "true"}),
    ], className="champ-menu")


def controle_segmente(id_, options, valeur, legende, **kw):
    """Choix exclusif court (mesure de la carte) : piste segmentée, option cochée en accent."""
    return html.Fieldset([
        html.Legend(legende, className="choix-lib"),
        html.Div(dcc.RadioItems(id=id_, value=valeur,
                                options=[{"label": v, "value": k} for k, v in options.items()],
                                inline=True, className="choix-radios", inputClassName="opt-input",
                                labelClassName="opt-txt", **kw), className="choix-opts"),
    ], className="choix choix-segment")


def bouton(libelle, id_=None, plein=False, href=None, **kw):
    """Bouton d'action : `.btn-plein` (une seule par zone) ou `.btn-contour`. Libellé à l'infinitif."""
    cls = "btn-plein" if plein else "btn-contour"
    if href is not None:
        return html.A(libelle, href=href, className=cls, **kw)
    return html.Button(libelle, id=id_, className=cls, n_clicks=0, **kw) if id_ else \
        html.Button(libelle, className=cls, **kw)


def lien_suite(txt, href, **kw):
    """Lien de fin de bloc : « … → ». Jamais bleu (le bleu est la sélection)."""
    return dcc.Link(f"{txt} →", href=href, className="lien-suite", **kw)


# ---- données -------------------------------------------------------------------------------------------------
def badge_classe(c, court=False):
    """Priorité P1 (robuste), P2 (probable), P3 (à surveiller) : puces **et** code, jamais la couleur seule."""
    code, lib = CLASSES.get(c, ("–", "non classée"))
    points = {"P1": "●●●", "P2": "●●○", "P3": "●○○"}.get(code, "")
    cls = {"P1": "badge-p1", "P2": "badge-p2", "P3": "badge-p3"}.get(code, "badge-p3")
    return html.Span([html.Span(points, className="pts", **{"aria-hidden": "true"}),
                      code if court else f"{code} · {lib.lower()}"],
                     className=f"badge {cls}", title=f"{code} · {lib.lower()}")


def barre_score(valeur, texte=None, max_=100):
    """Barre de score : piste grise (le score n'est pas une sélection) + valeur alignée à droite."""
    try:
        part = max(2.0, min(100.0, 100.0 * float(valeur) / max_))
    except (TypeError, ValueError):
        part = 2.0
    return html.Div([html.Span(html.Span(className="barre", style={"width": f"{part:.0f}%"}), className="piste"),
                     html.Span(texte if texte is not None else valeur, className="val-score")],
                    className="cell-score")


def barres_composantes(items, **kw):
    """Barres de composantes (`.comp-ligne`) : libellé, piste grise, valeur.

    `items` : (libellé, valeur 0-100). La piste grise reste visible derrière une barre courte et
    sépare le libellé de la barre ; le remplissage est gris, jamais l'accent.
    """
    lignes = []
    for lib, valeur in items:
        try:
            part = max(0.0, min(100.0, float(valeur)))
        except (TypeError, ValueError):
            part = 0.0
        lignes.append(html.Div([
            html.Span(lib, className="comp-lib"),
            html.Span(html.Span(className="comp-barre", style={"width": f"{part:.0f}%"}), className="comp-piste"),
            html.Span(valeur, className="comp-val"),
        ], className="comp-ligne"))
    return html.Div(lignes, className="comp", **kw)


def liste_chiffres(items, **kw):
    """Liste clé-valeur : libellé à gauche (il passe à la ligne), valeur chiffrée à droite."""
    enfants = []
    for lib, val in items:
        enfants += [html.Dt(lib), html.Dd(val)]
    return html.Dl(enfants, className="liste-chiffres", **kw)


_PHOTOS_PRESENTES = {}


def photo_presente(fichier):
    """Le fichier existe-t-il dans `assets/` ? Résultat mémorisé : un seul accès disque par chemin.

    Les portraits ne sont pas livrés avec le code : un clone du projet, une démonstration sur
    une autre machine ou un déploiement sans le dossier média n'en a aucun. La case doit alors se
    rendre **sans** `<img>` — jamais une image cassée.
    """
    if fichier not in _PHOTOS_PRESENTES:
        from pathlib import Path
        racine = Path(__file__).resolve().parent.parent / "assets"
        _PHOTOS_PRESENTES[fichier] = (racine / fichier).is_file()
    return _PHOTOS_PRESENTES[fichier]


def membre_equipe(nom, role, bio=None, photo=None, **kw):
    """Une case du bloc « L'équipe » : portrait rond, nom, rôle, une ligne.

    `photo` est un chemin **relatif à `assets/`** (« equipe/john.jpg ») : le fichier absent, la case
    se rend sans image (`photo_presente`). Le portrait est rond, carré à la source, `object-fit:
    cover`, 72 px (64 px sous 621 px), `alt` = le nom de la personne et dimensions explicites (la
    place est réservée avant le chargement) — aucune initiale en pastille, aucun avatar de
    remplacement. Pas de `loading="lazy"` : `html.Img` de Dash 4.5 refuse cette propriété, et le
    bloc est de toute façon le premier de la page (rien à différer).
    """
    texte_ = [html.P(nom, className="eq-nom"), html.P(role, className="eq-role")]
    if bio:
        texte_.append(html.P(bio, className="eq-bio"))
    img = None
    if photo and photo_presente(photo):
        img = html.Img(src="/assets/" + photo, alt=nom, className="eq-photo", width="72", height="72")
    return html.Div([img, html.Div(texte_, className="eq-txt")], className="eq-membre", **kw)


def grille_equipe(*cases, **kw):
    """Grille du bloc « L'équipe » : 2 colonnes au-dessus de 621 px, 1 en dessous."""
    return html.Div([html.Div(c, className="eq-membre") if getattr(c, "className", "") == "vide" else c
                     for c in cases if c is not None], className="eq-grille", **kw)


def legende_classee(titre_legende, classes, colonne=False, **kw):
    """Légende de carte : 5 classes écrites avec l'unité (jamais une barre continue).

    `colonne=True` : variante `.leg-rampe-colonne`, obligatoire quand la carte
    est dans une colonne latérale de moins de 480 px — à 5 colonnes de ~76 px, un libellé avec son
    unité passe à la ligne et la légende devient irrégulière.
    """
    cases = [html.Div([html.Span(className=f"leg-pastille leg-{cle}"),
                       html.Span(lib, className="leg-txt")], className="leg-case")
             for cle, lib in classes]
    return html.Div([html.Div(titre_legende, className="leg-titre"),
                     html.Div(cases, className="leg-rampe" + (" leg-rampe-colonne" if colonne else ""))],
                    className="legende", **kw)


def legende_rampe(titre_legende, libelles, colonne=False, **kw):
    """Légende de la rampe ocre à partir des 5 libellés de `figures.libelles_classes()`."""
    return legende_classee(titre_legende, list(zip(("c1", "c2", "c3", "c4", "c5"), libelles)),
                           colonne=colonne, **kw)


def legende_situation(**kw):
    return html.Span([html.Span(className="pastille pastille-province"), "province",
                      html.Span(className="pastille pastille-region"), "sa région"],
                     className="note legende-situation", **kw)


def legende_marqueurs(*items, lib=None, **kw):
    """Légende de marqueurs ou de motifs : chaque item est (classe de la pastille, libellé).

    Classes disponibles : `leg-rond leg-fiable`, `leg-rond leg-verifier`, `leg-case-carte leg-hachure`.
    Le motif ou le contour porte l'information en plus de la couleur.
    """
    enfants = [html.Span(lib, className="leg-lib")] if lib else []
    enfants += [html.Span([html.Span(className=cls), libelle], className="leg-item")
                for cls, libelle in items]
    return html.Div(enfants, className="legende-marqueurs", **kw)


# ---- états ---------------------------------------------------------------------------------------------------
def vide(phrase, suite=None, **kw):
    """État vide : dit ce qui manque **et** quoi faire. Jamais un tableau vide, jamais une illustration."""
    return html.P([html.Strong(phrase), " " + suite if suite else None], className="vide", **kw)


def bande_obsolete(depuis, derniere, **kw):
    """Bande ambre datée, au-dessus du contenu : un état obsolète n'est jamais rendu comme un état frais."""
    return html.Div([html.Span(className="obs-pt", **{"aria-hidden": "true"}),
                     html.P(f"Base injoignable depuis {depuis}. Les chiffres affichés sont ceux de la dernière "
                            f"mise à jour, le {derniere}."),
                     bouton("Réessayer", href="")], className="bande-obsolete", role="status", **kw)


def erreur_donnees(derniere=None):
    """Bloc erreur : le contenu disparaît (aucun chiffre périmé affiché comme s'il était frais)."""
    return html.Section([
        html.H2("Les données ne sont pas disponibles pour le moment"),
        html.P("La connexion à la base a échoué. Réessayez dans une minute ; si le problème persiste, "
               "consultez le journal du service."),
        html.P(f"Dernière lecture réussie : {derniere}.", className="err-detail") if derniere else None,
        bouton("Réessayer", href="", plein=True),
    ], className="bloc-erreur", role="alert")


def page_introuvable():
    """Une adresse inconnue n'est pas une panne de données : ton neutre, retour au travail."""
    return html.Section([
        html.H2("Page introuvable"),
        html.P("Cette adresse ne correspond à aucune page du tableau de bord."),
        lien_suite("Retour à la vue d'ensemble", "/"),
    ], className="bloc-erreur bloc-introuvable")


def squelette(hauteur=None, **kw):
    """Aplat de chargement : sans dégradé ni animation (ce serait la seule animation du produit)."""
    style = {"height": f"{hauteur}px"} if hauteur else None
    return html.I(className="sk", style=style, **{"aria-hidden": "true"}, **kw)


def zone_squelette(*enfants, hauteur=None, cls="", **kw):
    return html.Div([*enfants, squelette(hauteur)], className=("sk-zone " + cls).strip(), **kw)


def valeur_sk(valeur):
    """Valeur recouverte par son aplat, à la même géométrie (le libellé reste lisible)."""
    return html.Span([valeur, squelette()], className="v")


def chargement(enfant):
    return dcc.Loading(enfant, type="circle", delay_show=250)
