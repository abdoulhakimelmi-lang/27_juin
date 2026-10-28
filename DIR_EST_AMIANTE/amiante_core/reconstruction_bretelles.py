# -*- coding: utf-8 -*-
"""Reconstruction des bretelles.

PHASE 2 — NON IMPLÉMENTÉ.

Méthode prévue (à valider avec le script historique V8D) :
1. Dans interPlo_pr_2026, chercher route = <route du PDF>,
   nomplodeb = DB<n>, nomplofin = FB<n>.
2. Exiger exactement une correspondance (0 -> AUCUN, >1 -> AMBIGU, jamais
   accepté automatiquement).
3. Retrouver la géométrie dans REF_INTERPLO_TRONCONS_V1_CORRIGE via
   l'identifiant INTERPLO, en VÉRIFIANT la concordance entre objetid
   (couche d'origine) et ID_INTERPLO (couche locale) — par exemple en
   comparant aussi la route — et en signalant toute anomalie.

Les nomplodeb / nomplofin attendus sont déjà calculés par
nommage.analyser_nom_pdf (attributs nomplodeb_attendu / nomplofin_attendu).
"""

from __future__ import annotations


def reconstruire_bretelle(*args, **kwargs):
    raise NotImplementedError(
        "Reconstruction des bretelles non disponible (phase 2).")
