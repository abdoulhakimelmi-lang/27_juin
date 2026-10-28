# -*- coding: utf-8 -*-
"""Test de la Python Toolbox avec un FAUX arcpy et des données fictives.

Ce test vérifie la structure du .pyt et l'enchaînement du mode DIAGNOSTIC.
Il ne remplace pas un test dans ArcGIS Pro.
"""
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
sys.path.insert(0, RACINE)

import faux_arcpy  # noqa: E402

faux_arcpy.installer()

GDB = os.path.join("C:\\fictif", "sortie.gdb")
TRONCONS = "REF_TRONCONS_FICTIF"
POINTS = "REF_POINTS_FICTIF"
INTERPLO = "INTERPLO_FICTIF"


def charger_pyt():
    chemin = os.path.join(RACINE, "DIR_EST_AMIANTE_V3.pyt")
    loader = importlib.machinery.SourceFileLoader("dir_est_amiante_pyt", chemin)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def donnees_fictives():
    faux_arcpy.reinitialiser()
    champs_tr = [("OBJECTID", "OID"), ("Shape", "Geometry")] + [
        (c, "String") for c in ("ID_INTERPLO", "ROUTE", "DEPARTEMENT", "COTE")] + [
        (c, "Double") for c in ("PR_DEBUT", "PR_FIN", "ABS_DEBUT", "ABS_FIN", "CUMUL_DEBUT",
                                "CUMUL_FIN", "LONG_REF_M", "LONG_GEOM_M")] + [
        (c, "String") for c in ("LOGIQUE_DEB", "LOGIQUE_FIN", "LOGIQUE_2", "LOGIQUE_3")]
    faux_arcpy.ajouter_couche(TRONCONS, "Polyline", champs_tr, [
        {"ID_INTERPLO": "1", "ROUTE": "N0005", "COTE": "D"},
        {"ID_INTERPLO": "2", "ROUTE": "N0005", "COTE": "G"},
        {"ID_INTERPLO": "3", "ROUTE": "N59", "COTE": "D"},
    ])
    faux_arcpy.ajouter_couche(POINTS, "Point", [("OBJECTID", "OID"), ("CHAMP_INCONNU", "String")],
                              [{"CHAMP_INCONNU": "x"}])
    faux_arcpy.ajouter_couche(INTERPLO, "Polyline",
                              [("OBJECTID", "OID"), ("objetid", "Integer"), ("route", "String"),
                               ("nomplodeb", "String"), ("nomplofin", "String")],
                              [{"objetid": 10, "route": "54A933040", "nomplodeb": "DB3",
                                "nomplofin": "FB3"}])
    faux_arcpy.ajouter_couche(os.path.join(GDB, "AMIANTE_3PDF_V7B_TEST"), "Polyline",
                              [("OBJECTID", "OID")], [{"OBJECTID": 1}])


class TestToolbox(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pyt = charger_pyt()

    def setUp(self):
        donnees_fictives()
        self.dossier = tempfile.mkdtemp()
        for nom in ("2023_NA_39_N0005_PR109500_PR110000_I.pdf",
                    "2017_A_88_N0059_PR021500_G_PR025000_I.pdf",
                    "2020_A_54_N0004_PR010000_PR011000_U.pdf",
                    "2023_NA_54A933040_3.pdf",
                    "document scanné.pdf"):
            open(os.path.join(self.dossier, nom), "w").close()
        self.outil = self.pyt.TraitementPDFAmiante()
        self.params = self.outil.getParameterInfo()

    def tearDown(self):
        shutil.rmtree(self.dossier)

    def _remplir(self, mode="DIAGNOSTIC", prefixe="TEST"):
        valeurs = [self.dossier, TRONCONS, POINTS, INTERPLO, GDB, prefixe, mode]
        for p, v in zip(self.params, valeurs):
            p.value = v

    def test_structure(self):
        tb = self.pyt.Toolbox()
        self.assertEqual(tb.tools, [self.pyt.TraitementPDFAmiante])
        self.assertEqual(len(self.params), 14)
        # les 9 paramètres de la V2 restent identiques et dans le même ordre
        self.assertEqual([p.name for p in self.params],
                         ["dossier_pdf", "couche_troncons", "couche_points_pr", "couche_interplo",
                          "gdb_sortie", "prefixe", "mode", "couche_historique",
                          "champ_id_historique", "couches_historiques_sections",
                          "tolerance_geometrique_m", "tolerance_cumul", "tolerance_abscisse",
                          "seuil_alerte_ecart_cumul_m"])
        self.assertTrue(self.params[9].multiValue)
        self.assertEqual([p.value for p in self.params[10:]], [1.0, 0.001, 0.001, 100.0])
        self.assertTrue(all(p.datatype == "GPDouble" for p in self.params[10:]))
        self.assertEqual(self.params[0].datatype, "DEFolder")
        self.assertEqual(self.params[1].datatype, "GPFeatureLayer")
        self.assertEqual(self.params[2].datatype, "GPFeatureLayer")
        self.assertIn("GPTableView", self.params[3].datatype)
        self.assertEqual(self.params[4].datatype, "DEWorkspace")
        self.assertEqual(self.params[6].filter.list,
                         ["DIAGNOSTIC", "RECONSTRUCTION_BRETELLES", "RECONSTRUCTION_SECTIONS"])
        self.assertTrue(all(p.parameterType == "Required" for p in self.params[:7]))
        self.assertTrue(all(p.parameterType == "Optional" for p in self.params[7:]))
        self.assertEqual(self.params[8].parameterDependencies, ["couche_historique"])

    def test_activation_parametres_historique(self):
        self._remplir(mode="RECONSTRUCTION_BRETELLES")
        self.outil.updateParameters(self.params)
        self.assertTrue(self.params[7].enabled and self.params[8].enabled)
        self._remplir(mode="DIAGNOSTIC")
        self.outil.updateParameters(self.params)
        self.assertFalse(self.params[7].enabled or self.params[8].enabled)

    def test_mode_sections_disponible_et_parametres(self):
        self._remplir(mode="RECONSTRUCTION_SECTIONS")
        self.outil.updateParameters(self.params)
        self.assertTrue(all(p.enabled for p in self.params[9:]))
        self.assertFalse(self.params[7].enabled or self.params[8].enabled)
        self.outil.updateMessages(self.params)
        self.assertTrue(all(p.erreur is None for p in self.params))
        self.params[10].value = 0
        self.params[13].value = "abc"
        self.outil.updateMessages(self.params)
        self.assertIsNotNone(self.params[10].erreur)
        self.assertIsNotNone(self.params[13].erreur)
        self._remplir(mode="DIAGNOSTIC")
        self.outil.updateParameters(self.params)
        self.assertFalse(any(p.enabled for p in self.params[9:]))

    def test_couche_historique_identique_a_un_referentiel(self):
        self._remplir(mode="RECONSTRUCTION_SECTIONS")
        self.params[9].value = "HISTO_A;" + TRONCONS
        self.outil.updateMessages(self.params)
        self.assertIsNotNone(self.params[9].erreur)
        self.assertEqual(self.pyt.valeurs_multiples("a;'b c';d"), ["a", "b c", "d"])

    def test_messages_prefixe_invalide_et_couches_identiques(self):
        self._remplir(prefixe="1 mauvais")
        self.params[2].value = TRONCONS
        self.outil.updateMessages(self.params)
        self.assertIsNotNone(self.params[5].erreur)
        self.assertIsNotNone(self.params[2].erreur)

    def test_execute_diagnostic(self):
        avant = faux_arcpy.instantane()
        self._remplir()
        self.outil.execute(self.params, None)
        self.assertFalse(faux_arcpy.env.overwriteOutput)

        # Données existantes inchangées
        for chemin, contenu in avant.items():
            self.assertEqual(faux_arcpy.DONNEES[chemin], contenu, chemin)

        nouvelles = [c for c in faux_arcpy.DONNEES if c not in avant]
        self.assertEqual(len(nouvelles), 1)
        table = nouvelles[0]
        self.assertTrue(os.path.basename(table).startswith("TEST_DIAG_PDF_"))
        lignes = {l["NOM_PDF"]: l for l in faux_arcpy.DONNEES[table]["lignes"]}
        self.assertEqual(len(lignes), 5)
        self.assertEqual(lignes["2023_NA_39_N0005_PR109500_PR110000_I.pdf"]["ROUTE_REF"], "EXACTE")
        self.assertEqual(lignes["2023_NA_39_N0005_PR109500_PR110000_I.pdf"]["NB_TRONCONS_ROUTE"], 2)
        self.assertEqual(lignes["2017_A_88_N0059_PR021500_G_PR025000_I.pdf"]["ROUTE_REF"], "VARIANTE:N59")
        self.assertEqual(lignes["2020_A_54_N0004_PR010000_PR011000_U.pdf"]["ROUTE_REF"], "ABSENTE")
        self.assertEqual(lignes["2020_A_54_N0004_PR010000_PR011000_U.pdf"]["NIVEAU_DIAG"], "ERREUR")
        self.assertEqual(lignes["2023_NA_54A933040_3.pdf"]["ROUTE_REF"], "EXACTE")
        self.assertEqual(lignes["2023_NA_54A933040_3.pdf"]["NOMPLODEB_ATT"], "DB3")
        self.assertEqual(lignes["document scanné.pdf"]["TYPE_PDF"], "NON_RECONNU")

        textes = " ".join(t for _n, t in faux_arcpy.MESSAGES)
        self.assertIn("CHAMP_INCONNU", textes)          # champs de la couche points listés
        self.assertIn("entités au lieu des", textes)    # effectifs fictifs != annoncés

        # Seconde exécution : nouvelle table, la première n'est pas touchée
        premiere = faux_arcpy.instantane()[table]
        self.outil.execute(self.params, None)
        self.assertEqual(faux_arcpy.DONNEES[table], premiere)
        self.assertEqual(len([c for c in faux_arcpy.DONNEES if c not in avant]), 2)

    def test_champs_manquants_signales(self):
        faux_arcpy.DONNEES[INTERPLO]["champs"] = [("OBJECTID", "OID"), ("route", "String")]
        self._remplir()
        self.outil.execute(self.params, None)
        erreurs = [t for niv, t in faux_arcpy.MESSAGES if niv == "ERREUR"]
        self.assertTrue(any("objetid" in e and "nomplodeb" in e for e in erreurs))

    def test_execute_refuse_mode_inconnu(self):
        self._remplir(mode="RECONSTRUCTION_INCONNUE")
        avant = faux_arcpy.instantane()
        with self.assertRaises(faux_arcpy.ExecuteError):
            self.outil.execute(self.params, None)
        self.assertEqual(faux_arcpy.DONNEES, avant)


if __name__ == "__main__":
    unittest.main()
