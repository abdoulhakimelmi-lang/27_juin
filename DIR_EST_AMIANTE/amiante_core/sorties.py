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
    """Chemin complet d'une sortie qui n'existe pas encore.

    `existe` est injecté (arcpy.Exists en production) pour rester testable.
    """
    base = "{0}_{1}_{2}".format(prefixe, suffixe, horodatage(maintenant))
    candidat = os.path.join(espace, base)
    n = 2
    while existe(candidat):
        candidat = os.path.join(espace, "{0}_{1}".format(base, n))
        n += 1
        if n > 999:
            raise RuntimeError("Impossible de trouver un nom de sortie libre")
    return candidat


def tronquer(valeur, longueur: int):
    if isinstance(valeur, str) and longueur and len(valeur) > longueur:
        return valeur[:longueur - 3] + "..."
    return valeur


def preparer_ligne(donnees: Dict[str, object],
                   champs: Sequence[Tuple[str, str, int]]) -> List[object]:
    """Ordonne et tronque les valeurs selon la définition des champs."""
    return [tronquer(donnees.get(nom), long_) for nom, _type, long_ in champs]


def creer_table(chemin_table: str, champs: Sequence[Tuple[str, str, int]]) -> str:
    """Crée une NOUVELLE table de géodatabase. Refuse si elle existe."""
    import arcpy

    if arcpy.Exists(chemin_table):
        raise RuntimeError("Sortie déjà existante, aucune écriture : {0}".format(chemin_table))
    espace, nom = os.path.split(chemin_table)
    arcpy.management.CreateTable(espace, nom)
    for nom_champ, type_champ, longueur in champs:
        if type_champ == "TEXT":
            arcpy.management.AddField(chemin_table, nom_champ, "TEXT", field_length=longueur)
        else:
            arcpy.management.AddField(chemin_table, nom_champ, type_champ)
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
