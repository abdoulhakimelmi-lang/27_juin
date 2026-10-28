# -*- coding: utf-8 -*-
"""Modèle en mémoire du référentiel des tronçons pour la phase 3 (pur Python).

- Troncon : attributs de référencement + géométrie (objet arcpy ou équivalent).
- Reseau : tronçons indexés par (route, département), avec la liste des
  tronçons écartés et leur motif (règles de chargement de V6A).
- IndexPointsPR : extrémités DEBUT / FIN de REF_INTERPLO_POINTS_PR_V1, pour
  contrôler l'orientation des géométries (X_GEOM / Y_GEOM).

Aucune donnée n'est écrite.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from . import geometrie
from .controles import normaliser_code, normaliser_identifiant

# Champs du référentiel utilisés par la phase 3
CHAMPS_TRONCONS_SECTIONS = (
    "ID_INTERPLO", "ROUTE", "DEPARTEMENT", "COTE", "PR_DEBUT", "PR_FIN",
    "ABS_DEBUT", "ABS_FIN", "CUMUL_DEBUT", "CUMUL_FIN",
    "LOGIQUE_DEB", "LOGIQUE_FIN", "LOGIQUE_2", "LOGIQUE_3",
)
CHAMPS_LOGIQUES = ("LOGIQUE_DEB", "LOGIQUE_FIN", "LOGIQUE_2", "LOGIQUE_3")
CHAMPS_POINTS_ORIENTATION = ("ID_INTERPLO", "TYPE_POINT", "X_GEOM", "Y_GEOM")
CHAMPS_POINTS_OPTIONNELS = ("CUMUL",)

# Codes de logique utilisés comme indice de portion commune / transition de côté
LOGIQUES_PORTION_COMMUNE = ("DF", "FF")

# Tolérance de détection d'une géométrie fermée (extrémités confondues)
TOLERANCE_FERMETURE_M = 0.001

MOTIF_GEOMETRIE = "géométrie absente ou de moins de 2 sommets"
MOTIF_REFERENCEMENT = "référencement incomplet (PR, abscisses ou cumuls)"
MOTIF_CUMULS = "CUMUL_FIN <= CUMUL_DEBUT"
MOTIF_ROUTE = "route, département ou côté absent"
MOTIF_IDENTIFIANT = "ID_INTERPLO absent"


def normaliser_departement(valeur) -> Optional[str]:
    """'39', 39, '039', 39.0 -> '39' ; '2A' -> '2A'."""
    texte = normaliser_code(valeur)
    if texte is None:
        return None
    try:
        f = float(texte)
        if f.is_integer():
            return str(int(f))
    except ValueError:
        pass
    return texte


def _nombre(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(str(v).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def _entier(v) -> Optional[int]:
    n = _nombre(v)
    return int(n) if n is not None else None


class Troncon(object):
    __slots__ = ("id", "route", "dep", "cote", "pd", "pf", "ad", "af", "cd", "cf",
                 "logiques", "geom", "parties", "premier", "dernier", "nb_parties",
                 "ferme", "long_geom")

    def __init__(self, ident, route, dep, cote, pd, pf, ad, af, cd, cf, logiques, geom):
        self.id = ident
        self.route = route
        self.dep = dep
        self.cote = cote
        self.pd, self.pf, self.ad, self.af, self.cd, self.cf = pd, pf, ad, af, cd, cf
        self.logiques = tuple(logiques)
        self.geom = geom
        self.parties = geometrie.coordonnees(geom)
        self.premier, self.dernier = geometrie.extremites(self.parties)
        self.nb_parties = len(self.parties)
        d = geometrie.distance(self.premier, self.dernier)
        self.ferme = d is not None and d <= TOLERANCE_FERMETURE_M
        self.long_geom = geometrie.longueur(geom)

    @property
    def porte_df_ff(self) -> bool:
        return any(v in LOGIQUES_PORTION_COMMUNE for v in self.logiques)

    @property
    def long_ref(self) -> float:
        return self.cf - self.cd

    def __repr__(self) -> str:
        return "Troncon({0}, {1}, cumuls {2}-{3})".format(self.id, self.cote, self.cd, self.cf)


class Reseau(object):
    """Tronçons utilisables, indexés par (route, département)."""

    def __init__(self) -> None:
        self.par_route_dep: Dict[Tuple[str, str], List[Troncon]] = {}
        self.par_id: Dict[str, List[Troncon]] = {}
        self.ecartes: List[Tuple[object, str]] = []   # (identifiant, motif)

    @classmethod
    def depuis_lignes(cls, lignes: Iterable[Dict[str, object]],
                      champs: Dict[str, Optional[str]]) -> "Reseau":
        """`lignes` : dictionnaires {nom réel: valeur, 'SHAPE@': géométrie} ;
        `champs` : {champ attendu: nom réel}."""
        reseau = cls()

        def lire(brut, cle):
            nom = champs.get(cle)
            return brut.get(nom) if nom else None

        for brut in lignes:
            ident = normaliser_identifiant(lire(brut, "ID_INTERPLO"))
            if ident is None:
                reseau.ecartes.append((None, MOTIF_IDENTIFIANT))
                continue
            geom = brut.get("SHAPE@")
            if geom is None or (getattr(geom, "pointCount", 0) or 0) < 2:
                reseau.ecartes.append((ident, MOTIF_GEOMETRIE))
                continue
            route = normaliser_code(lire(brut, "ROUTE"))
            dep = normaliser_departement(lire(brut, "DEPARTEMENT"))
            cote = normaliser_code(lire(brut, "COTE"))
            if not route or not dep or not cote:
                reseau.ecartes.append((ident, MOTIF_ROUTE))
                continue
            valeurs = (_entier(lire(brut, "PR_DEBUT")), _entier(lire(brut, "PR_FIN")),
                       _nombre(lire(brut, "ABS_DEBUT")), _nombre(lire(brut, "ABS_FIN")),
                       _nombre(lire(brut, "CUMUL_DEBUT")), _nombre(lire(brut, "CUMUL_FIN")))
            if None in valeurs:
                reseau.ecartes.append((ident, MOTIF_REFERENCEMENT))
                continue
            if valeurs[5] <= valeurs[4]:
                reseau.ecartes.append((ident, MOTIF_CUMULS))
                continue
            logiques = [normaliser_code(lire(brut, c)) or "" for c in CHAMPS_LOGIQUES]
            t = Troncon(ident, route, dep, cote, *valeurs, logiques=logiques, geom=geom)
            reseau.par_route_dep.setdefault((route, dep), []).append(t)
            reseau.par_id.setdefault(ident, []).append(t)
        return reseau

    def troncons(self, route: Optional[str], dep: Optional[str]) -> List[Troncon]:
        return self.par_route_dep.get((normaliser_code(route) or "", normaliser_departement(dep) or ""), [])

    def nb_troncons(self) -> int:
        return sum(len(v) for v in self.par_route_dep.values())


class IndexPointsPR(object):
    """Points DEBUT / FIN par ID_INTERPLO (X_GEOM, Y_GEOM, CUMUL éventuel)."""

    def __init__(self, lignes: Iterable[Dict[str, object]], champs: Dict[str, Optional[str]]) -> None:
        self.points: Dict[str, Dict[str, List[Dict[str, object]]]] = {}

        def lire(brut, cle):
            nom = champs.get(cle)
            return brut.get(nom) if nom else None

        for brut in lignes:
            ident = normaliser_identifiant(lire(brut, "ID_INTERPLO"))
            type_point = normaliser_code(lire(brut, "TYPE_POINT"))
            x, y = _nombre(lire(brut, "X_GEOM")), _nombre(lire(brut, "Y_GEOM"))
            if ident is None or type_point not in ("DEBUT", "FIN") or x is None or y is None:
                continue
            self.points.setdefault(ident, {}).setdefault(type_point, []).append(
                {"xy": (x, y), "cumul": _nombre(lire(brut, "CUMUL"))})

    def extremites(self, ident: str) -> Tuple[Optional[Dict[str, object]], Optional[Dict[str, object]], str]:
        """(point DEBUT, point FIN, motif) ; motif vide si exactement un de chaque."""
        p = self.points.get(ident, {})
        deb, fin = p.get("DEBUT", []), p.get("FIN", [])
        if len(deb) != 1 or len(fin) != 1:
            return None, None, "points PR DEBUT/FIN : {0}/{1} trouvé(s)".format(len(deb), len(fin))
        return deb[0], fin[0], ""


def controler_orientation(t: Troncon, points: Optional[IndexPointsPR], tol_xy: float) -> Tuple[str, str]:
    """Contrôle du sens de numérisation d'un tronçon par les points PR.

    Renvoie (code, détail) : CONFORME, INVERSE, INCOHERENT, FERMEE ou
    NON_CONTROLE. Ne corrige jamais la géométrie.
    """
    if t.ferme:
        return "FERMEE", "extrémités géométriques confondues : sens indéterminable"
    if points is None:
        return "NON_CONTROLE", "couche points PR non exploitable"
    deb, fin, motif = points.extremites(t.id)
    if motif:
        return "NON_CONTROLE", motif
    d_deb = geometrie.distance(t.premier, deb["xy"])
    d_fin = geometrie.distance(t.dernier, fin["xy"])
    if d_deb <= tol_xy and d_fin <= tol_xy:
        return "CONFORME", ""
    if (geometrie.distance(t.premier, fin["xy"]) <= tol_xy
            and geometrie.distance(t.dernier, deb["xy"]) <= tol_xy):
        return "INVERSE", "géométrie numérisée de FIN vers DEBUT"
    return "INCOHERENT", "extrémités à {0:.3f} m / {1:.3f} m des points PR".format(d_deb, d_fin)


def ecarts_cumul_points(t: Troncon, points: Optional[IndexPointsPR], tol_cumul: float) -> List[str]:
    """Compare CUMUL_DEBUT / CUMUL_FIN du tronçon au CUMUL des points PR (information)."""
    if points is None:
        return []
    deb, fin, motif = points.extremites(t.id)
    if motif:
        return []
    alertes = []
    for etiquette, point, valeur in (("DEBUT", deb, t.cd), ("FIN", fin, t.cf)):
        if point["cumul"] is not None and abs(point["cumul"] - valeur) > tol_cumul:
            alertes.append("ID {0} : CUMUL du point {1} ({2}) différent du tronçon ({3})".format(
                t.id, etiquette, point["cumul"], valeur))
    return alertes


def cotes_texte(cotes: Sequence[str]) -> str:
    return "/".join(sorted(set(cotes)))
