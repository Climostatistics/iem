"""Hourly temperature frequencies."""
import datetime
import calendar

import numpy as np
from pandas.io.sql import read_sql
import matplotlib.colors as mpcolors
from pyiem.network import Table as NetworkTable
from pyiem.plot.use_agg import plt
from pyiem.util import get_autoplot_context, get_dbconn

PDICT = {'above': 'At or Above Threshold',
         'below': 'Below Threshold'}
PDICT2 = {'tmpf': "Air Temperature",
          'dwpf': "Dew Point Temp"}


def get_description():
    """ Return a dict describing how to call this plotter """
    desc = dict()
    desc['cache'] = 86400
    desc['description'] = """This plot presents the hourly frequency of having
    a certain temperature above or below a given threshold.  Values are
    partitioned by week of the year to smooth out some of the day to day
    variation."""
    desc['data'] = True
    desc['arguments'] = [
        dict(type='zstation', name='zstation', default='DSM',
             network='IA_ASOS', label='Select Station:'),
        dict(type='select', name='var', default='tmpf', options=PDICT2,
             label='Which Variable:'),
        dict(type='int', name='threshold', default=32,
             label='Temperature Threshold (F)'),
        dict(type='select', name='direction', default='below',
             label='Threshold direction:', options=PDICT),
    ]
    return desc


def plotter(fdict):
    """ Go """
    pgconn = get_dbconn('asos')

    ctx = get_autoplot_context(fdict, get_description())
    station = ctx['zstation']
    network = ctx['network']
    threshold = ctx['threshold']
    direction = ctx['direction']
    varname = ctx['var']

    nt = NetworkTable(network)

    mydir = "<" if direction == 'below' else '>='

    df = read_sql("""
    WITH data as (
 SELECT extract(week from valid) as week,
 extract(hour from (valid + '10 minutes'::interval) at time zone %s) as hour,
 """ + varname + """ as d from alldata where
      station = %s and """ + varname + """ between -70 and 140
    )
    SELECT week::int, hour::int,
    sum(case when d """+mydir+""" %s then 1 else 0 end),
    count(*) from data GROUP by week, hour
    """, pgconn, params=(nt.sts[station]['tzname'], station, threshold),
                  index_col=None)
    data = np.zeros((24, 53), 'f')
    df['freq[%]'] = df['sum'] / df['count'] * 100.
    for _, row in df.iterrows():
        data[int(row['hour']), int(row['week']) - 1] = row['freq[%]']

    sts = datetime.datetime(2012, 1, 1)
    xticks = []
    for i in range(1, 13):
        ts = sts.replace(month=i)
        xticks.append(float(ts.strftime("%j")) / 7.0)

    (fig, ax) = plt.subplots(1, 1)
    cmap = plt.get_cmap('jet')
    cmap.set_under('white')
    bins = np.arange(0, 101, 5)
    bins[0] = 1
    norm = mpcolors.BoundaryNorm(bins, cmap.N)
    res = ax.imshow(data, interpolation='nearest', aspect='auto',
                    extent=[0, 53, 24, 0], cmap=cmap, norm=norm)
    fig.colorbar(res, label='%', extend='min')
    ax.grid(True, zorder=11)
    ax.set_title(r"%s [%s]\nHourly %s %s %s$^\circ$F (%s-%s)" % (
                nt.sts[station]['name'], station, PDICT2[varname],
                PDICT[direction], threshold,
                nt.sts[station]['archive_begin'].year,
                datetime.datetime.now().year), size=12)

    ax.set_xticks(xticks)
    ax.set_ylabel("%s Timezone" % (nt.sts[station]['tzname'],))
    ax.set_xticklabels(calendar.month_abbr[1:])
    ax.set_xlim(0, 53)
    ax.set_ylim(0, 24)
    ax.set_yticks([0, 4, 8, 12, 16, 20, 24])
    ax.set_yticklabels(['12 AM', '4 AM', '8 AM', 'Noon', '4 PM', '8 PM',
                        'Mid'])

    return fig, df


if __name__ == '__main__':
    plotter(dict())
