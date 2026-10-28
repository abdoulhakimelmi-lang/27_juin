# -*- coding: utf-8 -*-
"""Faux module arcpy minimal, en mémoire, pour tester la toolbox hors ArcGIS Pro.

Il ne reproduit que les fonctions utilisées par le code et ne garantit en
rien le comportement réel d'arcpy : il sert à vérifier la structure et
l'enchaînement du code, pas sa compatibilité ArcGIS.
"""

import copy
import os
import sys
import types

DONNEES = {}     # chemin -> {"shape", "champs": [(nom, type)], "lignes": [dict], "fidset", "epsg", "has_m", "has_z"}
MESSAGES = []    # (niveau, texte)
CURSEURS = []    # (chemin, champs, epsg demandé) pour vérifier les lectures


def reinitialiser():
    DONNEES.clear()
    del MESSAGES[:]
    del CURSEURS[:]


def ajouter_couche(chemin, shape, champs, lignes, fidset="", epsg=2154, has_m=False, has_z=False):
    DONNEES[chemin] = {"shape": shape, "champs": list(champs),
                       "lignes": [dict(l) for l in lignes], "fidset": fidset,
                       "epsg": epsg, "has_m": has_m, "has_z": has_z}


class FauxPoint(object):
    def __init__(self, x, y):
        self.X = x
        self.Y = y


class FauxPolyligne(object):
    """Polyligne minimale : liste de parties, chacune liste de (x, y)."""

    def __init__(self, parties):
        self.parties = [list(p) for p in parties]

    def __iter__(self):
        return iter([[FauxPoint(x, y) for x, y in p] for p in self.parties])

    def __eq__(self, autre):
        return isinstance(autre, FauxPolyligne) and autre.parties == self.parties

    def __deepcopy__(self, memo):
        return FauxPolyligne(copy.deepcopy(self.parties))

    @property
    def partCount(self):
        return len(self.parties)

    @property
    def pointCount(self):
        return sum(len(p) for p in self.parties)

    @property
    def isEmpty(self):
        return self.pointCount == 0

    @property
    def length(self):
        import math
        return sum(math.hypot(b[0] - a[0], b[1] - a[1])
                   for p in self.parties for a, b in zip(p, p[1:]))


class SpatialReference(object):
    def __init__(self, code):
        self.factoryCode = code
        self.name = "EPSG_{0}".format(code)


def instantane():
    return copy.deepcopy(DONNEES)


class ExecuteError(Exception):
    pass


class _Filtre(object):
    def __init__(self):
        self.type = None
        self.list = []


class Parameter(object):
    def __init__(self, displayName="", name="", datatype="", parameterType="Required",
                 direction="Input", multiValue=False):
        self.displayName = displayName
        self.name = name
        self.datatype = datatype
        self.parameterType = parameterType
        self.direction = direction
        self.multiValue = multiValue
        self.filter = _Filtre()
        self.enabled = True
        self.parameterDependencies = []
        self.value = None
        self.erreur = None
        self.avertissement = None

    @property
    def valueAsText(self):
        return None if self.value is None else str(self.value)

    def setErrorMessage(self, texte):
        self.erreur = texte

    def setWarningMessage(self, texte):
        self.avertissement = texte


env = types.SimpleNamespace(overwriteOutput=True)


def AddMessage(t):
    MESSAGES.append(("INFO", t))


def AddWarning(t):
    MESSAGES.append(("AVERT", t))


def AddError(t):
    MESSAGES.append(("ERREUR", t))


def Exists(chemin):
    return chemin in DONNEES


class _Champ(object):
    def __init__(self, nom, type_):
        self.name = nom
        self.type = type_
        self.aliasName = nom


def ListFields(chemin):
    return [_Champ(n, t) for n, t in DONNEES[chemin]["champs"]]


def Describe(chemin):
    d = DONNEES[chemin]
    sr = SpatialReference(d["epsg"]) if d.get("epsg") else None
    return types.SimpleNamespace(
        shapeType=d["shape"], spatialReference=sr, FIDSet=d["fidset"],
        hasM=d.get("has_m", False), hasZ=d.get("has_z", False))


def _GetCount(chemin):
    return [str(len(DONNEES[chemin]["lignes"]))]


def _CreateTable(espace, nom):
    chemin = os.path.join(espace, nom)
    if chemin in DONNEES and not env.overwriteOutput:
        raise ExecuteError("ERROR 000258: existe déjà")
    DONNEES[chemin] = {"shape": None, "champs": [("OBJECTID", "OID")], "lignes": [], "fidset": "",
                       "epsg": None}


def _CreateFeatureclass(espace, nom, geometry_type, spatial_reference=None, has_m="DISABLED",
                        has_z="DISABLED", **kwargs):
    chemin = os.path.join(espace, nom)
    if chemin in DONNEES and not env.overwriteOutput:
        raise ExecuteError("ERROR 000258: existe déjà")
    DONNEES[chemin] = {"shape": "Polyline", "champs": [("OBJECTID", "OID"), ("Shape", "Geometry")],
                       "lignes": [], "fidset": "",
                       "epsg": spatial_reference.factoryCode if spatial_reference else None,
                       "has_m": has_m == "ENABLED", "has_z": has_z == "ENABLED"}


def _AddField(chemin, nom, type_, field_length=None, **kwargs):
    DONNEES[chemin]["champs"].append((nom, type_))


management = types.SimpleNamespace(GetCount=_GetCount, CreateTable=_CreateTable, AddField=_AddField,
                                   CreateFeatureclass=_CreateFeatureclass)

_JETONS = {"SHAPE@": "Shape", "OID@": "OBJECTID"}


class _SearchCursor(object):
    def __init__(self, chemin, champs, where_clause=None, spatial_reference=None):
        noms = {n.upper(): n for n, _ in DONNEES[chemin]["champs"]}
        noms.update({k: v for k, v in _JETONS.items()})
        self._cles = [noms[c.upper()] for c in champs]
        self._lignes = DONNEES[chemin]["lignes"]
        CURSEURS.append((chemin, list(champs),
                         spatial_reference.factoryCode if spatial_reference else None))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        for l in self._lignes:
            yield tuple(l.get(c) for c in self._cles)


class _InsertCursor(object):
    def __init__(self, chemin, champs):
        noms = {n for n, _ in DONNEES[chemin]["champs"]}
        champs = [_JETONS.get(c, c) for c in champs]
        manquants = [c for c in champs if c not in noms]
        if manquants:
            raise RuntimeError("Champs absents : {0}".format(manquants))
        self._chemin = chemin
        self._champs = list(champs)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def insertRow(self, valeurs):
        if len(valeurs) != len(self._champs):
            raise RuntimeError("Nombre de valeurs incorrect")
        DONNEES[self._chemin]["lignes"].append(dict(zip(self._champs, valeurs)))


da = types.SimpleNamespace(SearchCursor=_SearchCursor, InsertCursor=_InsertCursor)


def installer():
    """Installe ce module comme `arcpy` dans sys.modules."""
    sys.modules["arcpy"] = sys.modules[__name__]
    return sys.modules[__name__]
