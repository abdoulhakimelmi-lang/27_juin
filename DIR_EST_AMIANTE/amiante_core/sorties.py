# -*- coding: utf-8 -*-
"""Création des sorties — uniquement de NOUVELLES tables / classes d'entités.

Règle de sécurité : aucune fonction de ce module n'écrase ni ne modifie une
donnée existante. Si le nom calculé existe déjà, un suffixe _2, _3... est
ajouté ; si la création est demandée sur un nom existant, une exception est
levée.
"""

from __future__ import annotations

import csv
import datetime
import os
import re
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

LONGUEUR_MAX_PREFIXE = 30

# (nom, type arcpy, longueur texte)
CHAMPS_DIAGNOSTIC_PDF: Tuple[Tuple[str, str, int], ...] = (
    ("NOM_PDF", "TEXT", 255),
    ("TYPE_PDF", "TEXT", 20),
    ("ANNEE", "SHORT", 0),
    ("STATUT", "TEXT", 2),
    ("AMIANTE", "TEXT", 3),
    ("DEPARTEMENT", "TEXT", 3),
    ("ROUTE", "TEXT", 30),
    ("PR_DEBUT_TXT", "TEXT", 10),
    ("PR_DEBUT", "LONG", 0),
    ("ABS_DEBUT", "LONG", 0),
    ("COTE_DEBUT", "TEXT", 1),
    ("PR_FIN_TXT", "TEXT", 10),
    ("PR_FIN", "LONG", 0),
    ("ABS_FIN", "LONG", 0),
    ("COTE_FIN", "TEXT", 1),
    ("COTE_DEB_CTRL", "TEXT", 1),
    ("COTE_FIN_CTRL", "TEXT", 1),
    ("CHGT_COTE", "TEXT", 3),
    ("NUM_BRETELLE", "SHORT", 0),
    ("NOMPLODEB_ATT", "TEXT", 10),
    ("NOMPLOFIN_ATT", "TEXT", 10),
    ("ROUTE_REF", "TEXT", 20),          # résultat du contrôle de présence de la route
    ("NB_TRONCONS_ROUTE", "LONG", 0),
    ("NIVEAU_DIAG", "TEXT", 15),
    ("MESSAGES", "TEXT", 2000),
    ("DATE_TRAITEMENT", "DATE", 0),
)


# Bretelles : table de contrôle ET classe d'entités (11 premiers champs = liste demandée)
CHAMPS_BRETELLES: Tuple[Tuple[str, str, int], ...] = (
    ("NOM_PDF", "TEXT", 255),
    ("ANNEE", "SHORT", 0),
    ("STATUT_AM", "TEXT", 2),
    ("ROUTE", "TEXT", 30),
    ("DEPARTEMENT", "TEXT", 3),
    ("NUM_BRET", "SHORT", 0),
    ("ID_INTERPLO", "TEXT", 50),
    ("LONG_REF_M", "DOUBLE", 0),
    ("LONG_GEOM_M", "DOUBLE", 0),
    ("ECART_M", "DOUBLE", 0),
    ("CONTROLE", "TEXT", 60),
    ("ECART_PCT", "DOUBLE", 0),
    ("NOMPLODEB", "TEXT", 10),
    ("NOMPLOFIN", "TEXT", 10),
    ("OBJETID_ORIG", "TEXT", 50),
    ("NB_CORR_ORIG", "SHORT", 0),
    ("NB_CORR_LOCAL", "SHORT", 0),
    ("COTE", "TEXT", 5),
    ("LONG_GEOM_ATTR_M", "DOUBLE", 0),
    ("NB_PARTIES", "SHORT", 0),
    ("ANOMALIES", "TEXT", 2000),
    ("DATE_TRAITEMENT", "DATE", 0),
)

CHAMPS_COMPARAISON: Tuple[Tuple[str, str, int], ...] = (
    ("ID_INTERPLO", "TEXT", 50),
    ("ID_HISTO", "TEXT", 50),
    ("NOM_PDF", "TEXT", 255),
    ("LONG_NOUVEAU_M", "DOUBLE", 0),
    ("LONG_HISTO_M", "DOUBLE", 0),
    ("ECART_LONG_M", "DOUBLE", 0),
    ("DIST_MAX_M", "DOUBLE", 0),
    ("MEME_SENS", "TEXT", 3),
    ("RESULTAT", "TEXT", 40),
    ("MESSAGES", "TEXT", 500),
    ("DATE_TRAITEMENT", "DATE", 0),
)


def valider_prefixe(prefixe: str) -> List[str]:
    """Liste des problèmes du préfixe (liste vide = valide)."""
    erreurs = []
    if not prefixe:
        return ["Le préfixe est vide"]
    if not re.match(r"^[A-Za-z][A-Za-z0-9_]*$", prefixe):
        erreurs.append("Le préfixe doit commencer par une lettre et ne contenir que "
                       "lettres non accentuées, chiffres et _")
    if len(prefixe) > LONGUEUR_MAX_PREFIXE:
        erreurs.append("Le préfixe dépasse {0} caractères".format(LONGUEUR_MAX_PREFIXE))
    return erreurs


def horodatage(maintenant: datetime.datetime = None) -> str:
    return (maintenant or datetime.datetime.now()).strftime("%Y%m%d_%H%M%S")


def nom_sortie_unique(espace: str, prefixe: str, suffixe: str,
                      existe: Callable[[str], bool],
                      maintenant: datetime.datetime = None) -> str:
    """Chemin complet d'une sortie qui n'existe pas encore :
    <espace>/<prefixe>_<suffixe>_<AAAAMMJJ_HHMMSS>[_n].

    `existe` est injecté (arcpy.Exists en production) pour rester testable.
    """
    base = "{0}_{1}".format(prefixe, suffixe)
    return noms_sorties_uniques(espace, [base], existe, maintenant)[0]


def noms_sorties_uniques(espace: str, bases: Sequence[str], existe: Callable[[str], bool],
                         maintenant: datetime.datetime = None) -> List[str]:
    """Noms de plusieurs sorties liées, avec le même horodatage et le même
    suffixe éventuel, dont AUCUN n'existe déjà."""
    date = horodatage(maintenant)
    for n in range(1, 1000):
        fin = date if n == 1 else "{0}_{1}".format(date, n)
        candidats = [os.path.join(espace, "{0}_{1}".format(b, fin)) for b in bases]
        if not any(existe(c) for c in candidats):
            return candidats
    raise RuntimeError("Impossible de trouver des noms de sortie libres")


def tronquer(valeur, longueur: int):
    if isinstance(valeur, str) and longueur and len(valeur) > longueur:
        return valeur[:longueur - 3] + "..."
    return valeur


def preparer_ligne(donnees: Dict[str, object],
                   champs: Sequence[Tuple[str, str, int]]) -> List[object]:
    """Ordonne et tronque les valeurs selon la définition des champs."""
    return [tronquer(donnees.get(nom), long_) for nom, _type, long_ in champs]


def _ajouter_champs(chemin: str, champs: Sequence[Tuple[str, str, int]]) -> None:
    import arcpy

    for nom_champ, type_champ, longueur in champs:
        if type_champ == "TEXT":
            arcpy.management.AddField(chemin, nom_champ, "TEXT", field_length=longueur)
        else:
            arcpy.management.AddField(chemin, nom_champ, type_champ)


def creer_classe_entites(chemin_fc: str, champs: Sequence[Tuple[str, str, int]], epsg: int,
                         has_m: bool = False, has_z: bool = False) -> str:
    """Crée une NOUVELLE classe d'entités polyligne. Refuse si elle existe."""
    import arcpy

    if arcpy.Exists(chemin_fc):
        raise RuntimeError("Sortie déjà existante, aucune écriture : {0}".format(chemin_fc))
    espace, nom = os.path.split(chemin_fc)
    arcpy.management.CreateFeatureclass(
        espace, nom, "POLYLINE", spatial_reference=arcpy.SpatialReference(epsg),
        has_m="ENABLED" if has_m else "DISABLED", has_z="ENABLED" if has_z else "DISABLED")
    _ajouter_champs(chemin_fc, champs)
    return chemin_fc


def inserer_entites(chemin_fc: str, champs: Sequence[Tuple[str, str, int]],
                    lignes_geom: Iterable[Tuple[Dict[str, object], object]]) -> int:
    """Insère des couples (attributs, géométrie)."""
    import arcpy

    noms = [c[0] for c in champs] + ["SHAPE@"]
    n = 0
    with arcpy.da.InsertCursor(chemin_fc, noms) as cur:
        for donnees, geom in lignes_geom:
            cur.insertRow(preparer_ligne(donnees, champs) + [geom])
            n += 1
    return n


def creer_table(chemin_table: str, champs: Sequence[Tuple[str, str, int]]) -> str:
    """Crée une NOUVELLE table de géodatabase. Refuse si elle existe."""
    import arcpy

    if arcpy.Exists(chemin_table):
        raise RuntimeError("Sortie déjà existante, aucune écriture : {0}".format(chemin_table))
    espace, nom = os.path.split(chemin_table)
    arcpy.management.CreateTable(espace, nom)
    _ajouter_champs(chemin_table, champs)
    return chemin_table


def inserer_lignes(chemin_table: str, champs: Sequence[Tuple[str, str, int]],
                   lignes: Iterable[Dict[str, object]]) -> int:
    import arcpy

    noms = [c[0] for c in champs]
    n = 0
    with arcpy.da.InsertCursor(chemin_table, noms) as cur:
        for donnees in lignes:
            cur.insertRow(preparer_ligne(donnees, champs))
            n += 1
    return n


def ecrire_csv(chemin_csv: str, champs: Sequence[Tuple[str, str, int]],
               lignes: Iterable[Dict[str, object]]) -> int:
    """Export CSV (séparateur ';', UTF-8 avec BOM pour Excel). Refuse d'écraser."""
    if os.path.exists(chemin_csv):
        raise RuntimeError("Fichier déjà existant, aucune écriture : {0}".format(chemin_csv))
    noms = [c[0] for c in champs]
    n = 0
    with open(chemin_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(noms)
        for donnees in lignes:
            w.writerow(["" if v is None else v for v in preparer_ligne(donnees, champs)])
            n += 1
    return n
