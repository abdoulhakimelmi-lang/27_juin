# -*- coding: utf-8 -*-
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
sys.path.insert(0, os.path.dirname(ICI))

from faux_arcpy import FauxPolyligne  # noqa: E402
from amiante_core_v3 import comparaison as cp  # noqa: E402
from amiante_core_v3 import geometrie as g  # noqa: E402
from amiante_core_v3.controles import (departements_concordants, forme_souple_nomplo,  # noqa: E402
                                    normaliser_identifiant, verifier_code_echangeur)

LIGNE = [[(0.0, 0.0), (100.0, 0.0), (100.0, 50.0)]]


class TestGeometrie(unittest.TestCase):
    def test_acces_objet(self):
        p = FauxPolyligne(LIGNE)
        self.assertEqual(g.coordonnees(p), LIGNE)
        self.assertEqual(g.longueur(p), 150.0)
        self.assertEqual(g.nombre_parties(p), 1)
        self.assertFalse(g.geometrie_vide(p))
        self.assertTrue(g.geometrie_vide(None))
        self.assertTrue(g.geometrie_vide(FauxPolyligne([])))

    def test_hausdorff(self):
        self.assertEqual(g.distance_hausdorff(LIGNE, LIGNE), 0.0)
        inverse = [list(reversed(LIGNE[0]))]
        self.assertAlmostEqual(g.distance_hausdorff(LIGNE, inverse), 0.0, places=9)
        decale = [[(x, y + 0.5) for x, y in LIGNE[0]]]
        self.assertAlmostEqual(g.distance_hausdorff(LIGNE, decale), 0.5)
        # sommets intermédiaires supplémentaires sur le même tracé : distance nulle
        densifie = [[(0.0, 0.0), (50.0, 0.0), (100.0, 0.0), (100.0, 50.0)]]
        self.assertAlmostEqual(g.distance_hausdorff(LIGNE, densifie), 0.0)

    def test_hausdorff_ecart_en_milieu_de_segment(self):
        bosse = [[(0.0, 0.0), (50.0, 3.0), (100.0, 0.0), (100.0, 50.0)]]
        self.assertAlmostEqual(g.distance_hausdorff(LIGNE, bosse), 3.0, places=6)

    def test_hausdorff_tracé_plus_court(self):
        court = [[(0.0, 0.0), (100.0, 0.0)]]
        self.assertAlmostEqual(g.distance_hausdorff(LIGNE, court), 50.0)

    def test_sens_et_emprise(self):
        self.assertTrue(g.meme_sens(LIGNE, LIGNE, 0.01))
        self.assertFalse(g.meme_sens(LIGNE, [list(reversed(LIGNE[0]))], 0.01))
        self.assertEqual(g.emprise(LIGNE), (0.0, 0.0, 100.0, 50.0))
        self.assertTrue(g.emprises_proches((0, 0, 1, 1), (50, 0, 60, 1), 100))
        self.assertFalse(g.emprises_proches((0, 0, 1, 1), (500, 0, 600, 1), 100))


class TestControlesPhase2(unittest.TestCase):
    def test_identifiants(self):
        for v in (1234, 1234.0, "1234", " 1234 ", "1234.0"):
            self.assertEqual(normaliser_identifiant(v), "1234", v)
        self.assertIsNone(normaliser_identifiant(None))
        self.assertIsNone(normaliser_identifiant("  "))
        self.assertEqual(normaliser_identifiant("ab12"), "AB12")
        self.assertNotEqual(normaliser_identifiant("01234"), normaliser_identifiant("1234.5"))

    def test_formes_souples(self):
        self.assertEqual(forme_souple_nomplo("DB 03"), "DB3")
        self.assertEqual(forme_souple_nomplo("db3"), "DB3")
        self.assertEqual(forme_souple_nomplo("FB_12"), "FB12")

    def test_code_echangeur(self):
        self.assertEqual(verifier_code_echangeur("54A933040"), [])
        self.assertTrue(verifier_code_echangeur("ABCD1234"))
        self.assertTrue(verifier_code_echangeur(None))

    def test_departements(self):
        self.assertTrue(departements_concordants("54", 54))
        self.assertTrue(departements_concordants("054", "54"))
        self.assertFalse(departements_concordants("57", "54"))
        self.assertIsNone(departements_concordants(None, "54"))


def element(ident, parties, nom=None, oid=None):
    return {"id": ident, "nom_pdf": nom, "oid": oid, "parties": parties,
            "longueur": g.longueur_coordonnees(parties)}


class TestComparaison(unittest.TestCase):
    def test_par_identifiant(self):
        b = [[(1000.0, 0.0), (1200.0, 0.0)]]
        c = [[(2000.0, 0.0), (2100.0, 0.0)]]
        nouveaux = [element("1", LIGNE, "a.pdf"), element("2", b, "b.pdf"), element("3", c, "c.pdf")]
        histo = [element("1", [list(reversed(LIGNE[0]))]),            # même tracé, sens inverse
                 element("2", [[(1000.0, 0.0), (1200.0, 2.0)]]),       # tracé différent
                 element("4", c)]                                      # identifiant différent
        lignes = {l.get("ID_INTERPLO"): l for l in cp.comparer(nouveaux, histo)}
        self.assertEqual(lignes["1"]["RESULTAT"], cp.IDENTIQUE)
        self.assertEqual(lignes["1"]["MEME_SENS"], "NON")
        self.assertEqual(lignes["2"]["RESULTAT"], cp.TRACE_DIFFERENT)
        self.assertEqual(lignes["3"]["RESULTAT"], cp.ABSENT_HISTO)
        self.assertEqual(lignes["4"]["RESULTAT"], cp.ABSENT_NOUVEAU)
        self.assertEqual(cp.synthese(lignes.values()),
                         {cp.IDENTIQUE: 1, cp.TRACE_DIFFERENT: 1, cp.ABSENT_HISTO: 1, cp.ABSENT_NOUVEAU: 1})

    def test_longueur_differente_trace_proche(self):
        # tracé historique prolongé de 5 mm : distance 5 mm (< 1 cm), longueur +5 mm
        h = [[(0.0, 0.0), (100.0, 0.0), (100.0, 50.005)]]
        l_ = cp.comparer([element("1", LIGNE)], [element("1", h)])[0]
        self.assertEqual(l_["RESULTAT"], cp.IDENTIQUE)
        l_ = cp.comparer([element("1", LIGNE)], [element("1", h)], tol_long=0.001)[0]
        self.assertEqual(l_["RESULTAT"], cp.LONGUEUR_DIFFERENTE)

    def test_doublon_historique(self):
        l_ = cp.comparer([element("1", LIGNE)], [element("1", LIGNE), element("1", LIGNE)])[0]
        self.assertEqual(l_["RESULTAT"], cp.DOUBLON_HISTO)

    def test_mode_geometrique(self):
        b = [[(1000.0, 0.0), (1200.0, 0.0)]]
        nouveaux = [element("1", LIGNE, "a.pdf"), element("2", b, "b.pdf"),
                    element("3", [[(9000.0, 0.0), (9100.0, 0.0)]], "c.pdf")]
        histo = [element(None, b, oid=11), element(None, LIGNE, oid=10),
                 element(None, [[(5000.0, 0.0), (5100.0, 0.0)]], oid=12)]
        lignes = cp.comparer(nouveaux, histo, par_identifiant=False)
        self.assertEqual(lignes[0]["ID_HISTO"], "OID 10")
        self.assertEqual(lignes[0]["RESULTAT"], cp.IDENTIQUE)
        self.assertEqual(lignes[1]["ID_HISTO"], "OID 11")
        self.assertEqual(lignes[2]["RESULTAT"], cp.SANS_CORRESPONDANT)
        self.assertEqual(lignes[3], {"ID_HISTO": "OID 12", "RESULTAT": cp.ABSENT_NOUVEAU,
                                     "LONG_HISTO_M": 100.0})


if __name__ == "__main__":
    unittest.main()
