# -*- coding: utf-8 -*-
"""Localisation d'une extrémité de section (PR + abscisse) sur le référentiel.

Règles reprises À L'IDENTIQUE des scripts V6A (`localiser`) et V7B
(`localiser_sur_troncon`), sans interpolation supplémentaire :

1. borne exacte de début : PR_DEBUT == pr et |ABS_DEBUT - abs| <= tol_abs
   -> CUMUL_DEBUT ;
2. borne exacte de fin : PR_FIN == pr et |ABS_FIN - abs| <= tol_abs
   -> CUMUL_FIN ;
3. intérieur : PR_DEBUT == pr et
   CUMUL_DEBUT < CUMUL_DEBUT + abs - ABS_DEBUT < CUMUL_FIN (marges tol_cumul)
   -> ce cumul.

Aucune position n'est inventée : un PR qui ne correspond à aucune de ces
règles (par exemple un PR situé au milieu d'un tronçon commençant au PR
précédent) n'est pas localisé. Toutes les positions trouvées sont
renvoyées ; le choix éventuel est fait par la recherche de parcours.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Sequence

from .reseau import Troncon

MOTIF_BORNE_DEBUT = "BORNE_DEBUT"
MOTIF_BORNE_FIN = "BORNE_FIN"
MOTIF_INTERIEUR = "INTERIEUR"


class Position(object):
    """Position sur l'axe des cumuls d'un côté donné."""

    __slots__ = ("cote", "cumul", "motif", "id_source")

    def __init__(self, cote: str, cumul: float, motif: str, id_source: str) -> None:
        self.cote = cote
        self.cumul = cumul
        self.motif = motif
        self.id_source = id_source

    def cle(self):
        return (self.cote, round(self.cumul, 3))

    def __repr__(self) -> str:
        return "Position({0}, {1}, {2}, ID {3})".format(self.cote, self.cumul, self.motif, self.id_source)


def localiser(troncons: Sequence[Troncon], pr: int, abscisse: float, tol_abs: float, tol_cumul: float,
              filtre: Optional[Callable[[Troncon], bool]] = None) -> List[Position]:
    """Toutes les positions (côté, cumul) correspondant à PR + abscisse,
    dédoublonnées par (côté, cumul arrondi au mm) comme dans V6A.

    `filtre` limite la recherche aux tronçons admis (appliqué AVANT le
    dédoublonnage)."""
    trouvees: List[Position] = []
    for t in troncons:
        if filtre is not None and not filtre(t):
            continue
        if t.pd == pr and abs(t.ad - abscisse) <= tol_abs:
            trouvees.append(Position(t.cote, t.cd, MOTIF_BORNE_DEBUT, t.id))
        if t.pf == pr and abs(t.af - abscisse) <= tol_abs:
            trouvees.append(Position(t.cote, t.cf, MOTIF_BORNE_FIN, t.id))
        if t.pd == pr:
            cumul = t.cd + abscisse - t.ad
            if t.cd + tol_cumul < cumul < t.cf - tol_cumul:
                trouvees.append(Position(t.cote, cumul, MOTIF_INTERIEUR, t.id))
    uniques = {}
    for p in trouvees:
        uniques.setdefault(p.cle(), p)
    return sorted(uniques.values(), key=lambda p: (p.cote, p.cumul))
