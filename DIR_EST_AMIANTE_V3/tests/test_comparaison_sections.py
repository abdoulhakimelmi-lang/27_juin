# -*- coding: utf-8 -*-
"""Comparaison des sections avec l'historique — données fictives, sans arcpy."""
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(ICI))

from amiante_core_v3 import comparaison_sections as cs  # noqa: E402

LIGNE = [[(0.0, 0.0), (100.0, 0.0), (100.0, 50.0)]]
NOM = "2023_NA_70_N0101_PR010300_PR011500_I.pdf"


def nouveau(nom=NOM, ids=("101", "102"), parties=LIGNE, long_ref=150.0, statut="CANDIDAT_A_VALIDER"):
    return {"nom_pdf": nom, "statut": statut, "ids": list(ids), "long_ref": long_ref,
            "long_geom": 150.0 if parties else None, "parties": parties}


def histo(nom=NOM, ids=("101", "102"), parties=LIGNE, long_ref=150.0, couche="V6A"):
    return {"nom_pdf": nom, "couche": couche, "ids": list(ids), "long_ref": long_ref,
            "long_geom": 150.0, "parties": parties}


class TestOutils(unittest.TestCase):
    def test_lire_ids(self):
        self.assertEqual(cs.lire_ids("9837,10230"), ["9837", "10230"])
        self.assertEqual(cs.lire_ids(" 1; 2 ,3 "), ["1", "2", "3"])
        self.assertEqual(cs.lire_ids(None), [])

    def test_cle_u_egal_i(self):
        self.assertEqual(cs.cle_pdf("2022_NA_70_N0057_PR045100_PR045500_U.pdf"),
                         cs.cle_pdf("2022_NA_70_N0057_PR045100_PR045500_I.pdf"))
        self.assertNotEqual(cs.cle_pdf("2022_NA_70_N0057_PR045100_PR045500_I.pdf"),
                            cs.cle_pdf("2023_NA_70_N0057_PR045100_PR045500_I.pdf"))

    def test_comparer_ids(self):
        self.assertEqual(cs.comparer_ids(["1", "2"], ["1", "2"]), cs.IDS_IDENTIQUES)
        self.assertEqual(cs.comparer_ids(["1", "2"], ["2", "1"]), cs.IDS_ORDRE)
        self.assertEqual(cs.comparer_ids(["1", "2"], ["1", "3"]), cs.IDS_DIFFERENTS)

    def test_sens(self):
        inverse = [list(reversed(LIGNE[0]))]
        self.assertEqual(cs.sens(LIGNE, LIGNE), "MEME_SENS")
        self.assertEqual(cs.sens(LIGNE, inverse), "INVERSE")


class TestComparer(unittest.TestCase):
    def un(self, n, h):
        return cs.comparer([n], [h])[0]

    def test_identique(self):
        l = self.un(nouveau(), histo())
        self.assertEqual((l["RESULTAT"], l["DIST_MAX_M"], l["SENS"], l["CORRESPONDANCE_NOM"]),
                         (cs.R_IDENTIQUE, 0.0, "MEME_SENS", "IDENTIQUE"))

    def test_renommage_u_i_apparie_et_signale(self):
        l = self.un(nouveau(nom="2022_NA_70_N0057_PR045100_PR045500_I.pdf"),
                    histo(nom="2022_NA_70_N0057_PR045100_PR045500_U.pdf", couche="V6C"))
        self.assertEqual((l["RESULTAT"], l["CORRESPONDANCE_NOM"]), (cs.R_IDENTIQUE, "RENOMME"))
        self.assertIn("_U.pdf", l["MESSAGES"])

    def test_hausdorff_nul_mais_sens_inverse(self):
        l = self.un(nouveau(), histo(parties=[list(reversed(LIGNE[0]))]))
        self.assertEqual(l["DIST_MAX_M"], 0.0)
        self.assertEqual(l["RESULTAT"], cs.R_SENS)

    def test_ids_differents_ou_ordre(self):
        self.assertEqual(self.un(nouveau(), histo(ids=("101", "999")))["RESULTAT"], cs.R_IDS)
        self.assertEqual(self.un(nouveau(), histo(ids=("102", "101")))["RESULTAT"], cs.R_ORDRE)

    def test_ecart_geometrie_et_longueur(self):
        decale = [[(x, y + 0.5) for x, y in LIGNE[0]]]
        self.assertEqual(self.un(nouveau(), histo(parties=decale))["RESULTAT"], cs.R_GEOMETRIE)
        l = self.un(nouveau(long_ref=150.0), histo(long_ref=149.5))
        self.assertEqual((l["RESULTAT"], l["ECART_LONG_REF_M"]), (cs.R_LONGUEUR, 0.5))

    def test_non_reconstruit_et_absences(self):
        lignes = cs.comparer(
            [nouveau(statut="PARCOURS_AMBIGU", ids=(), parties=None),
             nouveau(nom="2023_NA_70_N0101_PR010100_PR010400_I.pdf")],
            [histo(), histo(nom="2019_A_70_N0101_PR001000_PR002000_I.pdf")])
        res = {(l.get("NOM_PDF") or l.get("NOM_PDF_HISTO")): l["RESULTAT"] for l in lignes}
        self.assertEqual(res[NOM], cs.R_NON_RECONSTRUIT)
        self.assertEqual(res["2023_NA_70_N0101_PR010100_PR010400_I.pdf"], cs.R_ABSENT_HISTO)
        self.assertEqual(res["2019_A_70_N0101_PR001000_PR002000_I.pdf"], cs.R_ABSENT_NOUVEAU)

    def test_doublon_historique(self):
        lignes = cs.comparer([nouveau()], [histo(couche="V6A"), histo(couche="V7B")])
        self.assertEqual(lignes[0]["RESULTAT"], cs.R_DOUBLON)
        self.assertIn("V7B", lignes[0]["MESSAGES"])


if __name__ == "__main__":
    unittest.main()
