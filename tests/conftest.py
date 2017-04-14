# -*- coding: utf-8 -*-
import os
from nuka import config

config['inventory_modules'].append('nuka.inventory.net')
config['templates'].append(os.path.join(
        os.path.dirname(__file__), 'templates'))
