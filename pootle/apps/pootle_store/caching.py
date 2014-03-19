#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2013 Zuza Software Foundation
#
# This file is part of Pootle.
#
# Pootle is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# Pootle is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# Pootle; if not, see <http://www.gnu.org/licenses/>.

"""
Caching functionality for Unit model
"""

from hashlib import md5

from translate.storage.statsdb import wordcount
from pootle.core.mixins import CachedMethods

from .util import OBSOLETE, UNTRANSLATED, FUZZY, TRANSLATED


def count_words(strings):
    return sum(wordcount(string) for string in strings)


def unit_update_cache(unit):
    """
    Triggered on unit.save() before anything is saved
    """

    if unit.id:
        orig = unit.__class__.objects.get(id=unit.id)
    else:
        orig = None
        unit.store.flag_for_deletion(CachedMethods.TOTAL)

    source_wordcount = count_words(unit.source_f.strings)
    target_wordcount = count_words(unit.target_f.strings)

    if not orig:
        # New instance. Calculate everything.
        unit.store.total_wordcount += source_wordcount
        if unit.state == TRANSLATED:
            unit.store.translated_wordcount += source_wordcount
        elif unit.state == FUZZY:
            unit.store.fuzzy_wordcount += source_wordcount

    if unit._source_updated:
        # update source related fields
        unit.source_hash = md5(unit.source_f.encode("utf-8")).hexdigest()
        difference = source_wordcount - unit.source_wordcount
        unit.store.total_wordcount += difference
        unit.source_wordcount = source_wordcount
        unit.source_length = len(unit.source_f)
        if not orig:
            unit.store.total_wordcount += difference

    if orig and unit._target_updated:
        # update target related fields
        unit.target_wordcount = target_wordcount

        # Case 1: Unit was not translated before
        if orig.state == UNTRANSLATED:
            if unit.state == UNTRANSLATED:
                pass
            elif unit.state == FUZZY:
                unit.store.fuzzy_wordcount += source_wordcount
            elif unit.state == TRANSLATED:
                unit.store.translated_wordcount += source_wordcount

        # Case 2: Unit was fuzzy before
        elif orig.state == FUZZY:
            if unit.state == UNTRANSLATED:
                unit.store.fuzzy_wordcount -= source_wordcount
            elif unit.state == FUZZY:
                unit.store.fuzzy_wordcount += difference
            elif unit.state == TRANSLATED:
                unit.store.fuzzy_wordcount -= source_wordcount
                unit.store.translated_wordcount += source_wordcount

        # Case 3: Unit was translated before
        elif orig.state == TRANSLATED:
            if unit.state == UNTRANSLATED:
                unit.store.translated_wordcount -= source_wordcount
            elif unit.state == FUZZY:
                unit.store.translated_wordcount -= source_wordcount
                unit.store.fuzzy_wordcount += source_wordcount
            elif unit.state == TRANSLATED:
                unit.store.translated_wordcount += difference

        unit.store.save()

        unit.target_length = len(unit.target_f)
        unit.store.flag_for_deletion(CachedMethods.LAST_ACTION,
                                        CachedMethods.PATH_SUMMARY)
        if filter(None, unit.target_f.strings):
            if unit.state == UNTRANSLATED:
                unit.state = TRANSLATED
                unit.store.flag_for_deletion(CachedMethods.TRANSLATED)
        # if it was TRANSLATED then set to UNTRANSLATED
        elif unit.state > FUZZY:
            unit.state = UNTRANSLATED
            unit.store.flag_for_deletion(CachedMethods.TRANSLATED)