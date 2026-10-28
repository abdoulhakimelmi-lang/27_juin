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


class _IndexSegments(object):
    """Grille des segments d'un tracé pour accélérer distance_point_polyligne.

    Résultat identique au calcul exhaustif : un segment situé à une distance
    d <= taille d'un point traverse forcément l'une des 9 cases voisines ; au-delà,
    on revient au calcul exhaustif.
    """

    def __init__(self, parties: Parties, taille: float = 25.0) -> None:
        self.parties = parties
        self.taille = taille
        self.cases = {}
        for partie in parties:
            for a, b in zip(partie, partie[1:]):
                x0, x1 = sorted((a[0], b[0]))
                y0, y1 = sorted((a[1], b[1]))
                for i in range(int(math.floor(x0 / taille)), int(math.floor(x1 / taille)) + 1):
                    for j in range(int(math.floor(y0 / taille)), int(math.floor(y1 / taille)) + 1):
                        self.cases.setdefault((i, j), []).append((a, b))

    def distance(self, p: Point) -> float:
        ci, cj = int(math.floor(p[0] / self.taille)), int(math.floor(p[1] / self.taille))
        meilleure = float("inf")
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for a, b in self.cases.get((ci + di, cj + dj), ()):
                    d = _dist_point_segment(p, a, b)
                    if d < meilleure:
                        meilleure = d
        if meilleure <= self.taille:
            return meilleure
        return distance_point_polyligne(p, self.parties)


def hausdorff_oriente(a: Parties, b: Parties, pas: float = PAS_DENSIFICATION_M) -> float:
    """Plus grand écart d'un point de `a` au tracé `b`."""
    if not a or not b:
        return float("inf")
    if any(len(partie) == 1 for partie in b):
        return max(distance_point_polyligne(p, b) for p in densifier(a, pas))
    index = _IndexSegments(b)
    return max(index.distance(p) for p in densifier(a, pas))


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


def extremites(parties: Parties) -> Tuple[Optional[Point], Optional[Point]]:
    """Premier et dernier sommet (toutes parties confondues)."""
    if not parties or not parties[0] or not parties[-1]:
        return None, None
    return parties[0][0], parties[-1][-1]


def distance(a: Optional[Point], b: Optional[Point]) -> Optional[float]:
    if a is None or b is None:
        return None
    return math.hypot(a[0] - b[0], a[1] - b[1])


def decouper_coordonnees(sommets: Sequence[Point], d0: float, d1: float) -> List[Point]:
    """Portion d'une ligne (une seule partie) entre les distances curvilignes
    d0 et d1, comme Polyline.segmentAlongLine(d0, d1, False).

    Sert aux tests hors ArcGIS ; dans ArcGIS Pro, le moteur utilise
    segmentAlongLine, méthode des scripts historiques.
    """
    if d1 < d0:
        raise ValueError("distance de fin inférieure à la distance de début")
    resultat: List[Point] = []
    cumul = 0.0

    def ajouter(p: Point) -> None:
        if not resultat or math.hypot(p[0] - resultat[-1][0], p[1] - resultat[-1][1]) > 1e-9:
            resultat.append(p)

    for a, b in zip(sommets, sommets[1:]):
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        debut_seg, fin_seg = cumul, cumul + seg
        if seg > 0 and fin_seg >= d0 and debut_seg <= d1:
            t0 = max(0.0, (d0 - debut_seg) / seg)
            t1 = min(1.0, (d1 - debut_seg) / seg)
            ajouter((a[0] + t0 * (b[0] - a[0]), a[1] + t0 * (b[1] - a[1])))
            ajouter((a[0] + t1 * (b[0] - a[0]), a[1] + t1 * (b[1] - a[1])))
        cumul = fin_seg
    return resultat


def assembler(portions: Sequence[Parties], tolerance_doublon: float = 1e-6) -> List[Point]:
    """Concatène des portions MONOPARTIES dans l'ordre, en supprimant les
    sommets consécutifs confondus (méthode V7B). Aucun segment n'est ajouté
    pour combler un écart : le contrôle des raccordements est fait avant."""
    points: List[Point] = []
    for parties in portions:
        if len(parties) != 1:
            raise ValueError("portion multipartie : assemblage refusé")
        for p in parties[0]:
            if points and math.hypot(p[0] - points[-1][0], p[1] - points[-1][1]) < tolerance_doublon:
                continue
            points.append(p)
    return points


def polyligne_arcpy(sommets: Sequence[Point], epsg: int):
    """Construit une polyligne arcpy monopartie (X, Y) en EPSG `epsg`."""
    import arcpy

    tableau = arcpy.Array([arcpy.Point(x, y) for x, y in sommets])
    return arcpy.Polyline(tableau, arcpy.SpatialReference(epsg))


def extraire_portion(geom, d0: float, d1: float):
    """Découpe d'un objet géométrie arcpy (méthode historique)."""
    return geom.segmentAlongLine(d0, d1, False)
