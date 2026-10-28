# DIR EST AMIANTE — Python Toolbox ArcGIS Pro

Version **0.2.1-phase2-correctif** : diagnostic (phase 1, validé sur le
VDI) et reconstruction des bretelles (phase 2, **à tester sur le VDI**).

> Ce code **n'a jamais été exécuté dans ArcGIS Pro**, y compris le
> chargement dans le Catalogue. Il a été testé avec un faux module `arcpy`
> (en mémoire) et des données fictives, sous Python 3.9, 3.11 et 3.13.

## Correctif de chargement (0.2.1)

**Problème constaté sur le VDI** : la phase 2 ne s'ouvrait pas dans le
Catalogue. L'erreur était
`ImportError: cannot import name 'comparaison' from 'amiante_core'`, avec
un `amiante_core` lu dans le dossier de la phase 1.

**Cause** : les deux phases utilisaient le même nom de paquet,
`amiante_core`, chargé par `sys.path`. Python garde chaque module en
mémoire sous son nom (`sys.modules`). Quand la boîte de phase 1 était
chargée en premier dans la session, la phase 2 recevait le paquet de la
phase 1, qui n'a pas `comparaison`. Un redémarrage ne suffit pas tant que
les deux boîtes sont dans le projet.

**Correction** :
- le paquet s'appelle désormais **`amiante_core_v2`** ;
- le fichier s'appelle **`DIR_EST_AMIANTE_V2.pyt`**, avec l'alias
  `DIRESTAMIANTEV2` et le libellé « DIR EST AMIANTE V2 », pour se distinguer
  de la phase 1 ;
- le `.pyt` charge le paquet **par son chemin exact**, celui du dossier du
  `.pyt`. Il **ne modifie plus `sys.path`**. Il retire de la mémoire toute
  autre copie de `amiante_core_v2` avant de charger la sienne, et vérifie que
  chaque sous-module vient bien de son dossier. Le `amiante_core` de la
  phase 1 n'est pas touché ;
- le moteur n'est plus importé à l'ouverture du `.pyt` : une erreur de
  chargement s'affiche sur le premier paramètre de l'outil au lieu de
  produire l'icône rouge ;
- le moteur est rechargé entièrement à chaque exécution, ce qui remplace
  `importlib.reload`. Le journal affiche « Moteur chargé depuis : … » ;
- tous les imports internes sont des imports relatifs en tête de module.

## Installation sur le VDI

1. Dans ArcGIS Pro, **retirer du projet** l'ancienne boîte de phase 2
   (clic droit > Retirer : aucun fichier n'est supprimé). La boîte de
   phase 1 peut rester.
2. Fermer ArcGIS Pro. Cela vide la mémoire Python, y compris les modules
   chargés à la main dans le Notebook.
3. Décompresser `DIR_EST_AMIANTE_phase2_correctif.zip` dans un **nouveau
   dossier**, par exemple
   `C:\Users\<vous>\Documents\DIR_EST_AMIANTE_phase2_correctif\`. Ne pas
   décompresser par-dessus l'ancienne phase 2 ni dans le dossier de la
   phase 1.
4. Vérifier que le dossier contient `DIR_EST_AMIANTE_V2.pyt` **et**, juste
   à côté, le dossier `amiante_core_v2`.
5. Ouvrir ArcGIS Pro et le projet. Dans le volet **Catalogue**, clic droit
   sur **Boîtes d'outils** > **Ajouter une boîte d'outils** >
   `DIR_EST_AMIANTE_V2.pyt`.
6. Ouvrir **DIR EST AMIANTE V2** > **Traitement des PDF Amiante**. Au
   lancement, le journal doit afficher la version `0.2.1-phase2-correctif`
   et le chemin du dossier `amiante_core_v2` utilisé.

### Si l'icône reste rouge

Dans un Notebook ArcGIS Pro, sans redémarrer :

```python
%run "C:\...\DIR_EST_AMIANTE_phase2_correctif\DIR_EST_AMIANTE\outils\verifier_chargement.py" "C:\...\DIR_EST_AMIANTE_phase2_correctif\DIR_EST_AMIANTE\DIR_EST_AMIANTE_V2.pyt"
```

Le script ne lit ni n'écrit aucune donnée SIG. Il affiche :
- les modules « amiante » déjà en mémoire ;
- le résultat de l'import du `.pyt` (nombre de paramètres) ;
- le dossier d'où vient chaque module du moteur ;
- l'erreur éventuelle renvoyée par `arcpy.ImportToolbox`.

Me transmettre la sortie complète.

## Paramètres

| # | Paramètre | Type |
|---|-----------|------|
| 1 | Dossier contenant les PDF | Dossier |
| 2 | Tronçons locaux (`REF_INTERPLO_TRONCONS_V1_CORRIGE`) | Couche polyligne |
| 3 | Points PR (`REF_INTERPLO_POINTS_PR_V1`) | Couche ponctuelle (lue, non exploitée en phase 2) |
| 4 | INTERPLO d'origine (`interPlo_pr_2026`) | Couche ou table |
| 5 | Géodatabase de sortie | Géodatabase fichier |
| 6 | Préfixe des résultats | Texte (ex. `TEST_ENVOI2`) |
| 7 | Mode | `DIAGNOSTIC`, `RECONSTRUCTION_BRETELLES`, `RECONSTRUCTION_SECTIONS` (bloqué) |
| 8 | Couche historique de comparaison | Facultatif, actif en mode bretelles |
| 9 | Champ identifiant INTERPLO de la couche historique | Facultatif ; par défaut `ID_INTERPLO` s'il existe |

Aucun chemin n'est écrit en dur dans le code.

## Mode DIAGNOSTIC (phase 1, inchangé)

Analyse des noms de PDF, structure des trois couches, présence des routes,
table `<PREFIXE>_DIAG_PDF_<date>`. Ajouts phase 2 : contrôle des références
spatiales (2154 / 2154 / 3857) et des champs de la couche points PR.

## Mode RECONSTRUCTION_BRETELLES (phase 2)

Pour chaque PDF bretelle, par exemple `2023_NA_54A933040_3.pdf` :

1. **Nom du PDF** : année 2023, statut NA, code échangeur `54A933040`,
   bretelle n° 3. Les sections courantes sont comptées puis ignorées.
2. **Code échangeur** : forme habituelle `<2-3 chiffres><lettre><chiffres>`
   (sinon avertissement) et présence dans le champ `route` d'INTERPLO.
3. **Numéro de bretelle** ≥ 1.
4. **DB{n} / FB{n}** : recherche `route = 54A933040`, `nomplodeb = DB3`,
   `nomplofin = FB3` (comparaison sans tenir compte des majuscules ni des
   espaces en début et fin). Une autre écriture (`DB03`, `DB 3`) est
   **signalée mais jamais acceptée**.
5. **Unicité dans INTERPLO** : exactement une ligne. L'`objetid` doit aussi
   être unique dans toute la couche.
6. **Unicité dans le référentiel local** : `ID_INTERPLO = objetid`,
   exactement une entité. Les types sont rapprochés sans créer d'équivalence
   (`1234`, `1234.0` et `"1234"` sont le même identifiant).
7. **Géométrie** lue en **EPSG:2154**, non vide et de longueur non nulle.
8. **Longueurs** : `LONG_REF_M` = champ de référencement du référentiel ;
   `LONG_GEOM_M` = longueur recalculée sur la géométrie. Si le `LONG_GEOM_M`
   stocké diffère de plus de 1 cm, un avertissement est émis.
9. **Écart** : `ECART_M = LONG_GEOM_M − LONG_REF_M` (et `ECART_PCT`).
10. **Statut** `CANDIDAT_A_VALIDER`.

Des avertissements, qui ne bloquent pas, sont émis si :
- la `ROUTE` ou le `DEPARTEMENT` du tronçon local ne concorde pas avec le
  code échangeur ;
- la géométrie a plusieurs parties ;
- deux PDF aboutissent au même `ID_INTERPLO`.

En cas d'absence ou d'ambiguïté, **aucune géométrie n'est créée**, et la
table de contrôle porte l'un des codes suivants :

| Code `CONTROLE` | Cause |
|---|---|
| `ANOMALIE_NOM_PDF` | nom non conforme |
| `ANOMALIE_CODE_ECHANGEUR_ABSENT` | route absente d'INTERPLO |
| `ANOMALIE_NUMERO_BRETELLE` | numéro 0 |
| `ANOMALIE_AUCUNE_CORRESPONDANCE_INTERPLO` | pas de ligne DB{n}/FB{n} (le détail indique les couples disponibles pour la route) |
| `ANOMALIE_CORRESPONDANCE_INTERPLO_AMBIGUE` | plusieurs lignes (les `objetid` sont listés) |
| `ANOMALIE_OBJETID_VIDE` / `ANOMALIE_OBJETID_NON_UNIQUE_INTERPLO` | identifiant d'origine inutilisable |
| `ANOMALIE_ID_ABSENT_REFERENTIEL_LOCAL` / `ANOMALIE_ID_AMBIGU_REFERENTIEL_LOCAL` | `ID_INTERPLO` introuvable ou en double |
| `ANOMALIE_GEOMETRIE_VIDE` | géométrie locale absente ou vide |

### Sorties (nouvelles uniquement, même horodatage)

- `<PREFIXE>_BRETELLES_<AAAAMMJJ_HHMMSS>` : classe d'entités polyligne en
  EPSG:2154. Elle a les mêmes propriétés Z/M que le référentiel local et ne
  contient que les candidats.
- `CONTROLE_<PREFIXE>_BRETELLES_<date>` : table, une ligne par PDF bretelle.
- `COMPARAISON_<PREFIXE>_BRETELLES_<date>` : table créée seulement si une
  couche historique est fournie.

Avec le préfixe `TEST_ENVOI2`, on obtient `TEST_ENVOI2_BRETELLES_<date>` et
`CONTROLE_TEST_ENVOI2_BRETELLES_<date>`.

Champs : `NOM_PDF, ANNEE, STATUT_AM, ROUTE, DEPARTEMENT, NUM_BRET,
ID_INTERPLO, LONG_REF_M, LONG_GEOM_M, ECART_M, CONTROLE`, puis des champs
de traçabilité : `ECART_PCT, NOMPLODEB, NOMPLOFIN, OBJETID_ORIG,
NB_CORR_ORIG, NB_CORR_LOCAL, COTE, LONG_GEOM_ATTR_M, NB_PARTIES, ANOMALIES,
DATE_TRAITEMENT`.

### Comparaison avec la couche historique

La comparaison porte sur les identifiants, les longueurs et les tracés, et
pas seulement sur le nombre d'entités :

- **par identifiant** : si un champ identifiant est indiqué en paramètre 9
  ou si la couche contient `ID_INTERPLO` ;
- **géométrique** sinon : chaque nouvelle bretelle est appariée au tracé
  historique le plus proche.

Pour chaque bretelle, l'outil calcule :
- l'écart de longueur ;
- `DIST_MAX_M`, la distance de Hausdorff densifiée tous les 1 m : c'est le
  plus grand écart entre les deux tracés, quel que soit leur sens ;
- `MEME_SENS`, qui indique si les deux tracés sont numérisés dans le même
  sens.

Les tolérances sont de **1 cm** pour le tracé et pour la longueur.

| Résultat | Signification |
|---|---|
| `IDENTIQUE` | tracé et longueur dans les tolérances |
| `TRACE_DIFFERENT` | distance max > 1 cm |
| `LONGUEUR_DIFFERENTE` | tracé proche mais longueur différente |
| `ABSENT_DE_L_HISTORIQUE` / `ABSENT_DU_NOUVEAU_RESULTAT` | identifiant d'un seul côté |
| `ID_EN_DOUBLE_DANS_HISTORIQUE` | identifiant présent plusieurs fois dans l'historique |
| `AUCUN_TRACE_HISTORIQUE_PROCHE` | mode géométrique : aucun tracé à moins de 100 m |

La couche historique est seulement lue, et ses géométries sont projetées à
la volée en EPSG:2154. Une différence de quelques millimètres ou centimètres
peut indiquer que l'ancien script V8D avait pris sa géométrie ailleurs, par
exemple dans la couche INTERPLO d'origine en EPSG:3857 : `DIST_MAX_M`
permet de le voir.

## Sécurité

- Lecture seule sur toutes les couches fournies : référentiels, INTERPLO
  Enterprise, couche historique. Aucun curseur d'écriture ne les concerne.
- `arcpy.env.overwriteOutput = False` à chaque exécution ; `True` n'est
  jamais utilisé.
- Noms de sortie horodatés. Si un nom existe déjà, le suffixe `_2`, `_3`…
  est ajouté à toutes les sorties liées, et la création d'une sortie
  existante est refusée.
- Contrôle des champs obligatoires **avant toute écriture** : en cas de
  champ manquant, rien n'est créé.
- INTERPLO d'origine : seuls les attributs sont lus, jamais la géométrie.
- Une **sélection active** sur une couche limite la lecture aux entités
  sélectionnées : le journal le signale. Effacer les sélections avant le
  test. Une requête de définition sur une couche a le même effet ; elle
  n'est pas détectée.

## Test de référence sur le VDI — à me renvoyer

1. Mode **RECONSTRUCTION_BRETELLES** sur `envoi_2`, préfixe `TEST_ENVOI2`,
   couche historique `AMIANTE_10_BRETELLES_V8D_TEST`. Paramètre 9 : le
   champ qui contient l'identifiant INTERPLO dans cette couche, s'il existe.
2. Attendu : 10 bretelles `CANDIDAT_A_VALIDER`, 39 sections ignorées et,
   dans la comparaison, 10 `IDENTIQUE`.
3. Me renvoyer :
   - **tous les messages** de l'outil ;
   - le contenu de la table `COMPARAISON_…`, en particulier `DIST_MAX_M` et
     `ECART_LONG_M` ;
   - en cas d'anomalie, la ligne correspondante de la table `CONTROLE_…` ;
   - le nom du champ identifiant de la couche V8D, s'il n'est pas
     `ID_INTERPLO`.
4. Puis le même mode sur `envoi_1`, sans couche historique.

## Tests (hors ArcGIS Pro)

```bash
python -m unittest discover -s tests -v
```

85 tests au total. Le code est compatible avec Python 3.7 et plus
(vérifié avec vermin) et pyflakes ne signale rien.

| Fichier | Contenu | Tests |
|---|---|---|
| `test_nommage.py` | analyse des noms de PDF | 18 |
| `test_controles_sorties.py` | contrôles, préfixe, noms uniques, CSV | 11 |
| `test_toolbox.py` | structure du `.pyt`, mode DIAGNOSTIC | 7 |
| `test_bretelles.py` | moteur bretelles : cas nominal et toutes les anomalies | 21 |
| `test_geometrie_comparaison.py` | Hausdorff, sens, identifiants, comparaison | 13 |
| `test_toolbox_bretelles.py` | mode bretelles de bout en bout | 6 |
| `test_coexistence_phases.py` | phases 1 et 2 dans le même Python | 9 |

Le test de coexistence construit, dans un dossier temporaire, une phase 1
(paquet `amiante_core` et `.pyt` reprenant son mécanisme d'import par
`sys.path`) et une phase 2 corrigée. Il vérifie :
- qu'il **reproduit l'erreur d'origine** avec l'ancien mécanisme ;
- que l'ordre de chargement phase 1 puis phase 2, ou l'inverse, est sans
  effet : chacune utilise son propre moteur ;
- que la phase 2 ne touche pas à `sys.path` ;
- qu'une copie périmée de `amiante_core_v2`, déjà en mémoire et en tête de
  `sys.path`, est ignorée ;
- qu'une exécution complète du mode bretelles fonctionne avec la phase 1
  chargée ;
- que deux copies de la phase 2 utilisent chacune leur propre moteur ;
- qu'un paquet incomplet ou absent n'empêche pas l'ouverture du `.pyt` et
  produit un message clair.

Le test de bout en bout porte sur 10 bretelles fictives, plus une bretelle
ambiguë, un code échangeur absent et 2 sections. Il vérifie :
- la comparaison par identifiant et la comparaison géométrique ;
- la détection d'un tracé décalé de 30 cm ;
- le blocage avant écriture quand un champ manque ;
- qu'une seconde exécution ne modifie pas les sorties de la première ;
- que les données d'entrée restent intactes.

### Inventaire sans ArcGIS

```bash
python outils/inventaire_pdf.py <dossier_pdf> <rapport.csv>
```

### Vérification du chargement (Notebook ArcGIS Pro)

```bash
python outils/verifier_chargement.py <chemin>/DIR_EST_AMIANTE_V2.pyt
```

## Architecture

```
DIR_EST_AMIANTE_V2.pyt           boîte à outils (chargement par chemin, paramètres, modes)
amiante_core_v2/
  nommage.py                     analyse des noms de PDF                [phase 1]
  referentiel.py                 lecture/structure des couches          [phases 1-2]
  controles.py                   règles de contrôle, identifiants       [phases 1-2]
  sorties.py                     tables / classes d'entités nouvelles   [phases 1-2]
  diagnostic.py                  mode DIAGNOSTIC                        [phase 1]
  reconstruction_bretelles.py    mode RECONSTRUCTION_BRETELLES          [phase 2]
  comparaison.py                 comparaison avec une couche historique [phase 2]
  geometrie.py                   longueurs, coordonnées, Hausdorff      [phase 2]
  localisation.py                localisation des PR                    [phase 3 — à faire]
  reconstruction_sections.py     reconstruction des sections            [phase 3 — à faire]
outils/inventaire_pdf.py         inventaire CSV sans ArcGIS
outils/verifier_chargement.py    diagnostic du chargement dans ArcGIS Pro
tests/                           tests unittest + faux arcpy
```

## Non implémenté

- **Phase 3** : localisation des PR via la couche points PR et
  reconstruction des sections courantes (logiques DF/FF, `LOGIQUE_2/3`,
  changements de côté, tronçons communs codés D). Elle attend les scripts
  historiques V6A, V6C et V7B, et le résultat du test réel de la phase 2.
- Validation manuelle des candidats : le statut reste `CANDIDAT_A_VALIDER`.
- Lecture du contenu des PDF : seuls les noms de fichiers sont analysés.
