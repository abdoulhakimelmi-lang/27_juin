# -*- coding: utf-8 -*-
"""Boîte à outils Python ArcGIS Pro — DIR EST AMIANTE.

Le dossier `amiante_core` doit se trouver à côté de ce fichier .pyt.

Phase 1 : mode DIAGNOSTIC (analyse des noms de PDF, structure des couches
INTERPLO, présence des routes, table de diagnostic). Le mode RECONSTRUCTION
est présent dans les paramètres mais bloqué tant que les phases 2 et 3 ne
sont pas livrées.

Sécurité : lecture seule sur les couches fournies ; écriture uniquement de
nouvelles tables au nom horodaté dans la géodatabase de sortie.
"""

import importlib
import os
import sys

import arcpy

_DOSSIER = os.path.dirname(os.path.abspath(__file__))
if _DOSSIER not in sys.path:
    sys.path.insert(0, _DOSSIER)

import amiante_core  # noqa: E402
from amiante_core import controles, diagnostic, nommage, referentiel, sorties  # noqa: E402

MODE_DIAGNOSTIC = "DIAGNOSTIC"
MODE_RECONSTRUCTION = "RECONSTRUCTION"


def _recharger_modules():
    """ArcGIS Pro garde les modules en mémoire : on les recharge à chaque
    exécution pour que les corrections déposées sur le VDI soient prises en
    compte sans redémarrer l'application."""
    for module in (amiante_core, nommage, controles, referentiel, sorties, diagnostic):
        importlib.reload(module)


class JournalArcpy(diagnostic.Journal):
    def info(self, texte):
        arcpy.AddMessage(texte)

    def avertissement(self, texte):
        arcpy.AddWarning(texte)

    def erreur(self, texte):
        arcpy.AddError(texte)


class Toolbox(object):
    def __init__(self):
        self.label = "DIR EST AMIANTE"
        self.alias = "DIRESTAMIANTE"
        self.tools = [TraitementPDFAmiante]


class TraitementPDFAmiante(object):
    # Indices des paramètres
    P_DOSSIER, P_TRONCONS, P_POINTS, P_INTERPLO, P_GDB, P_PREFIXE, P_MODE = range(7)

    def __init__(self):
        self.label = "Traitement des PDF Amiante"
        self.description = (
            "Analyse un dossier de PDF Amiante (sections courantes et bretelles) "
            "et contrôle leur correspondance avec le référentiel INTERPLO 2026. "
            "Phase 1 : mode DIAGNOSTIC uniquement.")
        self.canRunInBackground = False

    def getParameterInfo(self):
        p_dossier = arcpy.Parameter(
            displayName="Dossier contenant les PDF",
            name="dossier_pdf", datatype="DEFolder",
            parameterType="Required", direction="Input")

        p_troncons = arcpy.Parameter(
            displayName="Couche locale des tronçons INTERPLO (REF_INTERPLO_TRONCONS_V1_CORRIGE)",
            name="couche_troncons", datatype="GPFeatureLayer",
            parameterType="Required", direction="Input")
        p_troncons.filter.list = ["Polyline"]

        p_points = arcpy.Parameter(
            displayName="Couche locale des points PR (REF_INTERPLO_POINTS_PR_V1)",
            name="couche_points_pr", datatype="GPFeatureLayer",
            parameterType="Required", direction="Input")
        p_points.filter.list = ["Point", "Multipoint"]

        p_interplo = arcpy.Parameter(
            displayName="Couche INTERPLO d'origine (interPlo_pr_2026)",
            name="couche_interplo", datatype=["GPFeatureLayer", "GPTableView"],
            parameterType="Required", direction="Input")

        p_gdb = arcpy.Parameter(
            displayName="Géodatabase de sortie",
            name="gdb_sortie", datatype="DEWorkspace",
            parameterType="Required", direction="Input")
        p_gdb.filter.list = ["Local Database"]

        p_prefixe = arcpy.Parameter(
            displayName="Préfixe des résultats",
            name="prefixe", datatype="GPString",
            parameterType="Required", direction="Input")
        p_prefixe.value = "AMIANTE"

        p_mode = arcpy.Parameter(
            displayName="Mode de traitement",
            name="mode", datatype="GPString",
            parameterType="Required", direction="Input")
        p_mode.filter.type = "ValueList"
        p_mode.filter.list = [MODE_DIAGNOSTIC, MODE_RECONSTRUCTION]
        p_mode.value = MODE_DIAGNOSTIC

        return [p_dossier, p_troncons, p_points, p_interplo, p_gdb, p_prefixe, p_mode]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        p_prefixe = parameters[self.P_PREFIXE]
        if p_prefixe.valueAsText:
            erreurs = sorties.valider_prefixe(p_prefixe.valueAsText)
            if erreurs:
                p_prefixe.setErrorMessage(" ; ".join(erreurs))

        p_mode = parameters[self.P_MODE]
        if p_mode.valueAsText == MODE_RECONSTRUCTION:
            p_mode.setErrorMessage(
                "Mode RECONSTRUCTION non disponible en phase 1 "
                "(bretelles : phase 2, sections : phase 3).")

        p_gdb = parameters[self.P_GDB]
        if p_gdb.valueAsText and not p_gdb.valueAsText.lower().endswith(".gdb"):
            p_gdb.setWarningMessage("Une géodatabase fichier (.gdb) est attendue.")

        # Les trois couches doivent être distinctes.
        sources = {}
        for i in (self.P_TRONCONS, self.P_POINTS, self.P_INTERPLO):
            txt = parameters[i].valueAsText
            if txt:
                if txt in sources:
                    parameters[i].setErrorMessage(
                        "Même couche que le paramètre « {0} »".format(
                            parameters[sources[txt]].displayName))
                sources[txt] = i
        return

    def execute(self, parameters, messages):
        _recharger_modules()
        arcpy.env.overwriteOutput = False  # sécurité : jamais d'écrasement

        valeurs = [p.valueAsText for p in parameters]
        mode = valeurs[self.P_MODE]
        journal = JournalArcpy()
        journal.info("DIR EST AMIANTE — version {0} — mode {1}".format(
            amiante_core.__version__, mode))

        if mode != MODE_DIAGNOSTIC:
            journal.erreur("Mode {0} non disponible dans cette version.".format(mode))
            raise arcpy.ExecuteError("Mode non disponible")

        erreurs = sorties.valider_prefixe(valeurs[self.P_PREFIXE])
        if erreurs:
            journal.erreur(" ; ".join(erreurs))
            raise arcpy.ExecuteError("Préfixe invalide")

        diagnostic.executer_diagnostic(
            dossier_pdf=valeurs[self.P_DOSSIER],
            couche_troncons=valeurs[self.P_TRONCONS],
            couche_points=valeurs[self.P_POINTS],
            couche_interplo=valeurs[self.P_INTERPLO],
            gdb_sortie=valeurs[self.P_GDB],
            prefixe=valeurs[self.P_PREFIXE],
            journal=journal)
        return

    def postExecute(self, parameters):
        return
