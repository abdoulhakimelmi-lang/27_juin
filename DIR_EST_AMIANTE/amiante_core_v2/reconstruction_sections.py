# -*- coding: utf-8 -*-
"""Reconstruction des géométries des sections courantes.

PHASE 3 — NON IMPLÉMENTÉ.

Ce moteur sera écrit à partir des scripts historiques V6A, V6C et V7B. Aucune
règle d'enchaînement de tronçons (logiques DF / FF, LOGIQUE_2 / LOGIQUE_3,
changements de côté, tronçons communs codés D) n'est inventée ici.

Principe imposé : tout parcours ambigu (plusieurs enchaînements possibles)
est signalé et n'est jamais accepté automatiquement.
"""

from __future__ import annotations


def reconstruire_section(*args, **kwargs):
    raise NotImplementedError(
        "Reconstruction des sections non disponible : attend les scripts "
        "historiques V6A / V6C / V7B (phase 3).")
