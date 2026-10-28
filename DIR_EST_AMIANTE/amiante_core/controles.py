# -*- coding: utf-8 -*-
"""Contrôles métier génériques (pur Python, sans arcpy).

Seules les règles explicitement fournies sont codées ici. Les règles qui
dépendent des scripts historiques (logiques DF/FF, enchaînement des tronçons,
tolérances de longueur validées) seront ajoutées en phase 3.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence

from .nommage import cote_pour_controle

# Résultats de compatibilité de côté
COTE_IDENTIQUE = "IDENTIQUE"
COTE_TRONCON_COMMUN = "TRONCON_COMMUN"   # référentiel D, PDF I/U
COTE_INCOMPATIBLE = "INCOMPATIBLE"
COTE_INDETERMINE = "INDETERMINE"


def compatibilite_cote(cote_pdf: Optional[str], cote_ref: Optional[str]) -> str:
    """Compare le côté du PDF à celui d'un tronçon du référentiel.

    - U et I sont équivalents.
    - Un tronçon commun aux deux sens peut être codé D dans le référentiel
      alors que le PDF indique I ou U : résultat TRONCON_COMMUN (acceptable
      mais à tracer, jamais confondu avec IDENTIQUE).
    """
    pdf = cote_pour_controle(cote_pdf.strip()) if cote_pdf else None
    ref = cote_pour_controle(cote_ref.strip()) if cote_ref else None
    if not pdf or not ref:
        return COTE_INDETERMINE
    if pdf == ref:
        return COTE_IDENTIQUE
    if pdf == "I" and ref == "D":
        return COTE_TRONCON_COMMUN
    return COTE_INCOMPATIBLE


def ecart_longueurs(long_ref_m: Optional[float], long_geom_m: Optional[float]) -> Dict[str, Optional[float]]:
    """Écart entre longueur de référencement et longueur géométrique.

    Les deux longueurs restent distinctes : cette fonction ne choisit jamais
    l'une à la place de l'autre, elle mesure seulement l'écart.
    """
    if long_ref_m is None or long_geom_m is None:
        return {"ECART_M": None, "ECART_PCT": None}
    ecart = float(long_geom_m) - float(long_ref_m)
    pct = (ecart / float(long_ref_m) * 100.0) if long_ref_m else None
    return {"ECART_M": round(ecart, 3), "ECART_PCT": None if pct is None else round(pct, 3)}


def verifier_unicite(valeurs: Sequence[object]) -> Dict[object, int]:
    """Renvoie les valeurs présentes plusieurs fois avec leur nombre d'occurrences."""
    comptes: Dict[object, int] = {}
    for v in valeurs:
        comptes[v] = comptes.get(v, 0) + 1
    return {v: n for v, n in comptes.items() if n > 1}


def statut_candidats(nb_candidats: int) -> str:
    """Règle 'aucun parcours ambigu accepté automatiquement'."""
    if nb_candidats == 0:
        return "AUCUN"
    if nb_candidats == 1:
        return "UNIQUE"
    return "AMBIGU"


def normaliser_route(route: Optional[str]) -> Optional[str]:
    """Normalisation minimale (espaces, casse). Aucune réécriture du code route."""
    if route is None:
        return None
    return str(route).strip().upper()


def variantes_route(route: str) -> List[str]:
    """Variantes de codage d'une route nationale, à utiliser seulement pour
    signaler une correspondance non exacte (jamais pour l'accepter).

    'N0005' -> ['N0005', 'N5'] ; 'N5' -> ['N5', 'N0005'].
    """
    r = normaliser_route(route) or ""
    variantes = [r]
    i = 0
    while i < len(r) and r[i].isalpha():
        i += 1
    lettres, reste = r[:i], r[i:]
    j = 0
    while j < len(reste) and reste[j].isdigit():
        j += 1
    chiffres, suffixe = reste[:j], reste[j:]
    if lettres and chiffres:
        courte = lettres + str(int(chiffres)) + suffixe
        longue = lettres + chiffres.zfill(4) + suffixe
        for v in (courte, longue):
            if v not in variantes:
                variantes.append(v)
    return variantes


# -- Identifiants et codes INTERPLO (phase 2) ------------------------------

def normaliser_identifiant(valeur) -> Optional[str]:
    """Clé de comparaison d'un identifiant INTERPLO quel que soit son type.

    123 / 123.0 / '123' / ' 123 ' -> '123'. Une valeur non entière reste en
    texte (majuscules, sans espaces de bord). Ne crée aucune équivalence
    entre identifiants différents.
    """
    if valeur is None:
        return None
    if isinstance(valeur, bool):
        return str(valeur)
    if isinstance(valeur, int):
        return str(valeur)
    if isinstance(valeur, float):
        if valeur != valeur:  # NaN
            return None
        return str(int(valeur)) if valeur.is_integer() else repr(valeur)
    texte = str(valeur).strip().upper()
    if not texte:
        return None
    try:
        f = float(texte)
        if f.is_integer() and texte.lstrip("+-").replace(".", "", 1).isdigit():
            return str(int(f))
    except ValueError:
        pass
    return texte


def normaliser_code(valeur) -> Optional[str]:
    """Normalisation stricte d'un code texte (route, nomplodeb, nomplofin) :
    espaces de bord et casse seulement."""
    if valeur is None:
        return None
    texte = str(valeur).strip().upper()
    return texte or None


def forme_souple_nomplo(valeur) -> Optional[str]:
    """Forme tolérante de DB/FB : sans espaces internes ni zéros non
    significatifs ('DB 03' -> 'DB3'). Sert UNIQUEMENT à expliquer une
    absence de correspondance stricte, jamais à l'accepter."""
    texte = normaliser_code(valeur)
    if texte is None:
        return None
    texte = texte.replace(" ", "").replace("_", "").replace("-", "")
    i = 0
    while i < len(texte) and texte[i].isalpha():
        i += 1
    lettres, chiffres = texte[:i], texte[i:]
    if chiffres.isdigit():
        return lettres + str(int(chiffres))
    return texte


def verifier_code_echangeur(code: Optional[str]) -> List[str]:
    """Contrôle de forme du code échangeur (ex. 54A933040).

    Forme habituelle : 2 ou 3 chiffres (département), une lettre, puis des
    chiffres. Une forme différente n'est qu'un avertissement : la présence
    dans INTERPLO reste le contrôle décisif.
    """
    if not code:
        return ["code échangeur absent"]
    if not re.match(r"^\d{2,3}[A-Z]\d{3,8}$", code):
        return ["code échangeur '{0}' de forme inhabituelle".format(code)]
    return []


def departements_concordants(dep_a, dep_b) -> Optional[bool]:
    """Compare deux codes département ('54', 54, '054' -> concordants)."""
    a = normaliser_code(dep_a)
    b = normaliser_code(dep_b)
    if not a or not b:
        return None
    if a.isdigit() and b.isdigit():
        return int(a) == int(b)
    return a == b
