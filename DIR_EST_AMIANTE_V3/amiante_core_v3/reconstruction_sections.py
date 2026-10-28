# -*- coding: utf-8 -*-
"""Reconstruction automatique des sections courantes (phase 3).

Aucune liste d'identifiants INTERPLO prédéfinie : les parcours sont
recherchés à partir du nom du PDF (route, département, PR, abscisses,
côtés) et du référencement (cumuls, logiques, géométries).

Étapes pour chaque PDF de section :
1. réseau de la route et du département ;
2. localisation des extrémités (règles V6A / V7B, localisation.py) ;
3. énumération de tous les parcours admissibles (parcours.py) ;
4. 0 parcours -> PARCOURS_INTROUVABLE, plusieurs -> PARCOURS_AMBIGU, limite
   atteinte -> RECHERCHE_INCOMPLETE ; jamais de choix arbitraire ;
5. pour un parcours unique : contrôles géométriques (multipartie, fermée,
   orientation par les points PR), découpe proportionnelle au cumul avec
   segmentAlongLine (méthode historique), contrôle des raccordements,
   assemblage sans segment artificiel, longueurs ;
6. statut CANDIDAT_A_VALIDER, avec alertes éventuelles.

La partie moteur est pure Python ; executer_reconstruction_sections() fait
les lectures / écritures arcpy (nouvelles sorties uniquement).
"""

from __future__ import annotations

import datetime
import traceback
from typing import Callable, Dict, List, Optional

from . import comparaison_sections, geometrie, nommage, referentiel, sorties
from .diagnostic import ErreurTraitement
from .localisation import localiser
from .parcours import Admissibilite, Parametres, Parcours, rechercher
from .reseau import (CHAMPS_POINTS_OPTIONNELS, CHAMPS_POINTS_ORIENTATION, CHAMPS_TRONCONS_SECTIONS,
                     IndexPointsPR, Reseau, controler_orientation, ecarts_cumul_points)

CANDIDAT = "CANDIDAT_A_VALIDER"
S_ROUTE = "ROUTE_ABSENTE_REFERENTIEL"
S_PR_DEBUT = "PR_DEBUT_INTROUVABLE"
S_PR_FIN = "PR_FIN_INTROUVABLE"
S_INTROUVABLE = "PARCOURS_INTROUVABLE"
S_AMBIGU = "PARCOURS_AMBIGU"
S_INCOMPLETE = "RECHERCHE_INCOMPLETE"
S_RACCORDEMENT = "RACCORDEMENT_NON_CONFORME"
S_GEOMETRIE = "GEOMETRIE_PROBLEMATIQUE"
S_ERREUR = "ERREUR"

M_STRICT = "COTE_STRICT"
M_COMMUNE = "PORTION_COMMUNE_DF_FF"
M_CHANGEMENT = "CHANGEMENT_COTE"

# Statut des parcours dans la table détaillée
P_RETENU = "RETENU"
P_AMBIGU = "VARIANTE_AMBIGUE"
P_INCOMPLET = "VARIANTE_RECHERCHE_INCOMPLETE"
P_REJETE = "RETENU_PUIS_REJETE"


def decouper_arcpy(geom, d0: float, d1: float):
    """Découpe historique (V6A / V6C / V7B)."""
    return geom.segmentAlongLine(d0, d1, False)


class ResultatSection(object):
    def __init__(self, info: nommage.InfoPDF) -> None:
        self.info = info
        self.statut: Optional[str] = None
        self.methode: Optional[str] = None
        self.observations: List[str] = []
        self.alertes: List[str] = []
        self.parcours: Optional[Parcours] = None
        self.variantes: List[Parcours] = []
        self.nb_pos_debut = 0
        self.nb_pos_fin = 0
        self.sommets: Optional[List] = None
        self.long_ref: Optional[float] = None
        self.long_geom: Optional[float] = None
        self.ecart_racc_max: Optional[float] = None
        self.ecart_cumul_max: Optional[float] = None
        self.orientations: Dict[str, str] = {}
        self.portions: Dict[int, Dict[str, float]] = {}

    @property
    def est_candidat(self) -> bool:
        return self.statut == CANDIDAT

    def echec(self, statut: str, texte: str) -> "ResultatSection":
        self.statut = statut
        self.observations.append(texte)
        self.sommets = None
        return self

    @property
    def ids(self) -> List[str]:
        return self.parcours.ids if self.parcours else []

    def en_dict(self, date_traitement=None) -> Dict[str, object]:
        i = self.info
        return {
            "NOM_PDF": i.nom_fichier,
            "ANNEE": i.annee,
            "STATUT_AMIANTE": i.statut,
            "ROUTE": i.route,
            "DEPARTEMENT": i.departement,
            "COTE_DEBUT": i.cote_debut,
            "COTE_FIN": i.cote_fin,
            "COTE_DEB_CTRL": i.cote_debut_controle,
            "COTE_FIN_CTRL": i.cote_fin_controle,
            "PR_DEBUT": _pr_texte(i.pr_debut, i.abs_debut),
            "PR_FIN": _pr_texte(i.pr_fin, i.abs_fin),
            "PR_DEB_NUM": i.pr_debut,
            "ABS_DEB": i.abs_debut,
            "PR_FIN_NUM": i.pr_fin,
            "ABS_FIN": i.abs_fin,
            "IDS_INTERPLO": ",".join(self.ids) if self.ids else None,
            "NB_TRONCONS": len(self.ids) if self.ids else None,
            "LONG_REF_M": None if self.long_ref is None else round(self.long_ref, 3),
            "LONG_GEOM_M": None if self.long_geom is None else round(self.long_geom, 3),
            "ECART_M": (None if self.long_ref is None or self.long_geom is None
                        else round(self.long_geom - self.long_ref, 3)),
            "STATUT_RECONSTRUCTION": self.statut,
            "METHODE": self.methode,
            "NB_PARCOURS": len(self.variantes),
            "NB_POS_DEBUT": self.nb_pos_debut,
            "NB_POS_FIN": self.nb_pos_fin,
            "NB_CHGT_COTE": self.parcours.nb_changements_cote if self.parcours else None,
            "ECART_RACC_MAX_M": None if self.ecart_racc_max is None else round(self.ecart_racc_max, 3),
            "ECART_CUMUL_MAX_M": None if self.ecart_cumul_max is None else round(self.ecart_cumul_max, 3),
            "ALERTES": " | ".join(self.alertes) or None,
            "OBSERVATION": " | ".join(self.observations) or None,
            "DATE_TRAITEMENT": date_traitement,
        }

    def lignes_detail(self, date_traitement=None) -> List[Dict[str, object]]:
        lignes = []
        if self.statut == CANDIDAT:
            statut = P_RETENU
        elif self.statut == S_AMBIGU:
            statut = P_AMBIGU
        elif self.statut == S_INCOMPLETE:
            statut = P_INCOMPLET
        else:
            statut = P_REJETE   # parcours unique rejeté par les contrôles géométriques
        for num, parcours in enumerate(self.variantes, 1):
            for ordre, e in enumerate(parcours.etapes, 1):
                t = e.troncon
                portion = self.portions.get(ordre, {}) if parcours is self.parcours else {}
                lignes.append({
                    "NOM_PDF": self.info.nom_fichier,
                    "VARIANTE": num,
                    "STATUT_PARCOURS": statut,
                    "ORDRE": ordre,
                    "ID_INTERPLO": t.id,
                    "COTE": t.cote,
                    "APPARTENANCE": e.appartenance,
                    "CUMUL_DEBUT": t.cd,
                    "CUMUL_FIN": t.cf,
                    "CUMUL_ENTREE": None if e.entree is None else round(e.entree, 3),
                    "CUMUL_SORTIE": None if e.sortie is None else round(e.sortie, 3),
                    "LONG_REF_PORTION_M": (None if e.entree is None or e.sortie is None
                                           else round(e.sortie - e.entree, 3)),
                    "LONG_GEOM_PORTION_M": portion.get("long_geom"),
                    "TYPE_RACCORDEMENT": e.type_raccord,
                    "ECART_CUMUL_M": None if e.ecart_cumul is None else round(e.ecart_cumul, 3),
                    "DISTANCE_RACC_M": None if e.distance_racc is None else round(e.distance_racc, 3),
                    "LOGIQUES": "/".join(t.logiques),
                    "ORIENTATION": self.orientations.get(t.id) if parcours is self.parcours else None,
                    "ALERTES": " | ".join(e.alertes) or None,
                    "DATE_TRAITEMENT": date_traitement,
                })
        return lignes


def _pr_texte(pr, absc) -> Optional[str]:
    if pr is None or absc is None:
        return None
    return "PR{0}+{1:03d}".format(pr, absc)


def _texte_refus(refusees) -> str:
    if not refusees:
        return " ; aucun tronçon de la route ne porte ce PR et cette abscisse"
    return " ; position(s) trouvée(s) mais non admise(s) : " + ", ".join(
        "côté {0} cumul {1:.3f} (ID {2})".format(x.cote, x.cumul, x.id_source) for x in refusees)


def reconstruire_section(info: nommage.InfoPDF, reseau: Reseau, points: Optional[IndexPointsPR],
                         p: Parametres, decouper: Callable = decouper_arcpy) -> ResultatSection:
    r = ResultatSection(info)
    if info.type_pdf != nommage.TYPE_SECTION:
        return r.echec(S_ERREUR, "le PDF n'est pas une section courante")
    if info.messages:
        r.alertes.extend("nom PDF : " + m for m in info.messages)

    troncons = reseau.troncons(info.route, info.departement)
    if not troncons:
        return r.echec(S_ROUTE, "aucun tronçon utilisable pour {0} / département {1}".format(
            info.route, info.departement))

    cdeb, cfin = info.cote_debut_controle, info.cote_fin_controle
    admis = Admissibilite(cdeb, cfin)

    # Localisation des extrémités : seules les positions portées par un tronçon
    # admis à cette extrémité sont retenues ; les autres sont citées.
    def refus(fn):
        return lambda t: not fn(t)

    debuts = localiser(troncons, info.pr_debut, info.abs_debut, p.tol_abs, p.tol_cumul, admis.admis_au_debut)
    fins = localiser(troncons, info.pr_fin, info.abs_fin, p.tol_abs, p.tol_cumul, admis.admis_a_la_fin)
    debuts_refuses = [] if debuts else localiser(troncons, info.pr_debut, info.abs_debut, p.tol_abs,
                                                 p.tol_cumul, refus(admis.admis_au_debut))
    fins_refuses = [] if fins else localiser(troncons, info.pr_fin, info.abs_fin, p.tol_abs,
                                             p.tol_cumul, refus(admis.admis_a_la_fin))
    r.nb_pos_debut, r.nb_pos_fin = len(debuts), len(fins)
    if not debuts:
        return r.echec(S_PR_DEBUT, "{0} non localisé sur un tronçon admis (côté {1}{2}){3}".format(
            _pr_texte(info.pr_debut, info.abs_debut), cdeb, " ou D avec DF/FF" if cdeb == "I" else "",
            _texte_refus(debuts_refuses)))
    if not fins:
        return r.echec(S_PR_FIN, "{0} non localisé sur un tronçon admis (côté {1}{2}){3}".format(
            _pr_texte(info.pr_fin, info.abs_fin), cfin, " ou D avec DF/FF" if cfin == "I" else "",
            _texte_refus(fins_refuses)))
    if len(debuts) > 1:
        r.alertes.append("{0} positions possibles pour le début : {1}".format(
            len(debuts), ", ".join("{0}@{1:.3f} (ID {2})".format(x.cote, x.cumul, x.id_source) for x in debuts)))
    if len(fins) > 1:
        r.alertes.append("{0} positions possibles pour la fin : {1}".format(
            len(fins), ", ".join("{0}@{1:.3f} (ID {2})".format(x.cote, x.cumul, x.id_source) for x in fins)))
    if (info.pr_debut, info.abs_debut) > (info.pr_fin, info.abs_fin):
        r.observations.append("PR de début supérieur au PR de fin : parcours recherché dans le sens "
                              "des cumuls croissants uniquement")

    # Recherche des parcours
    rech = rechercher(troncons, debuts, fins, admis, p)
    r.variantes = rech.parcours
    if rech.incomplete:
        return r.echec(S_INCOMPLETE, "recherche interrompue ({0}) après {1} états ; {2} parcours déjà "
                       "trouvé(s) : aucun n'est retenu".format(rech.motif_incomplet, rech.nb_etats,
                                                               len(rech.parcours)))
    if not rech.parcours:
        details = ["{0} départ(s) possible(s)".format(len(rech.departs))]
        for ident, refus in rech.impasses[:5]:
            if refus:
                details.append("impasse après ID {0} : {1}".format(ident, "; ".join(
                    "ID {0} ({1}) {2}".format(*x) for x in refus[:4])))
            else:
                details.append("impasse après ID {0} : aucun tronçon raccordé à moins de {1} m".format(
                    ident, p.tol_xy))
        return r.echec(S_INTROUVABLE, " ; ".join(details))
    if len(rech.parcours) > 1:
        stricts = sum(1 for x in rech.parcours if x.strict)
        return r.echec(S_AMBIGU, "{0} parcours admissibles ({1} strict(s), {2} avec portion commune) : "
                       "{3}".format(len(rech.parcours), stricts, len(rech.parcours) - stricts,
                                    " / ".join(x.texte() for x in rech.parcours)))

    parcours = rech.parcours[0]
    r.parcours = parcours
    r.alertes.extend(parcours.alertes())
    ecarts_cumul = [abs(e.ecart_cumul) for e in parcours.etapes if e.ecart_cumul is not None]
    r.ecart_cumul_max = max(ecarts_cumul) if ecarts_cumul else 0.0

    if cdeb != cfin:
        r.methode = M_CHANGEMENT + ("+" + M_COMMUNE if not parcours.strict else "")
    else:
        r.methode = M_STRICT if parcours.strict else M_COMMUNE
    return _construire_geometrie(r, parcours, points, p, decouper)


def _construire_geometrie(r: ResultatSection, parcours: Parcours, points: Optional[IndexPointsPR],
                          p: Parametres, decouper: Callable) -> ResultatSection:
    problemes: List[str] = []
    for e in parcours.etapes:
        t = e.troncon
        if t.nb_parties != 1:
            problemes.append("ID {0} : géométrie MULTIPARTIE ({1} parties)".format(t.id, t.nb_parties))
        code, detail = controler_orientation(t, points, p.tol_xy)
        r.orientations[t.id] = code
        if code in ("FERMEE", "INVERSE", "INCOHERENT"):
            problemes.append("ID {0} : orientation {1} ({2})".format(t.id, code, detail))
        elif code == "NON_CONTROLE":
            r.alertes.append("ID {0} : orientation non contrôlée ({1})".format(t.id, detail))
        r.alertes.extend(ecarts_cumul_points(t, points, p.tol_cumul))
    if problemes:
        return r.echec(S_GEOMETRIE, " ; ".join(problemes))

    portions = []
    long_ref = 0.0
    for ordre, e in enumerate(parcours.etapes, 1):
        t = e.troncon
        f0 = (e.entree - t.cd) / (t.cf - t.cd)
        f1 = (e.sortie - t.cd) / (t.cf - t.cd)
        marge = p.tol_cumul / (t.cf - t.cd) + 1e-12
        if -marge < f0 < 0:
            f0 = 0.0
        if 1 < f1 < 1 + marge:
            f1 = 1.0
        if not (0 <= f0 < f1 <= 1):
            return r.echec(S_GEOMETRIE, "ID {0} : fractions de découpe invalides ({1:.6f} -> {2:.6f})".format(
                t.id, f0, f1))
        portion = decouper(t.geom, t.long_geom * f0, t.long_geom * f1)
        parties = geometrie.coordonnees(portion)
        if len(parties) != 1 or len(parties[0]) < 2:
            return r.echec(S_GEOMETRIE, "ID {0} : portion découpée vide ou multipartie ({1} parties)".format(
                t.id, len(parties)))
        portions.append(parties)
        long_ref += e.sortie - e.entree
        r.portions[ordre] = {"long_geom": round(geometrie.longueur_coordonnees(parties), 3)}

    ecarts = []
    for i in range(len(portions) - 1):
        d = geometrie.distance(portions[i][-1][-1], portions[i + 1][0][0])
        ecarts.append(d)
        if d > p.tol_xy:
            return r.echec(S_RACCORDEMENT, "raccordement {0} -> {1} : {2:.3f} m > {3} m".format(
                parcours.etapes[i].troncon.id, parcours.etapes[i + 1].troncon.id, d, p.tol_xy))
    r.ecart_racc_max = max(ecarts) if ecarts else 0.0

    sommets = geometrie.assembler(portions)
    long_geom = geometrie.longueur_coordonnees([sommets])
    if len(sommets) < 2 or long_geom <= 0:
        return r.echec(S_GEOMETRIE, "géométrie assemblée vide")
    r.sommets = sommets
    r.long_ref = long_ref
    r.long_geom = long_geom
    r.statut = CANDIDAT
    return r


def synthese(resultats: List[ResultatSection]) -> Dict[str, int]:
    s: Dict[str, int] = {"TOTAL": len(resultats)}
    for r in resultats:
        s[r.statut] = s.get(r.statut, 0) + 1
    s["AVEC_ALERTES"] = sum(1 for r in resultats if r.est_candidat and r.alertes)
    return s


# =========================================================================
# Exécution ArcGIS
# =========================================================================

def _journal_couche(desc, journal) -> None:
    for ligne in desc.lignes_rapport():
        if ligne.startswith("ERREUR"):
            journal.erreur(ligne)
        elif ligne.startswith("AVERTISSEMENT"):
            journal.avertissement(ligne)
        else:
            journal.info(ligne)


def executer_reconstruction_sections(dossier_pdf: str, couche_troncons, couche_points, couche_interplo,
                                     gdb_sortie: str, prefixe: str, journal, couches_histo=None,
                                     parametres: Optional[Parametres] = None) -> Dict[str, object]:
    """Mode RECONSTRUCTION_SECTIONS. Lecture seule sur toutes les couches
    fournies ; écrit une classe d'entités, une table de contrôle, une table
    détaillée des tronçons et, si des couches historiques sont fournies, une
    table de comparaison — toutes nouvelles."""
    import arcpy

    p = parametres or Parametres()
    resultat: Dict[str, object] = {}
    journal.info("Paramètres : " + p.resume())

    # 1. PDF ----------------------------------------------------------------
    journal.info("=== 1. Analyse des noms de PDF ===")
    infos = nommage.analyser_dossier(dossier_pdf)
    s_pdf = nommage.synthese(infos)
    sections = [i for i in infos if i.type_pdf == nommage.TYPE_SECTION]
    journal.info("PDF analysés : {0} | sections reconnues : {1} | bretelles ignorées : {2} | "
                 "non reconnus : {3}".format(s_pdf["TOTAL"], len(sections), s_pdf[nommage.TYPE_BRETELLE],
                                             s_pdf[nommage.TYPE_NON_RECONNU]))
    if not sections:
        journal.avertissement("Aucune section courante dans le dossier")

    # 2. Couches ------------------------------------------------------------
    journal.info("=== 2. Contrôle des couches ===")
    d_tr = referentiel.decrire_couche(couche_troncons, "Tronçons locaux", CHAMPS_TRONCONS_SECTIONS,
                                      referentiel.EFFECTIF_TRONCONS, referentiel.TYPE_GEOM_TRONCONS,
                                      referentiel.EPSG_TRONCONS)
    d_pt = referentiel.decrire_couche(couche_points, "Points PR", CHAMPS_POINTS_ORIENTATION,
                                      referentiel.EFFECTIF_POINTS_PR, referentiel.TYPE_GEOM_POINTS,
                                      referentiel.EPSG_POINTS_PR)
    _journal_couche(d_tr, journal)
    _journal_couche(d_pt, journal)
    if not d_tr.existe or d_tr.manquants:
        raise ErreurTraitement("Traitement arrêté avant toute écriture : tronçons locaux introuvables "
                               "ou champs absents ({0})".format(", ".join(d_tr.manquants)))

    histos = []
    for couche in couches_histo or []:
        d_h = referentiel.decrire_couche(couche, "Couche historique", comparaison_sections.CHAMPS_HISTO_REQUIS)
        _journal_couche(d_h, journal)
        if d_h.existe and not d_h.manquants:
            histos.append((couche, d_h))
        else:
            journal.avertissement("Couche historique ignorée pour la comparaison : {0}".format(couche))

    # 3. Lecture ------------------------------------------------------------
    corr_tr = d_tr.correspondance
    lignes_tr = referentiel.lire_lignes(couche_troncons, list(corr_tr.values()), geometrie=True,
                                        epsg=referentiel.EPSG_SORTIE)
    reseau = Reseau.depuis_lignes(lignes_tr, corr_tr)
    journal.info("Tronçons lus : {0} | utilisables : {1} | écartés : {2}".format(
        len(lignes_tr), reseau.nb_troncons(), len(reseau.ecartes)))
    motifs: Dict[str, int] = {}
    for _ident, motif in reseau.ecartes:
        motifs[motif] = motifs.get(motif, 0) + 1
    for motif, n in sorted(motifs.items()):
        journal.info("  écartés — {0} : {1}".format(motif, n))
    doublons = {k: len(v) for k, v in reseau.par_id.items() if len(v) > 1}
    if doublons:
        journal.avertissement("{0} ID_INTERPLO en double dans le référentiel local".format(len(doublons)))

    points = None
    if d_pt.existe and not d_pt.manquants:
        corr_pt = referentiel.resoudre_champs(d_pt.noms_champs,
                                              CHAMPS_POINTS_ORIENTATION + CHAMPS_POINTS_OPTIONNELS)
        lignes_pt = referentiel.lire_lignes(couche_points, [v for v in corr_pt.values() if v])
        points = IndexPointsPR(lignes_pt, corr_pt)
        journal.info("Points PR lus : {0} ({1} tronçons avec points)".format(len(lignes_pt), len(points.points)))
    else:
        journal.avertissement("Points PR inexploitables : orientation des tronçons NON contrôlée")

    # 4. Reconstruction ---------------------------------------------------------
    journal.info("=== 3. Reconstruction des sections ===")
    resultats: List[ResultatSection] = []
    for n, info in enumerate(sections, 1):
        try:
            r = reconstruire_section(info, reseau, points, p)
        except Exception as exc:  # une section en erreur n'arrête pas le lot
            r = ResultatSection(info).echec(S_ERREUR, "{0} : {1}".format(
                type(exc).__name__, exc))
            journal.avertissement(traceback.format_exc(limit=3))
        resultats.append(r)
        texte = "{0:02d} | {1:<28} | {2} | {3} tronçon(s) | {4}".format(
            n, r.statut, info.nom_fichier, len(r.ids), ",".join(r.ids))
        (journal.info if r.est_candidat else journal.avertissement)(texte)
        if r.est_candidat:
            journal.info("     méthode {0} | LONG_REF_M {1:.3f} | LONG_GEOM_M {2:.3f}".format(
                r.methode, r.long_ref, r.long_geom))
        for o in r.observations:
            journal.avertissement("     " + o)
        for a in r.alertes:
            journal.info("     alerte : " + a)

    # 5. Sorties ------------------------------------------------------------
    journal.info("=== 4. Création des sorties ===")
    maintenant = datetime.datetime.now()
    bases = ["{0}_SECTIONS".format(prefixe), "CONTROLE_{0}_SECTIONS".format(prefixe),
             "TRONCONS_{0}_SECTIONS".format(prefixe)]
    if histos:
        bases.append("COMPARAISON_{0}_SECTIONS".format(prefixe))
    noms = sorties.noms_sorties_uniques(gdb_sortie, bases, arcpy.Exists, maintenant)
    fc, table, detail = noms[0], noms[1], noms[2]

    lignes = [r.en_dict(maintenant) for r in resultats]
    sorties.creer_classe_entites(fc, sorties.CHAMPS_SECTIONS, referentiel.EPSG_SORTIE)
    n_fc = sorties.inserer_entites(fc, sorties.CHAMPS_SECTIONS, [
        (l, geometrie.polyligne_arcpy(r.sommets, referentiel.EPSG_SORTIE))
        for l, r in zip(lignes, resultats) if r.est_candidat])
    sorties.creer_table(table, sorties.CHAMPS_SECTIONS)
    n_tab = sorties.inserer_lignes(table, sorties.CHAMPS_SECTIONS, lignes)
    sorties.creer_table(detail, sorties.CHAMPS_DETAIL_SECTIONS)
    n_det = sorties.inserer_lignes(detail, sorties.CHAMPS_DETAIL_SECTIONS,
                                   [l for r in resultats for l in r.lignes_detail(maintenant)])
    journal.info("Classe d'entités créée : {0} ({1} géométries)".format(fc, n_fc))
    journal.info("Table de contrôle créée : {0} ({1} lignes)".format(table, n_tab))
    journal.info("Table détaillée des tronçons créée : {0} ({1} lignes)".format(detail, n_det))
    resultat.update({"classe_entites": fc, "table_controle": table, "table_troncons": detail,
                     "resultats": resultats, "nb_geometries": n_fc})

    # 6. Comparaison --------------------------------------------------------
    if histos:
        journal.info("=== 5. Comparaison avec les couches historiques ===")
        resultat["comparaison"] = comparaison_sections.executer_comparaison(
            resultats, histos, noms[3], journal, maintenant)

    # Résumé ----------------------------------------------------------------
    s = synthese(resultats)
    resultat["synthese"] = s
    journal.info("=== Résumé ===")
    journal.info("PDF analysés : {0} | sections reconnues : {1}".format(s_pdf["TOTAL"], len(sections)))
    journal.info("Reconstructions candidates : {0} (dont {1} avec alertes)".format(
        s.get(CANDIDAT, 0), s["AVEC_ALERTES"]))
    journal.info("Parcours ambigus : {0} | recherches incomplètes : {1}".format(
        s.get(S_AMBIGU, 0), s.get(S_INCOMPLETE, 0)))
    echecs = sum(v for k, v in s.items() if k not in ("TOTAL", "AVEC_ALERTES", CANDIDAT))
    journal.info("Échecs (tous statuts hors candidat) : {0}".format(echecs))
    for code in sorted(k for k in s if k not in ("TOTAL", "AVEC_ALERTES")):
        journal.info("  {0} : {1}".format(code, s[code]))
    journal.info("Géométries écrites : {0}".format(n_fc))
    journal.info("Rappel : CANDIDAT_A_VALIDER n'est pas une validation métier.")
    return resultat

