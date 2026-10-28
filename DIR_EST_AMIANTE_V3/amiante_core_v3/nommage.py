# -*- coding: utf-8 -*-
"""Analyse des noms de fichiers PDF Amiante.

Module pur Python : aucune dépendance à arcpy. Il peut être testé hors
ArcGIS Pro.

Formats reconnus (insensibles à la casse, extension .pdf obligatoire) :

Section courante, même côté aux deux extrémités ::

    2023_NA_39_N0005_PR109500_PR110000_I.pdf
    ANNEE_STATUT_DEPT_ROUTE_PRdeb_PRfin_COTE

Section courante avec changement de côté ::

    2017_A_88_N0059_PR021500_G_PR025000_I.pdf
    ANNEE_STATUT_DEPT_ROUTE_PRdeb_COTEdeb_PRfin_COTEfin

Bretelle ::

    2023_NA_54A933040_3.pdf
    ANNEE_STATUT_ROUTEBRETELLE_NUMERO
    -> recherche INTERPLO : route = 54A933040, nomplodeb = DB3, nomplofin = FB3

Codage des PR : les trois derniers chiffres sont l'abscisse en mètres, les
chiffres précédents le numéro de PR (PR109500 -> PR 109 + 500 m). Aucune
conversion en distance cumulée n'est faite ici : l'écart entre deux PR n'est
pas forcément de 1 000 m, la longueur ne peut être calculée qu'à partir du
référentiel.
"""

from __future__ import annotations

import datetime
import os
import re
from typing import Dict, List, Optional

TYPE_SECTION = "SECTION"
TYPE_BRETELLE = "BRETELLE"
TYPE_NON_RECONNU = "NON_RECONNU"

STATUTS = {"A": "OUI", "NA": "NON"}  # A = amianté, NA = non amianté
COTES_VALIDES = ("D", "G", "I", "U")

NIVEAU_OK = "OK"
NIVEAU_AVERTISSEMENT = "AVERTISSEMENT"
NIVEAU_ERREUR = "ERREUR"

_RE_SECTION = re.compile(
    r"^(?P<annee>\d{4})_(?P<statut>NA|A)_(?P<dept>\d{2,3}|2A|2B)_"
    r"(?P<route>[A-Z]{1,2}\d{1,5}[A-Z]{0,2})_"
    r"PR(?P<pr_deb>\d{4,7})(?:_(?P<cote_deb>[DGIU]))?_"
    r"PR(?P<pr_fin>\d{4,7})_(?P<cote_fin>[DGIU])$"
)

_RE_BRETELLE = re.compile(
    r"^(?P<annee>\d{4})_(?P<statut>NA|A)_"
    r"(?P<route>(?=[0-9A-Z]*\d)[0-9A-Z]{4,20})_"
    r"(?P<num>\d{1,3})$"
)

# Motif d'aide au diagnostic : préfixe ANNEE_STATUT reconnu mais reste non conforme.
_RE_PREFIXE = re.compile(r"^(?P<annee>\d{4})_(?P<statut>NA|A)_")


class InfoPDF(object):
    """Résultat de l'analyse d'un nom de PDF."""

    def __init__(self, nom_fichier: str, chemin: str = "") -> None:
        self.nom_fichier = nom_fichier
        self.chemin = chemin
        self.type_pdf = TYPE_NON_RECONNU
        self.annee: Optional[int] = None
        self.statut: Optional[str] = None       # "A" ou "NA"
        self.amiante: Optional[str] = None      # "OUI" ou "NON"
        self.departement: Optional[str] = None
        self.route: Optional[str] = None
        # Sections
        self.pr_debut_txt: Optional[str] = None
        self.pr_debut: Optional[int] = None
        self.abs_debut: Optional[int] = None
        self.pr_fin_txt: Optional[str] = None
        self.pr_fin: Optional[int] = None
        self.abs_fin: Optional[int] = None
        self.cote_debut: Optional[str] = None
        self.cote_fin: Optional[str] = None
        self.changement_cote = False
        # Bretelles
        self.num_bretelle_txt: Optional[str] = None
        self.num_bretelle: Optional[int] = None
        self.nomplodeb_attendu: Optional[str] = None
        self.nomplofin_attendu: Optional[str] = None
        # Diagnostic
        self.messages: List[str] = []
        self.niveau = NIVEAU_OK

    # -- messages ---------------------------------------------------------
    def ajouter_message(self, niveau: str, texte: str) -> None:
        self.messages.append("[{0}] {1}".format(niveau, texte))
        ordre = {NIVEAU_OK: 0, NIVEAU_AVERTISSEMENT: 1, NIVEAU_ERREUR: 2}
        if ordre[niveau] > ordre[self.niveau]:
            self.niveau = niveau

    # -- propriétés dérivées ----------------------------------------------
    @property
    def cote_debut_controle(self) -> Optional[str]:
        return cote_pour_controle(self.cote_debut)

    @property
    def cote_fin_controle(self) -> Optional[str]:
        return cote_pour_controle(self.cote_fin)

    def cle_identite(self) -> Optional[str]:
        """Clé permettant de détecter deux PDF décrivant le même objet."""
        if self.type_pdf == TYPE_SECTION:
            return "S|{0}|{1}|{2}|{3}|{4}|{5}".format(
                self.departement, self.route, self.pr_debut_txt,
                self.cote_debut_controle, self.pr_fin_txt, self.cote_fin_controle)
        if self.type_pdf == TYPE_BRETELLE:
            return "B|{0}|{1}".format(self.route, self.num_bretelle)
        return None

    def en_dict(self) -> Dict[str, object]:
        return {
            "NOM_PDF": self.nom_fichier,
            "TYPE_PDF": self.type_pdf,
            "ANNEE": self.annee,
            "STATUT": self.statut,
            "AMIANTE": self.amiante,
            "DEPARTEMENT": self.departement,
            "ROUTE": self.route,
            "PR_DEBUT_TXT": self.pr_debut_txt,
            "PR_DEBUT": self.pr_debut,
            "ABS_DEBUT": self.abs_debut,
            "COTE_DEBUT": self.cote_debut,
            "PR_FIN_TXT": self.pr_fin_txt,
            "PR_FIN": self.pr_fin,
            "ABS_FIN": self.abs_fin,
            "COTE_FIN": self.cote_fin,
            "COTE_DEB_CTRL": self.cote_debut_controle,
            "COTE_FIN_CTRL": self.cote_fin_controle,
            "CHGT_COTE": "OUI" if self.changement_cote else "NON",
            "NUM_BRETELLE": self.num_bretelle,
            "NOMPLODEB_ATT": self.nomplodeb_attendu,
            "NOMPLOFIN_ATT": self.nomplofin_attendu,
            "NIVEAU_DIAG": self.niveau,
            "MESSAGES": " | ".join(self.messages),
        }

    def __repr__(self) -> str:
        return "InfoPDF({0!r}, type={1})".format(self.nom_fichier, self.type_pdf)


def cote_pour_controle(cote: Optional[str]) -> Optional[str]:
    """U est équivalent à I pour les contrôles."""
    if cote is None:
        return None
    cote = cote.upper()
    return "I" if cote == "U" else cote


def decouper_pr(pr_txt: str):
    """'109500' -> (109, 500) ; '45100' -> (45, 100)."""
    return int(pr_txt[:-3]), int(pr_txt[-3:])


def _verifier_annee(info: InfoPDF) -> None:
    annee_max = datetime.date.today().year + 1
    if info.annee is not None and not 1980 <= info.annee <= annee_max:
        info.ajouter_message(NIVEAU_AVERTISSEMENT,
                             "Année {0} hors plage plausible".format(info.annee))


def analyser_nom_pdf(nom_fichier: str, chemin: str = "") -> InfoPDF:
    """Analyse un nom de fichier et renvoie un InfoPDF (jamais d'exception)."""
    info = InfoPDF(nom_fichier, chemin)
    base, ext = os.path.splitext(nom_fichier.strip())
    if ext.lower() != ".pdf":
        info.ajouter_message(NIVEAU_ERREUR, "Extension non PDF : '{0}'".format(ext))
        return info

    nom = base.strip().upper()
    if base != base.strip():
        info.ajouter_message(NIVEAU_AVERTISSEMENT, "Espaces en début/fin de nom")

    m = _RE_SECTION.match(nom)
    if m:
        _remplir_section(info, m)
        return info

    m = _RE_BRETELLE.match(nom)
    if m:
        _remplir_bretelle(info, m)
        return info

    m = _RE_PREFIXE.match(nom)
    if m:
        info.annee = int(m.group("annee"))
        info.statut = m.group("statut")
        info.amiante = STATUTS[info.statut]
        info.ajouter_message(
            NIVEAU_ERREUR,
            "Préfixe ANNEE_STATUT reconnu mais structure non conforme aux "
            "formats section ou bretelle")
    else:
        info.ajouter_message(NIVEAU_ERREUR, "Nom non conforme (ANNEE_A|NA_... attendu)")
    return info


def _remplir_section(info: InfoPDF, m) -> None:
    info.type_pdf = TYPE_SECTION
    info.annee = int(m.group("annee"))
    info.statut = m.group("statut")
    info.amiante = STATUTS[info.statut]
    info.departement = m.group("dept")
    info.route = m.group("route")
    info.pr_debut_txt = m.group("pr_deb")
    info.pr_fin_txt = m.group("pr_fin")
    info.pr_debut, info.abs_debut = decouper_pr(info.pr_debut_txt)
    info.pr_fin, info.abs_fin = decouper_pr(info.pr_fin_txt)
    info.cote_fin = m.group("cote_fin")
    info.cote_debut = m.group("cote_deb") or info.cote_fin
    info.changement_cote = info.cote_debut_controle != info.cote_fin_controle

    _verifier_annee(info)
    for etiquette, txt in (("début", info.pr_debut_txt), ("fin", info.pr_fin_txt)):
        if len(txt) != 6:
            info.ajouter_message(
                NIVEAU_AVERTISSEMENT,
                "PR {0} codé sur {1} chiffres ('{2}') au lieu de 6".format(
                    etiquette, len(txt), txt))
    for etiquette, absc in (("début", info.abs_debut), ("fin", info.abs_fin)):
        if absc >= 1000:  # impossible avec 3 chiffres, garde-fou
            info.ajouter_message(NIVEAU_ERREUR, "Abscisse {0} invalide".format(etiquette))

    pos_deb = (info.pr_debut, info.abs_debut)
    pos_fin = (info.pr_fin, info.abs_fin)
    if pos_deb == pos_fin:
        info.ajouter_message(NIVEAU_ERREUR, "PR début et PR fin identiques")
    elif pos_deb > pos_fin:
        info.ajouter_message(NIVEAU_AVERTISSEMENT,
                             "PR début supérieur au PR fin (sens décroissant ?)")
    if info.changement_cote:
        info.ajouter_message(
            NIVEAU_AVERTISSEMENT,
            "Changement de côté {0} -> {1} : reconstruction à vérifier".format(
                info.cote_debut, info.cote_fin))
    if "U" in (info.cote_debut, info.cote_fin):
        info.ajouter_message(NIVEAU_OK, "Côté U traité comme I pour les contrôles")


def _remplir_bretelle(info: InfoPDF, m) -> None:
    info.type_pdf = TYPE_BRETELLE
    info.annee = int(m.group("annee"))
    info.statut = m.group("statut")
    info.amiante = STATUTS[info.statut]
    info.route = m.group("route")
    info.num_bretelle_txt = m.group("num")
    info.num_bretelle = int(info.num_bretelle_txt)
    # Numéro sans zéro non significatif : 03 -> DB3 / FB3
    info.nomplodeb_attendu = "DB{0}".format(info.num_bretelle)
    info.nomplofin_attendu = "FB{0}".format(info.num_bretelle)
    m_dep = re.match(r"^(\d{2})[A-Z]", info.route)
    if m_dep:
        # Information indicative : non utilisée pour la recherche INTERPLO.
        info.departement = m_dep.group(1)
    _verifier_annee(info)
    if info.num_bretelle_txt != str(info.num_bretelle):
        info.ajouter_message(
            NIVEAU_AVERTISSEMENT,
            "Numéro de bretelle avec zéro non significatif ('{0}') : "
            "recherche avec DB{1}/FB{1}".format(info.num_bretelle_txt, info.num_bretelle))


def lister_pdf(dossier: str) -> List[str]:
    """Liste triée des fichiers .pdf (non récursif) d'un dossier."""
    if not os.path.isdir(dossier):
        raise IOError("Dossier introuvable : {0}".format(dossier))
    return sorted(
        f for f in os.listdir(dossier)
        if os.path.isfile(os.path.join(dossier, f)) and f.lower().endswith(".pdf"))


def lister_autres_fichiers(dossier: str) -> List[str]:
    """Fichiers ignorés (non PDF) du dossier, pour information."""
    return sorted(
        f for f in os.listdir(dossier)
        if os.path.isfile(os.path.join(dossier, f)) and not f.lower().endswith(".pdf"))


def analyser_dossier(dossier: str) -> List[InfoPDF]:
    """Analyse tous les PDF d'un dossier et signale les doublons potentiels."""
    infos = [analyser_nom_pdf(f, os.path.join(dossier, f)) for f in lister_pdf(dossier)]
    signaler_doublons(infos)
    return infos


def signaler_doublons(infos: List[InfoPDF]) -> None:
    """Deux PDF décrivant le même objet (année ou statut différents) -> avertissement."""
    groupes: Dict[str, List[InfoPDF]] = {}
    for info in infos:
        cle = info.cle_identite()
        if cle:
            groupes.setdefault(cle, []).append(info)
    for groupe in groupes.values():
        if len(groupe) < 2:
            continue
        statuts = set(i.statut for i in groupe)
        for info in groupe:
            autres = ", ".join(i.nom_fichier for i in groupe if i is not info)
            texte = "Doublon potentiel avec : {0}".format(autres)
            if len(statuts) > 1:
                texte += " (statuts A et NA contradictoires)"
            info.ajouter_message(NIVEAU_AVERTISSEMENT, texte)


def synthese(infos: List[InfoPDF]) -> Dict[str, int]:
    """Comptages par type, statut et niveau de diagnostic."""
    res = {
        "TOTAL": len(infos),
        TYPE_SECTION: 0, TYPE_BRETELLE: 0, TYPE_NON_RECONNU: 0,
        "AMIANTE": 0, "NON_AMIANTE": 0, "CHGT_COTE": 0,
        NIVEAU_OK: 0, NIVEAU_AVERTISSEMENT: 0, NIVEAU_ERREUR: 0,
    }
    for i in infos:
        res[i.type_pdf] += 1
        res[i.niveau] += 1
        if i.statut == "A":
            res["AMIANTE"] += 1
        elif i.statut == "NA":
            res["NON_AMIANTE"] += 1
        if i.changement_cote:
            res["CHGT_COTE"] += 1
    return res
