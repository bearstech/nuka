import os
import sys
import codecs
from nuka.task import Task
from nuka.utils import json
from nuka.utils import import_module


class setup(Task):

    @classmethod
    def get_inventory(self):
        modules = [m.split('=')[1] for m in sys.argv
                   if m.startswith('--inventory=')]
        modules.insert(0, 'nuka.inventory.python')

        inventory = {}
        done = set()
        for name in modules:
            if name not in done:
                done.add(name)
                mod = import_module(name)
                meth = getattr(mod, 'update_inventory', None)
                if meth is not None:
                    meth(inventory)
        return {'inventory': inventory}

    def do(self):
        dirname = os.path.dirname(sys.argv[0])
        cache = os.path.join(dirname, 'inventory.json')
        data = self.get_inventory()
        with codecs.open(cache, 'w') as fd:
            json.dump(data, fd)
        return data
