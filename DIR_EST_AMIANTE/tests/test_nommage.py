# -*- coding: utf-8 -*-
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from amiante_core import nommage as n  # noqa: E402


class TestSection(unittest.TestCase):
    def test_section_simple(self):
        i = n.analyser_nom_pdf("2023_NA_39_N0005_PR109500_PR110000_I.pdf")
        self.assertEqual(i.type_pdf, n.TYPE_SECTION)
        self.assertEqual(i.annee, 2023)
        self.assertEqual(i.statut, "NA")
        self.assertEqual(i.amiante, "NON")
        self.assertEqual(i.departement, "39")
        self.assertEqual(i.route, "N0005")
        self.assertEqual((i.pr_debut, i.abs_debut), (109, 500))
        self.assertEqual((i.pr_fin, i.abs_fin), (110, 0))
        self.assertEqual((i.cote_debut, i.cote_fin), ("I", "I"))
        self.assertFalse(i.changement_cote)
        self.assertEqual(i.niveau, n.NIVEAU_OK)

    def test_changement_cote(self):
        i = n.analyser_nom_pdf("2017_A_88_N0059_PR021500_G_PR025000_I.pdf")
        self.assertEqual(i.type_pdf, n.TYPE_SECTION)
        self.assertEqual(i.amiante, "OUI")
        self.assertEqual((i.pr_debut, i.abs_debut), (21, 500))
        self.assertEqual((i.pr_fin, i.abs_fin), (25, 0))
        self.assertEqual((i.cote_debut, i.cote_fin), ("G", "I"))
        self.assertTrue(i.changement_cote)
        self.assertEqual(i.niveau, n.NIVEAU_AVERTISSEMENT)

    def test_u_equivalent_i(self):
        i = n.analyser_nom_pdf("2020_A_54_N0004_PR010000_I_PR011000_U.pdf")
        self.assertEqual(i.cote_fin, "U")
        self.assertEqual(i.cote_fin_controle, "I")
        self.assertFalse(i.changement_cote)
        self.assertEqual(i.niveau, n.NIVEAU_OK)

    def test_pr_sur_5_chiffres(self):
        i = n.analyser_nom_pdf("2021_A_57_N0057_PR45100_PR45500_D.pdf")
        self.assertEqual(i.type_pdf, n.TYPE_SECTION)
        self.assertEqual((i.pr_debut, i.abs_debut), (45, 100))
        self.assertEqual((i.pr_fin, i.abs_fin), (45, 500))
        self.assertEqual(i.niveau, n.NIVEAU_AVERTISSEMENT)

    def test_pr_identiques_erreur(self):
        i = n.analyser_nom_pdf("2021_A_57_N0057_PR045100_PR045100_D.pdf")
        self.assertEqual(i.niveau, n.NIVEAU_ERREUR)

    def test_pr_decroissant_avertissement(self):
        i = n.analyser_nom_pdf("2021_A_57_N0057_PR046000_PR045100_D.pdf")
        self.assertEqual(i.niveau, n.NIVEAU_AVERTISSEMENT)

    def test_casse_et_extension(self):
        i = n.analyser_nom_pdf("2023_na_39_n0005_pr109500_pr110000_i.PDF")
        self.assertEqual(i.type_pdf, n.TYPE_SECTION)
        self.assertEqual(i.route, "N0005")

    def test_dictionnaire(self):
        d = n.analyser_nom_pdf("2023_NA_39_N0005_PR109500_PR110000_I.pdf").en_dict()
        self.assertEqual(d["TYPE_PDF"], "SECTION")
        self.assertEqual(d["PR_DEBUT_TXT"], "109500")
        self.assertEqual(d["CHGT_COTE"], "NON")


class TestBretelle(unittest.TestCase):
    def test_bretelle(self):
        i = n.analyser_nom_pdf("2023_NA_54A933040_3.pdf")
        self.assertEqual(i.type_pdf, n.TYPE_BRETELLE)
        self.assertEqual(i.route, "54A933040")
        self.assertEqual(i.num_bretelle, 3)
        self.assertEqual(i.nomplodeb_attendu, "DB3")
        self.assertEqual(i.nomplofin_attendu, "FB3")
        self.assertEqual(i.departement, "54")
        self.assertEqual(i.niveau, n.NIVEAU_OK)

    def test_bretelle_zero_non_significatif(self):
        i = n.analyser_nom_pdf("2023_A_54A933040_03.pdf")
        self.assertEqual(i.nomplodeb_attendu, "DB3")
        self.assertEqual(i.niveau, n.NIVEAU_AVERTISSEMENT)


class TestNonReconnu(unittest.TestCase):
    def test_extension(self):
        i = n.analyser_nom_pdf("2023_NA_54A933040_3.docx")
        self.assertEqual(i.type_pdf, n.TYPE_NON_RECONNU)
        self.assertEqual(i.niveau, n.NIVEAU_ERREUR)

    def test_statut_inconnu(self):
        i = n.analyser_nom_pdf("2023_X_39_N0005_PR109500_PR110000_I.pdf")
        self.assertEqual(i.type_pdf, n.TYPE_NON_RECONNU)

    def test_prefixe_seul(self):
        i = n.analyser_nom_pdf("2023_A_rapport final (1).pdf")
        self.assertEqual(i.type_pdf, n.TYPE_NON_RECONNU)
        self.assertEqual(i.statut, "A")
        self.assertEqual(i.niveau, n.NIVEAU_ERREUR)

    def test_cote_invalide(self):
        i = n.analyser_nom_pdf("2023_NA_39_N0005_PR109500_PR110000_X.pdf")
        self.assertEqual(i.type_pdf, n.TYPE_NON_RECONNU)

    def test_ne_leve_jamais(self):
        for nom in ("", ".pdf", "a.pdf", "____.pdf", "2023_A_.pdf"):
            n.analyser_nom_pdf(nom)


class TestDossier(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dossier)

    def _creer(self, noms):
        for nom in noms:
            open(os.path.join(self.dossier, nom), "w").close()

    def test_lot_fictif_39_sections_10_bretelles(self):
        sections = ["2023_NA_39_N0005_PR{0:03d}000_PR{0:03d}500_I.pdf".format(k)
                    for k in range(100, 139)]
        bretelles = ["2023_A_54A9330{0:02d}_{1}.pdf".format(k, k % 4 + 1) for k in range(10)]
        self._creer(sections + bretelles + ["notes.txt"])
        infos = n.analyser_dossier(self.dossier)
        s = n.synthese(infos)
        self.assertEqual(s["TOTAL"], 49)
        self.assertEqual(s[n.TYPE_SECTION], 39)
        self.assertEqual(s[n.TYPE_BRETELLE], 10)
        self.assertEqual(s[n.TYPE_NON_RECONNU], 0)
        self.assertEqual(n.lister_autres_fichiers(self.dossier), ["notes.txt"])

    def test_doublons_statuts_contradictoires(self):
        self._creer(["2019_A_39_N0005_PR109500_PR110000_I.pdf",
                     "2023_NA_39_N0005_PR109500_PR110000_U.pdf"])
        infos = n.analyser_dossier(self.dossier)
        for i in infos:
            self.assertEqual(i.niveau, n.NIVEAU_AVERTISSEMENT)
            self.assertIn("contradictoires", " ".join(i.messages))

    def test_dossier_absent(self):
        with self.assertRaises(IOError):
            n.analyser_dossier(os.path.join(self.dossier, "absent"))


if __name__ == "__main__":
    unittest.main()
