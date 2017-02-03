# -*- coding: utf-8 -*-
import os
import inspect
import importlib
from operator import attrgetter

from nuka.task import Task
from nuka import config


def main():
    for root, dirnames, filenames in os.walk('nuka/tasks'):
        for filename in filenames:
            if not filename.endswith('.py'):
                continue
            elif filename.startswith('__'):
                continue

            name = filename[:-3]

            if name in ('setup',):
                continue

            module = 'nuka.tasks.{0}'.format(name)
            mod = importlib.import_module(module)

            # get all tasks from module
            tasks = []
            for k in mod.__dict__:
                if not k.startswith('_'):
                    v = getattr(mod, k, None)
                    try:
                        if issubclass(v, Task) and v.__module__ == module:
                            tasks.append(v)
                    except TypeError:
                        pass

            # extract test code if any
            test_module = 'tests.tasks.test_{0}'.format(name)
            try:
                test = importlib.import_module(test_module)
            except ImportError:
                test = None
                test_module = None
            else:
                test_module = 'test_{0}'.format(name)

            for task in tasks:
                task.test_module = test_module
                task.test = getattr(
                    test, 'test_' + task.__name__ + '_doc', None)
                if task.test:
                    task.test_source = ''.join(
                        inspect.getsourcelines(task.test)[0][2:])

            # compile template and save it to docs/tasks
            ctx = dict(
                tasks=sorted(tasks, key=attrgetter('__name__')),
                module=module,
            )
            engine = config.get_template_engine()
            template = engine.get_template('sphinx/task_module.j2')
            with open('docs/tasks/{0}.rst'.format(name), 'w') as fd:
                fd.write(template.render(ctx))


if __name__ == '__main__':
    main()
