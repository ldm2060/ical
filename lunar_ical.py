#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''get lunar calendar from hk observatory

Hong Kong Observatory has been very kind to grant the permission for using the
lunar calendar data from their website.

'''

__license__ = 'BSD'
__copyright__ = '2020, Chen Wei <weichen302@gmail.com>'
__version__ = '0.0.3'

from io import StringIO
from datetime import datetime
from datetime import timedelta
import getopt
import gzip
import os
import re
import sqlite3
import sys
import urllib.request
import zlib
from lunarcalbase import cn_lunarcal

APPDIR = os.path.abspath(os.path.dirname(__file__))
DB_FILE = os.path.join(APPDIR, 'db', 'lunarcal.sqlite')
RE_CAL = re.compile('(\d{4})年(\d{1,2})月(\d{1,2})日')
#PROXY = {'http': 'http://localhost:8001'}
PROXY = None
URL = 'https://www.hko.gov.hk/tc/gts/time/calendar/text/files/T%dc.txt'
OUTPUT = os.path.join(APPDIR, 'jq.ics')

ICAL_HEAD = ('BEGIN:VCALENDAR\n'
             'PRODID:-//Chen Wei//Chinese Lunar Calendar//EN\n'
             'VERSION:2.0\n'
             'X-PUBLISHED-TTL:PT24H\n'
             'REFRESH-INTERVAL;VALUE=DURATION:P24H\n'
             'CALSCALE:GREGORIAN\n'
             'METHOD:PUBLISH\n'
             'X-WR-CALNAME:24节气\n'
             'X-WR-TIMEZONE:Asia/Shanghai\n'
             'X-WR-CALDESC:中国农历1901-2100, 包括节气. 数据来自香港天文台')

ICAL_SEC = ('BEGIN:VEVENT\n'
            'CLASS:PUBLIC\n'
            'DTSTAMP:%s\n'
            'UID:%s\n'
            'DTSTART;VALUE=DATE:%s\n'
            'DTEND;VALUE=DATE:%s\n'
            'STATUS:CONFIRMED\n'
            'SUMMARY;LANGUAGE=zh-cn:%s\n'
            'TRANSP:OPAQUE\n'
            'END:VEVENT')

ICAL_END = 'END:VCALENDAR'

D_SOLARTERM = { '冬至' :  '冬至' ,  '小寒' :  '小寒' ,  '大寒' :  '大寒' ,
                '立春' :  '立春' ,  '雨水' :  '雨水' ,  '驚蟄' :  '惊蛰' ,
                '春分' :  '春分' ,  '清明' :  '清明' ,  '穀雨' :  '谷雨' ,
                '立夏' :  '立夏' ,  '小滿' :  '小满' ,  '芒種' :  '芒种' ,
                '夏至' :  '夏至' ,  '小暑' :  '小暑' ,  '大暑' :  '大暑' ,
                '立秋' :  '立秋' ,  '處暑' :  '处暑' ,  '白露' :  '白露' ,
                '秋分' :  '秋分' ,  '寒露' :  '寒露' ,  '霜降' :  '霜降' ,
                '立冬' :  '立冬' ,  '小雪' :  '小雪' ,  '大雪' :  '大雪' }

def initdb():
    try:
        print('creating db dir')
        os.mkdir(os.path.join(APPDIR, 'db'))
    except OSError:
        pass

    conn = sqlite3.connect(DB_FILE)
    db = conn.cursor()
    db.execute('''CREATE TABLE IF NOT EXISTS ical (
                    id INTEGER PRIMARY KEY,
                    date TEXT UNIQUE,
                    lunardate TEXT,
                    holiday TEXT,
                    jieqi TEXT)''')
    conn.commit()
    db.close()


def printjieqi():
    sql = 'select jieqi from ical where jieqi NOT NULL limit 28'
    res = query_db(sql)
    d = -75
    for row in res:
        print("%d: u'%s', " % (d, row[0]))
        d += 15


def query_db(query, args=(), one=False):
    ''' wrap the db query, fetch into one step '''
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    db = conn.cursor()
    cur = db.execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def parse_hko(pageurl):
    ''' parse lunar calendar from hk Obs
    Args: pageurl
    Return:
          a string contains all posts'''

    print('grabbing and parsing %s' % pageurl)
    with urllib.request.urlopen(pageurl) as f:
        html = f.read()
        lines = html.decode('big5').split('\n')

    sql_nojq = ('insert or replace into ical (date,lunardate) '
                'values(?,?) ')
    sql_jq = ('insert or replace into ical (date,lunardate,jieqi) '
              'values(?,?,?) ')
    conn = sqlite3.connect(DB_FILE)
    db = conn.cursor()
    for line in lines:
        m = RE_CAL.match(line)
        if m:
            fds = line.split()
            # add leading zero to month and day
            if len(m.group(2)) == 1:
                str_m = '0%s' % m.group(2)
            else:
                str_m = m.group(2)
            if len(m.group(3)) == 1:
                str_d = '0%s' % m.group(3)
            else:
                str_d = m.group(3)

            dt = '%s-%s-%s' % (m.group(1), str_m, str_d)
            if len(fds) > 3:  # last field is jieqi
                db.execute(sql_jq, (dt, fds[1], fds[3]))
            else:
                db.execute(sql_nojq, (dt, fds[1]))
    conn.commit()


def update_cal():
    ''' fetch lunar calendar from HongKong Obs, parse it and save to db'''
    for y in range(1901, 2101):
        parse_hko(URL % y)


def gen_cal(start, end, fp):
    ''' generate lunar calendar in iCalendar format.
    Args:
        start and end date in ISO format, like 2010-12-31
        fp: path to output file
    Return:
        none
        '''
    startyear = int(start[:4])
    endyear = int(end[:4])
    if startyear > 1900 and endyear < 3101:
        # use Lunar Calendar from HKO
        print('use Lunar Calendar from HKO')
        sql = ('select date, lunardate, holiday, jieqi from ical '
               'where date>=? and date<=? order by date')
        rows = query_db(sql, (start, end))
    else:
        # compute Lunar Calendar by astronomical algorithm
        print('compute Lunar Calendar by astronomical algorithm ')
        rows = []
        for year in range(startyear, endyear + 1):
            row = cn_lunarcal(year)
            rows.extend(row)

    lines = [ICAL_HEAD]
    oneday = timedelta(days=1)
    for r in rows:
        dt = datetime.strptime(r['date'], '%Y-%m-%d')
        ld = []
        if r['holiday']:
            ld.append(r['holiday'])
        if r['jieqi']:
            ld.append(r['jieqi'])
        uid = '%s-lc@infinet.github.io' % r['date']
        summary = ' '.join(ld)
        utcstamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        line = ICAL_SEC % (utcstamp, uid, dt.strftime('%Y%m%d'),
                       (dt + oneday).strftime('%Y%m%d'), summary)
        lines.append(line)
    lines.append(ICAL_END)
    outputf = open(fp, 'w')
    outputf.write('\n'.join(lines))
    outputf.close()
    print('iCal lunar calendar from %s to %s saved to %s' % (start, end, fp))


def gen_cal_jieqi_only(start, end, fp):
    ''' generate Jieqi and Traditional Chinese in iCalendar format.
    Args:
        start and end date in ISO format, like 2010-12-31
        fp: path to output file
    Return:
        none
        '''
    startyear = int(start[:4])
    endyear = int(end[:4])
    if startyear > 1900 and endyear < 2101:
        # use Lunar Calendar from HKO
        print('use Lunar Calendar from HKO')
        sql = ('select date, lunardate, holiday, jieqi from ical '
               'where date>=? and date<=? order by date')
        rows = query_db(sql, (start, end))
    else:
        # compute Lunar Calendar by astronomical algorithm
        print('compute Lunar Calendar by astronomical algorithm ')
        rows = []
        for year in range(startyear, endyear + 1):
            row = cn_lunarcal(year)
            rows.extend(row)

    lines = [ICAL_HEAD]
    oneday = timedelta(days=1)
    for r in rows:
        if not r['holiday'] and not r['jieqi']:
            continue

        ld = []
        if r['holiday']:
            ld.append(r['holiday'])
        if r['jieqi']:
            ld.append(D_SOLARTERM[r['jieqi']])
        uid = '%s-lc@infinet.github.io' % r['date']
        summary = ' '.join(ld)
        utcstamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        dt = datetime.strptime(r['date'], '%Y-%m-%d')
        line = ICAL_SEC % (utcstamp, uid, dt.strftime('%Y%m%d'),
                       (dt + oneday).strftime('%Y%m%d'), summary)
        lines.append(line)
    lines.append(ICAL_END)
    outputf = open(fp, 'w')
    outputf.write('\n'.join(lines))
    outputf.close()
    print('iCal Jieqi/Traditional Chinese holiday calendar from %s to %s saved to %s' % (start, end, fp))


def post_process():
    ''' there are several mistakes in HK OBS data, the following date
    do not have a valid lunar date, instead are the weekday names, they
    are all 三十 '''
    sql_update = 'update ical set lunardate=? where date=?'

    HK_ERROR = ('2036-01-27', '2053-12-09', '2056-03-15',
                '2063-07-25', '2063-10-21', '2063-12-19')
    conn = sqlite3.connect(DB_FILE)
    db = conn.cursor()
    for d in HK_ERROR:
        print('fix lunar date for %s' % d)
        db.execute(sql_update, ('三十', d))
    conn.commit()
CN_DAY = {'初二': 2, '初三': 3, '初四': 4, '初五': 5, '初六': 6,
          '初七': 7, '初八': 8, '初九': 9, '初十': 10, '十一': 11,
          '十二': 12, '十三': 13, '十四': 14, '十五': 15, '十六': 16,
          '十七': 17, '十八': 18, '十九': 19, '二十': 20, '廿一': 21,
          '廿二': 22, '廿三': 23, '廿四': 24, '廿五': 25, '廿六': 26,
          '廿七': 27, '廿八': 28, '廿九': 29, '三十': 30}
CN_MON = {'正月': 1, '二月': 2, '三月': 3, '四月': 4,
          '五月': 5, '六月': 6, '七月': 7, '八月': 8,
          '九月': 9, '十月': 10, '十一月': 11, '十二月': 12,

          '閏正月': 101, '閏二月': 102, '閏三月': 103, '閏四月': 104,
          '閏五月': 105, '閏六月': 106, '閏七月': 107, '閏八月': 108,
          '閏九月': 109, '閏十月': 110, '閏十一月': 111, '閏十二月': 112}
def update_holiday():
    ''' write chinese traditional holiday to db

    腊八节(腊月初八)     除夕(腊月的最后一天)     春节(一月一日)
    元宵节(一月十五日)   寒食节(清明的前一天)     端午节(五月初五)
    七夕节(七月初七)     中元节(七月十五日)       中秋节(八月十五日)
    重阳节(九月九日)     下元节(十月十五日)

    '''
    sql = 'select * from ical order by date'
    rows = query_db(sql)
    args = []
    m = None
    previd = None
    for r in rows:
        try:
            d = CN_DAY[r['lunardate']]
        except KeyError:
            #print 'debug: %s %s' % (r['date'], r['lunardate'])
            m = CN_MON[r['lunardate']]
            d = 1

        if not m:
            continue

        if m == 12 and d == 8:
            args.append((r['id'], '腊八'))
        elif m == 10 and d == 15:
            args.append((r['id'], '下元节'))
        if r['jieqi'] == '清明':
            args.append((previd, '寒食节'))
        previd = r['id']

    sql_update = 'update ical set holiday=? where id=?'
    conn = sqlite3.connect(DB_FILE)
    db = conn.cursor()
    for arg in args:
        db.execute(sql_update, (arg[1], arg[0]))
        print('update %s' % arg[1])
    conn.commit()
    print('Chinese Traditional Holiday updated')

def main():
    cy = datetime.today().year
    start = '%d-01-01' % (cy - 1)
    end = '%d-12-31' % (cy + 1)

    if not os.path.exists(DB_FILE):
        initdb()
        update_cal()
        post_process()  # fix error in HK data
        update_holiday()
    gen_cal_jieqi_only(start, end, OUTPUT)


def verify_lunarcalendar():
    ''' verify lunar calendar against data from HKO'''
    start = 1949
    sql = 'select date, lunardate,jieqi from ical where date>=? and date<=?'
    while start < 2101:
        print('compare %d' % start)
        ystart = '%d-01-01' % start
        yend = '%d-12-31' % start
        res = query_db(sql, (ystart, yend))
        hko = []
        for x in res:
            if x[2]:
                hko.append((x[0], '%s %s' % (x[1], x[2])))
            else:
                hko.append((x[0], x[1]))

        aalc = cn_lunarcal(start)
        for i in range(len(aalc)):
            aaday, aaldate = aalc[i]['date'], aalc[i]['lunardate']
            if aalc[i]['jieqi']:
                aaldate = '%s %s' % (aalc[i]['lunardate'], aalc[i]['jieqi'])
            hkoday, hkoldate = hko[i]
            #print aaday, aaldate
            if aaday != hkoday or aaldate != hkoldate:
                print('AA %s %s, HKO %s %s' % (aaday, aaldate, hkoday,
                                               hkoldate))
        start += 1


if __name__ == "__main__":
    main()
    #verify_lunarcalendar()
