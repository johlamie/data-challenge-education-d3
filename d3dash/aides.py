"""Textes des infobulles : définition courte, puis éventuellement unité, source et « Lecture : ».

Règle d'interface : au plus 4 icônes « i » sur tout le site (normes, score de priorité, scénarios, fiabilité des
sites) ; les chiffres clés non évidents s'expliquent au survol ou au toucher du chiffre lui-même (sans icône).
Les lignes « Unité : », « Sens : », « Source : » et « Lecture : » sont mises en forme par assets/aide.js.
"""

SRC_ANNUAIRES = "annuaires statistiques du primaire DGESS/MENAPLN (2017-2018 à 2024-2025)"
SRC_ARRETE = "arrêté 2020-186/MENAPLN/SG/DGESS (manuel des normes éducatives)"
SRC_DGESS_ENS = "DGESS, tableau de bord du primaire (CNS565, p. 34)"


def texte(definition, unite=None, sens=None, source=None, lecture=None):
    lignes = [definition]
    if unite:
        lignes.append(f"Unité : {unite}")
    if sens:
        lignes.append(f"Sens : {sens}")
    if source:
        lignes.append(f"Source : {source}")
    if lecture:
        lignes.append(f"Lecture : {lecture}")
    return "\n".join(lignes)


# ---- les 4 icônes « i » du site ----
NORMES = texte("Effectif maximal visé : 50 élèves par classe (et par salle) et 50 élèves par enseignant. Les "
               "variantes 60 et 65 (ancien plafond) par classe, 45 et 55 par enseignant, montrent la sensibilité "
               "des besoins à la norme.", source=f"{SRC_ARRETE} ; {SRC_DGESS_ENS}")
SCORE = texte("Moyenne de 5 composantes, chacune classée de 0 à 100 parmi les 45 provinces (poids égaux) : élèves "
              "par salle, élèves par enseignant, salles à construire d'ici 2030, salles perdues pendant la crise, "
              "enfants hors de l'école. P1 = top 10 et dans le top 10 pour au moins 60 % de 5 000 pondérations "
              "tirées au hasard ; P2 = rang ≤ 15 ou top 10 dans au moins 25 % des tirages ; P3 = à surveiller.",
              unite="score sur 100, relatif aux 45 provinces", source="calcul de l'équipe, détail dans À propos")
SCENARIOS = texte("Effectifs 2030 = population 6-11 ans projetée (INSD) × taux de scolarisation supposé. "
                  "S1 : le taux actuel se maintient. S2 (central) : retour au taux d'avant-crise et réouverture des "
                  "salles fermées. S2b : même taux, sans réouverture. S3 : tous les enfants scolarisés (taux d'au moins 100 %).",
                  source="INSD (projections RGPH 2019), annuaires DGESS")
FIABILITE = texte("Un site est « fiable » si sa province est assez bien couverte par la carte des écoles "
                  "(OpenStreetMap recense au moins 50 % des écoles de l'annuaire) et si la localité n'est pas un "
                  "chef-lieu probable (qui a sans doute déjà une école non cartographiée). Sinon, la distance à "
                  "l'école est probablement surestimée : site à vérifier sur le terrain.",
                  source="OpenStreetMap (écoles), OCHA/BNDT (localités), annuaire DGESS 2024-2025")

# ---- infobulles des chiffres clés non évidents (sans icône) ----
_DEF_ENS = ("Somme, province par province, des enseignants qui manquent pour ne pas dépasser 50 élèves par "
            "enseignant dans le public. Les excédents d'une province ne compensent pas les manques d'une autre. "
            "Redéployables : enseignants en surplus dans les provinces sous la norme, qui couvriraient d'autant "
            "le manque total.")
# La cellule de chiffre n'écrit ni « redéployables » en entier ni la mention de record (elle y
# tiendrait sur quatre lignes) : les deux phrases ci-dessous les portent, rien n'est perdu.
KPI_DEFICIT_ENS = texte(_DEF_ENS, source=SRC_ANNUAIRES)
KPI_DEFICIT_ENS_RECORD = texte(_DEF_ENS + " Le manque n'a jamais été aussi élevé depuis 2017-2018.",
                               source=SRC_ANNUAIRES)


def deficit_ens(record=False):
    """Infobulle du manque national d'enseignants, avec la mention de record si elle est vraie."""
    return KPI_DEFICIT_ENS_RECORD if record else KPI_DEFICIT_ENS
KPI_DEFICIT_SALLES = texte("Somme, province par province, des salles qui manquent pour ne pas dépasser 50 élèves "
                           "par salle dans le public.", source=SRC_ANNUAIRES)
# variantes d'une seule province (fiche) : la somme « province par province » est un total national,
# elle serait fausse sur une fiche. Même définition, même source, au périmètre de la province affichée.
KPI_DEFICIT_ENS_PROVINCE = texte("Enseignants qui manquent dans cette province pour ne pas dépasser 50 élèves par "
                                 "enseignant dans le public.", source=SRC_ANNUAIRES)
KPI_DEFICIT_SALLES_PROVINCE = texte("Salles qui manquent dans cette province pour ne pas dépasser 50 élèves par "
                                    "salle dans le public.", source=SRC_ANNUAIRES)
# Le secteur choisi sur la fiche change le périmètre du chiffre affiché : l'infobulle le suit,
# sinon elle dirait « dans le public » devant un chiffre « public + privé ».
SECTEURS = {"PUBLIC": "dans le public", "TOTAL": "dans le public et le privé", "PRIVE": "dans le privé"}


def deficit_ens_province(statut="PUBLIC"):
    """Variante de KPI_DEFICIT_ENS_PROVINCE au secteur affiché (même définition, même source)."""
    return texte(f"Enseignants qui manquent dans cette province pour ne pas dépasser 50 élèves par enseignant "
                 f"{SECTEURS.get(statut, SECTEURS['PUBLIC'])}.", source=SRC_ANNUAIRES)


def deficit_salles_province(statut="PUBLIC"):
    """Variante de KPI_DEFICIT_SALLES_PROVINCE au secteur affiché (même définition, même source)."""
    return texte(f"Salles qui manquent dans cette province pour ne pas dépasser 50 élèves par salle "
                 f"{SECTEURS.get(statut, SECTEURS['PUBLIC'])}.", source=SRC_ANNUAIRES)


KPI_2030 = texte("Salles à construire entre 2025 et 2030 pour accueillir les élèves de 2030 à 50 par classe, "
                 "public et privé, dans le scénario central (retour au taux d'avant-crise, réouverture des salles "
                 "fermées).", source="projections INSD, annuaires DGESS ; calcul de l'équipe")
KPI_TBS = texte("Taux brut de scolarisation : élèves du primaire rapportés aux enfants de 6 à 11 ans. Peut "
                "dépasser 100 % (redoublants, âges décalés).", source=SRC_ANNUAIRES)
KPI_REDEPLOIEMENT = texte("Enseignants en surplus dans les provinces sous la norme, qui pourraient être "
                          "redéployés vers les provinces en manque (au plus le manque total).", source=SRC_ANNUAIRES)
KPI_SITES = texte("Localités à plus de 3 km d'une école connue, où une école servirait le plus d'enfants.",
                  source="OpenStreetMap, OCHA/BNDT, projections INSD")
