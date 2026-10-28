# -*- coding: utf-8 -*-
"""Comparaison des bretelles reconstruites avec une couche historique
(ex. AMIANTE_10_BRETELLES_V8D_TEST).

Trois critères, jamais le seul nombre d'entités :
- identifiants INTERPLO (présents des deux côtés, sans doublon) ;
- longueurs géométriques (écart en mètres) ;
- tracés (distance de Hausdorff densifiée, indépendante du sens).

Si la couche historique n'a pas de champ identifiant, chaque nouvelle
géométrie est appariée au tracé historique le plus proche.

La couche historique est lue en lecture seule.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from . import geometrie, referentiel, sorties
from .controles import normaliser_identifiant

TOLERANCE_TRACE_M = 0.01
TOLERANCE_LONGUEUR_M = 0.01
MARGE_RECHERCHE_M = 100.0

IDENTIQUE = "IDENTIQUE"
TRACE_DIFFERENT = "TRACE_DIFFERENT"
LONGUEUR_DIFFERENTE = "LONGUEUR_DIFFERENTE"
ABSENT_NOUVEAU = "ABSENT_DU_NOUVEAU_RESULTAT"
ABSENT_HISTO = "ABSENT_DE_L_HISTORIQUE"
DOUBLON_HISTO = "ID_EN_DOUBLE_DANS_HISTORIQUE"
SANS_CORRESPONDANT = "AUCUN_TRACE_HISTORIQUE_PROCHE"


def _verdict(dist: float, ecart_long: float, tol_trace: float, tol_long: float) -> str:
    if dist > tol_trace:
        return TRACE_DIFFERENT
    if abs(ecart_long) > tol_long:
        return LONGUEUR_DIFFERENTE
    return IDENTIQUE


def _comparer_paire(n: Dict[str, object], h: Dict[str, object], tol_trace: float,
                    tol_long: float) -> Dict[str, object]:
    dist = geometrie.distance_hausdorff(n["parties"], h["parties"])
    ecart = n["longueur"] - h["longueur"]
    sens = geometrie.meme_sens(n["parties"], h["parties"], max(tol_trace, 0.001))
    return {
        "LONG_NOUVEAU_M": round(n["longueur"], 3),
        "LONG_HISTO_M": round(h["longueur"], 3),
        "ECART_LONG_M": round(ecart, 4),
        "DIST_MAX_M": round(dist, 4),
        "MEME_SENS": None if sens is None else ("OUI" if sens else "NON"),
        "RESULTAT": _verdict(dist, ecart, tol_trace, tol_long),
    }


def comparer(nouveaux: List[Dict[str, object]], historiques: List[Dict[str, object]],
             par_identifiant: bool = True, tol_trace: float = TOLERANCE_TRACE_M,
             tol_long: float = TOLERANCE_LONGUEUR_M) -> List[Dict[str, object]]:
    """Compare deux listes d'éléments {'id', 'nom_pdf', 'parties', 'longueur'}.

    Renvoie une ligne par identifiant (mode identifiant) ou par nouvelle
    géométrie (mode géométrique), plus les éléments historiques non appariés.
    """
    lignes: List[Dict[str, object]] = []
    if par_identifiant:
        histo_par_id: Dict[Optional[str], List[Dict[str, object]]] = {}
        for h in historiques:
            histo_par_id.setdefault(h["id"], []).append(h)
        nouveaux_par_id: Dict[Optional[str], Dict[str, object]] = {}
        for n in nouveaux:
            nouveaux_par_id.setdefault(n["id"], n)  # doublons de PDF déjà signalés ailleurs
        for ident in sorted(set(nouveaux_par_id) | set(histo_par_id), key=lambda x: str(x)):
            n = nouveaux_par_id.get(ident)
            hs = histo_par_id.get(ident, [])
            ligne: Dict[str, object] = {"ID_INTERPLO": ident, "ID_HISTO": ident,
                                        "NOM_PDF": n["nom_pdf"] if n else None}
            if n is None:
                ligne["RESULTAT"] = ABSENT_NOUVEAU
                ligne["LONG_HISTO_M"] = round(hs[0]["longueur"], 3)
            elif not hs:
                ligne["RESULTAT"] = ABSENT_HISTO
                ligne["LONG_NOUVEAU_M"] = round(n["longueur"], 3)
            else:
                ligne.update(_comparer_paire(n, hs[0], tol_trace, tol_long))
                if len(hs) > 1:
                    ligne["RESULTAT"] = DOUBLON_HISTO
                    ligne["MESSAGES"] = "{0} entités historiques avec cet identifiant".format(len(hs))
            lignes.append(ligne)
        return lignes

    # Mode géométrique : appariement au tracé historique le plus proche
    utilises = set()
    emprises_h = [geometrie.emprise(h["parties"]) for h in historiques]
    for n in nouveaux:
        e_n = geometrie.emprise(n["parties"])
        meilleur, meilleure_dist = None, float("inf")
        for k, h in enumerate(historiques):
            if not geometrie.emprises_proches(e_n, emprises_h[k], MARGE_RECHERCHE_M):
                continue
            d = geometrie.distance_hausdorff(n["parties"], h["parties"])
            if d < meilleure_dist:
                meilleur, meilleure_dist = k, d
        ligne = {"ID_INTERPLO": n["id"], "NOM_PDF": n["nom_pdf"]}
        if meilleur is None:
            ligne["RESULTAT"] = SANS_CORRESPONDANT
            ligne["LONG_NOUVEAU_M"] = round(n["longueur"], 3)
        else:
            utilises.add(meilleur)
            ligne["ID_HISTO"] = "OID {0}".format(historiques[meilleur].get("oid"))
            ligne.update(_comparer_paire(n, historiques[meilleur], tol_trace, tol_long))
        lignes.append(ligne)
    for k, h in enumerate(historiques):
        if k not in utilises:
            lignes.append({"ID_HISTO": "OID {0}".format(h.get("oid")), "RESULTAT": ABSENT_NOUVEAU,
                           "LONG_HISTO_M": round(h["longueur"], 3)})
    return lignes


def synthese(lignes: List[Dict[str, object]]) -> Dict[str, int]:
    s: Dict[str, int] = {}
    for l in lignes:
        s[l["RESULTAT"]] = s.get(l["RESULTAT"], 0) + 1
    return s


# =========================================================================
# Exécution ArcGIS
# =========================================================================

def executer_comparaison(resultats, couche_histo, champ_id_histo: Optional[str], table_sortie: str,
                         journal, maintenant=None) -> Dict[str, object]:
    desc = referentiel.decrire_couche(couche_histo, "Couche historique", ())
    for ligne in desc.lignes_rapport():
        journal.info(ligne)
    if not desc.existe:
        journal.erreur("Couche historique introuvable : comparaison non réalisée")
        return {}

    champ = None
    if champ_id_histo:
        champ = referentiel.resoudre_champs(desc.noms_champs, [champ_id_histo])[champ_id_histo]
    if champ is None:
        champ = referentiel.resoudre_champs(desc.noms_champs, ["ID_INTERPLO"])["ID_INTERPLO"]
    par_id = champ is not None
    journal.info("Comparaison {0}".format(
        "par identifiant (champ {0})".format(champ) if par_id
        else "géométrique (aucun champ identifiant trouvé)"))

    epsg = referentiel.EPSG_SORTIE if desc.epsg else None
    if epsg is None:
        journal.avertissement("Référence spatiale historique inconnue : lecture sans projection")
    oid = "OID@"
    lignes_h = referentiel.lire_lignes(couche_histo, [oid] + ([champ] if champ else []),
                                       geometrie=True, epsg=epsg)
    historiques = []
    for l in lignes_h:
        g = l.get("SHAPE@")
        if geometrie.geometrie_vide(g):
            journal.avertissement("Entité historique OID {0} sans géométrie : ignorée".format(l.get(oid)))
            continue
        historiques.append({"id": normaliser_identifiant(l.get(champ)) if champ else None,
                            "oid": l.get(oid), "parties": geometrie.coordonnees(g),
                            "longueur": geometrie.longueur(g)})
    nouveaux = [{"id": r.id_interplo, "nom_pdf": r.info.nom_fichier,
                 "parties": geometrie.coordonnees(r.geom), "longueur": geometrie.longueur(r.geom)}
                for r in resultats if r.est_candidat]

    lignes = comparer(nouveaux, historiques, par_identifiant=par_id)
    s = synthese(lignes)
    journal.info("Historique : {0} entités | nouveaux candidats : {1}".format(len(historiques), len(nouveaux)))
    journal.info("Tolérances : tracé {0} m, longueur {1} m".format(TOLERANCE_TRACE_M, TOLERANCE_LONGUEUR_M))
    for l in lignes:
        texte = "{0} : {1} (écart longueur {2} m, distance max {3} m)".format(
            l.get("ID_INTERPLO") or l.get("ID_HISTO"), l["RESULTAT"],
            l.get("ECART_LONG_M"), l.get("DIST_MAX_M"))
        (journal.info if l["RESULTAT"] == IDENTIQUE else journal.avertissement)(texte)
    for code in sorted(s):
        journal.info("  {0} : {1}".format(code, s[code]))
    if s.get(IDENTIQUE, 0) == len(lignes) and lignes:
        journal.info("COMPARAISON : tous les identifiants, longueurs et tracés concordent.")
    else:
        journal.avertissement("COMPARAISON : des différences existent, voir la table de comparaison.")

    for l in lignes:
        l["DATE_TRAITEMENT"] = maintenant
    sorties.creer_table(table_sortie, sorties.CHAMPS_COMPARAISON)
    sorties.inserer_lignes(table_sortie, sorties.CHAMPS_COMPARAISON, lignes)
    journal.info("Table de comparaison créée : {0}".format(table_sortie))
    return {"table": table_sortie, "lignes": lignes, "synthese": s}
