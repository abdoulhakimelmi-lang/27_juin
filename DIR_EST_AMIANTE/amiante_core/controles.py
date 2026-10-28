# -*- coding: utf-8 -*-
"""Contrôles métier génériques (pur Python, sans arcpy).

Seules les règles explicitement fournies sont codées ici. Les règles qui
dépendent des scripts historiques (logiques DF/FF, enchaînement des tronçons,
tolérances de longueur validées) seront ajoutées en phase 3.
"""

from __future__ import annotations

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
