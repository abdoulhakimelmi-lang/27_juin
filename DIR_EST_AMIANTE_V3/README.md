# DIR EST AMIANTE V3 — Python Toolbox ArcGIS Pro

Version **0.3.0-phase3** : `DIR_EST_AMIANTE_V3.pyt` + paquet `amiante_core_v3`.

| Mode | Phase | État |
|---|---|---|
| `DIAGNOSTIC` | 1 | validé sur le VDI, comportement inchangé |
| `RECONSTRUCTION_BRETELLES` | 2 | validé sur le VDI (10 `IDENTIQUE`), comportement inchangé |
| `RECONSTRUCTION_SECTIONS` | 3 | **nouveau, à tester sur le VDI** |

> Le mode `RECONSTRUCTION_SECTIONS` **n'a jamais été exécuté dans ArcGIS
> Pro**. Il a été testé avec un faux module `arcpy` et des réseaux fictifs
> reproduisant la structure des cas diagnostiqués. Un statut
> `CANDIDAT_A_VALIDER` n'est **pas** une validation métier, et une
> concordance avec les couches historiques est une reproduction technique.

---

## 1. Installation sur le VDI (indépendante de la V2)

1. Décompresser `DIR_EST_AMIANTE_V3_phase3.zip` dans un **nouveau dossier**,
   par exemple `Documents\DIR_EST_AMIANTE_V3\`. Ne rien écraser : la V2
   (`DIR_EST_AMIANTE_V2.pyt` / `amiante_core_v2`) reste installée et
   utilisable.
2. Vérifier que `DIR_EST_AMIANTE_V3.pyt` et le dossier `amiante_core_v3`
   sont côte à côte.
3. ArcGIS Pro > volet **Catalogue** > clic droit sur **Boîtes d'outils** >
   **Ajouter une boîte d'outils** > `DIR_EST_AMIANTE_V3.pyt`. La boîte
   s'appelle « DIR EST AMIANTE V3 » (alias `DIRESTAMIANTEV3`) et peut
   cohabiter avec la V2 dans le même projet.
4. Au lancement, le journal affiche `version 0.3.0-phase3` et
   « Moteur chargé depuis : …\amiante_core_v3 ». Si l'icône reste rouge,
   voir la section 8.

Le moteur est chargé par **chemin explicite**, sans modifier `sys.path`. Les
paquets `amiante_core` (phase 1) et `amiante_core_v2` (phase 2) éventuellement
présents en mémoire ne peuvent pas être utilisés à sa place : un test le
vérifie.

## 2. Paramètres

Les 9 paramètres de la V2 sont **identiques et dans le même ordre**. Les
paramètres 10 à 14 sont actifs seulement en mode `RECONSTRUCTION_SECTIONS`.

| # | Paramètre | Défaut |
|---|---|---|
| 1 | Dossier contenant les PDF | — |
| 2 | Tronçons locaux `REF_INTERPLO_TRONCONS_V1_CORRIGE` | — |
| 3 | Points PR `REF_INTERPLO_POINTS_PR_V1` (contrôle d'orientation en phase 3) | — |
| 4 | INTERPLO d'origine `interPlo_pr_2026` (bretelles) | — |
| 5 | Géodatabase de sortie | — |
| 6 | Préfixe des résultats (ex. `TEST_ENVOI2`) | `AMIANTE` |
| 7 | Mode | `DIAGNOSTIC` |
| 8-9 | Couche historique des bretelles et champ identifiant (mode bretelles) | — |
| 10 | **Couches historiques des sections** (multivaleur : V6A, V6C, V7B) | — |
| 11 | Tolérance de continuité géométrique (m) | **1,0** (V6A/V6C/V7B) |
| 12 | Tolérance sur les cumuls | **0,001** (V6A/V6C/V7B) |
| 13 | Tolérance sur les abscisses | **0,001** (V6A/V7B) |
| 14 | Seuil d'alerte d'écart de cumul aux changements de côté (m) | **100**, **alerte seulement** |

Limites de recherche (constantes de `parcours.Parametres`, affichées dans le
journal) : 500 tronçons par parcours, 20 parcours, 200 000 états explorés,
60 s par PDF.

## 3. Règles appliquées par `RECONSTRUCTION_SECTIONS`

Le moteur n'utilise **aucune liste d'identifiants INTERPLO** : les scripts V6A,
V6C et V7B ne servent que de référence et de comparaison.

**Chargement du réseau** (règles V6A). Sont écartés, avec leur motif affiché
dans le journal :
- les tronçons dont la géométrie est absente ou a moins de 2 sommets ;
- ceux dont le référencement est incomplet ;
- ceux où `CUMUL_FIN ≤ CUMUL_DEBUT`.

Le département est normalisé : `070`, `70` et `70.0` sont équivalents.

**Localisation des extrémités** (`localisation.py`, règles V6A/V7B à
l'identique, sans autre interpolation) :
- `PR_DEBUT == pr` et `ABS_DEBUT == abs` donne `CUMUL_DEBUT` ;
- `PR_FIN == pr` et `ABS_FIN == abs` donne `CUMUL_FIN` ;
- `PR_DEBUT == pr` donne la position intérieure
  `CUMUL_DEBUT + abs − ABS_DEBUT`, strictement dans le tronçon.

Si aucune position n'est trouvée, le statut est `PR_DEBUT_INTROUVABLE` ou
`PR_FIN_INTROUVABLE`. Les positions trouvées sur un tronçon non admis sont
citées dans l'observation. Plusieurs positions possibles donnent une alerte,
et la recherche de parcours tranche.

**Côtés admis.** U est traité comme I, et la valeur d'origine du PDF est
conservée dans les sorties. Deux familles de tronçons sont admises :
- `STRICT` : le côté de début ou le côté de fin du PDF ;
- `PORTION_COMMUNE` : un tronçon côté D qui porte **lui-même** DF ou FF,
  quand le PDF comporte le côté I (règle V6C).

Les deux familles sont explorées **ensemble**. Un parcours strict
n'interrompt pas la recherche : une alternative par une portion commune
rend le PDF `PARCOURS_AMBIGU`.

**Raccordement A → B.** Trois contrôles distincts sont faits, et chacun est
enregistré dans la table détaillée :
1. **Géométrie** : distance entre la fin de A et le début de B ≤ tolérance
   géométrique. Ce contrôle est toujours exigé.
2. **Cumuls** :
   - même côté : `B.CUMUL_DEBUT ≤ A.CUMUL_FIN + tol` et
     `B.CUMUL_FIN > A.CUMUL_FIN + tol` (règle V6A). Un chevauchement est
     signalé ;
   - changement de côté : l'écart `B.CUMUL_DEBUT − A.CUMUL_FIN` est
     **toujours enregistré** et n'est **jamais** un critère d'exclusion. Un
     écart non nul donne une alerte, et un écart supérieur au seuil donne
     `TRANSITION_DOUTEUSE`.
3. **Côtés et logiques** : un changement de côté exige DF ou FF dans les 4
   logiques de A **ou** de B (règle V7B). DF ou FF ne suffit jamais seul :
   les contrôles 1 et 2 s'appliquent aussi.

Le nombre de changements de côté n'est pas limité : le cas D → I → D → I
est traité. Les autres codes de logique (CS, DB, DR, FD, SA, SC, DD, FB, FR)
ne sont **pas interprétés**.

**Recherche du parcours** (`parcours.py`) :
- énumération de **tous** les parcours simples, chaque tronçon étant visité
  au plus une fois, de chaque départ jusqu'à la première fin atteinte ;
- 0 parcours donne `PARCOURS_INTROUVABLE`, avec les impasses et le motif de
  refus de chaque voisin ;
- plusieurs parcours donnent `PARCOURS_AMBIGU`, avec toutes les variantes
  écrites dans la table détaillée et aucune géométrie ;
- si une limite est atteinte : `RECHERCHE_INCOMPLETE`, et **aucun** parcours
  n'est retenu, même s'il n'en a trouvé qu'un.

**Contrôles géométriques** du parcours unique :
- une géométrie **multipartie** ou **fermée** donne
  `GEOMETRIE_PROBLEMATIQUE`, sans traitement silencieux ;
- **orientation** par les points PR : le premier sommet est comparé au point
  DEBUT (`X_GEOM`, `Y_GEOM`) et le dernier au point FIN.
  - `INVERSE` ou `INCOHERENT` donne `GEOMETRIE_PROBLEMATIQUE` ; la géométrie
    n'est jamais retournée ;
  - si les points sont absents, l'alerte « orientation non contrôlée » est
    émise ;
- le `CUMUL` des points PR est comparé aux cumuls du tronçon, à titre
  d'alerte seulement.

**Découpe et assemblage** :
- fraction de découpe `(c − CUMUL_DEBUT) / (CUMUL_FIN − CUMUL_DEBUT)`,
  multipliée par la longueur, puis `segmentAlongLine(…, False)` : c'est la
  méthode historique ;
- un écart de raccordement entre portions supérieur à la tolérance donne
  `RACCORDEMENT_NON_CONFORME` ;
- assemblage comme dans V7B : les sommets consécutifs confondus sont
  supprimés, et **aucun segment n'est ajouté** pour combler une lacune.

**Longueurs** :
- `LONG_REF_M` est la **somme des portions de cumul** (règle V7B). Elle
  reste juste même avec un écart de cumul à un changement de côté ;
- `LONG_GEOM_M` est la longueur de la géométrie assemblée ;
- `ECART_M = LONG_GEOM_M − LONG_REF_M`.

**`METHODE`** :
- `COTE_STRICT` ;
- `PORTION_COMMUNE_DF_FF` : PDF à côté unique passant par une portion
  commune ;
- `CHANGEMENT_COTE`, ou `CHANGEMENT_COTE+PORTION_COMMUNE_DF_FF`.

### Statuts (`STATUT_RECONSTRUCTION`)

| Statut | Signification |
|---|---|
| `CANDIDAT_A_VALIDER` | parcours unique, contrôles passés (voir `ALERTES`) |
| `PR_DEBUT_INTROUVABLE` / `PR_FIN_INTROUVABLE` | aucune position fiable |
| `PARCOURS_INTROUVABLE` | aucun parcours admissible (impasses dans `OBSERVATION`) |
| `PARCOURS_AMBIGU` | plusieurs parcours admissibles, aucun choisi |
| `RECHERCHE_INCOMPLETE` | limite atteinte, aucun parcours retenu |
| `RACCORDEMENT_NON_CONFORME` | écart entre portions découpées supérieur à la tolérance |
| `GEOMETRIE_PROBLEMATIQUE` | multipartie, fermée, sens inverse ou incohérent, découpe invalide |
| `ROUTE_ABSENTE_REFERENTIEL` | aucun tronçon pour la route et le département |
| `ERREUR` | exception inattendue (détail dans `OBSERVATION` et le journal) |

## 4. Sorties (nouvelles, même horodatage, préfixe paramétrable)

Avec le préfixe `TEST_ENVOI2` :

| Sortie | Contenu |
|---|---|
| `TEST_ENVOI2_SECTIONS_<date>` | classe d'entités EPSG:2154, une entité par candidat |
| `CONTROLE_TEST_ENVOI2_SECTIONS_<date>` | une ligne par PDF de section, **y compris les échecs** |
| `TRONCONS_TEST_ENVOI2_SECTIONS_<date>` | une ligne par tronçon et par parcours (retenu, variantes ambiguës, parcours rejeté) |
| `COMPARAISON_TEST_ENVOI2_SECTIONS_<date>` | si des couches historiques sont fournies |

**Classe d'entités et table de contrôle** :
- identification : `NOM_PDF`, `ANNEE`, `STATUT_AMIANTE`, `ROUTE`,
  `DEPARTEMENT` ;
- côtés : `COTE_DEBUT`, `COTE_FIN` (valeurs du PDF), puis `COTE_DEB_CTRL`,
  `COTE_FIN_CTRL` (U → I) ;
- PR : `PR_DEBUT`, `PR_FIN` (ex. `PR109+500`), `PR_DEB_NUM`, `ABS_DEB`,
  `PR_FIN_NUM`, `ABS_FIN` ;
- parcours : `IDS_INTERPLO` (liste ordonnée, séparée par des virgules),
  `NB_TRONCONS` ;
- longueurs : `LONG_REF_M`, `LONG_GEOM_M`, `ECART_M` ;
- résultat : `STATUT_RECONSTRUCTION`, `METHODE`, `NB_PARCOURS`,
  `NB_POS_DEBUT`, `NB_POS_FIN`, `NB_CHGT_COTE`, `ECART_RACC_MAX_M`,
  `ECART_CUMUL_MAX_M`, `ALERTES`, `OBSERVATION`, `DATE_TRAITEMENT`.

**Table détaillée des tronçons** :
- repérage : `NOM_PDF`, `VARIANTE`, `STATUT_PARCOURS`, `ORDRE`,
  `ID_INTERPLO`, `COTE`, `APPARTENANCE` (STRICT ou PORTION_COMMUNE) ;
- cumuls : `CUMUL_DEBUT`, `CUMUL_FIN`, `CUMUL_ENTREE`, `CUMUL_SORTIE`, puis
  `LONG_REF_PORTION_M`, `LONG_GEOM_PORTION_M` ;
- raccordement : `TYPE_RACCORDEMENT` (`DEBUT_PARCOURS`, `MEME_COTE` ou
  `CHANGEMENT_COTE`), `ECART_CUMUL_M`, `DISTANCE_RACC_M` ;
- contrôle : `LOGIQUES`, `ORIENTATION`, `ALERTES`.

## 5. Comparaison avec les 39 géométries historiques

**Appariement par PDF** sur une clé normalisée : année, statut, département,
route, PR, et côtés avec U = I. Ainsi le V6C historique
`…PR045500_U.pdf` est apparié à `…PR045500_I.pdf`, et la correspondance est
marquée `RENOMME`.

**Éléments comparés** :
- liste **ordonnée** `IDS_INTERPLO` : `IDS_IDENTIQUES`,
  `MEME_ENSEMBLE_ORDRE_DIFFERENT` ou `IDS_DIFFERENTS` ;
- nombre de tronçons, écart de `LONG_REF_M`, écart de longueur
  géométrique ;
- `DIST_MAX_M`, la distance de Hausdorff densifiée à 1 m ;
- **sens** (`MEME_SENS`, `INVERSE` ou `INDETERMINE`), vérifié séparément par
  le premier et le dernier sommet, puisqu'une distance de Hausdorff nulle ne
  prouve pas le sens.

**Tolérances** : 1 cm pour le tracé et la longueur géométrique, 1 mm pour la
longueur de référencement.

**`RESULTAT`** : `IDENTIQUE`, `IDS_DIFFERENTS`, `IDS_ORDRE_DIFFERENT`,
`SENS_INVERSE`, `SENS_INDETERMINE`, `ECART_GEOMETRIE`, `ECART_LONGUEUR`,
`NON_RECONSTRUIT`, `ABSENT_HISTORIQUE`, `ABSENT_DU_LOT_ACTUEL` ou
`DOUBLON_HISTORIQUE`.

Les couches historiques sont lues en lecture seule et projetées à la volée
en EPSG:2154. Une couche sans `NOM_PDF` ou sans `IDS_INTERPLO` est ignorée,
avec un avertissement.

## 6. Sécurité

- Lecture seule sur toutes les couches fournies : tronçons, points PR,
  INTERPLO, couches historiques V6A, V6C, V7B et V8D. Aucun curseur
  d'écriture ne les concerne.
- `arcpy.env.overwriteOutput = False` à chaque exécution. Les noms de sortie
  sont horodatés, avec le suffixe `_2`, `_3`… si nécessaire, et la création
  d'une sortie existante est refusée.
- Champs obligatoires des tronçons contrôlés **avant toute écriture**.
- Une exception sur un PDF n'interrompt pas le lot : le statut `ERREUR` est
  inscrit dans la table de contrôle.
- Aucun accès aux PDF autre que la lecture de leur nom. Aucune connexion à
  PostgreSQL ni à ArcGIS Enterprise.
- **Effacer les sélections actives** sur les couches avant de lancer
  l'outil : une sélection limite la lecture, et le journal le signale.

## 7. Procédure de test dans ArcGIS Pro

**Test principal**

1. Paramètres :
   - mode `RECONSTRUCTION_SECTIONS`, dossier `envoi_2`, préfixe
     `TEST_ENVOI2` ;
   - couches historiques : `AMIANTE_INTERPLO_36PDF_V6A_TEST`,
     `AMIANTE_N0057_PR45100_PR45500_V6C_TEST` et `AMIANTE_3PDF_V7B_TEST` ;
   - tolérances par défaut.
2. Journal attendu :
   - PDF analysés : 49 | sections reconnues : 39 | bretelles ignorées : 10 ;
   - **objectif** : 39 `CANDIDAT_A_VALIDER`, mais tout autre statut est un
     résultat à analyser et non une erreur à masquer ;
   - comparaison : idéalement 39 `IDENTIQUE`, dont le V6C marqué `RENOMME`.
3. À me renvoyer :
   - **tous les messages** de l'outil ;
   - pour chaque PDF non candidat, ou dont la comparaison n'est pas
     `IDENTIQUE` : sa ligne de `CONTROLE_…`, ses lignes de `TRONCONS_…` et sa
     ligne de `COMPARAISON_…`.

**Non-régression** : relancer `DIAGNOSTIC` puis `RECONSTRUCTION_BRETELLES`
(avec V8D) depuis la V3. Les résultats attendus sont identiques à ceux de la
V2 : 49 PDF / 39 / 10 / 0 erreur, et 10 `IDENTIQUE`.

**Analyse d'un PDF particulier** : diagnostic en lecture seule, dans un
Notebook.

```python
%run "C:\...\DIR_EST_AMIANTE_V3\outils\diagnostic_section.py" "REF_INTERPLO_TRONCONS_V1_CORRIGE" "REF_INTERPLO_POINTS_PR_V1" "2022_NA_70_N0057_PR045100_PR045500_I.pdf"
```

Le script affiche les tronçons concernés, les positions, les départs, tous
les parcours, les impasses avec le motif de refus de chaque voisin, et le
statut final.

## 8. Dépannage du chargement

Dans un Notebook ArcGIS Pro :

```python
%run "C:\...\DIR_EST_AMIANTE_V3\outils\verifier_chargement.py" "C:\...\DIR_EST_AMIANTE_V3\DIR_EST_AMIANTE_V3.pyt"
```

Le script affiche :
- les modules « amiante » déjà en mémoire (`amiante_core`, `_v2`, `_v3`) ;
- l'origine de chaque module du moteur ;
- l'erreur éventuelle renvoyée par `arcpy.ImportToolbox`.

## 9. Modifications depuis la V2

**Nouveaux modules** :
- `reseau.py`, `parcours.py`, `comparaison_sections.py` ;
- `localisation.py` et `reconstruction_sections.py`, qui remplacent les
  ébauches.

**Modules étendus** :
- `geometrie.py` : extrémités, découpe pure équivalente à
  `segmentAlongLine`, assemblage sans segment artificiel, construction de la
  polyligne arcpy, distance de Hausdorff accélérée par un index spatial, au
  résultat identique ;
- `sorties.py` : champs des quatre sorties de sections.

**Boîte à outils** : `DIR_EST_AMIANTE_V3.pyt` avec le paquet
`amiante_core_v3`. Le mode `RECONSTRUCTION_SECTIONS` est activé, et les
paramètres 10 à 14 ont été ajoutés après les 9 existants.

**Outils** : `outils/diagnostic_section.py` (nouveau) ; `verifier_chargement.py`
reconnaît maintenant les trois générations de paquets.

**Phases 1 et 2** : `nommage`, `diagnostic`, `reconstruction_bretelles` et
`comparaison` n'ont pas été modifiés.

## 10. Tests (hors ArcGIS Pro)

```bash
python -m unittest discover -s tests -v
```

**131 tests**, qui passent sous Python 3.9, 3.11 et 3.13. Le code est
compatible avec Python 3.7 et plus (vérifié avec vermin) et pyflakes ne
signale rien.

| Fichier | Contenu | Tests |
|---|---|---|
| `test_nommage.py` | noms de PDF (phase 1) | 18 |
| `test_controles_sorties.py` | contrôles, préfixe, noms uniques | 11 |
| `test_toolbox.py` | structure du `.pyt` (14 paramètres), mode DIAGNOSTIC | 8 |
| `test_bretelles.py` / `test_toolbox_bretelles.py` | phase 2, non-régression | 21 / 6 |
| `test_geometrie_comparaison.py` | Hausdorff, sens, identifiants | 13 |
| `test_sections_moteur.py` | moteur de la phase 3, tous les cas | 27 |
| `test_comparaison_sections.py` | comparaison historique | 11 |
| `test_toolbox_sections.py` | mode sections de bout en bout | 6 |
| `test_coexistence_phases.py` | phases 1, V2 et V3 dans le même Python | 10 |

Les réseaux fictifs de `tests/donnees_sections.py` reproduisent la
**structure** des cas réels, avec des identifiants et des coordonnées
inventés :
- section sur 3 tronçons ;
- section dans un seul tronçon (cas C) ;
- découpe proportionnelle avec écart entre référencement et géométrie ;
- portion commune D/DF (cas V6C), refusée sans DF/FF ;
- G → I avec écart de cumul de +44 m (cas A) ;
- D → I → D → I (cas B) ;
- ambiguïté, y compris entre un parcours strict et une portion commune ;
- rupture géométrique, cumuls non continus, changement de côté sans DF/FF ;
- PR introuvable, positions multiples ;
- géométrie fermée, multipartie, sens inverse ;
- recherche incomplète, sur chacune des trois limites ;
- comparaison : renommage U/I, sens inverse à Hausdorff nul, IDS
  différents, absences, doublon.

## 11. Limites connues

- **Aucune exécution réelle** : le résultat sur les 39 sections n'est pas
  connu avant votre test.
- **PR non localisable** : un PR qui ne coïncide pas avec le `PR_DEBUT` d'un
  tronçon (ni avec une borne exacte) n'est pas localisé. C'est la règle
  V6A, sans interpolation supplémentaire.
- **Ambiguïtés nouvelles possibles** : l'exploration conjointe des parcours
  stricts et des portions communes peut rendre `PARCOURS_AMBIGU` une section
  que V6A reconstruisait. C'est voulu, pour ne pas masquer une ambiguïté
  réelle, mais cela doit être examiné au cas par cas.
- **Fin du parcours** : un parcours s'arrête au premier tronçon qui contient
  une position de fin admise, comme V6A. Une position de départ égale au
  `CUMUL_FIN` du dernier tronçon d'un côté, sans tronçon suivant du même
  côté, n'a pas de départ possible.
- **PDF à PR décroissant** : seul le sens des cumuls croissants est
  recherché. Un tel PDF donne un échec explicite.
- **Codes de logique** : seule la présence de DF ou FF est utilisée. Les
  autres codes ne sont pas interprétés.
- **Découpe proportionnelle** au cumul : sur les tronçons dont la longueur de
  référencement s'écarte de la longueur géométrique, la position découpée
  répartit l'écart uniformément, comme dans les scripts historiques.
- **Chevauchement de cumuls entre tronçons du même côté** : il est accepté
  et signalé, comme dans V6A. La géométrie peut alors contenir la portion
  chevauchante deux fois, et la somme des portions de `LONG_REF_M` diffère
  de « cumul de fin − cumul de début ».
- **Sorties** : les géométries sont créées en X/Y seulement, sans Z ni M,
  comme les couches historiques.
