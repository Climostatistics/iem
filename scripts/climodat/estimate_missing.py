"""Crude estimator of IEM Climate Stations

This is only run for the exceptions, when data is marked as missing for some
reason.  The main data estimator is found at `daily_estimator.py`.

This script utilizes the IEMRE web service to provide data.
"""
from __future__ import print_function
import sys

import requests
import pandas as pd
from pandas.io.sql import read_sql
from pyiem.network import Table as NetworkTable
from pyiem.util import get_dbconn

URI = (
    "http://iem.local/iemre/multiday/"
    "%(sdate)s/%(edate)s/%(lat)s/%(lon)s/json"
)


def process(cursor, station, df, meta):
    """do work for this station."""
    prefix = "daily" if meta["precip24_hour"] not in range(4, 11) else "12z"
    sdate = df["day"].min()
    edate = df["day"].max()
    wsuri = URI % {
        "sdate": "%s-%02i-%02i" % (sdate.year, sdate.month, sdate.day),
        "edate": "%s-%02i-%02i" % (edate.year, edate.month, edate.day),
        "lon": meta["lon"],
        "lat": meta["lat"],
    }
    req = requests.get(wsuri)
    if req.status_code != 200:
        print("%s got status %s" % (wsuri, req.status_code))
        return
    try:
        estimated = pd.DataFrame(req.json()["data"])
    except Exception as exp:
        print(
            ("\n%s Failure:%s\n%s\nExp: %s")
            % (station, req.content, wsuri, exp)
        )
        return
    estimated["date"] = pd.to_datetime(estimated["date"])
    estimated.set_index("date", inplace=True)
    for _, row in df.iterrows():
        newvals = row.to_dict()
        for col in ["high", "low", "precip"]:
            units = "f" if col != "precip" else "in"
            if not pd.isna(row[col]):
                continue
            if (
                col == "precip"
                and prefix == "12z"
                and not pd.isna(estimated.loc[row["day"]]["prism_precip_in"])
            ):
                newvals["precip"] = estimated.loc[row["day"]][
                    "prism_precip_in"
                ]
            else:
                newvals[col] = estimated.loc[row["day"]][
                    "%s_%s_%s" % (prefix, col, units)
                ]
        if None in newvals.values():
            print(
                "Skipping %s as there are missing values still" % (row["day"],)
            )
            continue
        print(
            ("Set station: %s day: %s high: %.0f low: %.0f precip: %.2f")
            % (
                station,
                row["day"],
                newvals["high"],
                newvals["low"],
                newvals["precip"],
            )
        )
        sql = """
            UPDATE alldata_%s SET estimated = true,
            high = %.0f, low = %.0f, precip = %.2f WHERE
            station = '%s' and day = '%s'
            """ % (
            station[:2],
            newvals["high"],
            newvals["low"],
            newvals["precip"],
            station,
            row["day"],
        )
        cursor.execute(sql.replace("nan", "null"))


def main(argv):
    """Go Main Go"""
    state = argv[1]
    nt = NetworkTable("%sCLIMATE" % (state,))
    pgconn = get_dbconn("coop")
    df = read_sql(
        """
        SELECT station, year, day, high, low, precip
        from alldata_"""
        + state
        + """
        WHERE (high is null or low is null or precip is null) and year >= 1893
        ORDER by station, day
    """,
        pgconn,
        index_col=None,
    )
    print("Processing %s rows for %s" % (len(df.index), state))
    for (_year, station), gdf in df.groupby(["year", "station"]):
        if station not in nt.sts:
            print("station %s is unknown, skipping..." % (station,))
            continue
        cursor = pgconn.cursor()
        process(cursor, station, gdf, nt.sts[station])
        cursor.close()
        pgconn.commit()


if __name__ == "__main__":
    main(sys.argv)
