# -*- coding: utf-8 -*-
# Copyright © 2011-2013 Binet Réseau
# See the LICENCE file for more informations

from .common import unittest, get_local_conf


class BasicTestCase(unittest.TestCase):

    def test_config(self):
        config = get_local_conf()
        self.assertTrue(config is not None)
