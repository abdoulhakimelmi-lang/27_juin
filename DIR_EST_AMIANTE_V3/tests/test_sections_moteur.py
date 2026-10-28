# -*- coding: utf-8 -*-
"""Moteur de reconstruction des sections (phase 3) — données fictives, sans arcpy."""
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
sys.path.insert(0, os.path.dirname(ICI))

import donnees_sections as ds  # noqa: E402
from faux_arcpy import FauxPolyligne  # noqa: E402
from amiante_core_v3 import geometrie, nommage  # noqa: E402
from amiante_core_v3 import reconstruction_sections as rs  # noqa: E402
from amiante_core_v3.localisation import localiser  # noqa: E402
from amiante_core_v3.parcours import Parametres  # noqa: E402
from amiante_core_v3.reseau import (MOTIF_CUMULS, MOTIF_REFERENCEMENT, IndexPointsPR, Reseau,  # noqa: E402
                                    normaliser_departement)

CHAMPS = {c: c for c in ds.CHAMPS}
CHAMPS_PTS = {c: c for c in ("ID_INTERPLO", "TYPE_POINT", "X_GEOM", "Y_GEOM", "CUMUL")}


def decouper(geom, d0, d1):
    return geom.segmentAlongLine(d0, d1, False)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lignes = ds.troncons()
        cls.reseau = Reseau.depuis_lignes(cls.lignes, CHAMPS)
        cls.points = IndexPointsPR(ds.points_pr(cls.lignes), CHAMPS_PTS)

    def section(self, nom, p=None, points="defaut", reseau=None):
        info = nommage.analyser_nom_pdf(nom)
        self.assertEqual(info.type_pdf, nommage.TYPE_SECTION, nom)
        return rs.reconstruire_section(info, reseau or self.reseau,
                                       self.points if points == "defaut" else points,
                                       p or Parametres(), decouper)


class TestChargement(Base):
    def test_exclusions_v6a(self):
        motifs = dict((str(i), m) for i, m in self.reseau.ecartes)
        self.assertEqual(motifs["9001"], MOTIF_CUMULS)
        self.assertEqual(motifs["9002"], MOTIF_REFERENCEMENT)
        self.assertNotIn("9001", self.reseau.par_id)

    def test_departement_normalise(self):
        self.assertEqual(normaliser_departement("070"), "70")
        self.assertEqual(normaliser_departement(70.0), "70")
        self.assertEqual(normaliser_departement("2a"), "2A")
        self.assertEqual(len(self.reseau.troncons("N0102", "70")), 3)


class TestLocalisation(Base):
    def test_regles_v6a(self):
        t = self.reseau.troncons("N0101", "70")
        pos = localiser(t, 10, 300, 0.001, 0.001)
        self.assertEqual([(p.cote, p.cumul, p.motif) for p in pos], [("I", 10300.0, "INTERIEUR")])
        # borne : fin de I1 et début de I2 au même cumul -> une seule position
        pos = localiser(t, 10, 600, 0.001, 0.001)
        self.assertEqual([(p.cumul) for p in pos], [10600.0])
        # PR situé dans un tronçon qui commence au PR précédent : non localisé (aucune invention)
        self.assertEqual(localiser(t, 11, 100, 0.001, 0.001), [])


class TestCasNominaux(Base):
    def test_section_multitroncons(self):
        r = self.section("2023_NA_70_N0101_PR010300_PR011500_I.pdf")
        self.assertEqual(r.statut, rs.CANDIDAT)
        self.assertEqual(r.ids, ["101", "102", "103"])
        self.assertEqual(r.methode, rs.M_STRICT)
        self.assertAlmostEqual(r.long_ref, 1200.0)
        # I3 : 300 m de référencement sur 800 -> 3/8 de 1 600 m = 600 m géométriques
        self.assertAlmostEqual(r.long_geom, 300 + 600 + 600)
        self.assertEqual(r.sommets[0], (300.0, 0.0))
        self.assertEqual(r.sommets[-1], (1800.0, 0.0))
        self.assertEqual(len(r.sommets), 4)          # sommets de jonction non dupliqués
        self.assertEqual(r.ecart_racc_max, 0.0)
        d = r.en_dict()
        self.assertEqual((d["IDS_INTERPLO"], d["NB_TRONCONS"], d["PR_DEBUT"], d["PR_FIN"]),
                         ("101,102,103", 3, "PR10+300", "PR11+500"))
        self.assertEqual(d["ECART_M"], 300.0)

    def test_section_dans_un_seul_troncon(self):
        r = self.section("2023_NA_70_N0101_PR010100_PR010400_I.pdf")
        self.assertEqual((r.statut, r.ids), (rs.CANDIDAT, ["101"]))
        self.assertEqual(r.sommets, [(100.0, 0.0), (400.0, 0.0)])
        self.assertAlmostEqual(r.long_ref, 300.0)

    def test_u_equivaut_a_i_et_valeur_d_origine_conservee(self):
        r = self.section("2023_NA_70_N0101_PR010100_PR010400_U.pdf")
        self.assertEqual(r.statut, rs.CANDIDAT)
        d = r.en_dict()
        self.assertEqual((d["COTE_DEBUT"], d["COTE_FIN"], d["COTE_FIN_CTRL"]), ("U", "U", "I"))

    def test_portion_commune_df_ff_cas_v6c(self):
        r = self.section("2022_NA_70_N0102_PR001100_PR001800_U.pdf")
        self.assertEqual(r.statut, rs.CANDIDAT, r.observations)
        self.assertEqual(r.ids, ["202", "203"])
        self.assertEqual(r.methode, rs.M_COMMUNE)
        self.assertEqual([e.appartenance for e in r.parcours.etapes], ["PORTION_COMMUNE", "STRICT"])
        self.assertAlmostEqual(r.long_ref, 700.0)

    def test_portion_commune_refusee_sans_df_ff(self):
        lignes = ds.troncons()
        for l in lignes:
            if l["ID_INTERPLO"] == 202:
                l["LOGIQUE_DEB"] = "SC"
        reseau = Reseau.depuis_lignes(lignes, CHAMPS)
        r = self.section("2022_NA_70_N0102_PR001100_PR001800_I.pdf", reseau=reseau)
        self.assertEqual(r.statut, rs.S_PR_DEBUT)   # le D sans DF/FF n'est pas admis
        self.assertIsNone(r.sommets)

    def test_changement_cote_avec_ecart_de_cumul_cas_a(self):
        r = self.section("2017_A_88_N0103_PR021500_G_PR023500_I.pdf")
        self.assertEqual(r.statut, rs.CANDIDAT, r.observations)
        self.assertEqual(r.ids, ["301", "302", "303"])
        self.assertEqual(r.methode, rs.M_CHANGEMENT)
        e = r.parcours.etapes[2]
        self.assertEqual((e.type_raccord, e.ecart_cumul, e.distance_racc), ("CHANGEMENT_COTE", 44.0, 0.0))
        self.assertEqual(r.ecart_cumul_max, 44.0)
        self.assertIn("écart de cumul 44.000 m", " ".join(r.alertes))
        self.assertNotIn("TRANSITION_DOUTEUSE", " ".join(r.alertes))
        # LONG_REF = somme des portions : 500 + 1000 + (2500 - 2044)
        self.assertAlmostEqual(r.long_ref, 1956.0)
        detail = r.lignes_detail()
        self.assertEqual([l["TYPE_RACCORDEMENT"] for l in detail],
                         ["DEBUT_PARCOURS", "MEME_COTE", "CHANGEMENT_COTE"])
        self.assertEqual(detail[2]["ECART_CUMUL_M"], 44.0)

    def test_seuil_d_alerte_n_exclut_pas(self):
        r = self.section("2017_A_88_N0103_PR021500_G_PR023500_I.pdf",
                         p=Parametres(seuil_alerte_ecart_cumul=30))
        self.assertEqual(r.statut, rs.CANDIDAT)
        self.assertIn("TRANSITION_DOUTEUSE", " ".join(r.alertes))

    def test_plusieurs_changements_de_cote_cas_b(self):
        r = self.section("2017_A_88_N0104_PR030100_D_PR031800_I.pdf")
        self.assertEqual(r.statut, rs.CANDIDAT, r.observations)
        self.assertEqual(r.ids, ["401", "402", "403", "404"])
        self.assertEqual(r.parcours.nb_changements_cote, 3)
        self.assertEqual(r.ecart_cumul_max, 0.0)
        self.assertAlmostEqual(r.long_ref, 1700.0)

    def test_positions_multiples_avec_parcours_unique(self):
        lignes = [ds.tr(1, "N0120", "54", "I", 20, 0, 21, 0, 0, 1000, ds.ligne_droite(0, 1000, 40000)),
                  ds.tr(2, "N0120", "54", "I", 21, 0, 22, 0, 1000, 2000, ds.ligne_droite(1000, 2000, 40000)),
                  ds.tr(3, "N0120", "54", "I", 21, 0, 22, 0, 7000, 8000, ds.ligne_droite(0, 1000, 40500))]
        r = self.section("2020_A_54_N0120_PR020100_PR021300_I.pdf",
                         reseau=Reseau.depuis_lignes(lignes, CHAMPS), points=None)
        self.assertEqual((r.statut, r.ids, r.nb_pos_fin), (rs.CANDIDAT, ["1", "2"], 2))
        self.assertIn("2 positions possibles pour la fin", " ".join(r.alertes))
        self.assertIn("orientation non contrôlée", " ".join(r.alertes))


class TestAnomalies(Base):
    def verifier_echec(self, r, statut):
        self.assertEqual(r.statut, statut, r.observations)
        self.assertIsNone(r.sommets)
        self.assertFalse(r.est_candidat)
        self.assertTrue(r.observations)

    def test_route_absente(self):
        self.verifier_echec(self.section("2023_NA_70_N0999_PR010100_PR010400_I.pdf"), rs.S_ROUTE)

    def test_pr_introuvables(self):
        self.verifier_echec(self.section("2023_NA_70_N0101_PR015000_PR016000_I.pdf"), rs.S_PR_DEBUT)
        self.verifier_echec(self.section("2023_NA_70_N0101_PR010100_PR015000_I.pdf"), rs.S_PR_FIN)
        # côté G inexistant sur la route
        self.verifier_echec(self.section("2023_NA_70_N0101_PR010100_PR010400_G.pdf"), rs.S_PR_DEBUT)

    def test_ambiguite_jamais_resolue_arbitrairement(self):
        r = self.section("2023_NA_39_N0105_PR005100_PR005800_I.pdf")
        self.verifier_echec(r, rs.S_AMBIGU)
        self.assertEqual(len(r.variantes), 2)
        detail = r.lignes_detail()
        self.assertEqual({l["STATUT_PARCOURS"] for l in detail}, {"VARIANTE_AMBIGUE"})
        self.assertEqual({l["VARIANTE"] for l in detail}, {1, 2})
        self.assertEqual(r.en_dict()["NB_PARCOURS"], 2)

    def test_parcours_strict_n_arrete_pas_la_recherche(self):
        r = self.section("2023_NA_39_N0108_PR008100_PR008700_I.pdf")
        self.verifier_echec(r, rs.S_AMBIGU)
        self.assertIn("1 strict(s), 1 avec portion commune", r.observations[0])
        self.assertEqual(sorted(v.ids for v in r.variantes), [["801", "802"], ["801", "803", "802"]])

    def test_rupture_geometrique(self):
        r = self.section("2023_NA_39_N0106_PR005100_PR005800_I.pdf")
        self.verifier_echec(r, rs.S_INTROUVABLE)
        self.assertIn("impasse après ID 601", r.observations[0])

    def test_changement_de_cote_sans_df_ff(self):
        r = self.section("2023_NA_39_N0107_PR007100_G_PR007800_I.pdf")
        self.verifier_echec(r, rs.S_INTROUVABLE)
        self.assertIn("sans DF/FF", r.observations[0])

    def test_cumuls_non_continus_meme_cote(self):
        lignes = ds.troncons()
        for l in lignes:
            if l["ID_INTERPLO"] == 102:
                l["CUMUL_DEBUT"], l["CUMUL_FIN"] = 10650, 11200
        r = self.section("2023_NA_70_N0101_PR010300_PR011500_I.pdf", reseau=Reseau.depuis_lignes(lignes, CHAMPS))
        self.verifier_echec(r, rs.S_INTROUVABLE)
        self.assertIn("cumuls non continus", r.observations[0])

    def test_geometrie_fermee(self):
        r = self.section("2023_NA_39_N0109_PR009100_PR009500_I.pdf")
        self.verifier_echec(r, rs.S_GEOMETRIE)
        self.assertIn("FERMEE", r.observations[0])
        self.assertEqual({l["STATUT_PARCOURS"] for l in r.lignes_detail()}, {"RETENU_PUIS_REJETE"})

    def test_geometrie_multipartie(self):
        r = self.section("2023_NA_39_N0110_PR010100_PR010800_I.pdf")
        self.verifier_echec(r, rs.S_GEOMETRIE)
        self.assertIn("MULTIPARTIE", r.observations[0])

    def test_sens_inverse_detecte_par_les_points_pr(self):
        r = self.section("2023_NA_39_N0111_PR011100_PR011500_I.pdf")
        self.verifier_echec(r, rs.S_GEOMETRIE)
        self.assertIn("INVERSE", r.observations[0])

    def test_recherche_incomplete(self):
        for p in (Parametres(max_parcours=1), Parametres(max_etats=1)):
            r = self.section("2023_NA_39_N0105_PR005100_PR005800_I.pdf", p=p)
            self.verifier_echec(r, rs.S_INCOMPLETE)
        r = self.section("2023_NA_70_N0101_PR010300_PR011500_I.pdf", p=Parametres(max_profondeur=2))
        self.verifier_echec(r, rs.S_INCOMPLETE)
        self.assertIn("plus de 2 tronçons", r.observations[0])

    def test_pr_decroissant_signale(self):
        r = self.section("2023_NA_70_N0101_PR011500_PR010300_I.pdf")
        self.assertNotEqual(r.statut, rs.CANDIDAT)
        self.assertIn("PR de début supérieur", " ".join(r.observations))


class TestGeometrieV3(unittest.TestCase):
    def test_decoupe_identique_a_segment_along_line_simule(self):
        g = FauxPolyligne([[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]])
        self.assertEqual(geometrie.coordonnees(g.segmentAlongLine(5, 15, False)),
                         [geometrie.decouper_coordonnees(g.parties[0], 5, 15)])

    def test_assemblage_refuse_multipartie(self):
        with self.assertRaises(ValueError):
            geometrie.assembler([[[(0, 0), (1, 0)], [(2, 0), (3, 0)]]])

    def test_assemblage_sans_segment_artificiel(self):
        pts = geometrie.assembler([[[(0, 0), (1, 0)]], [[(1, 0), (2, 0)]]])
        self.assertEqual(pts, [(0, 0), (1, 0), (2, 0)])


if __name__ == "__main__":
    unittest.main()
