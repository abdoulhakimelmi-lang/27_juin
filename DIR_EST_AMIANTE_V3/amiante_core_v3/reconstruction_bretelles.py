# -*- coding: utf-8 -*-
"""Reconstruction des bretelles (phase 2).

Méthode, pour chaque PDF bretelle (ex. 2023_NA_54A933040_3.pdf) :

1. dans interPlo_pr_2026 : route = 54A933040, nomplodeb = DB3, nomplofin = FB3
   -> exactement une ligne exigée, dont on lit `objetid` ;
2. dans REF_INTERPLO_TRONCONS_V1_CORRIGE : ID_INTERPLO = objetid
   -> exactement une entité exigée, dont on lit la géométrie en EPSG:2154 ;
3. contrôles (géométrie non vide, longueurs, écart, concordance route /
   département) puis statut CANDIDAT_A_VALIDER.

Toute absence ou ambiguïté produit une anomalie explicite et AUCUNE
géométrie. Aucune liste fixe d'identifiants n'est utilisée.

La partie « moteur » (IndexOrigine, IndexLocal, resoudre_bretelle) est pure
Python ; executer_reconstruction_bretelles() fait les lectures/écritures arcpy.
"""

from __future__ import annotations

import datetime
from typing import Dict, List, Optional

from . import comparaison, geometrie, nommage, referentiel, sorties
from .diagnostic import ErreurTraitement
from .controles import (departements_concordants, forme_souple_nomplo, normaliser_code,
                        normaliser_identifiant, verifier_code_echangeur)

CANDIDAT = "CANDIDAT_A_VALIDER"
A_NOM_PDF = "ANOMALIE_NOM_PDF"
A_CODE_ECHANGEUR = "ANOMALIE_CODE_ECHANGEUR_ABSENT"
A_NUMERO = "ANOMALIE_NUMERO_BRETELLE"
A_AUCUNE_ORIGINE = "ANOMALIE_AUCUNE_CORRESPONDANCE_INTERPLO"
A_AMBIGU_ORIGINE = "ANOMALIE_CORRESPONDANCE_INTERPLO_AMBIGUE"
A_OBJETID_VIDE = "ANOMALIE_OBJETID_VIDE"
A_OBJETID_DOUBLON = "ANOMALIE_OBJETID_NON_UNIQUE_INTERPLO"
A_ABSENT_LOCAL = "ANOMALIE_ID_ABSENT_REFERENTIEL_LOCAL"
A_AMBIGU_LOCAL = "ANOMALIE_ID_AMBIGU_REFERENTIEL_LOCAL"
A_GEOM_VIDE = "ANOMALIE_GEOMETRIE_VIDE"

# Écart toléré entre LONG_GEOM_M stocké et la longueur recalculée (information)
TOLERANCE_LONG_GEOM_ATTR_M = 0.01


class IndexOrigine(object):
    """Index en mémoire de interPlo_pr_2026 (attributs seulement)."""

    def __init__(self, lignes: List[Dict[str, object]], champs: Dict[str, str]) -> None:
        """`champs` : {'objetid': nom réel, 'route': ..., 'nomplodeb': ..., 'nomplofin': ...}."""
        self.par_route: Dict[str, List[Dict[str, object]]] = {}
        self.compte_objetid: Dict[str, int] = {}
        for brut in lignes:
            ligne = {
                "objetid": normaliser_identifiant(brut.get(champs["objetid"])),
                "route": normaliser_code(brut.get(champs["route"])),
                "deb": normaliser_code(brut.get(champs["nomplodeb"])),
                "fin": normaliser_code(brut.get(champs["nomplofin"])),
            }
            ligne["deb_souple"] = forme_souple_nomplo(ligne["deb"])
            ligne["fin_souple"] = forme_souple_nomplo(ligne["fin"])
            if ligne["route"]:
                self.par_route.setdefault(ligne["route"], []).append(ligne)
            if ligne["objetid"] is not None:
                self.compte_objetid[ligne["objetid"]] = self.compte_objetid.get(ligne["objetid"], 0) + 1

    def doublons_objetid(self) -> Dict[str, int]:
        return {k: v for k, v in self.compte_objetid.items() if v > 1}


class IndexLocal(object):
    """Index en mémoire du référentiel local des tronçons, par ID_INTERPLO."""

    def __init__(self, lignes: List[Dict[str, object]], champs: Dict[str, Optional[str]]) -> None:
        """`champs` : {'ID_INTERPLO': nom réel, 'LONG_REF_M': ..., 'ROUTE': nom|None, ...}."""
        self.par_id: Dict[str, List[Dict[str, object]]] = {}

        def lire(brut, cle):
            nom = champs.get(cle)
            return brut.get(nom) if nom else None

        for brut in lignes:
            ident = normaliser_identifiant(lire(brut, "ID_INTERPLO"))
            if ident is None:
                continue
            self.par_id.setdefault(ident, []).append({
                "id": ident,
                "route": normaliser_code(lire(brut, "ROUTE")),
                "departement": normaliser_code(lire(brut, "DEPARTEMENT")),
                "cote": normaliser_code(lire(brut, "COTE")),
                "long_ref": lire(brut, "LONG_REF_M"),
                "long_geom_attr": lire(brut, "LONG_GEOM_M"),
                "geom": brut.get("SHAPE@"),
            })

    def doublons(self) -> Dict[str, int]:
        return {k: len(v) for k, v in self.par_id.items() if len(v) > 1}


class ResultatBretelle(object):
    def __init__(self, info: nommage.InfoPDF) -> None:
        self.info = info
        self.controle: Optional[str] = None
        self.anomalies: List[str] = []
        self.avertissements: List[str] = []
        self.objetid: Optional[str] = None
        self.nb_corr_origine: Optional[int] = None
        self.nb_corr_local: Optional[int] = None
        self.id_interplo: Optional[str] = None
        self.departement: Optional[str] = info.departement
        self.cote: Optional[str] = None
        self.long_ref: Optional[float] = None
        self.long_geom: Optional[float] = None
        self.long_geom_attr: Optional[float] = None
        self.ecart_m: Optional[float] = None
        self.ecart_pct: Optional[float] = None
        self.nb_parties: Optional[int] = None
        self.geom = None

    @property
    def est_candidat(self) -> bool:
        return self.controle == CANDIDAT

    def anomalie(self, code: str, detail: str) -> "ResultatBretelle":
        self.controle = code
        self.anomalies.append("{0} : {1}".format(code, detail))
        self.geom = None
        return self

    def texte_anomalies(self) -> str:
        return " | ".join(self.anomalies + ["AVERT : " + a for a in self.avertissements])

    def en_dict(self, date_traitement=None) -> Dict[str, object]:
        i = self.info
        return {
            "NOM_PDF": i.nom_fichier,
            "ANNEE": i.annee,
            "STATUT_AM": i.statut,
            "ROUTE": i.route,
            "DEPARTEMENT": self.departement,
            "NUM_BRET": i.num_bretelle,
            "ID_INTERPLO": self.id_interplo,
            "LONG_REF_M": self.long_ref,
            "LONG_GEOM_M": self.long_geom,
            "ECART_M": self.ecart_m,
            "CONTROLE": self.controle,
            "ECART_PCT": self.ecart_pct,
            "NOMPLODEB": i.nomplodeb_attendu,
            "NOMPLOFIN": i.nomplofin_attendu,
            "OBJETID_ORIG": self.objetid,
            "NB_CORR_ORIG": self.nb_corr_origine,
            "NB_CORR_LOCAL": self.nb_corr_local,
            "COTE": self.cote,
            "LONG_GEOM_ATTR_M": self.long_geom_attr,
            "NB_PARTIES": self.nb_parties,
            "ANOMALIES": self.texte_anomalies(),
            "DATE_TRAITEMENT": date_traitement,
        }


def _resume_couples(lignes: List[Dict[str, object]], limite: int = 15) -> str:
    couples = sorted(set("{0}/{1}".format(l["deb"], l["fin"]) for l in lignes))
    texte = ", ".join(couples[:limite])
    if len(couples) > limite:
        texte += ", ... ({0} couples)".format(len(couples))
    return texte


def _flottant(valeur) -> Optional[float]:
    try:
        return None if valeur is None else float(valeur)
    except (TypeError, ValueError):
        return None


def resoudre_bretelle(info: nommage.InfoPDF, origine: IndexOrigine, local: IndexLocal) -> ResultatBretelle:
    """Applique les contrôles 1 à 10 à un PDF bretelle."""
    r = ResultatBretelle(info)

    # 1. Format du nom
    if info.type_pdf != nommage.TYPE_BRETELLE:
        return r.anomalie(A_NOM_PDF, "nom non reconnu comme bretelle")
    if info.niveau == nommage.NIVEAU_ERREUR:
        return r.anomalie(A_NOM_PDF, " | ".join(info.messages))
    for m in info.messages:
        r.avertissements.append("nom PDF : " + m)

    # 2. Code échangeur
    r.avertissements.extend(verifier_code_echangeur(info.route))
    lignes_route = origine.par_route.get(normaliser_code(info.route) or "", [])
    if not lignes_route:
        return r.anomalie(A_CODE_ECHANGEUR,
                          "route {0} absente de interPlo_pr_2026".format(info.route))

    # 3. Numéro de bretelle
    if info.num_bretelle is None or info.num_bretelle < 1:
        return r.anomalie(A_NUMERO, "numéro de bretelle invalide ({0})".format(info.num_bretelle_txt))

    # 4. Correspondance DB{n} / FB{n}
    db, fb = info.nomplodeb_attendu, info.nomplofin_attendu
    candidats = [l for l in lignes_route if l["deb"] == db and l["fin"] == fb]
    r.nb_corr_origine = len(candidats)

    # 5. Unicité de la correspondance INTERPLO
    if not candidats:
        details = []
        if not any(l["deb"] == db for l in lignes_route):
            details.append("{0} absent de nomplodeb".format(db))
        if not any(l["fin"] == fb for l in lignes_route):
            details.append("{0} absent de nomplofin".format(fb))
        if not details:
            details.append("{0} et {1} présents mais jamais sur la même ligne".format(db, fb))
        souples = [l for l in lignes_route
                   if l["deb_souple"] == forme_souple_nomplo(db)
                   and l["fin_souple"] == forme_souple_nomplo(fb)]
        if souples:
            details.append("correspondance seulement sous une autre écriture ({0}), "
                           "non acceptée".format(_resume_couples(souples)))
        details.append("couples disponibles pour {0} : {1}".format(info.route, _resume_couples(lignes_route)))
        return r.anomalie(A_AUCUNE_ORIGINE, " ; ".join(details))
    if len(candidats) > 1:
        return r.anomalie(A_AMBIGU_ORIGINE, "{0} lignes {1}/{2} pour {3} (objetid : {4})".format(
            len(candidats), db, fb, info.route,
            ", ".join(str(c["objetid"]) for c in candidats)))

    objetid = candidats[0]["objetid"]
    r.objetid = objetid
    if objetid is None:
        return r.anomalie(A_OBJETID_VIDE, "objetid vide dans interPlo_pr_2026")
    if origine.compte_objetid.get(objetid, 0) > 1:
        return r.anomalie(A_OBJETID_DOUBLON, "objetid {0} présent {1} fois dans interPlo_pr_2026".format(
            objetid, origine.compte_objetid[objetid]))

    # 6. Unicité dans le référentiel local
    entites = local.par_id.get(objetid, [])
    r.nb_corr_local = len(entites)
    if not entites:
        return r.anomalie(A_ABSENT_LOCAL, "objetid {0} absent de ID_INTERPLO".format(objetid))
    if len(entites) > 1:
        return r.anomalie(A_AMBIGU_LOCAL, "ID_INTERPLO {0} présent {1} fois".format(objetid, len(entites)))
    ent = entites[0]
    r.id_interplo = ent["id"]
    r.cote = ent["cote"]
    if ent["departement"]:
        r.departement = ent["departement"]

    # 7. Géométrie
    geom = ent["geom"]
    if geometrie.geometrie_vide(geom):
        return r.anomalie(A_GEOM_VIDE, "géométrie absente ou vide pour ID_INTERPLO {0}".format(objetid))
    r.nb_parties = geometrie.nombre_parties(geom)
    if r.nb_parties > 1:
        r.avertissements.append("géométrie en {0} parties".format(r.nb_parties))

    # 8-9. Longueurs et écart (référencement et géométrie restent distincts)
    r.long_ref = _flottant(ent["long_ref"])
    r.long_geom = round(geometrie.longueur(geom), 3)
    r.long_geom_attr = _flottant(ent["long_geom_attr"])
    if r.long_ref is None:
        r.avertissements.append("LONG_REF_M vide : écart non calculé")
    else:
        r.ecart_m = round(r.long_geom - r.long_ref, 3)
        if r.long_ref:
            r.ecart_pct = round(r.ecart_m / r.long_ref * 100.0, 3)
    if r.long_geom_attr is not None and abs(r.long_geom_attr - r.long_geom) > TOLERANCE_LONG_GEOM_ATTR_M:
        r.avertissements.append("LONG_GEOM_M stocké ({0:.3f}) différent de la longueur recalculée "
                                "({1:.3f})".format(r.long_geom_attr, r.long_geom))

    # Concordances informatives entre les deux couches
    if ent["route"] and ent["route"] != normaliser_code(info.route):
        r.avertissements.append("ROUTE locale {0} différente du code échangeur {1}".format(
            ent["route"], info.route))
    if departements_concordants(ent["departement"], info.departement) is False:
        r.avertissements.append("DEPARTEMENT local {0} différent du département du code {1}".format(
            ent["departement"], info.departement))

    # 10. Statut
    r.controle = CANDIDAT
    r.geom = geom
    return r


def signaler_doublons_resultats(resultats: List[ResultatBretelle]) -> None:
    """Deux PDF qui aboutissent au même ID_INTERPLO -> avertissement."""
    par_id: Dict[str, List[ResultatBretelle]] = {}
    for r in resultats:
        if r.est_candidat:
            par_id.setdefault(r.id_interplo, []).append(r)
    for groupe in par_id.values():
        if len(groupe) > 1:
            for r in groupe:
                autres = ", ".join(x.info.nom_fichier for x in groupe if x is not r)
                r.avertissements.append("même ID_INTERPLO que : {0}".format(autres))


def resoudre_toutes(infos: List[nommage.InfoPDF], origine: IndexOrigine,
                    local: IndexLocal) -> List[ResultatBretelle]:
    resultats = [resoudre_bretelle(i, origine, local) for i in infos
                 if i.type_pdf == nommage.TYPE_BRETELLE]
    signaler_doublons_resultats(resultats)
    return resultats


def synthese(resultats: List[ResultatBretelle]) -> Dict[str, int]:
    s: Dict[str, int] = {"TOTAL": len(resultats)}
    for r in resultats:
        s[r.controle] = s.get(r.controle, 0) + 1
    return s


# =========================================================================
# Exécution ArcGIS
# =========================================================================

def _verifier_couche(desc, journal, bloquants: List[str]) -> None:
    for ligne in desc.lignes_rapport():
        if ligne.startswith("ERREUR"):
            journal.erreur(ligne)
        elif ligne.startswith("AVERTISSEMENT"):
            journal.avertissement(ligne)
        else:
            journal.info(ligne)
    if not desc.existe:
        bloquants.append("{0} introuvable".format(desc.libelle))
    elif desc.manquants:
        bloquants.append("{0} : champs absents {1}".format(desc.libelle, ", ".join(desc.manquants)))


def executer_reconstruction_bretelles(dossier_pdf: str, couche_troncons, couche_points,
                                      couche_interplo, gdb_sortie: str, prefixe: str, journal,
                                      couche_histo=None, champ_id_histo: Optional[str] = None
                                      ) -> Dict[str, object]:
    """Mode RECONSTRUCTION_BRETELLES. Lecture seule sur toutes les couches
    fournies ; écrit une classe d'entités, une table de contrôle et, si une
    couche historique est fournie, une table de comparaison — toutes nouvelles."""
    import arcpy

    resultat: Dict[str, object] = {}

    # Analyse des PDF ------------------------------------------------------
    journal.info("=== 1. Analyse des noms de PDF ===")
    infos = nommage.analyser_dossier(dossier_pdf)
    s_pdf = nommage.synthese(infos)
    journal.info("PDF : {0} | bretelles : {1} | sections ignorées : {2} | non reconnus : {3}".format(
        s_pdf["TOTAL"], s_pdf[nommage.TYPE_BRETELLE], s_pdf[nommage.TYPE_SECTION],
        s_pdf[nommage.TYPE_NON_RECONNU]))
    if not s_pdf[nommage.TYPE_BRETELLE]:
        journal.avertissement("Aucune bretelle dans le dossier")

    # Couches --------------------------------------------------------------
    journal.info("=== 2. Contrôle des couches ===")
    bloquants: List[str] = []
    d_ip = referentiel.decrire_couche(couche_interplo, "INTERPLO d'origine",
                                      referentiel.CHAMPS_BRETELLES_INTERPLO,
                                      referentiel.EFFECTIF_INTERPLO,
                                      referentiel.TYPE_GEOM_INTERPLO, referentiel.EPSG_INTERPLO)
    d_tr = referentiel.decrire_couche(couche_troncons, "Tronçons locaux",
                                      referentiel.CHAMPS_BRETELLES_LOCAL_REQUIS,
                                      referentiel.EFFECTIF_TRONCONS,
                                      referentiel.TYPE_GEOM_TRONCONS, referentiel.EPSG_TRONCONS)
    d_pt = referentiel.decrire_couche(couche_points, "Points PR (non utilisée en phase 2)",
                                      (), referentiel.EFFECTIF_POINTS_PR,
                                      referentiel.TYPE_GEOM_POINTS, referentiel.EPSG_POINTS_PR)
    for d in (d_ip, d_tr):
        _verifier_couche(d, journal, bloquants)
    if not d_pt.existe:
        journal.avertissement("Couche points PR introuvable (non bloquant en phase 2)")
    if bloquants:
        raise ErreurTraitement("Traitement arrêté avant toute écriture : " + " ; ".join(bloquants))

    # Lecture INTERPLO d'origine (attributs seulement) -----------------------
    champs_ip = {k: v for k, v in d_ip.correspondance.items()}
    lignes_ip = referentiel.lire_lignes(couche_interplo, list(champs_ip.values()))
    origine = IndexOrigine(lignes_ip, champs_ip)
    dbl = origine.doublons_objetid()
    journal.info("interPlo_pr_2026 : {0} lignes lues, {1} routes".format(len(lignes_ip), len(origine.par_route)))
    if dbl:
        journal.avertissement("{0} objetid en double dans interPlo_pr_2026".format(len(dbl)))

    # Lecture du référentiel local (géométrie en EPSG:2154) ------------------
    corr_local = referentiel.resoudre_champs(
        d_tr.noms_champs,
        referentiel.CHAMPS_BRETELLES_LOCAL_REQUIS + referentiel.CHAMPS_BRETELLES_LOCAL_OPTIONNELS)
    for cle in referentiel.CHAMPS_BRETELLES_LOCAL_OPTIONNELS:
        if corr_local[cle] is None:
            journal.avertissement("Champ facultatif {0} absent du référentiel local".format(cle))
    lignes_tr = referentiel.lire_lignes(couche_troncons, [v for v in corr_local.values() if v],
                                        geometrie=True, epsg=referentiel.EPSG_SORTIE)
    local = IndexLocal(lignes_tr, corr_local)
    journal.info("Référentiel local : {0} entités lues, {1} ID_INTERPLO distincts".format(
        len(lignes_tr), len(local.par_id)))
    if local.doublons():
        journal.avertissement("{0} ID_INTERPLO en double dans le référentiel local".format(
            len(local.doublons())))

    # Résolution -------------------------------------------------------------
    journal.info("=== 3. Recherche des bretelles ===")
    resultats = resoudre_toutes(infos, origine, local)
    for r in resultats:
        texte = "{0} : {1} -> objetid {2} -> ID_INTERPLO {3}".format(
            r.info.nom_fichier, r.controle, r.objetid, r.id_interplo)
        if r.est_candidat:
            texte += " | LONG_REF_M {0} | LONG_GEOM_M {1} | ECART_M {2}".format(
                r.long_ref, r.long_geom, r.ecart_m)
            journal.info(texte)
        else:
            journal.avertissement(texte)
        for a in r.anomalies:
            journal.avertissement("    " + a)
        for a in r.avertissements:
            journal.info("    avert. : " + a)

    # Sorties ----------------------------------------------------------------
    journal.info("=== 4. Création des sorties ===")
    maintenant = datetime.datetime.now()
    bases = ["{0}_BRETELLES".format(prefixe), "CONTROLE_{0}_BRETELLES".format(prefixe)]
    if couche_histo:
        bases.append("COMPARAISON_{0}_BRETELLES".format(prefixe))
    noms = sorties.noms_sorties_uniques(gdb_sortie, bases, arcpy.Exists, maintenant)
    fc, table = noms[0], noms[1]

    lignes = [r.en_dict(maintenant) for r in resultats]
    sorties.creer_classe_entites(fc, sorties.CHAMPS_BRETELLES, referentiel.EPSG_SORTIE,
                                 has_m=d_tr.has_m, has_z=d_tr.has_z)
    n_fc = sorties.inserer_entites(fc, sorties.CHAMPS_BRETELLES,
                                   [(l, r.geom) for l, r in zip(lignes, resultats) if r.est_candidat])
    sorties.creer_table(table, sorties.CHAMPS_BRETELLES)
    n_tab = sorties.inserer_lignes(table, sorties.CHAMPS_BRETELLES, lignes)
    journal.info("Classe d'entités créée : {0} ({1} géométries candidates)".format(fc, n_fc))
    journal.info("Table de contrôle créée : {0} ({1} lignes)".format(table, n_tab))
    resultat.update({"classe_entites": fc, "table_controle": table, "resultats": resultats})

    # Comparaison avec la couche historique ---------------------------------
    if couche_histo:
        journal.info("=== 5. Comparaison avec la couche historique ===")
        resultat["comparaison"] = comparaison.executer_comparaison(
            resultats, couche_histo, champ_id_histo, noms[2], journal, maintenant)

    # Résumé -----------------------------------------------------------------
    s = synthese(resultats)
    resultat["synthese"] = s
    journal.info("=== Résumé ===")
    journal.info("Bretelles analysées : {0}".format(s["TOTAL"]))
    for code in sorted(k for k in s if k != "TOTAL"):
        journal.info("  {0} : {1}".format(code, s[code]))
    return resultat
