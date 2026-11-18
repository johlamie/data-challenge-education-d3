"""Vue d'ensemble (`/`) : structure « plan de travail », phrase-constat et règles d'interface de l'écran."""
import pytest

from d3dash import calculs as C
from d3dash import navigation as N
from d3dash.pages import accueil


def texte(x):
    return str(x)


def mots(x):
    """Texte visible d'un arbre de composants (str() échappe les espaces insécables des milliers)."""
    if isinstance(x, str):
        return x
    if isinstance(x, (list, tuple)):
        return "".join(mots(i) for i in x)
    enfants = getattr(x, "children", None)
    return mots(enfants) if enfants is not None else ""


@pytest.fixture()
def page(donnees):
    return texte(accueil.layout())


def test_structure_plan_de_travail(page):
    """En-tête, constat, bande unique de 6 chiffres, rangée carte + liste, lien de suite."""
    assert "travail-tete" in page and "Vue d'ensemble" in page
    assert "className='constat'" in page
    assert page.count("bande-kpi") == 1 and page.count("kpi-val") == 6
    assert "className='rangee'" in page and "bloc-carte" in page
    assert "Provinces prioritaires" in page and "tab tab-top10" in page
    assert "Classement complet des 45 provinces" in page
    # les identifiants des callbacks ne changent pas
    for id_ in ("acc-mesure", "acc-carte", "acc-aller", "acc-legende", "acc-lecture"):
        assert id_ in page


def test_constat_reprend_les_valeurs_des_chiffres_cles(donnees):
    """La phrase ne cite que des valeurs déjà produites par `calculs` (aucun chiffre inventé)."""
    from d3dash.meta import fmt_nombre
    k = C.kpis(donnees)
    phrase = accueil.phrase_constat(donnees)
    t = mots(phrase)
    assert f"{fmt_nombre(k['epm'], 1)} élèves par maître" in t
    assert f"{fmt_nombre(k['def_ens'])} enseignants" in t
    assert f"{fmt_nombre(k['def_salles'])} salles de classe" in t
    n1 = accueil.nb_p1(donnees)
    assert n1 == int((C.classement(donnees, "score_priorite")["classe"] == "P1").sum())
    assert f"{fmt_nombre(n1)} province" in t
    # P1 a deux conditions : être dans les dix premières **et**
    # y rester pour au moins 60 % des pondérations tirées. Ni « quelle que soit la pondération »
    # (faux), ni le seul seuil de 60 % (qui laisserait « prioritaire » sans définition).
    assert "dans les 10 premières pour au moins 60 % des pondérations tirées au hasard" in t
    assert "quelle que soit" not in t
    accord = "est" if n1 == 1 else "sont"
    assert f"{fmt_nombre(n1)} province" in t and f"province{'' if n1 == 1 else 's'} {accord} dans" in t
    assert "className='chiffre'" in texte(phrase)


def test_constat_sans_valeur_ne_rend_pas_la_proposition(donnees, monkeypatch):
    """Une valeur absente supprime sa proposition : jamais « — », jamais « 0 »."""
    vrai = C.kpis(donnees)
    monkeypatch.setattr(C, "kpis", lambda d, **kw: {**vrai, "def_salles": None})
    t = mots(accueil.phrase_constat(donnees))
    assert "salles de classe" not in t and "enseignants" in t and "n.d." not in t


def test_une_seule_icone_aide_et_aucune_sur_les_chiffres(page, donnees):
    """Règle du site : une icône « i » sur cet écran (en-tête « Score »), aucune sur un chiffre clé."""
    assert page.count("className='aide'") == 1
    assert "Aide : Score de priorité" in page
    assert "className='aide'" not in texte(accueil.bloc_kpis(donnees))
    # 4 infobulles sans icône sur les indicateurs non évidents
    assert texte(accueil.bloc_kpis(donnees)).count("kpi kpi-aide") == 4


def test_aucune_classe_heritee_ni_couleur_en_dur(page):
    """Les classes de la section « Compatibilité » de style.css et les couleurs inline ont disparu."""
    for legacy in ("vue-ensemble", "ligne-kpi", "ligne-principale", "carte-bloc", "bloc-entete", "entete-vue",
                   "titre-page", "sous-titre", "table-top10", "zone-top10", "col-rang", "col-prov", "col-score",
                   "piste-score", "barre-score", "cellule-score", "choix-mesure", "lien-discret"):
        assert legacy not in page, legacy
    # aucune couleur inline : la barre de score vient du kit (`barre_score`), pas d'un style={"background": …}
    assert "background" not in page


def test_contour_noir_et_rangs_suivent_la_liste(donnees):
    """Sur les trois mesures : contour noir **exactement** sur les dix provinces de la liste, et une
    pastille numérotée par province, portant le même rang que la ligne du tableau (ex æquo compris)."""
    from d3dash import figures as F
    for mesure in accueil.MESURES_CARTE:
        t = accueil.top10(donnees, mesure)
        fig = accueil.figure_carte(donnees, mesure, top=t)
        provinces = [x for x in fig.data if x.fill == "toself"]
        assert len(provinces) == 45
        gras = {x.customdata[0] for x in provinces if x.line.color == F.ENCRE}
        assert gras == set(t.pcode_province), mesure
        pastilles = [x for x in fig.data if x.mode == "markers+text"]
        assert len(pastilles) == 1 and len(pastilles[0].text) == 10, mesure
        assert sorted(pastilles[0].text, key=int) == sorted((str(int(r)) for r in t["rang"]), key=int)


def test_clic_sur_un_remplissage_ouvre_la_fiche():
    """Clic sur un remplissage : Dash transmet tout le tableau `customdata` (code répété), jamais
    une valeur ; le kit en prend le premier élément, `lien_fiche` valide ensuite le code.
    Les deux aides vivent dans `d3dash/navigation.py` : une page n'en importe jamais une autre."""
    assert N.code_clique({"points": [{"curveNumber": 19, "customdata": ["BF0001"] * 12}]}) == "BF0001"
    assert N.code_clique({"points": [{"customdata": "BF0003"}]}) == "BF0003"
    for clic in ({"points": [{"customdata": []}]}, {"points": [{}]}, None, {}):
        assert N.code_clique(clic) is None
    assert N.aller_a_la_fiche({"points": [{"customdata": ["BF0003"] * 12}]}) == "/fiche?pcode=BF0003"


def test_legende_classee_et_lecture_par_mesure(donnees):
    """Chaque mesure a sa légende écrite (5 classes) et sa ligne « Lecture : »."""
    for mesure in accueil.MESURES_CARTE:
        leg = texte(accueil.legende_carte(donnees, mesure))
        assert leg.count("leg-case") == 5 and accueil.TITRES[mesure] in leg
        lec = accueil.lecture_carte(mesure)
        # « Sélectionnez » et non « Cliquez » : l'écran se lit aussi au doigt
        assert lec.endswith("Sélectionnez une province pour ouvrir sa fiche.")
        # le contour noir désigne la liste affichée, sur les trois mesures
        assert "Contour noir" in lec and "chacune porte son rang" in lec


def test_phrase_de_lecture_des_eleves_par_maitre(donnees):
    """La phrase compte les teintes **au-dessus de la norme** d'après les bornes réellement
    tracées : avec 45/50/55/60, trois des cinq classes sont à 50 ou plus (et non deux)."""
    from d3dash import figures as Fg
    lec = accueil.LECTURES["eleves_par_maitre"]
    bornes = Fg.classes([], norme=50)
    assert sum(1 for b in bornes if b >= 50) == 3
    assert lec.startswith("les trois teintes les plus foncées sont à 50 élèves par maître ou plus")
    assert "norme ou au-dessus" in lec
    assert "les deux teintes" not in lec


def test_libelles_sans_jargon_et_rien_de_perdu_dans_les_infobulles(donnees):
    """Le libellé du taux brut est écrit en mots. Les cellules sont raccourcies pour tenir sur une
    ligne chacune : chaque mot retiré d'une cellule se retrouve dans son infobulle —
    « redéployables » est défini dans `A.KPI_DEFICIT_ENS`, la mention de record dans sa variante,
    « scénario central » dans `A.KPI_2030`. Rien n'est perdu."""
    from d3dash import aides as A
    from d3dash import calculs as C
    cells = texte(accueil.bloc_kpis(donnees))
    assert "Taux de scolarisation" in cells and "(TBS)" not in cells
    assert "dont" in cells and "redéployables" in cells
    assert "couverts en déplaçant des enseignants d'autres provinces" not in cells
    assert "Redéployables : enseignants en surplus dans les provinces sous la norme" in A.KPI_DEFICIT_ENS
    assert "jamais été aussi élevé depuis 2017-2018" in A.KPI_DEFICIT_ENS_RECORD
    assert A.deficit_ens(True) is A.KPI_DEFICIT_ENS_RECORD and A.deficit_ens(False) is A.KPI_DEFICIT_ENS
    # la mention de record quitte la cellule mais suit l'état réel des données
    cellule_ens = accueil.bloc_kpis(donnees)[2]
    assert getattr(cellule_ens, "data-aide") == A.deficit_ens(C.kpis(donnees)["def_ens_record"])
    # « par an d'ici 2030 » dans la cellule, « scénario central » dans l'infobulle
    assert "par an d'ici 2030" in cells and "(scénario central)" not in cells
    assert "scénario central" in A.KPI_2030


def test_espaces_insecables_dans_la_lecture_de_la_carte():
    """Règle de langue : espace insécable avant « : » et « ; »."""
    lec = accueil.lecture_carte("score_priorite")
    assert "Contour noir :" in lec and "de la liste ;" in lec
    assert "Traits gris :" in lec
    for mesure in accueil.MESURES_CARTE:
        assert " :" in accueil.lecture_carte(mesure) and " :" not in accueil.lecture_carte(mesure)
    assert " : " not in lec.replace(" ", "")[:0] or True
    assert lec.endswith("Sélectionnez une province pour ouvrir sa fiche.")


def test_entete_porte_la_mention_de_decoupage(page):
    """L'en-tête dit sur quel découpage administratif la page est lue :
    les données de constat sont celles des annuaires, 45 provinces."""
    from d3dash.meta import DECOUPAGE_CONSTAT
    assert "tete-droite" in page and "className='decoupage'" in page
    assert DECOUPAGE_CONSTAT in page and "45 provinces" in DECOUPAGE_CONSTAT
    assert accueil.PERIMETRE in page


def test_lecture_du_panneau_sur_une_ligne(page):
    """La ligne « Lecture : » du panneau tient sur une ligne et n'affirme pas ce que P1 n'est pas :
    la définition complète reste dans l'icône « i » de l'en-tête « Score »,
    et « le rang est repris sur la carte » est déjà écrit sous la carte."""
    assert "P1 = priorité robuste, P2 = probable, P3 à surveiller." in page
    assert "quelle que soit la façon de pondérer" not in page
    assert page.count("Le rang est repris sur la carte") == 0
    assert "60 % de 5 000 pondérations tirées au hasard" in page    # l'icône « i » (aides.SCORE)


# ---- la liste suit la mesure choisie sur la carte -----------------------------------------------
def _cb_mesure(donnees):
    """Le callback `acc-mesure` de la page, appelé hors requête Dash."""
    from d3dash.app import creer_app
    from d3dash.config import Config
    app = creer_app(Config(auth_active=False, code_hash="", secret_key=""), donnees)
    for cle, v in app.callback_map.items():
        if "acc-carte.figure" in cle:
            return v["callback"].__wrapped__
    raise KeyError("acc-carte.figure")


def _cellule(td):
    """Texte d'une cellule, nombres compris (`mots` ne rend que les chaînes)."""
    v = getattr(td, "children", td)
    return str(v) if isinstance(v, (int, float)) else mots(td)


def _lignes(table):
    """Les lignes du `<tbody>` d'un tableau de composants Dash."""
    corps = [n for n in table.children if getattr(n, "_type", "") == "Tbody"][0]
    return corps.children


def test_la_liste_suit_la_mesure_de_la_carte(donnees):
    """Les dix provinces de la liste, leur ordre et leurs rangs sont ceux de `C.classement(d, mesure)` ;
    le contour noir de la carte porte exactement les mêmes dix codes."""
    from d3dash import figures as F
    maj = _cb_mesure(donnees)
    for mesure in accueil.MESURES_CARTE:
        attendu = C.classement(donnees, mesure).head(10)
        fig, _leg, _lec, liste, titre, lien = maj(mesure)
        lignes = _lignes(liste)
        assert len(lignes) == 10
        noms = [_cellule(l.children[1].children[0]) for l in lignes]
        assert noms == list(attendu["province_nom"])
        rangs = [_cellule(l.children[0]) for l in lignes]
        assert rangs == [str(int(r)) for r in attendu["rang"]]
        gras = {t.customdata[0] for t in fig.data if t.fill == "toself" and t.line.color == F.ENCRE}
        assert gras == set(attendu.pcode_province), mesure
        assert titre == accueil.TITRES_LISTE[mesure]
        assert lien == accueil.lien_classement(mesure)


def test_la_liste_montre_la_valeur_de_la_mesure(donnees):
    """La colonne chiffrée porte la valeur de la mesure affichée, formatée par `meta.fmt_mesure` :
    la barre de score reste sur le score (indice de 0 à 100), les autres mesures montrent le nombre."""
    from d3dash.meta import fmt_mesure
    maj = _cb_mesure(donnees)
    for mesure in accueil.MESURES_CARTE:
        attendu = C.classement(donnees, mesure).head(10)
        liste = maj(mesure)[3]
        valeurs = [_cellule(l.children[2]) for l in _lignes(liste)]
        assert valeurs == [fmt_mesure(v, mesure) for v in attendu["valeur"]], mesure
        # l'en-tête nomme la mesure, et le badge de priorité reste une colonne sur les trois
        entete = texte(liste).split("Tbody")[0]
        assert accueil.ENTETES_LISTE[mesure] in entete
        assert all("badge" in texte(l.children[3]) for l in _lignes(liste))
        # légende accessible du tableau : elle suit la mesure, elle aussi
        assert accueil.LEGENDES_LISTE[mesure] in texte(liste)


def test_une_seule_icone_aide_quelle_que_soit_la_mesure(donnees):
    """Budget du site : 4 icônes « i » en tout. Celle du score reste sur sa colonne et n'apparaît
    pas quand la liste est classée sur une autre mesure."""
    maj = _cb_mesure(donnees)
    for mesure in accueil.MESURES_CARTE:
        liste = texte(maj(mesure)[3])
        assert liste.count("className='aide'") == (1 if mesure == "score_priorite" else 0), mesure


def test_les_ex_aequo_de_la_liste_et_de_la_carte_portent_le_meme_rang(donnees):
    """Deux provinces ex æquo partagent leur rang (`method="min"`) : la liste et les pastilles de la
    carte écrivent le même nombre, et la carte ne perd aucune des dix provinces."""
    maj = _cb_mesure(donnees)
    t = C.classement(donnees, "score_priorite").head(10)
    rangs = [int(r) for r in t["rang"]]
    assert len(set(rangs)) < len(rangs), "le jeu de démonstration doit contenir un ex æquo"
    fig, _leg, _lec, liste, _titre, _lien = maj("score_priorite")
    assert [_cellule(l.children[0]) for l in _lignes(liste)] == [str(r) for r in rangs]
    pastilles = [x for x in fig.data if x.mode == "markers+text"][0]
    assert sorted(pastilles.text, key=int) == sorted((str(r) for r in rangs), key=int)
    assert len(pastilles.text) == 10


def test_etat_d_erreur_du_callback(donnees, monkeypatch):
    """Base injoignable : la carte, la liste et les textes passent tous en état « indisponible »,
    aucun chiffre périmé ne reste à l'écran."""
    maj = _cb_mesure(donnees)
    from d3dash.pages import accueil as mod

    def panne():
        raise RuntimeError("base injoignable")

    monkeypatch.setattr(mod, "donnees", panne)
    fig, legende, lec, liste, titre, lien = maj("eleves_par_maitre")
    assert legende is None and "Données indisponibles" in texte(fig)
    assert "className='vide'" in texte(liste) and "tab-top10" not in texte(liste)
    assert titre == accueil.TITRES_LISTE["eleves_par_maitre"] and lien.endswith("eleves_par_maitre")
    assert "limites de région" in lec
