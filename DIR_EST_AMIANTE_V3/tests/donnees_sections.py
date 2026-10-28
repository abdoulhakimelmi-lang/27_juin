# -*- coding: utf-8 -*-
"""Réseaux FICTIFS reproduisant la structure des cas réels diagnostiqués.

Aucun identifiant, cumul ou coordonnée réels : les valeurs sont inventées.
Chaque tronçon est numérisé dans le sens des cumuls croissants, sauf
mention contraire.

Routes fictives :
- N0101 / 70 : côté I sur 3 tronçons (section classique, section dans un
  seul tronçon, découpe proportionnelle avec écart réf./géom.) ;
- N0102 / 70 : trou du réseau I comblé par une portion commune D portant DF
  (cas V6C), département écrit « 070 » sur un tronçon ;
- N0103 / 88 : G -> I avec écart de cumul +44 m et FF (cas A) ;
- N0104 / 88 : D -> I -> D -> I, cumuls continus, DF/FF (cas B) ;
- N0105 / 39 : deux tronçons I parallèles -> ambiguïté ;
- N0106 / 39 : rupture géométrique de 5 m ;
- N0107 / 39 : changement de côté sans DF/FF ;
- N0108 / 39 : alternative stricte + portion commune -> ambiguïté ;
- N0109 / 39 : géométrie fermée sur le parcours ;
- N0110 / 39 : géométrie multipartie sur le parcours ;
- N0111 / 39 : tronçon numérisé à l'envers (selon les points PR).
"""
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

from faux_arcpy import FauxPolyligne  # noqa: E402

CHAMPS = ("ID_INTERPLO", "ROUTE", "DEPARTEMENT", "COTE", "PR_DEBUT", "PR_FIN", "ABS_DEBUT", "ABS_FIN",
          "CUMUL_DEBUT", "CUMUL_FIN", "LOGIQUE_DEB", "LOGIQUE_FIN", "LOGIQUE_2", "LOGIQUE_3")


def tr(ident, route, dep, cote, pd, ad, pf, af, cd, cf, parties, logiques=("SC", "SC", "SC", "SC")):
    ligne = dict(zip(CHAMPS, (ident, route, dep, cote, pd, pf, ad, af, cd, cf) + tuple(logiques)))
    ligne["SHAPE@"] = FauxPolyligne(parties)
    return ligne


def ligne_droite(x0, x1, y=0.0):
    return [[(float(x0), y), (float(x1), y)]]


def troncons():
    t = []
    # N0101 / 70 : I1 [PR10+0 -> PR10+600], I2 [PR10+600 -> PR11+200], I3 [PR11+200 -> PR12+0]
    t.append(tr(101, "N0101", "70", "I", 10, 0, 10, 600, 10000, 10600, ligne_droite(0, 600)))
    t.append(tr(102, "N0101", "70", "I", 10, 600, 11, 200, 10600, 11200, ligne_droite(600, 1200)))
    # I3 : longueur géométrique 1 600 m pour 800 m de référencement (découpe proportionnelle)
    t.append(tr(103, "N0101", "70", "I", 11, 200, 12, 0, 11200, 12000, ligne_droite(1200, 2800)))

    # N0102 / 70 : Ia (I), Dc (D, DF), Ib (I)
    t.append(tr(201, "N0102", "070", "I", 0, 0, 1, 0, 0, 1000, ligne_droite(0, 1000, 5000)))
    t.append(tr(202, "N0102", "70", "D", 1, 0, 1, 500, 1000, 1500, ligne_droite(1000, 1500, 5000),
                ("DF", "SC", "SC", "SC")))
    t.append(tr(203, "N0102", "70", "I", 1, 500, 2, 500, 1500, 2500, ligne_droite(1500, 2500, 5000)))

    # N0103 / 88 : G1, G2 (FF), I1 avec écart de cumul +44 m, continuité géométrique parfaite
    t.append(tr(301, "N0103", "88", "G", 21, 0, 22, 0, 0, 1000, ligne_droite(0, 1000, 9000)))
    t.append(tr(302, "N0103", "88", "G", 22, 0, 23, 0, 1000, 2000, ligne_droite(1000, 2000, 9000),
                ("SC", "FF", "SC", "SC")))
    t.append(tr(303, "N0103", "88", "I", 23, 44, 24, 0, 2044, 3000, ligne_droite(2000, 2956, 9000)))

    # N0104 / 88 : D1 -> I1 -> D2 -> I2, DF/FF aux transitions, cumuls continus
    t.append(tr(401, "N0104", "88", "D", 30, 0, 30, 500, 0, 500, ligne_droite(0, 500, 12000),
                ("SC", "DF", "SC", "SC")))
    t.append(tr(402, "N0104", "88", "I", 30, 500, 31, 0, 500, 1000, ligne_droite(500, 1000, 12000),
                ("FF", "SC", "SC", "SC")))
    t.append(tr(403, "N0104", "88", "D", 31, 0, 31, 500, 1000, 1500, ligne_droite(1000, 1500, 12000),
                ("DF", "FF", "SC", "SC")))
    t.append(tr(404, "N0104", "88", "I", 31, 500, 32, 0, 1500, 2000, ligne_droite(1500, 2000, 12000),
                ("FF", "SC", "SC", "SC")))

    # N0105 / 39 : A puis deux tronçons I parallèles (même géométrie, cumuls identiques)
    t.append(tr(501, "N0105", "39", "I", 5, 0, 5, 500, 0, 500, ligne_droite(0, 500, 15000)))
    t.append(tr(502, "N0105", "39", "I", 5, 500, 6, 0, 500, 1000, ligne_droite(500, 1000, 15000)))
    t.append(tr(503, "N0105", "39", "I", 5, 500, 6, 0, 500, 1000, ligne_droite(500, 1000, 15000)))

    # N0106 / 39 : rupture géométrique de 5 m entre deux tronçons I aux cumuls continus
    t.append(tr(601, "N0106", "39", "I", 5, 0, 5, 500, 0, 500, ligne_droite(0, 500, 18000)))
    t.append(tr(602, "N0106", "39", "I", 5, 500, 6, 0, 500, 1000, ligne_droite(505, 1005, 18000)))

    # N0107 / 39 : G -> I sans DF/FF
    t.append(tr(701, "N0107", "39", "G", 7, 0, 7, 500, 0, 500, ligne_droite(0, 500, 21000)))
    t.append(tr(702, "N0107", "39", "I", 7, 500, 8, 0, 500, 1000, ligne_droite(500, 1000, 21000)))

    # N0108 / 39 : I1 -> I2 direct, et I1 -> Dc (DF) -> I2 par un tracé parallèle
    t.append(tr(801, "N0108", "39", "I", 8, 0, 8, 400, 0, 400, ligne_droite(0, 400, 24000)))
    t.append(tr(802, "N0108", "39", "I", 8, 400, 9, 0, 400, 1000, ligne_droite(400, 1000, 24000)))
    t.append(tr(803, "N0108", "39", "D", 8, 400, 8, 400, 400, 400.5,
                [[(400.0, 24000.0), (400.5, 24000.0)]], ("DF", "FF", "SC", "SC")))

    # N0109 / 39 : tronçon I fermé (extrémités confondues)
    t.append(tr(901, "N0109", "39", "I", 9, 0, 10, 0, 0, 1000,
                [[(0.0, 27000.0), (300.0, 27000.0), (300.0, 27300.0), (0.0, 27000.0)]]))

    # N0110 / 39 : tronçon I multipartie
    t.append(tr(1001, "N0110", "39", "I", 10, 0, 11, 0, 0, 1000,
                [[(0.0, 30000.0), (400.0, 30000.0)], [(400.0, 30000.0), (1000.0, 30000.0)]]))

    # N0111 / 39 : tronçon I numérisé de FIN vers DEBUT (points PR inversés)
    t.append(tr(1101, "N0111", "39", "I", 11, 0, 12, 0, 0, 1000, ligne_droite(1000, 0, 33000)))

    # Tronçons à écarter au chargement (règles V6A)
    t.append(tr(9001, "N0101", "70", "I", 12, 0, 12, 0, 12000, 12000, ligne_droite(5000, 5100)))
    t.append(tr(9002, "N0101", "70", "I", None, 0, 12, 0, 12000, 12100, ligne_droite(6000, 6100)))
    return t


def points_pr(lignes_troncons, inverser=(1101,)):
    """Points DEBUT / FIN (X_GEOM, Y_GEOM, CUMUL) tirés des géométries ; pour
    les identifiants de `inverser`, les points reflètent un tronçon numérisé à
    l'envers."""
    pts = []
    for l in lignes_troncons:
        parties = l["SHAPE@"].parties
        if not parties:
            continue
        premier, dernier = parties[0][0], parties[-1][-1]
        if l["ID_INTERPLO"] in inverser:
            premier, dernier = dernier, premier
        pts.append({"ID_INTERPLO": l["ID_INTERPLO"], "TYPE_POINT": "DEBUT", "X_GEOM": premier[0],
                    "Y_GEOM": premier[1], "CUMUL": l["CUMUL_DEBUT"]})
        pts.append({"ID_INTERPLO": l["ID_INTERPLO"], "TYPE_POINT": "FIN", "X_GEOM": dernier[0],
                    "Y_GEOM": dernier[1], "CUMUL": l["CUMUL_FIN"]})
    return pts
