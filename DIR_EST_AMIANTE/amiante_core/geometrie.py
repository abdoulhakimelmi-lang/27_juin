# -*- coding: utf-8 -*-
"""Opérations géométriques.

Deux familles de fonctions :
- les accès aux objets géométrie arcpy (longueur, vacuité, extraction des
  coordonnées), qui n'importent pas arcpy et acceptent tout objet exposant
  la même interface ;
- des calculs purs sur listes de coordonnées (distance de Hausdorff
  densifiée), utilisés pour comparer deux tracés.

Les géométries du référentiel sont seulement lues ; les résultats sont des
copies écrites dans de nouvelles classes d'entités (voir sorties.py).
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

Point = Tuple[float, float]
Parties = List[List[Point]]

PAS_DENSIFICATION_M = 1.0


# -- objets géométrie (arcpy ou équivalent) -------------------------------

def geometrie_vide(geom) -> bool:
    """Vrai si la géométrie est absente, sans sommet ou de longueur nulle."""
    if geom is None:
        return True
    if getattr(geom, "isEmpty", False):
        return True
    if not getattr(geom, "pointCount", 0):
        return True
    longueur = getattr(geom, "length", None)
    return longueur is None or longueur <= 0


def longueur(geom) -> Optional[float]:
    """Longueur planaire dans l'unité de la référence spatiale (m en EPSG:2154)."""
    if geom is None:
        return None
    return float(geom.length)


def nombre_parties(geom) -> int:
    return int(getattr(geom, "partCount", 0) or 0)


def coordonnees(geom) -> Parties:
    """Liste des parties, chacune liste de (x, y). Les sommets None
    (séparateurs d'anneaux intérieurs) sont ignorés."""
    parties: Parties = []
    if geom is None:
        return parties
    for partie in geom:
        sommets = [(float(p.X), float(p.Y)) for p in partie if p is not None]
        if sommets:
            parties.append(sommets)
    return parties


# -- calculs purs ---------------------------------------------------------

def _dist_point_segment(p: Point, a: Point, b: Point) -> float:
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def distance_point_polyligne(p: Point, parties: Parties) -> float:
    meilleure = float("inf")
    for partie in parties:
        if len(partie) == 1:
            meilleure = min(meilleure, math.hypot(p[0] - partie[0][0], p[1] - partie[0][1]))
        for a, b in zip(partie, partie[1:]):
            d = _dist_point_segment(p, a, b)
            if d < meilleure:
                meilleure = d
    return meilleure


def densifier(parties: Parties, pas: float = PAS_DENSIFICATION_M) -> List[Point]:
    """Sommets + points intermédiaires tous les `pas` mètres."""
    points: List[Point] = []
    for partie in parties:
        if not partie:
            continue
        points.append(partie[0])
        for a, b in zip(partie, partie[1:]):
            seg = math.hypot(b[0] - a[0], b[1] - a[1])
            n = int(seg // pas) if pas > 0 else 0
            for k in range(1, n + 1):
                t = k * pas / seg
                if t < 1.0:
                    points.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
            points.append(b)
    return points


def hausdorff_oriente(a: Parties, b: Parties, pas: float = PAS_DENSIFICATION_M) -> float:
    """Plus grand écart d'un point de `a` au tracé `b`."""
    if not a or not b:
        return float("inf")
    return max(distance_point_polyligne(p, b) for p in densifier(a, pas))


def distance_hausdorff(a: Parties, b: Parties, pas: float = PAS_DENSIFICATION_M) -> float:
    """Distance de Hausdorff symétrique (densifiée) entre deux tracés.

    0 = tracés superposés ; indépendante du sens de numérisation.
    """
    return max(hausdorff_oriente(a, b, pas), hausdorff_oriente(b, a, pas))


def longueur_coordonnees(parties: Parties) -> float:
    return sum(math.hypot(b[0] - a[0], b[1] - a[1])
               for partie in parties for a, b in zip(partie, partie[1:]))


def emprise(parties: Parties) -> Optional[Tuple[float, float, float, float]]:
    xs = [p[0] for partie in parties for p in partie]
    ys = [p[1] for partie in parties for p in partie]
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def emprises_proches(e1: Optional[Sequence[float]], e2: Optional[Sequence[float]],
                     marge: float) -> bool:
    if e1 is None or e2 is None:
        return False
    return not (e1[2] + marge < e2[0] or e2[2] + marge < e1[0]
                or e1[3] + marge < e2[1] or e2[3] + marge < e1[1])


def meme_sens(a: Parties, b: Parties, tolerance: float) -> Optional[bool]:
    """Vrai si les deux tracés commencent au même endroit (même sens)."""
    if not a or not b:
        return None
    da = math.hypot(a[0][0][0] - b[0][0][0], a[0][0][1] - b[0][0][1])
    return da <= tolerance


def extraire_portion(*args, **kwargs):
    """Découpe d'un tronçon entre deux positions — phase 3."""
    raise NotImplementedError("Découpe de tronçons non disponible (phase 3).")
