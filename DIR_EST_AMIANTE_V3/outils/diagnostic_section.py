# -*- coding: utf-8 -*-
"""Diagnostic détaillé d'UNE section, en LECTURE SEULE (Notebook ArcGIS Pro).

Affiche, sans rien écrire : les tronçons de la route et du département, les
positions de début / fin, les départs possibles, tous les parcours
admissibles, les impasses avec le motif de refus de chaque voisin, puis le
statut final.

Usage dans un Notebook ArcGIS Pro :
    %run "<dossier>\\outils\\diagnostic_section.py" "<couche tronçons>" "<couche points PR>" "<nom du PDF>"

Exemple :
    %run "...\\outils\\diagnostic_section.py" "REF_INTERPLO_TRONCONS_V1_CORRIGE" "REF_INTERPLO_POINTS_PR_V1" "2022_NA_70_N0057_PR045100_PR045500_I.pdf"
"""

import importlib.util
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAQUET = "amiante_core_v3"


def charger():
    """Charge amiante_core_v3 par chemin explicite (même méthode que le .pyt)."""
    for nom in [n for n in sys.modules if n == PAQUET or n.startswith(PAQUET + ".")]:
        del sys.modules[nom]
    dossier = os.path.join(RACINE, PAQUET)
    spec = importlib.util.spec_from_file_location(PAQUET, os.path.join(dossier, "__init__.py"),
                                                  submodule_search_locations=[dossier])
    paquet = importlib.util.module_from_spec(spec)
    sys.modules[PAQUET] = paquet
    spec.loader.exec_module(paquet)
    return {n: importlib.import_module(PAQUET + "." + n)
            for n in ("nommage", "referentiel", "reseau", "localisation", "parcours", "reconstruction_sections")}


def main(couche_troncons, couche_points, nom_pdf):
    m = charger()
    nommage, referentiel, reseau_m = m["nommage"], m["referentiel"], m["reseau"]
    localisation, parcours_m, rs = m["localisation"], m["parcours"], m["reconstruction_sections"]

    info = nommage.analyser_nom_pdf(nom_pdf)
    print("PDF :", nom_pdf, "| type :", info.type_pdf, "|", " | ".join(info.messages))
    if info.type_pdf != nommage.TYPE_SECTION:
        return

    d_tr = referentiel.decrire_couche(couche_troncons, "Tronçons", reseau_m.CHAMPS_TRONCONS_SECTIONS)
    if d_tr.manquants:
        print("Champs absents :", d_tr.manquants)
        return
    lignes = referentiel.lire_lignes(couche_troncons, list(d_tr.correspondance.values()),
                                     geometrie=True, epsg=referentiel.EPSG_SORTIE)
    reseau = reseau_m.Reseau.depuis_lignes(lignes, d_tr.correspondance)
    points = None
    d_pt = referentiel.decrire_couche(couche_points, "Points PR", reseau_m.CHAMPS_POINTS_ORIENTATION)
    if d_pt.existe and not d_pt.manquants:
        corr = referentiel.resoudre_champs(d_pt.noms_champs, reseau_m.CHAMPS_POINTS_ORIENTATION
                                           + reseau_m.CHAMPS_POINTS_OPTIONNELS)
        points = reseau_m.IndexPointsPR(referentiel.lire_lignes(couche_points, [v for v in corr.values() if v]),
                                        corr)

    p = parcours_m.Parametres()
    troncons = reseau.troncons(info.route, info.departement)
    print("\nTronçons {0} / {1} : {2}".format(info.route, info.departement, len(troncons)))
    for t in sorted(troncons, key=lambda x: (x.cote, x.cd)):
        if t.pd in (info.pr_debut, info.pr_fin) or t.pf in (info.pr_debut, info.pr_fin):
            print("  ID {0:<8} {1} PR{2}+{3:g} -> PR{4}+{5:g} | cumuls {6:.3f} -> {7:.3f} | logiques {8} | "
                  "{9} partie(s){10}".format(t.id, t.cote, t.pd, t.ad, t.pf, t.af, t.cd, t.cf, "/".join(t.logiques),
                                             t.nb_parties, " | FERMEE" if t.ferme else ""))

    admis = parcours_m.Admissibilite(info.cote_debut_controle, info.cote_fin_controle)
    for etiquette, pr, absc in (("Début", info.pr_debut, info.abs_debut), ("Fin", info.pr_fin, info.abs_fin)):
        print("\n{0} PR{1}+{2:03d} — toutes positions (avant filtre des côtés) :".format(etiquette, pr, absc))
        for pos in localisation.localiser(troncons, pr, absc, p.tol_abs, p.tol_cumul):
            print("   ", pos)

    debuts = localisation.localiser(troncons, info.pr_debut, info.abs_debut, p.tol_abs, p.tol_cumul,
                                    admis.admis_au_debut)
    fins = localisation.localiser(troncons, info.pr_fin, info.abs_fin, p.tol_abs, p.tol_cumul,
                                  admis.admis_a_la_fin)
    rech = parcours_m.rechercher(troncons, debuts, fins, admis, p)
    print("\nDéparts :", [(pos.cote, pos.cumul, t.id) for pos, t in rech.departs])
    print("États explorés :", rech.nb_etats, "| incomplète :", rech.incomplete, rech.motif_incomplet)
    for k, pc in enumerate(rech.parcours, 1):
        print("Parcours {0} : {1}".format(k, pc.texte()))
        for e in pc.etapes:
            print("    ID {0:<8} {1} {2:<16} écart cumul {3} | distance {4} | {5}".format(
                e.troncon.id, e.troncon.cote, e.type_raccord, e.ecart_cumul, e.distance_racc,
                " ; ".join(e.alertes)))
    for ident, refus in rech.impasses:
        print("Impasse après ID {0} : {1}".format(ident, refus or "aucun voisin à moins de {0} m".format(p.tol_xy)))

    r = rs.reconstruire_section(info, reseau, points, p)
    print("\nSTATUT :", r.statut, "| méthode :", r.methode, "| IDS :", ",".join(r.ids))
    print("LONG_REF_M :", r.long_ref, "| LONG_GEOM_M :", r.long_geom)
    for o in r.observations:
        print("Observation :", o)
    for a in r.alertes:
        print("Alerte :", a)
    print("\nAucune donnée n'a été écrite.")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
    else:
        main(sys.argv[1], sys.argv[2], sys.argv[3])
