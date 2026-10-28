# -*- coding: utf-8 -*-
"""Orchestration du mode DIAGNOSTIC (phase 1).

Étapes, toutes en lecture seule sur les données existantes :
1. inventaire et analyse des noms de PDF du dossier ;
2. description des trois couches INTERPLO (champs, effectifs, géométrie) ;
3. contrôle de présence des routes des PDF dans le référentiel ;
4. écriture d'une NOUVELLE table de diagnostic dans la géodatabase de sortie.
"""

from __future__ import annotations

import datetime
from typing import Dict, List, Optional

from . import nommage, referentiel, sorties
from .controles import normaliser_route, variantes_route


class Journal(object):
    """Journal minimal ; la toolbox fournit une version branchée sur arcpy."""

    def __init__(self) -> None:
        self.lignes: List[str] = []

    def info(self, texte: str) -> None:
        self.lignes.append("INFO " + texte)

    def avertissement(self, texte: str) -> None:
        self.lignes.append("AVERT " + texte)

    def erreur(self, texte: str) -> None:
        self.lignes.append("ERREUR " + texte)


def controle_route(route: Optional[str], comptes: Optional[Dict[str, int]]):
    """Renvoie (statut, nombre d'entités) pour une route.

    statut : EXACTE, VARIANTE:<code>, ABSENTE ou NON_CONTROLEE.
    Une VARIANTE n'est jamais considérée comme une correspondance validée.
    """
    if comptes is None or not route:
        return "NON_CONTROLEE", None
    r = normaliser_route(route)
    if r in comptes:
        return "EXACTE", comptes[r]
    for v in variantes_route(r)[1:]:
        if v in comptes:
            return "VARIANTE:{0}".format(v), comptes[v]
    return "ABSENTE", 0


def appliquer_controles_routes(infos: List[nommage.InfoPDF],
                               comptes_troncons: Optional[Dict[str, int]],
                               comptes_interplo: Optional[Dict[str, int]]) -> List[Dict[str, object]]:
    """Ajoute le contrôle de route à chaque PDF et renvoie les lignes de sortie."""
    lignes = []
    for info in infos:
        if info.type_pdf == nommage.TYPE_SECTION:
            statut, nb = controle_route(info.route, comptes_troncons)
            source = "tronçons locaux"
        elif info.type_pdf == nommage.TYPE_BRETELLE:
            statut, nb = controle_route(info.route, comptes_interplo)
            source = "INTERPLO d'origine"
        else:
            statut, nb = "NON_CONTROLEE", None
            source = None
        if statut == "ABSENTE":
            info.ajouter_message(nommage.NIVEAU_ERREUR,
                                 "Route {0} absente de la couche {1}".format(info.route, source))
        elif statut.startswith("VARIANTE"):
            info.ajouter_message(
                nommage.NIVEAU_AVERTISSEMENT,
                "Route {0} trouvée uniquement sous la forme {1} dans la couche {2} "
                "(codage à confirmer)".format(info.route, statut.split(":", 1)[1], source))
        ligne = info.en_dict()
        ligne["ROUTE_REF"] = statut
        ligne["NB_TRONCONS_ROUTE"] = nb
        lignes.append(ligne)
    return lignes


def executer_diagnostic(dossier_pdf: str, couche_troncons, couche_points, couche_interplo,
                        gdb_sortie: str, prefixe: str, journal: Journal,
                        ecrire_sortie: bool = True) -> Dict[str, object]:
    """Exécute le diagnostic complet. Renvoie un dictionnaire de résultats."""
    resultat: Dict[str, object] = {"table": None}

    # 1. PDF -------------------------------------------------------------
    journal.info("=== 1. Analyse des noms de PDF ===")
    journal.info("Dossier : {0}".format(dossier_pdf))
    infos = nommage.analyser_dossier(dossier_pdf)
    autres = nommage.lister_autres_fichiers(dossier_pdf)
    if autres:
        journal.info("{0} fichier(s) non PDF ignoré(s)".format(len(autres)))
    if not infos:
        journal.erreur("Aucun fichier PDF dans le dossier")
    resultat["infos"] = infos

    # 2. Couches ---------------------------------------------------------
    journal.info("=== 2. Structure des couches INTERPLO ===")
    d_tr = referentiel.decrire_couche(couche_troncons, "Couche 1 — tronçons locaux",
                                      referentiel.CHAMPS_TRONCONS,
                                      referentiel.EFFECTIF_TRONCONS,
                                      referentiel.TYPE_GEOM_TRONCONS)
    d_pt = referentiel.decrire_couche(couche_points, "Couche 2 — points PR",
                                      referentiel.CHAMPS_POINTS_PR,
                                      referentiel.EFFECTIF_POINTS_PR,
                                      referentiel.TYPE_GEOM_POINTS)
    d_ip = referentiel.decrire_couche(couche_interplo, "Couche 3 — INTERPLO d'origine",
                                      referentiel.CHAMPS_INTERPLO,
                                      referentiel.EFFECTIF_INTERPLO)
    for d in (d_tr, d_pt, d_ip):
        for ligne in d.lignes_rapport():
            if ligne.startswith("ERREUR"):
                journal.erreur(ligne)
            elif ligne.startswith("AVERTISSEMENT"):
                journal.avertissement(ligne)
            else:
                journal.info(ligne)
    journal.info("Rappel : les champs de la couche points PR ne sont pas encore "
                 "exploités ; merci de transmettre la liste ci-dessus.")
    resultat["couches"] = (d_tr, d_pt, d_ip)

    # 3. Routes ----------------------------------------------------------
    journal.info("=== 3. Présence des routes dans le référentiel ===")
    comptes_tr = comptes_ip = None
    champ_route_tr = d_tr.correspondance.get("ROUTE") if d_tr.existe else None
    champ_route_ip = d_ip.correspondance.get("route") if d_ip.existe else None
    if champ_route_tr:
        comptes_tr = referentiel.compter_par_route(couche_troncons, champ_route_tr)
    else:
        journal.avertissement("Champ ROUTE indisponible : routes des sections non contrôlées")
    if champ_route_ip:
        comptes_ip = referentiel.compter_par_route(couche_interplo, champ_route_ip)
    else:
        journal.avertissement("Champ route indisponible : routes des bretelles non contrôlées")
    lignes = appliquer_controles_routes(infos, comptes_tr, comptes_ip)
    maintenant = datetime.datetime.now()
    for ligne in lignes:
        ligne["DATE_TRAITEMENT"] = maintenant

    # Synthèse -----------------------------------------------------------
    s = nommage.synthese(infos)
    resultat["synthese"] = s
    journal.info("=== Synthèse ===")
    journal.info("PDF : {0} | sections : {1} | bretelles : {2} | non reconnus : {3}".format(
        s["TOTAL"], s[nommage.TYPE_SECTION], s[nommage.TYPE_BRETELLE], s[nommage.TYPE_NON_RECONNU]))
    journal.info("Amiantés (A) : {0} | non amiantés (NA) : {1} | changements de côté : {2}".format(
        s["AMIANTE"], s["NON_AMIANTE"], s["CHGT_COTE"]))
    journal.info("Diagnostic : OK {0} | avertissements {1} | erreurs {2}".format(
        s[nommage.NIVEAU_OK], s[nommage.NIVEAU_AVERTISSEMENT], s[nommage.NIVEAU_ERREUR]))
    for info in infos:
        if info.niveau == nommage.NIVEAU_ERREUR:
            journal.avertissement("{0} : {1}".format(info.nom_fichier, " | ".join(info.messages)))

    # 4. Sortie ----------------------------------------------------------
    if ecrire_sortie:
        import arcpy

        table = sorties.nom_sortie_unique(gdb_sortie, prefixe, "DIAG_PDF", arcpy.Exists,
                                          maintenant)
        sorties.creer_table(table, sorties.CHAMPS_DIAGNOSTIC_PDF)
        n = sorties.inserer_lignes(table, sorties.CHAMPS_DIAGNOSTIC_PDF, lignes)
        journal.info("Table de diagnostic créée : {0} ({1} lignes)".format(table, n))
        resultat["table"] = table
    resultat["lignes"] = lignes
    return resultat
