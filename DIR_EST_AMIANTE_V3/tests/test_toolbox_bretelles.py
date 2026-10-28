# -*- coding: utf-8 -*-
"""Mode RECONSTRUCTION_BRETELLES de bout en bout, avec un FAUX arcpy.

Simule le test de référence : 10 bretelles fictives et une couche
historique fictive. Ne remplace pas le test réel dans ArcGIS Pro.
"""
import os
import shutil
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
sys.path.insert(0, os.path.dirname(ICI))

import faux_arcpy  # noqa: E402
from faux_arcpy import FauxPolyligne  # noqa: E402
from test_toolbox import charger_pyt  # noqa: E402

faux_arcpy.installer()

GDB = os.path.join("C:\\fictif", "sortie.gdb")
TRONCONS, POINTS, INTERPLO, HISTO = "TRONCONS_FICTIFS", "POINTS_FICTIFS", "INTERPLO_FICTIF", "HISTO_FICTIF"
CHAMPS_POINTS = ["ID_INTERPLO", "ROUTE", "DEPARTEMENT", "COTE", "TYPE_POINT", "PR", "ABSCISSE",
                 "CUMUL", "X_GEOM", "Y_GEOM", "X_REF", "Y_REF", "ECART_XY_M", "CONTROLE_XY",
                 "LOGIQUE_DEB", "LOGIQUE_FIN", "LOGIQUE_2", "LOGIQUE_3", "CONTROLE_TRONCON"]


def geom(k):
    x0 = 900000.0 + 1000 * k
    return FauxPolyligne([[(x0, 6800000.0), (x0 + 120.0, 6800000.0), (x0 + 120.0, 6800080.0 + k)]])


def code(k):
    return "54A9330{0:02d}".format(k)


def construire(champs_interplo=("objetid", "route", "nomplodeb", "nomplofin")):
    faux_arcpy.reinitialiser()
    # 10 bretelles résolubles (k = 0..9) + identifiants locaux "étrangers"
    lignes_ip = [{"objetid": 5000 + k, "route": code(k), "nomplodeb": "DB{0}".format(k + 1),
                  "nomplofin": "FB{0}".format(k + 1)} for k in range(10)]
    lignes_ip += [{"objetid": 6001, "route": "54A777777", "nomplodeb": "DB1", "nomplofin": "FB1"},
                  {"objetid": 6002, "route": "54A777777", "nomplodeb": "DB1", "nomplofin": "FB1"}]
    lignes_ip = [{c: l[c] for c in champs_interplo} for l in lignes_ip]
    faux_arcpy.ajouter_couche(INTERPLO, "Polyline", [("OBJECTID", "OID")] + [
        (c, "String") for c in champs_interplo], lignes_ip, epsg=3857)

    champs_tr = [("OBJECTID", "OID"), ("Shape", "Geometry"), ("ID_INTERPLO", "Integer"),
                 ("ROUTE", "String"), ("DEPARTEMENT", "String"), ("COTE", "String"),
                 ("LONG_REF_M", "Double"), ("LONG_GEOM_M", "Double")]
    lignes_tr = [{"OBJECTID": k + 1, "Shape": geom(k), "ID_INTERPLO": 5000 + k, "ROUTE": code(k),
                  "DEPARTEMENT": "54", "COTE": "D", "LONG_REF_M": 200.0,
                  "LONG_GEOM_M": round(geom(k).length, 3)} for k in range(10)]
    lignes_tr += [{"OBJECTID": 99, "Shape": geom(50), "ID_INTERPLO": 6001, "ROUTE": "54A777777",
                   "DEPARTEMENT": "54", "COTE": "D", "LONG_REF_M": 1.0, "LONG_GEOM_M": 1.0}]
    faux_arcpy.ajouter_couche(TRONCONS, "Polyline", champs_tr, lignes_tr, has_m=True)

    faux_arcpy.ajouter_couche(POINTS, "Point", [("OBJECTID", "OID"), ("Shape", "Geometry")] + [
        (c, "String") for c in CHAMPS_POINTS], [{"OBJECTID": 1}])


def construire_histo(avec_id=True, decalage_k=None):
    champs = [("OBJECTID", "OID"), ("Shape", "Geometry")] + ([("ID_INTERP", "Integer")] if avec_id else [])
    lignes = []
    for k in range(10):
        g = geom(k)
        if k == decalage_k:
            g = FauxPolyligne([[(x, y + 0.30) for x, y in g.parties[0]]])
        l_ = {"OBJECTID": 100 + k, "Shape": g}
        if avec_id:
            l_["ID_INTERP"] = 5000 + k
        lignes.append(l_)
    faux_arcpy.ajouter_couche(HISTO, "Polyline", champs, lignes)


class TestModeBretelles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pyt = charger_pyt()

    def setUp(self):
        construire()
        self.dossier = tempfile.mkdtemp()
        noms = ["2023_NA_{0}_{1}.pdf".format(code(k), k + 1) for k in range(10)]
        noms += ["2023_A_54A777777_1.pdf",                      # ambigu dans INTERPLO
                 "2023_A_54A888888_2.pdf",                      # code échangeur absent
                 "2023_NA_39_N0005_PR109500_PR110000_I.pdf",    # section : ignorée
                 "2017_A_88_N0059_PR021500_G_PR025000_I.pdf"]   # section : ignorée
        for nom in noms:
            open(os.path.join(self.dossier, nom), "w").close()
        self.outil = self.pyt.TraitementPDFAmiante()
        self.params = self.outil.getParameterInfo()

    def tearDown(self):
        shutil.rmtree(self.dossier)

    def executer(self, histo=None, champ=None):
        valeurs = [self.dossier, TRONCONS, POINTS, INTERPLO, GDB, "TEST_ENVOI2",
                   "RECONSTRUCTION_BRETELLES", histo, champ]
        for p, v in zip(self.params, valeurs):
            p.value = v
        self.outil.updateParameters(self.params)
        self.outil.updateMessages(self.params)
        self.assertTrue(all(p.erreur is None for p in self.params))
        self.outil.execute(self.params, None)

    def nouvelles(self, avant):
        return {os.path.basename(c).rsplit("_", 2)[0]: c for c in faux_arcpy.DONNEES if c not in avant}

    def test_reconstruction_complete(self):
        avant = faux_arcpy.instantane()
        self.executer()
        self.assertFalse(faux_arcpy.env.overwriteOutput)
        for chemin, contenu in avant.items():
            self.assertEqual(faux_arcpy.DONNEES[chemin], contenu, chemin)

        sorties = self.nouvelles(avant)
        self.assertEqual(sorties.keys(), {"TEST_ENVOI2_BRETELLES", "CONTROLE_TEST_ENVOI2_BRETELLES"})
        fc, table = sorties["TEST_ENVOI2_BRETELLES"], sorties["CONTROLE_TEST_ENVOI2_BRETELLES"]
        self.assertEqual(fc.rsplit("_", 2)[1:], table.rsplit("_", 2)[1:])  # même horodatage

        d_fc = faux_arcpy.DONNEES[fc]
        self.assertEqual(d_fc["epsg"], 2154)
        self.assertTrue(d_fc["has_m"])                       # mêmes propriétés M que la source
        self.assertEqual(len(d_fc["lignes"]), 10)
        for ligne in d_fc["lignes"]:
            k = int(ligne["ID_INTERPLO"]) - 5000
            self.assertEqual(ligne["Shape"], geom(k))
            self.assertEqual(ligne["CONTROLE"], "CANDIDAT_A_VALIDER")
            self.assertEqual(ligne["NUM_BRET"], k + 1)
            self.assertEqual(ligne["LONG_GEOM_M"], round(geom(k).length, 3))
            self.assertEqual(ligne["ECART_M"], round(geom(k).length - 200.0, 3))

        lignes_t = {l["NOM_PDF"]: l for l in faux_arcpy.DONNEES[table]["lignes"]}
        self.assertEqual(len(lignes_t), 12)
        self.assertEqual(lignes_t["2023_A_54A777777_1.pdf"]["CONTROLE"],
                         "ANOMALIE_CORRESPONDANCE_INTERPLO_AMBIGUE")
        self.assertEqual(lignes_t["2023_A_54A888888_2.pdf"]["CONTROLE"], "ANOMALIE_CODE_ECHANGEUR_ABSENT")
        self.assertIn("6001, 6002", lignes_t["2023_A_54A777777_1.pdf"]["ANOMALIES"])

        # la géométrie locale a été lue en EPSG:2154 ; INTERPLO sans géométrie
        lectures = {c: (champs, epsg) for c, champs, epsg in faux_arcpy.CURSEURS}
        self.assertEqual(lectures[TRONCONS][1], 2154)
        self.assertNotIn("SHAPE@", lectures[INTERPLO][0])

        textes = " ".join(t for _n, t in faux_arcpy.MESSAGES)
        self.assertIn("sections ignorées : 2", textes)
        self.assertIn("CANDIDAT_A_VALIDER : 10", textes)

    def test_comparaison_historique_par_identifiant(self):
        construire_histo(avec_id=True)
        avant = faux_arcpy.instantane()
        self.executer(HISTO, "ID_INTERP")
        self.assertEqual(faux_arcpy.DONNEES[HISTO], avant[HISTO])
        comp = self.nouvelles(avant)["COMPARAISON_TEST_ENVOI2_BRETELLES"]
        lignes = faux_arcpy.DONNEES[comp]["lignes"]
        self.assertEqual(len(lignes), 10)
        self.assertTrue(all(l["RESULTAT"] == "IDENTIQUE" for l in lignes))
        self.assertTrue(all(l["DIST_MAX_M"] == 0.0 and l["ECART_LONG_M"] == 0.0 for l in lignes))
        textes = " ".join(t for _n, t in faux_arcpy.MESSAGES)
        self.assertIn("tous les identifiants, longueurs et tracés concordent", textes)

    def test_comparaison_detecte_trace_decale(self):
        construire_histo(avec_id=True, decalage_k=4)
        avant = faux_arcpy.instantane()
        self.executer(HISTO, "ID_INTERP")
        comp = self.nouvelles(avant)["COMPARAISON_TEST_ENVOI2_BRETELLES"]
        res = {l["ID_INTERPLO"]: l for l in faux_arcpy.DONNEES[comp]["lignes"]}
        self.assertEqual(res["5004"]["RESULTAT"], "TRACE_DIFFERENT")
        self.assertAlmostEqual(res["5004"]["DIST_MAX_M"], 0.30, places=3)
        self.assertEqual(sum(1 for l in res.values() if l["RESULTAT"] == "IDENTIQUE"), 9)

    def test_comparaison_geometrique_sans_champ_identifiant(self):
        construire_histo(avec_id=False)
        avant = faux_arcpy.instantane()
        self.executer(HISTO, None)
        comp = self.nouvelles(avant)["COMPARAISON_TEST_ENVOI2_BRETELLES"]
        lignes = faux_arcpy.DONNEES[comp]["lignes"]
        self.assertTrue(all(l["RESULTAT"] == "IDENTIQUE" for l in lignes))
        self.assertEqual(sorted(l["ID_HISTO"] for l in lignes), ["OID {0}".format(100 + k) for k in range(10)])

    def test_noms_existants_jamais_reutilises(self):
        avant = faux_arcpy.instantane()
        self.executer()
        premiere = {c: faux_arcpy.instantane()[c] for c in self.nouvelles(avant).values()}
        self.executer()
        for c, contenu in premiere.items():
            self.assertEqual(faux_arcpy.DONNEES[c], contenu)
        self.assertEqual(len([c for c in faux_arcpy.DONNEES if c not in avant]), 4)

    def test_champ_manquant_bloque_avant_ecriture(self):
        construire(champs_interplo=("objetid", "route", "nomplodeb"))
        avant = faux_arcpy.instantane()
        with self.assertRaises(faux_arcpy.ExecuteError):
            self.executer()
        self.assertEqual(set(faux_arcpy.DONNEES), set(avant))
        erreurs = " ".join(t for n, t in faux_arcpy.MESSAGES if n == "ERREUR")
        self.assertIn("nomplofin", erreurs)
        self.assertIn("avant toute écriture", erreurs)


if __name__ == "__main__":
    unittest.main()
