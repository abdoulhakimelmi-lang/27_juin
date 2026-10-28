# -*- coding: utf-8 -*-
"""Phases 1 et 2 présentes dans le même interpréteur Python (cas du VDI).

Reproduit l'incident : la phase 1 (paquet `amiante_core`, ajouté à sys.path)
est chargée avant la phase 2 ; l'ancien mécanisme d'import de la phase 2
récupérait alors le paquet de la phase 1 :
    ImportError: cannot import name 'comparaison' from 'amiante_core'

Les dossiers des deux phases sont construits dans un répertoire temporaire.
La phase 1 y est simulée par une copie du moteur sans les modules de la
phase 2 et un .pyt qui reprend son mécanisme d'import d'origine.
Faux arcpy : ne remplace pas un test dans ArcGIS Pro.
"""
import importlib
import importlib.machinery
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(ICI)
sys.path.insert(0, ICI)

import faux_arcpy  # noqa: E402
import test_toolbox_bretelles as tb  # noqa: E402

faux_arcpy.installer()

PYT_PHASE1 = '''# -*- coding: utf-8 -*-
# Reproduction du mécanisme d'import de la phase 1
import os
import sys

import arcpy

_DOSSIER = os.path.dirname(os.path.abspath(__file__))
if _DOSSIER not in sys.path:
    sys.path.insert(0, _DOSSIER)

import amiante_core  # noqa: E402
from amiante_core import controles, diagnostic, nommage, referentiel, sorties  # noqa: E402


class Toolbox(object):
    def __init__(self):
        self.label = "DIR EST AMIANTE"
        self.alias = "DIRESTAMIANTE"
        self.tools = [TraitementPDFAmiante]


class TraitementPDFAmiante(object):
    def getParameterInfo(self):
        return [arcpy.Parameter(name="p{0}".format(i)) for i in range(7)]
'''

# Ancien en-tête de la phase 2 (avant correctif), pour reproduire l'erreur
PYT_PHASE2_ANCIEN = '''import os
import sys

_DOSSIER = os.path.dirname(os.path.abspath(__file__))
if _DOSSIER not in sys.path:
    sys.path.insert(0, _DOSSIER)

import amiante_core  # noqa: E402
from amiante_core import comparaison  # noqa: E402
'''


def charger_pyt(chemin, nom):
    loader = importlib.machinery.SourceFileLoader(nom, chemin)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def fichier(module):
    return os.path.realpath(module.__file__)


class TestCoexistence(unittest.TestCase):
    def setUp(self):
        self.sys_path = list(sys.path)
        self.modules = {k: v for k, v in sys.modules.items() if k.startswith("amiante_core")}
        for k in self.modules:
            del sys.modules[k]
        self.tmp = os.path.realpath(tempfile.mkdtemp())

        # Phase 1 : Documents/DIR_EST_AMIANTE_phase1/DIR_EST_AMIANTE
        self.dossier_p1 = os.path.join(self.tmp, "Documents", "DIR_EST_AMIANTE_phase1", "DIR_EST_AMIANTE")
        paquet_p1 = os.path.join(self.dossier_p1, "amiante_core")
        shutil.copytree(os.path.join(RACINE, "amiante_core_v2"), paquet_p1,
                        ignore=shutil.ignore_patterns("__pycache__", "comparaison.py",
                                                      "reconstruction_bretelles.py"))
        with open(os.path.join(paquet_p1, "__init__.py"), "w", encoding="utf-8") as f:
            f.write('__version__ = "0.1.0-phase1"\n')
        self.pyt_p1 = os.path.join(self.dossier_p1, "DIR_EST_AMIANTE.pyt")
        with open(self.pyt_p1, "w", encoding="utf-8") as f:
            f.write(PYT_PHASE1)

        # Phase 2 corrigée : Downloads/DIR_EST_AMIANTE_phase2/DIR_EST_AMIANTE
        self.dossier_p2 = os.path.join(self.tmp, "Downloads", "DIR_EST_AMIANTE_phase2", "DIR_EST_AMIANTE")
        shutil.copytree(os.path.join(RACINE, "amiante_core_v2"),
                        os.path.join(self.dossier_p2, "amiante_core_v2"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        self.pyt_p2 = os.path.join(self.dossier_p2, "DIR_EST_AMIANTE_V2.pyt")
        shutil.copy(os.path.join(RACINE, "DIR_EST_AMIANTE_V2.pyt"), self.pyt_p2)

    def tearDown(self):
        sys.path[:] = self.sys_path
        for k in [k for k in sys.modules if k.startswith("amiante_core")]:
            del sys.modules[k]
        sys.modules.update(self.modules)
        shutil.rmtree(self.tmp)

    def verifier_moteur_phase2(self, pyt, dossier):
        m = pyt.moteur()
        racine = os.path.join(dossier, "amiante_core_v2") + os.sep
        self.assertTrue(fichier(m.paquet).startswith(racine))
        for nom in pyt.SOUS_MODULES:
            self.assertTrue(fichier(getattr(m, nom)).startswith(racine), nom)
        self.assertTrue(m.paquet.__version__.startswith("0.2"))
        return m

    # -- reproduction de l'incident ----------------------------------------
    def test_ancien_mecanisme_reproduit_l_erreur(self):
        charger_pyt(self.pyt_p1, "pyt_phase1")
        ancien = os.path.join(self.tmp, "Downloads", "ancien", "DIR_EST_AMIANTE.pyt")
        os.makedirs(os.path.dirname(ancien))
        shutil.copytree(os.path.join(self.dossier_p2, "amiante_core_v2"),
                        os.path.join(os.path.dirname(ancien), "amiante_core"))
        with open(ancien, "w", encoding="utf-8") as f:
            f.write(PYT_PHASE2_ANCIEN)
        with self.assertRaises(ImportError) as ctx:
            charger_pyt(ancien, "pyt_phase2_ancien")
        self.assertIn("comparaison", str(ctx.exception))

    # -- correctif ---------------------------------------------------------
    def test_phase1_puis_phase2(self):
        p1 = charger_pyt(self.pyt_p1, "pyt_phase1")
        paquet_p1 = sys.modules["amiante_core"]
        p2 = charger_pyt(self.pyt_p2, "pyt_phase2")

        outil = p2.TraitementPDFAmiante()
        params = outil.getParameterInfo()
        self.assertEqual(len(params), 9)
        self.assertEqual(p2.Toolbox().tools, [p2.TraitementPDFAmiante])
        self.verifier_moteur_phase2(p2, self.dossier_p2)

        # la phase 1 n'est pas perturbée
        self.assertIs(sys.modules["amiante_core"], paquet_p1)
        self.assertTrue(fichier(paquet_p1).startswith(self.dossier_p1 + os.sep))
        self.assertEqual(len(p1.TraitementPDFAmiante().getParameterInfo()), 7)
        self.assertNotEqual(p1.Toolbox().alias, p2.Toolbox().alias)

    def test_phase2_puis_phase1(self):
        p2 = charger_pyt(self.pyt_p2, "pyt_phase2")
        self.verifier_moteur_phase2(p2, self.dossier_p2)
        chemins = list(sys.path)
        charger_pyt(self.pyt_p1, "pyt_phase1")
        self.assertTrue(fichier(sys.modules["amiante_core"]).startswith(self.dossier_p1 + os.sep))
        self.verifier_moteur_phase2(p2, self.dossier_p2)
        self.assertEqual(chemins[0], sys.path[1])   # seule la phase 1 a modifié sys.path

    def test_pyt_phase2_ne_modifie_pas_sys_path(self):
        avant = list(sys.path)
        p2 = charger_pyt(self.pyt_p2, "pyt_phase2")
        p2.moteur(recharger=True)
        self.assertEqual(sys.path, avant)

    def test_version_perimee_en_memoire_et_dans_sys_path(self):
        # une autre copie de amiante_core_v2 (sans comparaison.py) est déjà
        # importée ET placée en tête de sys.path
        autre = os.path.join(self.tmp, "Documents", "copie_perimee")
        shutil.copytree(os.path.join(self.dossier_p2, "amiante_core_v2"),
                        os.path.join(autre, "amiante_core_v2"),
                        ignore=shutil.ignore_patterns("comparaison.py"))
        sys.path.insert(0, autre)
        importlib.import_module("amiante_core_v2.nommage")
        self.assertTrue(fichier(sys.modules["amiante_core_v2"]).startswith(autre))

        p2 = charger_pyt(self.pyt_p2, "pyt_phase2")
        self.verifier_moteur_phase2(p2, self.dossier_p2)
        self.assertTrue(fichier(sys.modules["amiante_core_v2.nommage"]).startswith(self.dossier_p2))

    def test_execution_bretelles_avec_phase1_chargee(self):
        charger_pyt(self.pyt_p1, "pyt_phase1")
        p2 = charger_pyt(self.pyt_p2, "pyt_phase2")
        tb.construire()
        dossier_pdf = tempfile.mkdtemp(dir=self.tmp)
        for k in range(10):
            open(os.path.join(dossier_pdf, "2023_NA_{0}_{1}.pdf".format(tb.code(k), k + 1)), "w").close()
        outil = p2.TraitementPDFAmiante()
        params = outil.getParameterInfo()
        valeurs = [dossier_pdf, tb.TRONCONS, tb.POINTS, tb.INTERPLO, tb.GDB, "TEST_ENVOI2",
                   "RECONSTRUCTION_BRETELLES", None, None]
        for p, v in zip(params, valeurs):
            p.value = v
        outil.updateParameters(params)
        outil.updateMessages(params)
        self.assertTrue(all(p.erreur is None for p in params))
        avant = faux_arcpy.instantane()
        outil.execute(params, None)
        nouvelles = [c for c in faux_arcpy.DONNEES if c not in avant]
        self.assertEqual(len(nouvelles), 2)
        fc = [c for c in nouvelles if os.path.basename(c).startswith("TEST_ENVOI2_BRETELLES_")][0]
        self.assertEqual(len(faux_arcpy.DONNEES[fc]["lignes"]), 10)
        textes = [t for _n, t in faux_arcpy.MESSAGES]
        self.assertIn("Moteur chargé depuis : {0}".format(
            os.path.join(self.dossier_p2, "amiante_core_v2")), textes)

    def test_deux_copies_phase2_chacune_son_moteur(self):
        copie_b = os.path.join(self.tmp, "Documents", "DIR_EST_AMIANTE_phase2", "DIR_EST_AMIANTE")
        shutil.copytree(self.dossier_p2, copie_b)
        pa = charger_pyt(self.pyt_p2, "pyt_phase2_a")
        pb = charger_pyt(os.path.join(copie_b, "DIR_EST_AMIANTE_V2.pyt"), "pyt_phase2_b")
        self.verifier_moteur_phase2(pb, copie_b)
        self.verifier_moteur_phase2(pa, self.dossier_p2)
        pa.moteur(recharger=True)
        self.verifier_moteur_phase2(pa, self.dossier_p2)

    def test_paquet_incomplet_n_empeche_pas_l_ouverture(self):
        os.remove(os.path.join(self.dossier_p2, "amiante_core_v2", "comparaison.py"))
        p2 = charger_pyt(self.pyt_p2, "pyt_phase2")      # le .pyt s'ouvre
        outil = p2.TraitementPDFAmiante()
        params = outil.getParameterInfo()
        self.assertEqual(len(params), 9)
        outil.updateMessages(params)                     # erreur claire dans l'outil
        self.assertIn("comparaison", params[0].erreur)
        self.assertNotIn("amiante_core_v2", sys.modules)
        with self.assertRaises(faux_arcpy.ExecuteError):
            outil.execute(params, None)

    def test_paquet_absent(self):
        shutil.rmtree(os.path.join(self.dossier_p2, "amiante_core_v2"))
        p2 = charger_pyt(self.pyt_p2, "pyt_phase2")
        params = p2.TraitementPDFAmiante().getParameterInfo()
        p2.TraitementPDFAmiante().updateMessages(params)
        self.assertIn("introuvable", params[0].erreur)


if __name__ == "__main__":
    unittest.main()
