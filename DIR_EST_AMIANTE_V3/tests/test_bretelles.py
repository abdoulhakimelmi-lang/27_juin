# -*- coding: utf-8 -*-
"""Moteur de correspondance des bretelles — données fictives, sans arcpy."""
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
sys.path.insert(0, os.path.dirname(ICI))

from faux_arcpy import FauxPolyligne  # noqa: E402
from amiante_core_v3 import nommage  # noqa: E402
from amiante_core_v3 import reconstruction_bretelles as rb  # noqa: E402

CHAMPS_IP = {"objetid": "objetid", "route": "route", "nomplodeb": "nomplodeb", "nomplofin": "nomplofin"}
CHAMPS_LOCAL = {"ID_INTERPLO": "ID_INTERPLO", "LONG_REF_M": "LONG_REF_M", "ROUTE": "ROUTE",
                "DEPARTEMENT": "DEPARTEMENT", "COTE": "COTE", "LONG_GEOM_M": "LONG_GEOM_M"}

GEOM_500 = FauxPolyligne([[(0.0, 0.0), (300.0, 0.0), (300.0, 200.0)]])  # 500 m


def ip(objetid, route, deb, fin):
    return {"objetid": objetid, "route": route, "nomplodeb": deb, "nomplofin": fin}


def loc(ident, geom=GEOM_500, long_ref=495.0, route="54A933040", dep="54", long_geom=500.0):
    return {"ID_INTERPLO": ident, "LONG_REF_M": long_ref, "ROUTE": route, "DEPARTEMENT": dep,
            "COTE": "D", "LONG_GEOM_M": long_geom, "SHAPE@": geom}


def resoudre(nom, lignes_ip, lignes_local):
    return rb.resoudre_bretelle(nommage.analyser_nom_pdf(nom),
                                rb.IndexOrigine(lignes_ip, CHAMPS_IP),
                                rb.IndexLocal(lignes_local, CHAMPS_LOCAL))


BASE_IP = [ip(1001, "54A933040", "DB1", "FB1"), ip(1002, "54A933040", "DB2", "FB2"),
           ip(1003, "54A933040", "DB3", "FB3"), ip(2001, "57A111111", "DB3", "FB3")]


class TestCasNominal(unittest.TestCase):
    def test_correspondance_unique(self):
        r = resoudre("2023_NA_54A933040_3.pdf", BASE_IP, [loc("1001"), loc("1003")])
        self.assertEqual(r.controle, rb.CANDIDAT)
        self.assertEqual(r.objetid, "1003")
        self.assertEqual(r.id_interplo, "1003")
        self.assertEqual((r.nb_corr_origine, r.nb_corr_local), (1, 1))
        self.assertIs(r.geom, GEOM_500)
        self.assertEqual(r.long_geom, 500.0)
        self.assertEqual(r.long_ref, 495.0)
        self.assertEqual(r.ecart_m, 5.0)
        self.assertAlmostEqual(r.ecart_pct, 1.01, places=2)
        self.assertEqual(r.avertissements, [])
        d = r.en_dict()
        self.assertEqual([d[k] for k in ("NOM_PDF", "ANNEE", "STATUT_AM", "ROUTE", "DEPARTEMENT",
                                         "NUM_BRET", "ID_INTERPLO", "CONTROLE")],
                         ["2023_NA_54A933040_3.pdf", 2023, "NA", "54A933040", "54", 3, "1003",
                          "CANDIDAT_A_VALIDER"])

    def test_types_identifiants_differents(self):
        # objetid entier côté INTERPLO, ID_INTERPLO réel ou texte côté local
        for ident_local in (1003.0, " 1003 ", "1003"):
            r = resoudre("2023_NA_54A933040_3.pdf", BASE_IP, [loc(ident_local)])
            self.assertEqual(r.controle, rb.CANDIDAT, ident_local)

    def test_casse_et_espaces_interplo(self):
        r = resoudre("2023_NA_54A933040_3.pdf", [ip(7, " 54a933040 ", "db3 ", "Fb3")], [loc(7)])
        self.assertEqual(r.controle, rb.CANDIDAT)

    def test_route_locale_differente_signalee(self):
        r = resoudre("2023_NA_54A933040_3.pdf", BASE_IP, [loc("1003", route="N0004", dep="57")])
        self.assertEqual(r.controle, rb.CANDIDAT)
        texte = " ".join(r.avertissements)
        self.assertIn("ROUTE locale N0004", texte)
        self.assertIn("DEPARTEMENT local 57", texte)

    def test_long_ref_vide(self):
        r = resoudre("2023_NA_54A933040_3.pdf", BASE_IP, [loc("1003", long_ref=None)])
        self.assertEqual(r.controle, rb.CANDIDAT)
        self.assertIsNone(r.ecart_m)
        self.assertIn("LONG_REF_M vide", " ".join(r.avertissements))

    def test_long_geom_stockee_differente(self):
        r = resoudre("2023_NA_54A933040_3.pdf", BASE_IP, [loc("1003", long_geom=480.0)])
        self.assertIn("LONG_GEOM_M stocké", " ".join(r.avertissements))

    def test_multipartie(self):
        g = FauxPolyligne([[(0, 0), (10, 0)], [(20, 0), (30, 0)]])
        r = resoudre("2023_NA_54A933040_3.pdf", BASE_IP, [loc("1003", geom=g)])
        self.assertEqual(r.controle, rb.CANDIDAT)
        self.assertEqual(r.nb_parties, 2)


class TestAnomalies(unittest.TestCase):
    def verifier(self, r, code):
        self.assertEqual(r.controle, code)
        self.assertIsNone(r.geom)
        self.assertFalse(r.est_candidat)
        self.assertTrue(r.anomalies[0].startswith(code))

    def test_code_echangeur_absent(self):
        self.verifier(resoudre("2023_NA_54A999999_3.pdf", BASE_IP, [loc("1003")]), rb.A_CODE_ECHANGEUR)

    def test_numero_zero(self):
        self.verifier(resoudre("2023_NA_54A933040_0.pdf", BASE_IP, [loc("1003")]), rb.A_NUMERO)

    def test_db_absent(self):
        r = resoudre("2023_NA_54A933040_7.pdf", BASE_IP, [loc("1003")])
        self.verifier(r, rb.A_AUCUNE_ORIGINE)
        self.assertIn("DB7 absent de nomplodeb", r.anomalies[0])
        self.assertIn("DB1/FB1", r.anomalies[0])

    def test_db_fb_jamais_ensemble(self):
        lignes = [ip(1, "54A933040", "DB3", "FB4"), ip(2, "54A933040", "DB4", "FB3")]
        r = resoudre("2023_NA_54A933040_3.pdf", lignes, [loc(1), loc(2)])
        self.verifier(r, rb.A_AUCUNE_ORIGINE)
        self.assertIn("jamais sur la même ligne", r.anomalies[0])

    def test_autre_ecriture_non_acceptee(self):
        r = resoudre("2023_NA_54A933040_3.pdf", [ip(5, "54A933040", "DB03", "FB 3")], [loc(5)])
        self.verifier(r, rb.A_AUCUNE_ORIGINE)
        self.assertIn("autre écriture", r.anomalies[0])

    def test_ambiguite_interplo(self):
        lignes = BASE_IP + [ip(1004, "54A933040", "DB3", "FB3")]
        r = resoudre("2023_NA_54A933040_3.pdf", lignes, [loc("1003"), loc("1004")])
        self.verifier(r, rb.A_AMBIGU_ORIGINE)
        self.assertIn("1003, 1004", r.anomalies[0])

    def test_objetid_vide(self):
        self.verifier(resoudre("2023_NA_54A933040_3.pdf", [ip(None, "54A933040", "DB3", "FB3")], []),
                      rb.A_OBJETID_VIDE)

    def test_objetid_en_double_dans_interplo(self):
        lignes = BASE_IP + [ip(1003, "57A000000", "DB9", "FB9")]
        self.verifier(resoudre("2023_NA_54A933040_3.pdf", lignes, [loc("1003")]), rb.A_OBJETID_DOUBLON)

    def test_absent_local(self):
        self.verifier(resoudre("2023_NA_54A933040_3.pdf", BASE_IP, [loc("1001")]), rb.A_ABSENT_LOCAL)

    def test_ambigu_local(self):
        r = resoudre("2023_NA_54A933040_3.pdf", BASE_IP, [loc("1003"), loc(1003)])
        self.verifier(r, rb.A_AMBIGU_LOCAL)
        self.assertEqual(r.nb_corr_local, 2)

    def test_geometrie_vide(self):
        for g in (None, FauxPolyligne([]), FauxPolyligne([[(5, 5), (5, 5)]])):
            self.verifier(resoudre("2023_NA_54A933040_3.pdf", BASE_IP, [loc("1003", geom=g)]),
                          rb.A_GEOM_VIDE)

    def test_nom_non_bretelle(self):
        info = nommage.analyser_nom_pdf("2023_NA_39_N0005_PR109500_PR110000_I.pdf")
        r = rb.resoudre_bretelle(info, rb.IndexOrigine(BASE_IP, CHAMPS_IP),
                                 rb.IndexLocal([], CHAMPS_LOCAL))
        self.verifier(r, rb.A_NOM_PDF)


class TestLot(unittest.TestCase):
    def test_sections_ignorees_et_doublons(self):
        noms = ["2023_NA_39_N0005_PR109500_PR110000_I.pdf", "2019_A_54A933040_3.pdf",
                "2023_NA_54A933040_3.pdf", "2023_NA_54A933040_2.pdf"]
        infos = [nommage.analyser_nom_pdf(n) for n in noms]
        res = rb.resoudre_toutes(infos, rb.IndexOrigine(BASE_IP, CHAMPS_IP),
                                 rb.IndexLocal([loc("1003")], CHAMPS_LOCAL))
        self.assertEqual(len(res), 3)
        self.assertEqual([r.controle for r in res], [rb.CANDIDAT, rb.CANDIDAT, rb.A_ABSENT_LOCAL])
        self.assertIn("même ID_INTERPLO", " ".join(res[0].avertissements))
        s = rb.synthese(res)
        self.assertEqual(s, {"TOTAL": 3, rb.CANDIDAT: 2, rb.A_ABSENT_LOCAL: 1})

    def test_doublons_index(self):
        o = rb.IndexOrigine(BASE_IP + [ip(1001, "X", "DB1", "FB1")], CHAMPS_IP)
        self.assertEqual(o.doublons_objetid(), {"1001": 2})
        l_ = rb.IndexLocal([loc(1), loc("1"), loc(2)], CHAMPS_LOCAL)
        self.assertEqual(l_.doublons(), {"1": 2})


if __name__ == "__main__":
    unittest.main()
