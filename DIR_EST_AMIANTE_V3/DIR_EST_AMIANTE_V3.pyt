# -*- coding: utf-8 -*-
"""Boîte à outils Python ArcGIS Pro — DIR EST AMIANTE V3 (phases 1 à 3).

Le dossier `amiante_core_v3` doit se trouver à côté de ce fichier .pyt.

Modes :
- DIAGNOSTIC (phase 1) : analyse des noms de PDF, structure des couches
  INTERPLO, présence des routes, table de diagnostic ;
- RECONSTRUCTION_BRETELLES (phase 2) : géométries candidates des bretelles,
  table de contrôle, comparaison facultative avec une couche historique ;
- RECONSTRUCTION_SECTIONS (phase 3) : reconstruction automatique des
  sections courantes (sans identifiants prédéfinis), table de contrôle,
  table détaillée des tronçons, comparaison facultative avec les couches
  historiques V6A / V6C / V7B.

Chargement du moteur : le paquet `amiante_core_v3` est chargé par CHEMIN
EXPLICITE depuis le dossier de ce .pyt, sans modifier sys.path. Une autre
version présente dans la même session (phase 1 `amiante_core`, phase 2
`amiante_core_v2`, ou une autre copie de la V3) ne peut donc pas être
importée à sa place. Le moteur
n'est chargé qu'à la première validation ou exécution : une erreur de
chargement s'affiche dans l'outil au lieu d'empêcher l'ouverture de la boîte.

Sécurité : lecture seule sur les couches fournies ; écriture uniquement de
nouvelles sorties au nom horodaté dans la géodatabase de sortie ;
overwriteOutput forcé à False.
"""

import importlib
import importlib.util
import os
import sys
import types

import arcpy

_DOSSIER = os.path.dirname(os.path.abspath(__file__))
PAQUET = "amiante_core_v3"
DOSSIER_PAQUET = os.path.join(_DOSSIER, PAQUET)
SOUS_MODULES = ("nommage", "controles", "referentiel", "sorties", "geometrie",
                "diagnostic", "comparaison", "reconstruction_bretelles",
                "reseau", "localisation", "parcours", "reconstruction_sections",
                "comparaison_sections")

MODE_DIAGNOSTIC = "DIAGNOSTIC"
MODE_BRETELLES = "RECONSTRUCTION_BRETELLES"
MODE_SECTIONS = "RECONSTRUCTION_SECTIONS"
MODES_DISPONIBLES = (MODE_DIAGNOSTIC, MODE_BRETELLES, MODE_SECTIONS)

# Valeurs par défaut des tolérances (scripts historiques V6A / V6C / V7B)
DEFAUT_TOL_XY = 1.0
DEFAUT_TOL_CUMUL = 0.001
DEFAUT_TOL_ABS = 0.001
DEFAUT_SEUIL_ECART_CUMUL = 100.0


def valeurs_multiples(texte):
    """'a;b;\'c d\'' -> ['a', 'b', 'c d'] (valeur d'un paramètre multivaleur)."""
    if not texte:
        return []
    return [v.strip().strip("'").strip('"') for v in texte.split(";") if v.strip()]

_MOTEUR = None


def _normaliser(chemin):
    return os.path.normcase(os.path.realpath(os.path.abspath(chemin)))


def _vient_du_dossier(module, dossier):
    fichier = getattr(module, "__file__", None)
    if not fichier:
        return False
    return _normaliser(fichier).startswith(_normaliser(dossier) + os.sep)


def _purger_paquet():
    for nom in list(sys.modules):
        if nom == PAQUET or nom.startswith(PAQUET + "."):
            del sys.modules[nom]


def charger_moteur():
    """Charge (ou recharge) amiante_core_v3 depuis le dossier de ce .pyt.

    - toute version de amiante_core_v3 déjà en mémoire est retirée de
      sys.modules (les modules de la phase 1, nommés amiante_core, ne sont
      pas touchés) ;
    - le paquet est importé depuis son fichier __init__.py exact ;
    - l'origine de chaque sous-module est vérifiée.
    Renvoie un espace de noms : moteur.nommage, moteur.diagnostic, ...
    """
    init = os.path.join(DOSSIER_PAQUET, "__init__.py")
    if not os.path.isfile(init):
        raise ImportError("Paquet {0} introuvable : {1} (le dossier {0} doit être à côté "
                          "du fichier .pyt)".format(PAQUET, init))
    importlib.invalidate_caches()
    _purger_paquet()
    spec = importlib.util.spec_from_file_location(
        PAQUET, init, submodule_search_locations=[DOSSIER_PAQUET])
    paquet = importlib.util.module_from_spec(spec)
    sys.modules[PAQUET] = paquet
    try:
        spec.loader.exec_module(paquet)
        modules = {nom: importlib.import_module(PAQUET + "." + nom) for nom in SOUS_MODULES}
    except Exception:
        _purger_paquet()
        raise
    for nom, module in [("__init__", paquet)] + list(modules.items()):
        if not _vient_du_dossier(module, DOSSIER_PAQUET):
            _purger_paquet()
            raise ImportError("Module {0}.{1} chargé depuis {2} au lieu de {3}".format(
                PAQUET, nom, getattr(module, "__file__", "?"), DOSSIER_PAQUET))
    return types.SimpleNamespace(paquet=paquet, dossier=DOSSIER_PAQUET, **modules)


def moteur(recharger=False):
    """Moteur en cache pour la validation ; rechargé à chaque exécution pour
    prendre en compte les corrections sans redémarrer ArcGIS Pro."""
    global _MOTEUR
    if _MOTEUR is None or recharger:
        _MOTEUR = charger_moteur()
    return _MOTEUR


class JournalArcpy(object):
    """Journal branché sur les messages de géotraitement."""

    def info(self, texte):
        arcpy.AddMessage(texte)

    def avertissement(self, texte):
        arcpy.AddWarning(texte)

    def erreur(self, texte):
        arcpy.AddError(texte)


class Toolbox(object):
    def __init__(self):
        self.label = "DIR EST AMIANTE V3"
        self.alias = "DIRESTAMIANTEV3"
        self.tools = [TraitementPDFAmiante]


class TraitementPDFAmiante(object):
    # Indices des paramètres
    (P_DOSSIER, P_TRONCONS, P_POINTS, P_INTERPLO, P_GDB, P_PREFIXE, P_MODE,
     P_HISTO, P_CHAMP_HISTO, P_HISTO_SECTIONS, P_TOL_XY, P_TOL_CUMUL, P_TOL_ABS,
     P_SEUIL_CUMUL) = range(14)
    P_SECTIONS = (P_HISTO_SECTIONS, P_TOL_XY, P_TOL_CUMUL, P_TOL_ABS, P_SEUIL_CUMUL)

    def __init__(self):
        self.label = "Traitement des PDF Amiante"
        self.description = (
            "Analyse un dossier de PDF Amiante (sections courantes et bretelles) "
            "et contrôle leur correspondance avec le référentiel INTERPLO 2026. "
            "Modes DIAGNOSTIC, RECONSTRUCTION_BRETELLES et RECONSTRUCTION_SECTIONS.")
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
        p_mode.filter.list = [MODE_DIAGNOSTIC, MODE_BRETELLES, MODE_SECTIONS]
        p_mode.value = MODE_DIAGNOSTIC

        p_histo = arcpy.Parameter(
            displayName="Couche historique de comparaison (facultatif, ex. AMIANTE_10_BRETELLES_V8D_TEST)",
            name="couche_historique", datatype="GPFeatureLayer",
            parameterType="Optional", direction="Input")
        p_histo.filter.list = ["Polyline"]
        p_histo.enabled = False

        p_champ_histo = arcpy.Parameter(
            displayName="Champ identifiant INTERPLO de la couche historique (facultatif)",
            name="champ_id_historique", datatype="Field",
            parameterType="Optional", direction="Input")
        p_champ_histo.parameterDependencies = [p_histo.name]
        p_champ_histo.enabled = False

        # --- Paramètres de la phase 3 (actifs en mode RECONSTRUCTION_SECTIONS) ---
        p_histo_sections = arcpy.Parameter(
            displayName="Couches historiques des sections (facultatif, ex. V6A, V6C, V7B)",
            name="couches_historiques_sections", datatype="GPFeatureLayer",
            parameterType="Optional", direction="Input", multiValue=True)
        p_histo_sections.filter.list = ["Polyline"]

        def p_double(nom, libelle, defaut):
            prm = arcpy.Parameter(displayName=libelle, name=nom, datatype="GPDouble",
                                  parameterType="Optional", direction="Input")
            prm.value = defaut
            return prm

        p_tol_xy = p_double("tolerance_geometrique_m",
                            "Tolérance de continuité géométrique (m)", DEFAUT_TOL_XY)
        p_tol_cumul = p_double("tolerance_cumul",
                               "Tolérance sur les cumuls (m)", DEFAUT_TOL_CUMUL)
        p_tol_abs = p_double("tolerance_abscisse",
                             "Tolérance sur les abscisses (m)", DEFAUT_TOL_ABS)
        p_seuil = p_double("seuil_alerte_ecart_cumul_m",
                           "Seuil d'alerte d'écart de cumul aux changements de côté (m, alerte seulement)",
                           DEFAUT_SEUIL_ECART_CUMUL)
        params_sections = [p_histo_sections, p_tol_xy, p_tol_cumul, p_tol_abs, p_seuil]
        for prm in params_sections:
            prm.enabled = False

        return [p_dossier, p_troncons, p_points, p_interplo, p_gdb, p_prefixe, p_mode,
                p_histo, p_champ_histo] + params_sections

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        bretelles = parameters[self.P_MODE].valueAsText == MODE_BRETELLES
        parameters[self.P_HISTO].enabled = bretelles
        parameters[self.P_CHAMP_HISTO].enabled = bretelles
        sections = parameters[self.P_MODE].valueAsText == MODE_SECTIONS
        for i in self.P_SECTIONS:
            parameters[i].enabled = sections
        return

    def updateMessages(self, parameters):
        try:
            m = moteur()
        except Exception as exc:  # message visible dans la fenêtre de l'outil
            parameters[self.P_DOSSIER].setErrorMessage(
                "Moteur {0} non chargé depuis {1} : {2}".format(PAQUET, DOSSIER_PAQUET, exc))
            return

        p_prefixe = parameters[self.P_PREFIXE]
        if p_prefixe.valueAsText:
            erreurs = m.sorties.valider_prefixe(p_prefixe.valueAsText)
            if erreurs:
                p_prefixe.setErrorMessage(" ; ".join(erreurs))

        if parameters[self.P_MODE].valueAsText == MODE_SECTIONS:
            for i in (self.P_TOL_XY, self.P_TOL_CUMUL, self.P_TOL_ABS, self.P_SEUIL_CUMUL):
                txt = parameters[i].valueAsText
                try:
                    valeur = float(txt.replace(",", ".")) if txt else None
                except ValueError:
                    valeur = None
                if txt and (valeur is None or valeur <= 0):
                    parameters[i].setErrorMessage("Valeur strictement positive attendue")

        p_gdb = parameters[self.P_GDB]
        if p_gdb.valueAsText and not p_gdb.valueAsText.lower().endswith(".gdb"):
            p_gdb.setWarningMessage("Une géodatabase fichier (.gdb) est attendue.")

        # Les couches de référence et de comparaison doivent être distinctes.
        sources = {}
        for i in (self.P_TRONCONS, self.P_POINTS, self.P_INTERPLO, self.P_HISTO, self.P_HISTO_SECTIONS):
            for txt in valeurs_multiples(parameters[i].valueAsText) if i == self.P_HISTO_SECTIONS \
                    else [parameters[i].valueAsText]:
                if not txt:
                    continue
                if txt in sources:
                    parameters[i].setErrorMessage(
                        "« {0} » déjà utilisée par le paramètre « {1} »".format(
                            txt, parameters[sources[txt]].displayName))
                sources[txt] = i
        return

    def execute(self, parameters, messages):
        arcpy.env.overwriteOutput = False  # sécurité : jamais d'écrasement
        journal = JournalArcpy()
        try:
            m = moteur(recharger=True)
        except Exception as exc:
            journal.erreur("Moteur {0} non chargé depuis {1} : {2}".format(PAQUET, DOSSIER_PAQUET, exc))
            raise arcpy.ExecuteError(str(exc))

        valeurs = [p.valueAsText for p in parameters]
        mode = valeurs[self.P_MODE]
        journal.info("DIR EST AMIANTE — version {0} — mode {1}".format(m.paquet.__version__, mode))
        journal.info("Moteur chargé depuis : {0}".format(m.dossier))

        if mode not in MODES_DISPONIBLES:
            journal.erreur("Mode {0} non disponible dans cette version.".format(mode))
            raise arcpy.ExecuteError("Mode non disponible")

        erreurs = m.sorties.valider_prefixe(valeurs[self.P_PREFIXE])
        if erreurs:
            journal.erreur(" ; ".join(erreurs))
            raise arcpy.ExecuteError("Préfixe invalide")

        communs = dict(
            dossier_pdf=valeurs[self.P_DOSSIER],
            couche_troncons=valeurs[self.P_TRONCONS],
            couche_points=valeurs[self.P_POINTS],
            couche_interplo=valeurs[self.P_INTERPLO],
            gdb_sortie=valeurs[self.P_GDB],
            prefixe=valeurs[self.P_PREFIXE],
            journal=journal)
        try:
            if mode == MODE_DIAGNOSTIC:
                m.diagnostic.executer_diagnostic(**communs)
            elif mode == MODE_BRETELLES:
                m.reconstruction_bretelles.executer_reconstruction_bretelles(
                    couche_histo=valeurs[self.P_HISTO],
                    champ_id_histo=valeurs[self.P_CHAMP_HISTO],
                    **communs)
            else:
                parametres = m.parcours.Parametres(
                    tol_xy=_reel(valeurs[self.P_TOL_XY], DEFAUT_TOL_XY),
                    tol_cumul=_reel(valeurs[self.P_TOL_CUMUL], DEFAUT_TOL_CUMUL),
                    tol_abs=_reel(valeurs[self.P_TOL_ABS], DEFAUT_TOL_ABS),
                    seuil_alerte_ecart_cumul=_reel(valeurs[self.P_SEUIL_CUMUL], DEFAUT_SEUIL_ECART_CUMUL))
                m.reconstruction_sections.executer_reconstruction_sections(
                    couches_histo=valeurs_multiples(valeurs[self.P_HISTO_SECTIONS]),
                    parametres=parametres, **communs)
        except m.diagnostic.ErreurTraitement as exc:
            journal.erreur(str(exc))
            raise arcpy.ExecuteError(str(exc))
        return

    def postExecute(self, parameters):
        return


def _reel(texte, defaut):
    """Valeur numérique d'un paramètre (virgule décimale acceptée)."""
    if not texte:
        return defaut
    return float(str(texte).replace(",", "."))
