# Copyright 2017 by Bearstech <py@bearstech.com>
#
# This file is part of nuka.
#
# nuka is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# nuka is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with nuka. If not, see <http://www.gnu.org/licenses/>.

import os
import sys
from uuid import uuid4
from operator import itemgetter
from collections import defaultdict

import jinja2

import nuka
from nuka.utils import json
from nuka.task import teardown


def round_dict(d):
    for k, v in list(d.items()):
        if isinstance(v, float):
            d[k + '_str'] = str(round(v, 1))
    return d


class Item(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self['uid'] = str(uuid4()).replace('-', '')

    def __getattr__(self, attr):
        return self[attr]


def get_report_data(host):

    all_tasks = {}
    subtasks = defaultdict(list)
    for t in host._task_times:
        task = t['task']
        if not task.cancelled():
            if t['type'] == 'task':
                all_tasks[id(t['task'])] = t
            else:
                subtasks[id(t['task'])].append(t)
    if not all_tasks:  # pragma: no cover
        return

    all_tasks = sorted(all_tasks.values(), key=itemgetter('start'))

    stats = {}

    _start = all_tasks[0]['start']

    tasks = []
    for row, task_dict in enumerate(all_tasks):
        row += 1
        task = task_dict['task']
        m = task_dict
        local_time = m['time']
        task_name = task.__class_name__()

        stat = stats.setdefault(
            task_name,
            {'name': task_name, 'calls': 0,
             'time': 0, 'remote_time': 0})
        stat['calls'] += 1
        stat['time'] += local_time
        stat['remote_time'] += m.get('remote_time', 0.)

        name = '{0}({1})'.format(
                task_name,
                task.args.get('name', repr(task.args))
        )
        t = Item(
            type="task",
            name=jinja2.escape(name),
            short_name=task_name.replace('nuka.tasks.', ''),
            start=(m['start'] - _start),
            time=local_time,
            rc=task.res.get('rc', 0),
            row=row,
            filename=m['filename'],
            lineno=m['lineno'],
            funcs=[],
            remote_calls=[],
        )
        tasks.append(round_dict(t))

        subs = sorted(subtasks[id(task)], key=itemgetter('start'))
        sh_start = None
        for item in subs:
            if item['type'] == 'api_call':
                name = item['name']
            elif item['type'] == 'pre_process':
                name = 'pre_process()'
            elif item['type'] == 'post_process':
                name = 'post_process()'
                item['type'] == 'pre_process'
            else:
                cmd = ' '.join(item['cmd'])
                if nuka.config['script'] in cmd:
                    cmd = 'nuka/script.py'
                name = 'subprocess({0})'.format(cmd)
            func = Item(
                name=name,
                type=item['type'],
                start=(item['start'] - _start),
                time=item['time'],
                parent=t.uid,
                latency=item.get('latency'),
                remote_calls=[],
            )
            if 'meta' in item:
                sh_start = func['start'] + item['latency']
                shs = item['meta']['remote_calls']
                for sh in shs:
                    tsh = Item(
                        type="sh",
                        start=sh_start,
                        name='sh({0})'.format(sh['cmd']),
                        time=sh['time'],
                        parent=t.uid,
                        rc=sh['rc'],
                    )
                    func['remote_calls'].append(round_dict(tsh))
                    sh_start += tsh.time
            t['funcs'].append(round_dict(func))

    _end = all_tasks[-1]
    _real_end = _end
    i = 1
    while isinstance(_real_end['task'], teardown):
        i += 1
        try:
            _real_end = all_tasks[-i]
        except IndexError:
            _real_end = _end
            break

    for k, v in stats.items():
        v['avg_time'] = v['time'] / v['calls']
        v['avg_remote_time'] = v['remote_time'] / v['calls']
        for kk, vv in v.items():
            if isinstance(vv, float):
                v[kk] = '%.3f' % vv
    stats = sorted(stats.values(),
                   key=itemgetter('remote_time'),
                   reverse=True)

    data = {
        'host': host.name,
        'tasks': tasks,
        'stats': stats,
        'total_time': _end['start'] + _end['time'] - _start,
        'real_time': _real_end['start'] + _real_end['time'] - _start,
    }
    return data


def build_reports(hosts):
    hosts_data = {}
    for host in hosts:
        data = get_report_data(host)
        if data:
            hosts_data[str(host)] = round_dict(data)

    if not hosts_data:
        return

    dirname = nuka.config['reports']['dirname']
    if not os.path.isdir(dirname):
        os.makedirs(dirname)

    data = {'hosts': hosts_data, 'total_time': 0}
    data['total_time'] = max([d['total_time'] for d in hosts_data.values()])
    data['total_tasks'] = max([len(d['tasks']) for d in hosts_data.values()])

    engine = nuka.config.get_template_engine()

    report_name = nuka.config['reports'].get('name')
    if report_name is None:
        filename = os.path.split(sys.argv[0])[-1]
        report_name = os.path.splitext(filename)[0]

    filename = os.path.join(dirname, '{0}.json'.format(report_name))
    dumped_data = json.dumps(data, indent=2)
    with open(filename, 'w') as fd:
        fd.write(dumped_data)

    ctx = dict(
        data=data,
        dumped_data=dumped_data,
    )

    filename = os.path.join(dirname, '{0}_gantt.html'.format(report_name))
    template = engine.get_template('reports/gantt.html.j2')
    with open(filename, 'w') as fd:
        fd.write(template.render(ctx))

    filename = os.path.join(dirname, '{0}_stats.html'.format(report_name))
    template = engine.get_template('reports/stats.html.j2')
    with open(filename, 'w') as fd:
        fd.write(template.render(ctx))


def run_dev_server():  # pragma: no cover
    """Usage: python -m nuka.report <type> <data_filename>"""
    from wsgiref.simple_server import make_server
    engine = nuka.config.get_template_engine()
    type, filename = sys.argv[-2:]

    def app(environ, start_response):
        start_response('200 OK',
                       [('Content-Type', 'text/html; charset=utf8')])
        template = engine.get_template('reports/{0}.html.j2'.format(type))
        with open(filename) as fd:
            data = json.load(fd)
        html = template.render(dict(data=data, dumped_data=json.dumps(data)))
        return [html.encode('utf8')]

    httpd = make_server('', 8000, app)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':  # pragma: no cover
    run_dev_server()
