# -*- coding: utf-8 -*-
"""Comparaison technique des sections reconstruites avec les couches
historiques (V6A, V6C, V7B) — lecture seule.

Appariement par PDF sur une clé normalisée (année, statut, département,
route, PR, côtés avec U = I) : un PDF renommé de _U en _I reste apparié et
le renommage est signalé.

Pour chaque paire : listes ORDONNÉES d'ID_INTERPLO (champ texte
IDS_INTERPLO), nombre de tronçons, longueur de référencement, longueur
géométrique, distance de Hausdorff densifiée et sens de numérisation
(premier / dernier sommet : une distance de Hausdorff nulle ne prouve pas le
même sens).

Une concordance est une reproduction technique, pas une validation métier.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Tuple

from . import geometrie, nommage, referentiel, sorties
from .controles import normaliser_identifiant

CHAMPS_HISTO_REQUIS = ("NOM_PDF", "IDS_INTERPLO")
CHAMPS_HISTO_OPTIONNELS = ("LONG_REF_M", "LONG_GEOM_M")

TOLERANCE_TRACE_M = 0.01
TOLERANCE_LONGUEUR_M = 0.01
TOLERANCE_LONG_REF_M = 0.001
TOLERANCE_SENS_M = 0.01

IDS_IDENTIQUES = "IDS_IDENTIQUES"
IDS_ORDRE = "MEME_ENSEMBLE_ORDRE_DIFFERENT"
IDS_DIFFERENTS = "IDS_DIFFERENTS"

R_IDENTIQUE = "IDENTIQUE"
R_IDS = "IDS_DIFFERENTS"
R_ORDRE = "IDS_ORDRE_DIFFERENT"
R_SENS = "SENS_INVERSE"
R_SENS_INDETERMINE = "SENS_INDETERMINE"
R_GEOMETRIE = "ECART_GEOMETRIE"
R_LONGUEUR = "ECART_LONGUEUR"
R_NON_RECONSTRUIT = "NON_RECONSTRUIT"
R_ABSENT_HISTO = "ABSENT_HISTORIQUE"
R_ABSENT_NOUVEAU = "ABSENT_DU_LOT_ACTUEL"
R_DOUBLON = "DOUBLON_HISTORIQUE"

NOM_IDENTIQUE = "IDENTIQUE"
NOM_RENOMME = "RENOMME"


def lire_ids(texte) -> List[str]:
    """'9837,10230' / '9837; 10230' -> ['9837', '10230'] (ordre conservé)."""
    if texte is None:
        return []
    return [normaliser_identifiant(x) for x in re.split(r"[,;\s]+", str(texte).strip()) if x]


def cle_pdf(nom: Optional[str]):
    """Clé d'appariement d'un PDF de section (U = I sur les deux côtés)."""
    if not nom:
        return None
    info = nommage.analyser_nom_pdf(str(nom).strip())
    if info.type_pdf == nommage.TYPE_SECTION:
        return (info.annee, info.statut, info.cle_identite())
    return ("NOM", str(nom).strip().upper())


def comparer_ids(nouveaux: Sequence[str], historiques: Sequence[str]) -> str:
    if list(nouveaux) == list(historiques):
        return IDS_IDENTIQUES
    if sorted(nouveaux) == sorted(historiques):
        return IDS_ORDRE
    return IDS_DIFFERENTS


def sens(a: geometrie.Parties, b: geometrie.Parties, tol: float = TOLERANCE_SENS_M) -> str:
    pa, da = geometrie.extremites(a)
    pb, db = geometrie.extremites(b)
    if None in (pa, da, pb, db) or geometrie.distance(pa, da) <= tol:
        return "INDETERMINE"
    if geometrie.distance(pa, pb) <= tol and geometrie.distance(da, db) <= tol:
        return "MEME_SENS"
    if geometrie.distance(pa, db) <= tol and geometrie.distance(da, pb) <= tol:
        return "INVERSE"
    return "INDETERMINE"


def _arrondi(v, n=3):
    return None if v is None else round(v, n)


def comparer(nouveaux: List[Dict[str, object]], historiques: List[Dict[str, object]],
             tol_trace: float = TOLERANCE_TRACE_M, tol_long: float = TOLERANCE_LONGUEUR_M,
             tol_ref: float = TOLERANCE_LONG_REF_M) -> List[Dict[str, object]]:
    """`nouveaux` : {nom_pdf, statut, ids, long_ref, long_geom, parties} ;
    `historiques` : {nom_pdf, couche, ids, long_ref, long_geom, parties}."""
    index: Dict[object, List[Dict[str, object]]] = {}
    for h in historiques:
        index.setdefault(cle_pdf(h["nom_pdf"]), []).append(h)
    utilises = set()
    lignes = []
    for n in nouveaux:
        cle = cle_pdf(n["nom_pdf"])
        hs = index.get(cle, [])
        ligne: Dict[str, object] = {
            "NOM_PDF": n["nom_pdf"], "STATUT_RECONSTRUCTION": n["statut"],
            "IDS_NOUVEAU": ",".join(n["ids"]) or None,
            "NB_TRONCONS_NOUVEAU": len(n["ids"]) or None,
            "LONG_REF_NOUVEAU_M": _arrondi(n["long_ref"]), "LONG_GEOM_NOUVEAU_M": _arrondi(n["long_geom"]),
        }
        messages = []
        if not hs:
            ligne["RESULTAT"] = R_ABSENT_HISTO
            lignes.append(ligne)
            continue
        utilises.add(cle)
        h = hs[0]
        ligne.update({
            "NOM_PDF_HISTO": h["nom_pdf"], "COUCHE_HISTO": h["couche"],
            "CORRESPONDANCE_NOM": NOM_IDENTIQUE if h["nom_pdf"] == n["nom_pdf"] else NOM_RENOMME,
            "IDS_HISTO": ",".join(h["ids"]) or None, "NB_TRONCONS_HISTO": len(h["ids"]) or None,
            "LONG_REF_HISTO_M": _arrondi(h["long_ref"]), "LONG_GEOM_HISTO_M": _arrondi(h["long_geom"]),
        })
        if ligne["CORRESPONDANCE_NOM"] == NOM_RENOMME:
            messages.append("nom historique {0}".format(h["nom_pdf"]))
        if len(hs) > 1:
            ligne["RESULTAT"] = R_DOUBLON
            messages.append("{0} entités historiques : {1}".format(
                len(hs), ", ".join("{0} ({1})".format(x["nom_pdf"], x["couche"]) for x in hs)))
            ligne["MESSAGES"] = " | ".join(messages)
            lignes.append(ligne)
            continue
        ligne["COMPARAISON_IDS"] = comparer_ids(n["ids"], h["ids"]) if n["ids"] else None
        if n["parties"] is None:
            ligne["RESULTAT"] = R_NON_RECONSTRUIT
            messages.append("statut {0}".format(n["statut"]))
            ligne["MESSAGES"] = " | ".join(messages)
            lignes.append(ligne)
            continue
        if n["long_ref"] is not None and h["long_ref"] is not None:
            ligne["ECART_LONG_REF_M"] = round(n["long_ref"] - h["long_ref"], 4)
        if h["long_geom"] is not None:
            ligne["ECART_LONG_GEOM_M"] = round(n["long_geom"] - h["long_geom"], 4)
        dist = geometrie.distance_hausdorff(n["parties"], h["parties"])
        ligne["DIST_MAX_M"] = round(dist, 4)
        ligne["SENS"] = sens(n["parties"], h["parties"])

        if ligne["COMPARAISON_IDS"] == IDS_DIFFERENTS:
            ligne["RESULTAT"] = R_IDS
        elif ligne["COMPARAISON_IDS"] == IDS_ORDRE:
            ligne["RESULTAT"] = R_ORDRE
        elif ligne["SENS"] == "INVERSE":
            ligne["RESULTAT"] = R_SENS
        elif dist > tol_trace:
            ligne["RESULTAT"] = R_GEOMETRIE
        elif ((ligne.get("ECART_LONG_GEOM_M") is not None and abs(ligne["ECART_LONG_GEOM_M"]) > tol_long)
              or (ligne.get("ECART_LONG_REF_M") is not None and abs(ligne["ECART_LONG_REF_M"]) > tol_ref)):
            ligne["RESULTAT"] = R_LONGUEUR
        elif ligne["SENS"] != "MEME_SENS":
            ligne["RESULTAT"] = R_SENS_INDETERMINE
        else:
            ligne["RESULTAT"] = R_IDENTIQUE
        ligne["MESSAGES"] = " | ".join(messages) or None
        lignes.append(ligne)

    for cle, hs in index.items():
        if cle in utilises:
            continue
        for h in hs:
            lignes.append({"NOM_PDF_HISTO": h["nom_pdf"], "COUCHE_HISTO": h["couche"],
                           "IDS_HISTO": ",".join(h["ids"]) or None, "NB_TRONCONS_HISTO": len(h["ids"]) or None,
                           "LONG_REF_HISTO_M": _arrondi(h["long_ref"]),
                           "LONG_GEOM_HISTO_M": _arrondi(h["long_geom"]),
                           "RESULTAT": R_ABSENT_NOUVEAU,
                           "MESSAGES": "PDF historique absent du dossier analysé"})
    return lignes


def synthese(lignes: List[Dict[str, object]]) -> Dict[str, int]:
    s: Dict[str, int] = {}
    for l in lignes:
        s[l["RESULTAT"]] = s.get(l["RESULTAT"], 0) + 1
    return s


# =========================================================================
# Exécution ArcGIS
# =========================================================================

def lire_historiques(histos: Sequence[Tuple[object, object]], journal) -> List[Dict[str, object]]:
    """`histos` : [(couche, DescriptionCouche)] déjà contrôlées."""
    elements = []
    for couche, desc in histos:
        corr = referentiel.resoudre_champs(desc.noms_champs, CHAMPS_HISTO_REQUIS + CHAMPS_HISTO_OPTIONNELS)
        noms = [v for v in corr.values() if v]
        epsg = referentiel.EPSG_SORTIE if desc.epsg else None
        lignes = referentiel.lire_lignes(couche, noms, geometrie=True, epsg=epsg)
        n = 0
        for l in lignes:
            g = l.get("SHAPE@")
            if geometrie.geometrie_vide(g):
                journal.avertissement("{0} : entité sans géométrie ignorée ({1})".format(
                    couche, l.get(corr["NOM_PDF"])))
                continue
            def lire(cle):
                return l.get(corr[cle]) if corr.get(cle) else None
            parties = geometrie.coordonnees(g)
            elements.append({
                "nom_pdf": str(lire("NOM_PDF") or "").strip(),
                "couche": str(couche),
                "ids": lire_ids(lire("IDS_INTERPLO")),
                "long_ref": _flottant(lire("LONG_REF_M")),
                "long_geom": geometrie.longueur_coordonnees(parties),
                "parties": parties,
            })
            n += 1
        journal.info("{0} : {1} géométries historiques lues".format(couche, n))
    return elements


def _flottant(v):
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def executer_comparaison(resultats, histos, table_sortie: str, journal, maintenant=None) -> Dict[str, object]:
    historiques = lire_historiques(histos, journal)
    nouveaux = [{"nom_pdf": r.info.nom_fichier, "statut": r.statut, "ids": r.ids,
                 "long_ref": r.long_ref, "long_geom": r.long_geom,
                 "parties": [list(r.sommets)] if r.sommets else None} for r in resultats]
    lignes = comparer(nouveaux, historiques)
    s = synthese(lignes)
    journal.info("Historique : {0} géométries | sections du lot : {1}".format(len(historiques), len(nouveaux)))
    journal.info("Tolérances : tracé {0} m, longueur géométrique {1} m, longueur de référencement {2} m".format(
        TOLERANCE_TRACE_M, TOLERANCE_LONGUEUR_M, TOLERANCE_LONG_REF_M))
    for l in lignes:
        texte = "{0} : {1} | IDS {2} | écart réf. {3} | écart géom. {4} | distance max {5} | sens {6}".format(
            l.get("NOM_PDF") or l.get("NOM_PDF_HISTO"), l["RESULTAT"], l.get("COMPARAISON_IDS"),
            l.get("ECART_LONG_REF_M"), l.get("ECART_LONG_GEOM_M"), l.get("DIST_MAX_M"), l.get("SENS"))
        if l.get("COUCHE_HISTO"):
            texte += " | historique : {0}".format(l["COUCHE_HISTO"])
        if l.get("CORRESPONDANCE_NOM") == NOM_RENOMME:
            texte += " | nom historique différent : {0}".format(l.get("NOM_PDF_HISTO"))
        (journal.info if l["RESULTAT"] == R_IDENTIQUE else journal.avertissement)(texte)
    for code in sorted(s):
        journal.info("  {0} : {1}".format(code, s[code]))
    journal.info("Rappel : une concordance avec l'historique est une reproduction technique, "
                 "pas une validation métier.")
    for l in lignes:
        l["DATE_TRAITEMENT"] = maintenant
    sorties.creer_table(table_sortie, sorties.CHAMPS_COMPARAISON_SECTIONS)
    sorties.inserer_lignes(table_sortie, sorties.CHAMPS_COMPARAISON_SECTIONS, lignes)
    journal.info("Table de comparaison créée : {0} ({1} lignes)".format(table_sortie, len(lignes)))
    return {"table": table_sortie, "lignes": lignes, "synthese": s}
