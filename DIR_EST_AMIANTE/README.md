# DIR EST AMIANTE — Python Toolbox ArcGIS Pro

Version **0.2.0-phase2** : diagnostic (phase 1, validé sur le VDI) et
reconstruction des bretelles (phase 2, **à tester sur le VDI**).

> Le code de la phase 2 **n'a jamais été exécuté dans ArcGIS Pro**. Il a été
> testé avec un faux module `arcpy` (en mémoire) et des données fictives,
> sous Python 3.9, 3.11 et 3.13.

## Installation sur le VDI

1. **Ne pas écraser la version de phase 1** si vous souhaitez la garder :
   décompresser l'archive dans un nouveau dossier, par exemple
   `DIR_EST_AMIANTE_phase2`.
2. Le dossier `amiante_core` doit rester à côté de `DIR_EST_AMIANTE.pyt`.
3. Dans ArcGIS Pro : volet **Catalogue** > clic droit sur **Boîtes
   d'outils** > **Ajouter une boîte d'outils** > `DIR_EST_AMIANTE.pyt`.
   Si l'ancienne boîte est déjà dans le projet, la retirer d'abord (clic
   droit > Retirer du projet : cela ne supprime aucun fichier).
4. Ouvrir l'outil **Traitement des PDF Amiante**. L'outil recharge ses
   modules à chaque exécution : il n'est pas nécessaire de redémarrer
   ArcGIS Pro après une correction des fichiers `.py`.

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

Le code est compatible avec Python 3.7 et plus (vérifié avec vermin) et
pyflakes ne signale rien.

| Fichier | Contenu | Tests |
|---|---|---|
| `test_nommage.py` | analyse des noms de PDF | 18 |
| `test_controles_sorties.py` | contrôles, préfixe, noms uniques, CSV | 11 |
| `test_toolbox.py` | structure du `.pyt`, mode DIAGNOSTIC | 7 |
| `test_bretelles.py` | moteur bretelles : cas nominal et toutes les anomalies | 21 |
| `test_geometrie_comparaison.py` | Hausdorff, sens, identifiants, comparaison | 13 |
| `test_toolbox_bretelles.py` | mode bretelles de bout en bout | 6 |

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

## Architecture

```
DIR_EST_AMIANTE.pyt              boîte à outils (paramètres, validation, modes)
amiante_core/
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
tests/                           tests unittest + faux arcpy
```

## Non implémenté

- **Phase 3** : localisation des PR via la couche points PR et
  reconstruction des sections courantes (logiques DF/FF, `LOGIQUE_2/3`,
  changements de côté, tronçons communs codés D). Elle attend les scripts
  historiques V6A, V6C et V7B, et le résultat du test réel de la phase 2.
- Validation manuelle des candidats : le statut reste `CANDIDAT_A_VALIDER`.
- Lecture du contenu des PDF : seuls les noms de fichiers sont analysés.
