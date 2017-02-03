# -*- coding: utf-8 -*-
import os
from nuka import config

config['templates'].append(os.path.join(
        os.path.dirname(__file__), 'templates'))
