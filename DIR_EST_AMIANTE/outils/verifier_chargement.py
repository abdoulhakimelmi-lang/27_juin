# -*- coding: utf-8 -*-
"""Vérifie le chargement de DIR_EST_AMIANTE_V2.pyt (à lancer dans un Notebook
ArcGIS Pro ou dans la fenêtre Python). Lecture seule : aucune donnée SIG
n'est lue ni écrite.

Usage dans un Notebook :
    %run "<dossier>\\outils\\verifier_chargement.py" "<dossier>\\DIR_EST_AMIANTE_V2.pyt"
Sans argument, le .pyt situé dans le dossier parent est utilisé.
"""

import importlib.machinery
import importlib.util
import os
import sys
import traceback


def verifier(chemin_pyt):
    chemin_pyt = os.path.abspath(chemin_pyt)
    print("Fichier .pyt :", chemin_pyt, "(existe)" if os.path.isfile(chemin_pyt) else "(INTROUVABLE)")
    print("Python :", sys.version.split()[0])
    autres = sorted(k for k in sys.modules if k.split(".")[0] in ("amiante_core", "amiante_core_v2"))
    print("Modules amiante déjà en mémoire :", ", ".join(autres) or "aucun")

    # 1. Import du .pyt comme le fait ArcGIS Pro
    try:
        loader = importlib.machinery.SourceFileLoader("verif_dir_est_amiante_v2", chemin_pyt)
        spec = importlib.util.spec_from_loader(loader.name, loader)
        pyt = importlib.util.module_from_spec(spec)
        loader.exec_module(pyt)
        outil = pyt.Toolbox().tools[0]()
        print("OK  .pyt importé ; outil :", outil.label, "; paramètres :", len(outil.getParameterInfo()))
    except Exception:
        print("ERREUR à l'import du .pyt :")
        traceback.print_exc()
        return

    # 2. Chargement du moteur
    try:
        m = pyt.moteur(recharger=True)
        print("OK  moteur", m.paquet.__version__, "chargé depuis", m.dossier)
        for nom in pyt.SOUS_MODULES:
            print("    {0:<26} {1}".format(nom, getattr(m, nom).__file__))
    except Exception:
        print("ERREUR au chargement du moteur :")
        traceback.print_exc()
        return

    # 3. Chargement par ArcGIS Pro lui-même
    try:
        import arcpy

        arcpy.ImportToolbox(chemin_pyt)
        print("OK  arcpy.ImportToolbox a accepté la boîte à outils")
    except Exception:
        print("ERREUR arcpy.ImportToolbox :")
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cible = sys.argv[1]
    else:
        cible = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "DIR_EST_AMIANTE_V2.pyt")
    verifier(cible)
