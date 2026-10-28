# -*- coding: utf-8 -*-
"""Accès en lecture seule aux couches INTERPLO.

Les fonctions « pures » (vérification de champs, résolution des noms) sont
testables sans arcpy. Les fonctions qui lisent les couches importent arcpy
au moment de l'appel. Aucune fonction de ce module n'écrit dans une couche.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence

# Couche 1 — tronçons locaux
CHAMPS_TRONCONS = (
    "ID_INTERPLO", "ROUTE", "DEPARTEMENT", "COTE", "PR_DEBUT", "PR_FIN",
    "ABS_DEBUT", "ABS_FIN", "CUMUL_DEBUT", "CUMUL_FIN", "LONG_REF_M",
    "LONG_GEOM_M", "LOGIQUE_DEB", "LOGIQUE_FIN", "LOGIQUE_2", "LOGIQUE_3",
)
# Couche 2 — points PR (champs relevés sur le VDI ; exploitation en phase 3)
CHAMPS_POINTS_PR = (
    "ID_INTERPLO", "ROUTE", "DEPARTEMENT", "COTE", "TYPE_POINT", "PR", "ABSCISSE",
    "CUMUL", "X_GEOM", "Y_GEOM", "X_REF", "Y_REF", "ECART_XY_M", "CONTROLE_XY",
    "LOGIQUE_DEB", "LOGIQUE_FIN", "LOGIQUE_2", "LOGIQUE_3", "CONTROLE_TRONCON",
)
# Couche 3 — INTERPLO d'origine
CHAMPS_INTERPLO = ("objetid", "route", "nomplodeb", "nomplofin")

# Effectifs annoncés (information : un écart produit un avertissement, pas une erreur)
EFFECTIF_TRONCONS = 3257
EFFECTIF_POINTS_PR = 6514
EFFECTIF_INTERPLO = 3257

TYPE_GEOM_TRONCONS = "Polyline"
TYPE_GEOM_POINTS = "Point"
TYPE_GEOM_INTERPLO = "Polyline"

# Références spatiales annoncées (code EPSG)
EPSG_TRONCONS = 2154
EPSG_POINTS_PR = 2154
EPSG_INTERPLO = 3857
EPSG_SORTIE = 2154

# Champs nécessaires à la reconstruction des bretelles
CHAMPS_BRETELLES_INTERPLO = ("objetid", "route", "nomplodeb", "nomplofin")
CHAMPS_BRETELLES_LOCAL_REQUIS = ("ID_INTERPLO", "LONG_REF_M")
CHAMPS_BRETELLES_LOCAL_OPTIONNELS = ("ROUTE", "DEPARTEMENT", "COTE", "LONG_GEOM_M")


def resoudre_champs(champs_presents: Iterable[str], champs_requis: Iterable[str]) -> Dict[str, Optional[str]]:
    """Associe chaque champ requis au nom réel (comparaison insensible à la casse).

    Renvoie {champ_requis: nom_reel_ou_None}.
    """
    index = {c.upper(): c for c in champs_presents}
    return {req: index.get(req.upper()) for req in champs_requis}


def champs_manquants(champs_presents: Iterable[str], champs_requis: Iterable[str]) -> List[str]:
    return [req for req, reel in resoudre_champs(champs_presents, champs_requis).items() if reel is None]


class DescriptionCouche(object):
    """Résumé d'une couche, construit par decrire_couche()."""

    def __init__(self, libelle: str, source: str) -> None:
        self.libelle = libelle
        self.source = source
        self.existe = False
        self.type_geometrie: Optional[str] = None
        self.reference_spatiale: Optional[str] = None
        self.epsg: Optional[int] = None
        self.has_m = False
        self.has_z = False
        self.effectif: Optional[int] = None
        self.champs: List[Dict[str, object]] = []
        self.correspondance: Dict[str, Optional[str]] = {}
        self.manquants: List[str] = []
        self.anomalies: List[str] = []

    @property
    def noms_champs(self) -> List[str]:
        return [str(c["nom"]) for c in self.champs]

    def lignes_rapport(self) -> List[str]:
        lignes = ["--- {0} ---".format(self.libelle), "Source : {0}".format(self.source)]
        if not self.existe:
            lignes.append("ERREUR : couche introuvable")
            return lignes
        lignes.append("Géométrie : {0} | Référence spatiale : {1} | Entités : {2}".format(
            self.type_geometrie, self.reference_spatiale, self.effectif))
        lignes.append("Champs ({0}) : {1}".format(
            len(self.champs),
            ", ".join("{0} [{1}]".format(c["nom"], c["type"]) for c in self.champs)))
        if self.manquants:
            lignes.append("ERREUR : champs requis absents : {0}".format(", ".join(self.manquants)))
        for a in self.anomalies:
            lignes.append("AVERTISSEMENT : {0}".format(a))
        return lignes


def decrire_couche(source, libelle: str, champs_requis: Sequence[str],
                   effectif_attendu: Optional[int] = None,
                   type_geom_attendu: Optional[str] = None,
                   epsg_attendu: Optional[int] = None) -> DescriptionCouche:
    """Lit la structure d'une couche (lecture seule)."""
    import arcpy

    desc_c = DescriptionCouche(libelle, str(source))
    if not arcpy.Exists(source):
        return desc_c
    desc_c.existe = True
    d = arcpy.Describe(source)
    desc_c.type_geometrie = getattr(d, "shapeType", None)
    sr = getattr(d, "spatialReference", None)
    if sr is not None:
        desc_c.epsg = getattr(sr, "factoryCode", None)
        desc_c.reference_spatiale = "{0} ({1})".format(
            getattr(sr, "name", "?"), getattr(sr, "factoryCode", "?"))
    desc_c.has_m = bool(getattr(d, "hasM", False))
    desc_c.has_z = bool(getattr(d, "hasZ", False))
    desc_c.effectif = int(arcpy.management.GetCount(source)[0])
    desc_c.champs = [{"nom": f.name, "type": f.type, "alias": f.aliasName}
                     for f in arcpy.ListFields(source)]
    desc_c.correspondance = resoudre_champs(desc_c.noms_champs, champs_requis)
    desc_c.manquants = [k for k, v in desc_c.correspondance.items() if v is None]

    if effectif_attendu is not None and desc_c.effectif != effectif_attendu:
        desc_c.anomalies.append("{0} entités au lieu des {1} annoncées".format(
            desc_c.effectif, effectif_attendu))
    if type_geom_attendu and desc_c.type_geometrie and desc_c.type_geometrie != type_geom_attendu:
        desc_c.anomalies.append("géométrie {0} au lieu de {1}".format(
            desc_c.type_geometrie, type_geom_attendu))
    if epsg_attendu and desc_c.epsg and desc_c.epsg != epsg_attendu:
        desc_c.anomalies.append("référence spatiale EPSG:{0} au lieu de EPSG:{1}".format(
            desc_c.epsg, epsg_attendu))
    if getattr(d, "FIDSet", None):
        desc_c.anomalies.append(
            "une sélection est active sur la couche : seules les entités "
            "sélectionnées seront lues")
    return desc_c


def compter_par_route(source, champ_route: str) -> Dict[str, int]:
    """Nombre d'entités par valeur de route (valeurs normalisées : strip + majuscules)."""
    import arcpy

    comptes: Dict[str, int] = {}
    with arcpy.da.SearchCursor(source, [champ_route]) as cur:
        for (val,) in cur:
            if val is None:
                continue
            cle = str(val).strip().upper()
            comptes[cle] = comptes.get(cle, 0) + 1
    return comptes


def lire_lignes(source, champs: Sequence[str], geometrie: bool = False,
                epsg: Optional[int] = None) -> List[Dict[str, object]]:
    """Lit une couche en lecture seule et renvoie une liste de dictionnaires.

    `champs` sont les noms RÉELS des champs. Avec `geometrie=True`, la clé
    'SHAPE@' contient l'objet géométrie, projeté dans `epsg` si fourni.
    """
    import arcpy

    noms = list(champs) + (["SHAPE@"] if geometrie else [])
    kwargs = {}
    if geometrie and epsg:
        kwargs["spatial_reference"] = arcpy.SpatialReference(epsg)
    lignes = []
    with arcpy.da.SearchCursor(source, noms, **kwargs) as cur:
        for valeurs in cur:
            lignes.append(dict(zip(noms, valeurs)))
    return lignes
