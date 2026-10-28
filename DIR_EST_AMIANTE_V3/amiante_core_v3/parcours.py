# -*- coding: utf-8 -*-
"""Recherche des parcours d'une section courante (pur Python).

Principes (validés avec la DIR Est) :

- réseau limité à la route et au département du PDF ;
- côtés admis :
    * STRICT : côté de début ou de fin du PDF (U = I) ;
    * PORTION_COMMUNE : tronçon côté D portant lui-même DF ou FF, lorsque le
      PDF comporte le côté I (règle V6C) ;
  les deux familles sont explorées ENSEMBLE : un parcours strict n'interrompt
  pas la recherche, afin de ne pas masquer une ambiguïté réelle ;
- raccordement A -> B, trois contrôles distincts et enregistrés :
    1. continuité géométrique : fin(A) -> début(B) <= tol_xy (toujours exigée) ;
    2. continuité des cumuls :
       - même côté : B.CUMUL_DEBUT <= A.CUMUL_FIN + tol et
         B.CUMUL_FIN > A.CUMUL_FIN + tol (règle d'enchaînement V6A) ;
       - changement de côté : écart B.CUMUL_DEBUT - A.CUMUL_FIN ENREGISTRÉ,
         jamais critère d'exclusion ; au-delà du seuil d'alerte la
         transition est signalée douteuse ;
    3. côtés et logiques : un changement de côté exige DF ou FF dans les
       logiques de A ou de B (règle V7B). DF/FF ne suffit jamais seul : les
       contrôles 1 et 2 s'appliquent aussi ;
- énumération de TOUS les parcours simples (chaque tronçon au plus une fois)
  entre les positions de début et de fin ; si une limite (profondeur,
  nombre d'états, nombre de parcours, durée) est atteinte, la recherche est
  déclarée INCOMPLÈTE et aucun parcours n'est retenu.
"""

from __future__ import annotations

import math
import time
from typing import Dict, List, Optional, Sequence, Set, Tuple

from . import geometrie
from .localisation import Position
from .reseau import Troncon

STRICT = "STRICT"
PORTION_COMMUNE = "PORTION_COMMUNE"

RACCORD_DEBUT = "DEBUT_PARCOURS"
RACCORD_MEME_COTE = "MEME_COTE"
RACCORD_CHANGEMENT_COTE = "CHANGEMENT_COTE"


class Parametres(object):
    """Tolérances et limites, documentées et modifiables depuis la boîte à outils."""

    def __init__(self, tol_xy: float = 1.0, tol_cumul: float = 0.001, tol_abs: float = 0.001,
                 seuil_alerte_ecart_cumul: float = 100.0, max_profondeur: int = 500,
                 max_parcours: int = 20, max_etats: int = 200000, max_secondes: float = 60.0) -> None:
        self.tol_xy = float(tol_xy)                  # V6A / V6C / V7B : 1 m
        self.tol_cumul = float(tol_cumul)            # V6A / V6C / V7B : 0,001
        self.tol_abs = float(tol_abs)                # V6A / V7B : 0,001
        self.seuil_alerte_ecart_cumul = float(seuil_alerte_ecart_cumul)  # alerte, pas exclusion
        self.max_profondeur = int(max_profondeur)    # tronçons par parcours
        self.max_parcours = int(max_parcours)        # parcours distincts conservés
        self.max_etats = int(max_etats)              # étapes d'exploration par PDF
        self.max_secondes = float(max_secondes)      # durée par PDF

    def resume(self) -> str:
        return ("tolérance géométrique {0} m, cumul {1}, abscisse {2}, seuil d'alerte écart de cumul "
                "{3} m, limites : {4} tronçons/parcours, {5} parcours, {6} états, {7} s".format(
                    self.tol_xy, self.tol_cumul, self.tol_abs, self.seuil_alerte_ecart_cumul,
                    self.max_profondeur, self.max_parcours, self.max_etats, self.max_secondes))


class Etape(object):
    """Un tronçon d'un parcours, avec la description de son raccordement."""

    __slots__ = ("troncon", "appartenance", "type_raccord", "ecart_cumul", "distance_racc",
                 "entree", "sortie", "alertes")

    def __init__(self, troncon: Troncon, appartenance: str, type_raccord: str,
                 ecart_cumul: Optional[float], distance_racc: Optional[float]) -> None:
        self.troncon = troncon
        self.appartenance = appartenance
        self.type_raccord = type_raccord
        self.ecart_cumul = ecart_cumul
        self.distance_racc = distance_racc
        self.entree: Optional[float] = None   # cumul de découpe à l'entrée du tronçon
        self.sortie: Optional[float] = None   # cumul de découpe à la sortie
        self.alertes: List[str] = []


class Parcours(object):
    def __init__(self, etapes: List[Etape], debut: Position, fin: Position) -> None:
        self.etapes = etapes
        self.debut = debut
        self.fin = fin

    @property
    def ids(self) -> List[str]:
        return [e.troncon.id for e in self.etapes]

    def signature(self):
        return (tuple(self.ids), round(self.debut.cumul, 3), round(self.fin.cumul, 3))

    @property
    def strict(self) -> bool:
        return all(e.appartenance == STRICT for e in self.etapes)

    @property
    def nb_changements_cote(self) -> int:
        return sum(1 for e in self.etapes if e.type_raccord == RACCORD_CHANGEMENT_COTE)

    def alertes(self) -> List[str]:
        return [a for e in self.etapes for a in e.alertes]

    def texte(self) -> str:
        return "{0} [{1}]".format(",".join(self.ids), STRICT if self.strict else PORTION_COMMUNE)


class ResultatRecherche(object):
    def __init__(self) -> None:
        self.parcours: List[Parcours] = []
        self.incomplete = False
        self.motif_incomplet = ""
        self.nb_etats = 0
        self.departs: List[Tuple[Position, Troncon]] = []
        # tronçons sans suite admissible : (id, [(id voisin, côté, motif de refus)])
        self.impasses: List[Tuple[str, List[Tuple[str, str, str]]]] = []


class Admissibilite(object):
    """Côtés admis pour un PDF donné (côtés normalisés, U = I)."""

    def __init__(self, cote_debut: str, cote_fin: str) -> None:
        self.cote_debut = cote_debut
        self.cote_fin = cote_fin
        self.cotes_pdf = {cote_debut, cote_fin}

    def appartenance(self, t: Troncon) -> Optional[str]:
        if t.cote in self.cotes_pdf:
            return STRICT
        if t.cote == "D" and "I" in self.cotes_pdf and t.porte_df_ff:
            return PORTION_COMMUNE
        return None

    @staticmethod
    def _extremite(cote_pdf: str, t: Troncon) -> bool:
        return t.cote == cote_pdf or (cote_pdf == "I" and t.cote == "D" and t.porte_df_ff)

    def admis_au_debut(self, t: Troncon) -> bool:
        return self._extremite(self.cote_debut, t)

    def admis_a_la_fin(self, t: Troncon) -> bool:
        return self._extremite(self.cote_fin, t)


class _Grille(object):
    """Index spatial simple des premiers sommets des tronçons."""

    def __init__(self, troncons: Sequence[Troncon], taille: float) -> None:
        self.taille = max(taille, 1e-6)
        self.cases: Dict[Tuple[int, int], List[Troncon]] = {}
        for t in troncons:
            if t.premier is not None:
                self.cases.setdefault(self._case(t.premier), []).append(t)

    def _case(self, p):
        return (int(math.floor(p[0] / self.taille)), int(math.floor(p[1] / self.taille)))

    def proches(self, p) -> List[Troncon]:
        if p is None:
            return []
        cx, cy = self._case(p)
        res = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                res.extend(self.cases.get((cx + dx, cy + dy), []))
        return res


def raccordement(a: Troncon, b: Troncon, p: Parametres):
    """Évalue le raccordement a -> b.

    Renvoie (admis, type, écart de cumul, distance, alertes, motif de refus).
    """
    distance = geometrie.distance(a.dernier, b.premier)
    ecart = b.cd - a.cf
    if distance is None or distance > p.tol_xy:
        return False, None, ecart, distance, [], "rupture géométrique"
    if a.cote == b.cote:
        if not (b.cd <= a.cf + p.tol_cumul and b.cf > a.cf + p.tol_cumul):
            return False, RACCORD_MEME_COTE, ecart, distance, [], "cumuls non continus"
        alertes = []
        if ecart < -p.tol_cumul:
            alertes.append("chevauchement de cumuls {0:.3f} m entre {1} et {2}".format(ecart, a.id, b.id))
        return True, RACCORD_MEME_COTE, ecart, distance, alertes, ""
    if not (a.porte_df_ff or b.porte_df_ff):
        return False, RACCORD_CHANGEMENT_COTE, ecart, distance, [], "changement de côté sans DF/FF"
    alertes = []
    if abs(ecart) > p.seuil_alerte_ecart_cumul:
        alertes.append("TRANSITION_DOUTEUSE {0}->{1} ({2}->{3}) : écart de cumul {4:.3f} m "
                       "> seuil {5} m".format(a.id, b.id, a.cote, b.cote, ecart, p.seuil_alerte_ecart_cumul))
    elif abs(ecart) > p.tol_cumul:
        alertes.append("écart de cumul {0:.3f} m au changement de côté {1}->{2} ({3}->{4})".format(
            ecart, a.id, b.id, a.cote, b.cote))
    return True, RACCORD_CHANGEMENT_COTE, ecart, distance, alertes, ""


def rechercher(troncons: Sequence[Troncon], debuts: Sequence[Position], fins: Sequence[Position],
               admis: Admissibilite, p: Parametres) -> ResultatRecherche:
    """Énumère tous les parcours admissibles entre les positions de début et de fin."""
    res = ResultatRecherche()
    candidats = [t for t in troncons if admis.appartenance(t)]
    grille = _Grille(troncons, max(p.tol_xy, 1.0))
    fins_par_cote: Dict[str, List[Position]] = {}
    for f in fins:
        fins_par_cote.setdefault(f.cote, []).append(f)

    for pos in debuts:
        for t in candidats:
            if (t.cote == pos.cote and admis.admis_au_debut(t)
                    and t.cd <= pos.cumul + p.tol_cumul and t.cf > pos.cumul + p.tol_cumul):
                res.departs.append((pos, t))

    signatures: Set[tuple] = set()
    t0 = time.time()

    def arreter(motif: str) -> bool:
        res.incomplete = True
        res.motif_incomplet = res.motif_incomplet or motif
        return True

    for pos_debut, t_depart in res.departs:
        premiere = Etape(t_depart, admis.appartenance(t_depart), RACCORD_DEBUT, None, None)
        pile = [([premiere], {t_depart.id}, pos_debut.cumul)]
        while pile:
            etapes, visites, entree = pile.pop()
            res.nb_etats += 1
            if res.nb_etats > p.max_etats:
                arreter("nombre d'états explorés > {0}".format(p.max_etats))
                break
            if res.nb_etats % 500 == 0 and time.time() - t0 > p.max_secondes:
                arreter("durée de recherche > {0} s".format(p.max_secondes))
                break
            t = etapes[-1].troncon
            # Fin atteinte sur ce tronçon ?
            fin_trouvee = False
            if admis.admis_a_la_fin(t):
                for f in fins_par_cote.get(t.cote, []):
                    if entree + p.tol_cumul < f.cumul <= t.cf + p.tol_cumul:
                        fin_trouvee = True
                        parcours = Parcours(_copier(etapes), pos_debut, f)
                        if parcours.signature() not in signatures:
                            signatures.add(parcours.signature())
                            res.parcours.append(parcours)
                            if len(res.parcours) > p.max_parcours:
                                arreter("plus de {0} parcours distincts".format(p.max_parcours))
            if res.incomplete:
                break
            if fin_trouvee:
                continue  # un parcours s'arrête à la première fin atteinte (V6A)
            if len(etapes) >= p.max_profondeur:
                arreter("parcours de plus de {0} tronçons".format(p.max_profondeur))
                break
            suites = 0
            refus: List[Tuple[str, str, str]] = []
            for u in grille.proches(t.dernier):
                if u.id in visites or u is t:
                    continue
                dist_u = geometrie.distance(t.dernier, u.premier)
                if dist_u is None or dist_u > p.tol_xy:
                    continue  # tronçon voisin dans la grille mais non raccordé
                if not admis.appartenance(u):
                    refus.append((u.id, u.cote, "côté {0} non admis{1}".format(
                        u.cote, " (D sans DF/FF)" if u.cote == "D" else "")))
                    continue
                admis_r, type_r, ecart, dist, alertes, motif = raccordement(t, u, p)
                if not admis_r:
                    refus.append((u.id, u.cote, motif))
                    continue
                e = Etape(u, admis.appartenance(u), type_r, ecart, dist)
                e.alertes.extend(alertes)
                pile.append((etapes + [e], visites | {u.id}, u.cd))
                suites += 1
            if not suites and len(res.impasses) < 10:
                res.impasses.append((t.id, refus))
        if res.incomplete:
            break

    for parcours in res.parcours:
        _fixer_bornes(parcours)
    return res


def _copier(etapes: List[Etape]) -> List[Etape]:
    copie = []
    for e in etapes:
        n = Etape(e.troncon, e.appartenance, e.type_raccord, e.ecart_cumul, e.distance_racc)
        n.alertes = list(e.alertes)
        copie.append(n)
    return copie


def _fixer_bornes(parcours: Parcours) -> None:
    """Cumuls de découpe : début du PDF sur le premier tronçon, fin sur le
    dernier, tronçons intermédiaires entiers (V6A / V7B)."""
    n = len(parcours.etapes)
    for i, e in enumerate(parcours.etapes):
        e.entree = parcours.debut.cumul if i == 0 else e.troncon.cd
        e.sortie = parcours.fin.cumul if i == n - 1 else e.troncon.cf
