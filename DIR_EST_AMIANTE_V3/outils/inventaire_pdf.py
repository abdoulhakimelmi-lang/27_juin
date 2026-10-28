# -*- coding: utf-8 -*-
"""Inventaire d'un dossier de PDF Amiante, SANS ArcGIS.

Utile pour inventorier un nouveau lot (ex. envoi_1) avant de lancer la
boîte à outils. Écrit un CSV (séparateur ';') qui n'écrase jamais un
fichier existant.

Usage :
    python outils/inventaire_pdf.py <dossier_pdf> [<fichier_csv>]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from amiante_core_v3 import diagnostic, nommage, sorties  # noqa: E402


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    dossier = argv[1]
    infos = nommage.analyser_dossier(dossier)
    lignes = diagnostic.appliquer_controles_routes(infos, None, None)
    s = nommage.synthese(infos)
    print("PDF : {0} | sections : {1} | bretelles : {2} | non reconnus : {3}".format(
        s["TOTAL"], s[nommage.TYPE_SECTION], s[nommage.TYPE_BRETELLE], s[nommage.TYPE_NON_RECONNU]))
    print("A : {0} | NA : {1} | changements de côté : {2}".format(
        s["AMIANTE"], s["NON_AMIANTE"], s["CHGT_COTE"]))
    print("OK : {0} | avertissements : {1} | erreurs : {2}".format(
        s[nommage.NIVEAU_OK], s[nommage.NIVEAU_AVERTISSEMENT], s[nommage.NIVEAU_ERREUR]))
    for info in infos:
        if info.niveau != nommage.NIVEAU_OK:
            print("  {0} [{1}] {2}".format(info.nom_fichier, info.niveau, " | ".join(info.messages)))
    if len(argv) > 2:
        n = sorties.ecrire_csv(argv[2], sorties.CHAMPS_DIAGNOSTIC_PDF, lignes)
        print("CSV écrit : {0} ({1} lignes)".format(argv[2], n))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
