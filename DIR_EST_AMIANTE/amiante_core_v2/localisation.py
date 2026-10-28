# -*- coding: utf-8 -*-
"""Localisation des extrémités des sections sur le référentiel.

PHASE 3 — NON IMPLÉMENTÉ.

Rôle prévu :
- retrouver, pour une route / un côté / un PR+abscisse, le tronçon de
  REF_INTERPLO_TRONCONS_V1_CORRIGE qui contient la position ;
- contrôler la position à l'aide de REF_INTERPLO_POINTS_PR_V1.

Prérequis avant développement :
- liste exacte des champs de REF_INTERPLO_POINTS_PR_V1 (à relever sur le VDI
  avec le mode DIAGNOSTIC, qui affiche tous les champs de la couche) ;
- règles de calcul issues des scripts historiques V6A / V6C / V7B
  (usage de ABS_DEBUT / ABS_FIN / CUMUL_DEBUT / CUMUL_FIN et des logiques).
"""

from __future__ import annotations


def localiser_position(*args, **kwargs):
    raise NotImplementedError(
        "Localisation PR non disponible : attend les champs de la couche "
        "points PR et les scripts historiques (phase 3).")
