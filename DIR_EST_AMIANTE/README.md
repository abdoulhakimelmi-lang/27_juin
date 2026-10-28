# DIR EST AMIANTE — Python Toolbox ArcGIS Pro

Version **0.1.0-phase1** (diagnostic uniquement).

> Ce code **n'a jamais été exécuté dans ArcGIS Pro**. Il a été testé avec
> un faux module `arcpy` (en mémoire) et des données fictives. Le premier
> vrai test aura lieu sur le VDI.

## Installation sur le VDI

1. Copier le dossier `DIR_EST_AMIANTE` complet, par exemple dans le
   dossier du projet ArcGIS Pro. Le dossier `amiante_core` doit rester à côté
   de `DIR_EST_AMIANTE.pyt`.
2. Dans ArcGIS Pro : volet **Catalogue** > clic droit sur **Boîtes
   d'outils** > **Ajouter une boîte d'outils** > choisir `DIR_EST_AMIANTE.pyt`.
3. Ouvrir l'outil **Traitement des PDF Amiante**.

## Paramètres

| # | Paramètre | Type |
|---|-----------|------|
| 1 | Dossier contenant les PDF | Dossier |
| 2 | Couche locale des tronçons (`REF_INTERPLO_TRONCONS_V1_CORRIGE`) | Couche d'entités polyligne |
| 3 | Couche locale des points PR (`REF_INTERPLO_POINTS_PR_V1`) | Couche d'entités ponctuelle |
| 4 | INTERPLO d'origine (`interPlo_pr_2026`) | Couche d'entités ou table |
| 5 | Géodatabase de sortie | Géodatabase fichier |
| 6 | Préfixe des résultats | Texte (lettre puis lettres/chiffres/_, 30 car. max) |
| 7 | Mode de traitement | `DIAGNOSTIC` ou `RECONSTRUCTION` (bloqué en phase 1) |

Aucun chemin n'est écrit en dur dans le code.

## Ce que fait le mode DIAGNOSTIC

1. **Analyse des noms de PDF** du dossier (non récursif) :
   - section : `2023_NA_39_N0005_PR109500_PR110000_I.pdf` ;
   - section avec changement de côté : `2017_A_88_N0059_PR021500_G_PR025000_I.pdf` ;
   - bretelle : `2023_NA_54A933040_3.pdf` → `route=54A933040`, `nomplodeb=DB3`, `nomplofin=FB3`.
   - `A` = amianté, `NA` = non amianté ; `U` traité comme `I` pour les contrôles ;
   - PR : 3 derniers chiffres = abscisse (m), le reste = numéro de PR
     (`PR45100` est accepté avec un avertissement car codé sur 5 chiffres) ;
   - avertissements : changement de côté, PR décroissants, doublons potentiels
     (même objet dans deux PDF, statuts A/NA contradictoires signalés) ;
   - erreurs : nom non conforme, PR début = PR fin.
2. **Structure des trois couches** : géométrie, référence spatiale, nombre
   d'entités (comparé aux effectifs annoncés 3 257 / 6 514 / 3 257), **liste
   complète des champs**, champs requis manquants (comparaison insensible à la
   casse), sélection active éventuelle.
3. **Présence des routes** : route des sections dans le champ `ROUTE` des
   tronçons locaux, route des bretelles dans le champ `route` d'INTERPLO.
   Résultat `EXACTE`, `VARIANTE:<code>` (ex. `N0059` trouvé seulement en
   `N59` — signalé, jamais accepté), `ABSENTE` ou `NON_CONTROLEE`.
4. **Nouvelle table** `<PREFIXE>_DIAG_PDF_<AAAAMMJJ_HHMMSS>` dans la
   géodatabase de sortie, une ligne par PDF.

## Sécurité

- Lecture seule sur les trois couches fournies (aucun curseur d'écriture
  ouvert dessus).
- `arcpy.env.overwriteOutput = False` à chaque exécution.
- Nom de sortie horodaté ; si le nom existe déjà, suffixe `_2`, `_3`… ;
  création refusée si la table existe.
- Aucun accès aux 109 sections Amiante originales ni aux quatre couches de
  résultats historiques.

## Premier test sur le VDI — à me renvoyer

1. Lancer le mode **DIAGNOSTIC** sur `envoi_2` (attendu : 49 PDF, 39
   sections, 10 bretelles).
2. Copier **l'intégralité des messages** de l'onglet *Messages* de l'outil
   (ou les erreurs Python complètes en cas d'échec).
3. En particulier, me transmettre la **liste des champs de
   `REF_INTERPLO_POINTS_PR_V1`** affichée par le diagnostic, et indiquer si
   les routes sont `EXACTE` ou `VARIANTE`.
4. Recommencer avec `envoi_1`.

Les noms de PDF non reconnus apparaissent dans la table avec
`TYPE_PDF = NON_RECONNU` : me transmettre ces noms permettra d'élargir les
formats acceptés.

### Inventaire sans ArcGIS

```bash
python outils/inventaire_pdf.py <dossier_pdf> <rapport.csv>
```

N'utilise pas arcpy (aucun contrôle de route). N'écrase jamais un CSV existant.

## Tests (hors ArcGIS Pro)

```bash
python -m unittest discover -s tests -v
```

35 tests : analyse des noms, contrôles, sorties, structure du `.pyt` et
exécution du diagnostic sur un faux `arcpy` (vérifie aussi que les données
existantes ne sont jamais modifiées).

## Architecture

```
DIR_EST_AMIANTE.pyt              boîte à outils (paramètres, validation, exécution)
amiante_core/
  nommage.py                     analyse des noms de PDF            [phase 1]
  referentiel.py                 lecture/structure des couches      [phase 1]
  controles.py                   règles de contrôle génériques      [phase 1, partiel]
  sorties.py                     création de nouvelles sorties      [phase 1]
  diagnostic.py                  orchestration du mode DIAGNOSTIC   [phase 1]
  reconstruction_bretelles.py    correspondance bretelles           [phase 2 — à faire]
  localisation.py                localisation des PR                [phase 3 — à faire]
  reconstruction_sections.py     reconstruction des sections        [phase 3 — à faire]
  geometrie.py                   découpe / assemblage des géométries [phases 2-3 — à faire]
outils/inventaire_pdf.py         inventaire CSV sans ArcGIS
tests/                           tests unittest + faux arcpy
```

## Non implémenté (volontairement)

- Correspondance des bretelles dans INTERPLO (`route`/`nomplodeb`/`nomplofin`),
  contrôle d'unicité, concordance `objetid` ↔ `ID_INTERPLO` — **phase 2**.
- Localisation des PR et reconstruction des sections (logiques DF/FF,
  `LOGIQUE_2/3`, changements de côté, tronçons communs codés D) — **phase 3**,
  après réception des scripts historiques V6A, V6C, V7B, V8D. Aucune règle
  n'est inventée en leur absence.
- Création de classes d'entités géométriques en sortie.
- Lecture du contenu des PDF (seuls les noms de fichiers sont analysés).
