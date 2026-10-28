# -*- coding: utf-8 -*-
import datetime
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from amiante_core_v2 import controles as c  # noqa: E402
from amiante_core_v2 import referentiel as r  # noqa: E402
from amiante_core_v2 import sorties as s  # noqa: E402
from amiante_core_v2.diagnostic import controle_route  # noqa: E402


class TestControles(unittest.TestCase):
    def test_cotes(self):
        self.assertEqual(c.compatibilite_cote("I", "I"), c.COTE_IDENTIQUE)
        self.assertEqual(c.compatibilite_cote("U", "I"), c.COTE_IDENTIQUE)
        self.assertEqual(c.compatibilite_cote("I", "U"), c.COTE_IDENTIQUE)
        self.assertEqual(c.compatibilite_cote("U", "D"), c.COTE_TRONCON_COMMUN)
        self.assertEqual(c.compatibilite_cote("I", "D"), c.COTE_TRONCON_COMMUN)
        self.assertEqual(c.compatibilite_cote("D", "I"), c.COTE_INCOMPATIBLE)
        self.assertEqual(c.compatibilite_cote("G", "D"), c.COTE_INCOMPATIBLE)
        self.assertEqual(c.compatibilite_cote(None, "D"), c.COTE_INDETERMINE)

    def test_longueurs_distinctes(self):
        e = c.ecart_longueurs(500.0, 512.5)
        self.assertEqual(e["ECART_M"], 12.5)
        self.assertEqual(e["ECART_PCT"], 2.5)
        self.assertIsNone(c.ecart_longueurs(None, 3.0)["ECART_M"])
        self.assertIsNone(c.ecart_longueurs(0, 3.0)["ECART_PCT"])

    def test_unicite_et_ambiguite(self):
        self.assertEqual(c.verifier_unicite([1, 2, 2, 3, 3, 3]), {2: 2, 3: 3})
        self.assertEqual(c.statut_candidats(0), "AUCUN")
        self.assertEqual(c.statut_candidats(1), "UNIQUE")
        self.assertEqual(c.statut_candidats(2), "AMBIGU")

    def test_variantes_route(self):
        self.assertEqual(c.variantes_route("N0005"), ["N0005", "N5"])
        self.assertEqual(c.variantes_route(" n5 "), ["N5", "N0005"])
        self.assertEqual(c.variantes_route("54A933040"), ["54A933040"])

    def test_controle_route(self):
        comptes = {"N0005": 12, "N59": 3}
        self.assertEqual(controle_route("N0005", comptes), ("EXACTE", 12))
        self.assertEqual(controle_route("N0059", comptes), ("VARIANTE:N59", 3))
        self.assertEqual(controle_route("N0004", comptes), ("ABSENTE", 0))
        self.assertEqual(controle_route("N0004", None), ("NON_CONTROLEE", None))


class TestReferentiel(unittest.TestCase):
    def test_resolution_insensible_casse(self):
        res = r.resoudre_champs(["OBJECTID", "Route", "NOMPLODEB"], r.CHAMPS_INTERPLO)
        self.assertEqual(res["route"], "Route")
        self.assertEqual(res["nomplodeb"], "NOMPLODEB")
        self.assertEqual(r.champs_manquants(["Route", "NOMPLODEB"], r.CHAMPS_INTERPLO),
                         ["objetid", "nomplofin"])


class TestSorties(unittest.TestCase):
    def test_prefixe(self):
        self.assertEqual(s.valider_prefixe("AMIANTE_ENVOI2"), [])
        self.assertTrue(s.valider_prefixe(""))
        self.assertTrue(s.valider_prefixe("2AMIANTE"))
        self.assertTrue(s.valider_prefixe("AMIANTÉ"))
        self.assertTrue(s.valider_prefixe("A B"))
        self.assertTrue(s.valider_prefixe("A" * 31))

    def test_nom_unique_ne_reprend_jamais_existant(self):
        t = datetime.datetime(2026, 10, 28, 9, 30, 0)
        existants = {os.path.join("x.gdb", "P_DIAG_PDF_20261028_093000"),
                     os.path.join("x.gdb", "P_DIAG_PDF_20261028_093000_2")}
        nom = s.nom_sortie_unique("x.gdb", "P", "DIAG_PDF", existants.__contains__, t)
        self.assertEqual(nom, os.path.join("x.gdb", "P_DIAG_PDF_20261028_093000_3"))

    def test_tronquer(self):
        champs = (("A", "TEXT", 5), ("B", "LONG", 0))
        self.assertEqual(s.preparer_ligne({"A": "abcdefgh", "B": 3}, champs), ["ab...", 3])

    def test_csv_sans_ecrasement(self):
        d = tempfile.mkdtemp()
        try:
            chemin = os.path.join(d, "diag.csv")
            self.assertEqual(s.ecrire_csv(chemin, s.CHAMPS_DIAGNOSTIC_PDF, [{"NOM_PDF": "a.pdf"}]), 1)
            with self.assertRaises(RuntimeError):
                s.ecrire_csv(chemin, s.CHAMPS_DIAGNOSTIC_PDF, [])
        finally:
            shutil.rmtree(d)

    def test_noms_champs_valides(self):
        for nom, _t, _l in s.CHAMPS_DIAGNOSTIC_PDF:
            self.assertLessEqual(len(nom), 31)
            self.assertRegex(nom, r"^[A-Z][A-Z0-9_]*$")


if __name__ == "__main__":
    unittest.main()
