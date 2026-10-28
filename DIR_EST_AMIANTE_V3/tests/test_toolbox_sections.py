# -*- coding: utf-8 -*-
"""Mode RECONSTRUCTION_SECTIONS de bout en bout, avec un FAUX arcpy.

Données fictives (tests/donnees_sections.py) ; ne remplace pas le test réel
dans ArcGIS Pro.
"""
import os
import shutil
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
sys.path.insert(0, os.path.dirname(ICI))

import donnees_sections as ds  # noqa: E402
import faux_arcpy  # noqa: E402
from faux_arcpy import FauxPolyligne  # noqa: E402
from test_toolbox import charger_pyt  # noqa: E402

faux_arcpy.installer()

GDB = os.path.join("C:\\fictif", "sortie.gdb")
TRONCONS, POINTS, INTERPLO = "TRONCONS_FICTIFS", "POINTS_FICTIFS", "INTERPLO_FICTIF"
H_V6A, H_V6C, H_V7B = "HISTO_V6A_FICTIF", "HISTO_V6C_FICTIF", "HISTO_V7B_FICTIF"

PDF_SECTIONS = [
    "2023_NA_70_N0101_PR010300_PR011500_I.pdf",      # classique, 3 tronçons
    "2022_NA_70_N0102_PR001100_PR001800_I.pdf",      # portion commune D/DF (renommé, historique en _U)
    "2017_A_88_N0103_PR021500_G_PR023500_I.pdf",     # G -> I, écart de cumul 44 m
    "2017_A_88_N0104_PR030100_D_PR031800_I.pdf",     # D -> I -> D -> I
    "2023_NA_39_N0105_PR005100_PR005800_I.pdf",      # ambigu
    "2023_NA_39_N0106_PR005100_PR005800_I.pdf",      # rupture
]
PDF_BRETELLES = ["2023_NA_54A933040_3.pdf", "2018_A_54A933040_1.pdf"]


def construire():
    faux_arcpy.reinitialiser()
    types = {"ID_INTERPLO": "Integer", "ROUTE": "String", "DEPARTEMENT": "String", "COTE": "String"}
    champs = [("OBJECTID", "OID"), ("Shape", "Geometry")] + [
        (c, types.get(c, "Double" if c.startswith(("PR_", "ABS_", "CUMUL_")) else "String"))
        for c in ds.CHAMPS]
    lignes = ds.troncons()
    pts = ds.points_pr(lignes)
    rows = []
    for k, l in enumerate(lignes, 1):
        r = {c: l[c] for c in ds.CHAMPS}
        r.update({"OBJECTID": k, "Shape": l["SHAPE@"]})
        rows.append(r)
    faux_arcpy.ajouter_couche(TRONCONS, "Polyline", champs, rows)
    faux_arcpy.ajouter_couche(POINTS, "Point", [("OBJECTID", "OID"), ("Shape", "Geometry"), ("ID_INTERPLO", "Integer"),
                                                ("TYPE_POINT", "String"), ("X_GEOM", "Double"),
                                                ("Y_GEOM", "Double"), ("CUMUL", "Double")],
                              [dict(p, OBJECTID=k) for k, p in enumerate(pts, 1)])
    faux_arcpy.ajouter_couche(INTERPLO, "Polyline", [("OBJECTID", "OID"), ("objetid", "Integer"),
                                                     ("route", "String"), ("nomplodeb", "String"),
                                                     ("nomplofin", "String")], [], epsg=3857)
    champs_h = [("OBJECTID", "OID"), ("Shape", "Geometry"), ("NOM_PDF", "String"), ("ROUTE", "String"),
                ("DEP", "String"), ("IDS_INTERPLO", "String"), ("LONG_REF_M", "Double"), ("LONG_GEOM_M", "Double")]

    def h(oid, nom, ids, coords, long_ref):
        g = FauxPolyligne([coords])
        return {"OBJECTID": oid, "Shape": g, "NOM_PDF": nom, "IDS_INTERPLO": ids, "LONG_REF_M": long_ref,
                "LONG_GEOM_M": g.length}

    # V6A : sommets de jonction dupliqués (assemblage historique sans dédoublonnage)
    faux_arcpy.ajouter_couche(H_V6A, "Polyline", champs_h, [
        h(1, PDF_SECTIONS[0], "101,102,103",
          [(300.0, 0.0), (600.0, 0.0), (600.0, 0.0), (1200.0, 0.0), (1200.0, 0.0), (1800.0, 0.0)], 1200.0),
        h(2, PDF_SECTIONS[4], "501,502", [(100.0, 15000.0), (800.0, 15000.0)], 700.0)])
    faux_arcpy.ajouter_couche(H_V6C, "Polyline", champs_h, [
        h(1, "2022_NA_70_N0102_PR001100_PR001800_U.pdf", "202,203",
          [(1100.0, 5000.0), (1500.0, 5000.0), (1800.0, 5000.0)], 700.0)])
    faux_arcpy.ajouter_couche(H_V7B, "Polyline", champs_h, [
        h(1, PDF_SECTIONS[2], "301,302,303", [(500.0, 9000.0), (1000.0, 9000.0), (2000.0, 9000.0),
                                              (2456.0, 9000.0)], 1956.0),
        h(2, PDF_SECTIONS[3], "401,402,403,404", [(100.0, 12000.0), (500.0, 12000.0), (1000.0, 12000.0),
                                                  (1500.0, 12000.0), (1800.0, 12000.0)], 1700.0)])


class TestModeSections(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pyt = charger_pyt()

    def setUp(self):
        construire()
        self.dossier = tempfile.mkdtemp()
        for nom in PDF_SECTIONS + PDF_BRETELLES:
            open(os.path.join(self.dossier, nom), "w").close()
        self.outil = self.pyt.TraitementPDFAmiante()
        self.params = self.outil.getParameterInfo()

    def tearDown(self):
        shutil.rmtree(self.dossier)

    def executer(self, histos=(H_V6A, H_V6C, H_V7B), seuil=None):
        valeurs = [self.dossier, TRONCONS, POINTS, INTERPLO, GDB, "TEST_ENVOI2", "RECONSTRUCTION_SECTIONS",
                   None, None, ";".join(histos) or None, 1.0, 0.001, 0.001, seuil or 100.0]
        for p, v in zip(self.params, valeurs):
            p.value = v
        self.outil.updateParameters(self.params)
        self.outil.updateMessages(self.params)
        self.assertTrue(all(p.erreur is None for p in self.params), [p.erreur for p in self.params])
        self.outil.execute(self.params, None)

    def nouvelles(self, avant):
        return {os.path.basename(c).rsplit("_", 2)[0]: c for c in faux_arcpy.DONNEES if c not in avant}

    def test_reconstruction_et_comparaison(self):
        avant = faux_arcpy.instantane()
        self.executer()
        self.assertFalse(faux_arcpy.env.overwriteOutput)
        for chemin, contenu in avant.items():                      # aucune donnée source modifiée
            self.assertEqual(faux_arcpy.DONNEES[chemin], contenu, chemin)

        s = self.nouvelles(avant)
        self.assertEqual(set(s), {"TEST_ENVOI2_SECTIONS", "CONTROLE_TEST_ENVOI2_SECTIONS",
                                  "TRONCONS_TEST_ENVOI2_SECTIONS", "COMPARAISON_TEST_ENVOI2_SECTIONS"})
        self.assertEqual(len({c.rsplit("_", 2)[1:][0] + c.rsplit("_", 2)[2] for c in s.values()}), 1)

        fc = faux_arcpy.DONNEES[s["TEST_ENVOI2_SECTIONS"]]
        self.assertEqual(fc["epsg"], 2154)
        geoms = {l["NOM_PDF"]: l for l in fc["lignes"]}
        self.assertEqual(set(geoms), set(PDF_SECTIONS[:4]))
        self.assertEqual(geoms[PDF_SECTIONS[0]]["Shape"].parties,
                         [[(300.0, 0.0), (600.0, 0.0), (1200.0, 0.0), (1800.0, 0.0)]])
        self.assertEqual(geoms[PDF_SECTIONS[2]]["IDS_INTERPLO"], "301,302,303")
        self.assertEqual(geoms[PDF_SECTIONS[1]]["METHODE"], "PORTION_COMMUNE_DF_FF")

        ctrl = {l["NOM_PDF"]: l for l in faux_arcpy.DONNEES[s["CONTROLE_TEST_ENVOI2_SECTIONS"]]["lignes"]}
        self.assertEqual(len(ctrl), 6)                               # bretelles exclues
        self.assertEqual(ctrl[PDF_SECTIONS[4]]["STATUT_RECONSTRUCTION"], "PARCOURS_AMBIGU")
        self.assertEqual(ctrl[PDF_SECTIONS[5]]["STATUT_RECONSTRUCTION"], "PARCOURS_INTROUVABLE")
        self.assertIn("44.000", ctrl[PDF_SECTIONS[2]]["ALERTES"])

        detail = faux_arcpy.DONNEES[s["TRONCONS_TEST_ENVOI2_SECTIONS"]]["lignes"]
        ambigu = [l for l in detail if l["NOM_PDF"] == PDF_SECTIONS[4]]
        self.assertEqual({l["VARIANTE"] for l in ambigu}, {1, 2})
        self.assertEqual(len([l for l in detail if l["NOM_PDF"] == PDF_SECTIONS[3]]), 4)

        comp = {(l.get("NOM_PDF") or l.get("NOM_PDF_HISTO")): l
                for l in faux_arcpy.DONNEES[s["COMPARAISON_TEST_ENVOI2_SECTIONS"]]["lignes"]}
        for nom in PDF_SECTIONS[:4]:
            self.assertEqual(comp[nom]["RESULTAT"], "IDENTIQUE", (nom, comp[nom]))
            self.assertEqual(comp[nom]["SENS"], "MEME_SENS")
        self.assertEqual(comp[PDF_SECTIONS[1]]["CORRESPONDANCE_NOM"], "RENOMME")
        self.assertEqual(comp[PDF_SECTIONS[4]]["RESULTAT"], "NON_RECONSTRUIT")
        self.assertEqual(comp[PDF_SECTIONS[5]]["RESULTAT"], "ABSENT_HISTORIQUE")

        textes = " ".join(t for _n, t in faux_arcpy.MESSAGES)
        for attendu in ("sections reconnues : 6", "Reconstructions candidates : 4", "Parcours ambigus : 1",
                        "Géométries écrites : 4", "bretelles ignorées : 2", "pas une validation métier"):
            self.assertIn(attendu, textes)

    def test_sans_couche_historique(self):
        avant = faux_arcpy.instantane()
        self.executer(histos=())
        self.assertEqual(len(self.nouvelles(avant)), 3)

    def test_noms_existants_jamais_reutilises(self):
        avant = faux_arcpy.instantane()
        self.executer()
        premiere = {c: faux_arcpy.instantane()[c] for c in self.nouvelles(avant).values()}
        self.executer()
        for c, contenu in premiere.items():
            self.assertEqual(faux_arcpy.DONNEES[c], contenu)
        self.assertEqual(len([c for c in faux_arcpy.DONNEES if c not in avant]), 8)

    def test_champ_manquant_bloque_avant_ecriture(self):
        faux_arcpy.DONNEES[TRONCONS]["champs"] = [c for c in faux_arcpy.DONNEES[TRONCONS]["champs"]
                                                  if c[0] != "LOGIQUE_3"]
        avant = faux_arcpy.instantane()
        with self.assertRaises(faux_arcpy.ExecuteError):
            self.executer()
        self.assertEqual(set(faux_arcpy.DONNEES), set(avant))
        self.assertIn("LOGIQUE_3", " ".join(t for n, t in faux_arcpy.MESSAGES if n == "ERREUR"))

    def test_couche_historique_incomplete_ignoree(self):
        faux_arcpy.DONNEES[H_V7B]["champs"] = [c for c in faux_arcpy.DONNEES[H_V7B]["champs"]
                                               if c[0] != "IDS_INTERPLO"]
        avant = faux_arcpy.instantane()
        self.executer()
        comp = self.nouvelles(avant)["COMPARAISON_TEST_ENVOI2_SECTIONS"]
        res = {l.get("NOM_PDF"): l["RESULTAT"] for l in faux_arcpy.DONNEES[comp]["lignes"]}
        self.assertEqual(res[PDF_SECTIONS[2]], "ABSENT_HISTORIQUE")
        self.assertIn("Couche historique ignorée", " ".join(t for _n, t in faux_arcpy.MESSAGES))

    def test_points_pr_absents_orientation_non_controlee(self):
        faux_arcpy.DONNEES[POINTS]["champs"] = [c for c in faux_arcpy.DONNEES[POINTS]["champs"]
                                                if c[0] != "X_GEOM"]
        avant = faux_arcpy.instantane()
        self.executer(histos=())
        ctrl = self.nouvelles(avant)["CONTROLE_TEST_ENVOI2_SECTIONS"]
        lignes = {l["NOM_PDF"]: l for l in faux_arcpy.DONNEES[ctrl]["lignes"]}
        self.assertIn("orientation non contrôlée", lignes[PDF_SECTIONS[0]]["ALERTES"])
        self.assertIn("orientation des tronçons NON contrôlée", " ".join(t for _n, t in faux_arcpy.MESSAGES))


if __name__ == "__main__":
    unittest.main()
