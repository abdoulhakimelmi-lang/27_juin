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

DONNEES = {}     # chemin -> {"shape": str|None, "champs": [(nom, type)], "lignes": [dict], "fidset": str}
MESSAGES = []    # (niveau, texte)


def reinitialiser():
    DONNEES.clear()
    del MESSAGES[:]


def ajouter_couche(chemin, shape, champs, lignes, fidset=""):
    DONNEES[chemin] = {"shape": shape, "champs": list(champs),
                       "lignes": [dict(l) for l in lignes], "fidset": fidset}


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
    return types.SimpleNamespace(
        shapeType=d["shape"],
        spatialReference=types.SimpleNamespace(name="RGF_1993_Lambert_93", factoryCode=2154),
        FIDSet=d["fidset"])


def _GetCount(chemin):
    return [str(len(DONNEES[chemin]["lignes"]))]


def _CreateTable(espace, nom):
    chemin = os.path.join(espace, nom)
    if chemin in DONNEES and not env.overwriteOutput:
        raise ExecuteError("ERROR 000258: existe déjà")
    DONNEES[chemin] = {"shape": None, "champs": [("OBJECTID", "OID")], "lignes": [], "fidset": ""}


def _AddField(chemin, nom, type_, field_length=None, **kwargs):
    DONNEES[chemin]["champs"].append((nom, type_))


management = types.SimpleNamespace(GetCount=_GetCount, CreateTable=_CreateTable, AddField=_AddField)


class _SearchCursor(object):
    def __init__(self, chemin, champs):
        noms = {n.upper(): n for n, _ in DONNEES[chemin]["champs"]}
        self._cles = [noms[c.upper()] for c in champs]
        self._lignes = DONNEES[chemin]["lignes"]

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
