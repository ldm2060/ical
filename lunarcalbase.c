#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include "astro.h"
#include "lunarcalbase.h"



/* solar term's angle + 120 / 15 */
static char *CN_SOLARTERM[] = {
    "Сѩ", "��ѩ", "����", "С��", "��", "����", "��ˮ", "�@�U",
    "����", "����", "�Y��", "����", "С�M", "â�N", "����", "С��",
    "����", "����", "̎��", "��¶", "���", "��¶", "˪��", "����",
    "Сѩ", "��ѩ", "����"
};



/* Traditional Chinese holiday */
static char *CN_HOLIDAY[] = {
    "����", "��Ϧ", "����", "Ԫ��", "��ʳ",
    "����", "��Ϧ", "��Ԫ", "����", "����", "��Ԫ",
};

static double newmoons[MAX_NEWMOONS];
static struct solarterm solarterms[MAX_SOLARTERMS];
static int nm_before_ws_index;

static struct lunarcal_cache *cached_lcs[CACHESIZE];
static int cache_initialized = 0;  /* flag for initialized cache */
static int cachep = 0;  /* next free location in cache */
static int rewinded = 0;  /* cache rewinded? free pointers */


/* normalize Julian Day to midnight after adjust timezone and deltaT */
double normjd(double jd, double tz)
{
    double deltat, tmp, jd_i, jd_f;
    GregorianDate g;
    g = jd2g(jd);
    deltat = deltaT(g.year, g.month);
    tmp = jd + (tz * 3600.0 - deltat) / 86400.0;
    g = jd2g(tmp);
    jd_f = modf(tmp, &jd_i);
    if (jd_f >= 0.5)
        jd = jd_i + 0.5;
    else
        jd = jd_i - 0.5;
    return jd;
}


/* initialize cache storage */
void init_cache(void)
{
    int i;
    struct lunarcal_cache *p;

    if (cache_initialized)
        return;

    for (i = 0; i < CACHESIZE; i++) {
        p = (struct lunarcal_cache *) malloc(sizeof(struct lunarcal_cache));
        memset(p, 0, sizeof(struct lunarcal_cache));
        p->year = -1;
        p->len = -1;
        cached_lcs[i] = p;
    }

    cache_initialized = 1;
}


void cn_lunarcal(int year)
{
    int i, k, len1, len2;
    double ystart, yend;
    struct lunarcal *thisyear[MAX_DAYS];
    struct lunarcal *nextyear[MAX_DAYS];
    struct lunarcal *output[MAX_DAYS];

    init_cache();
    len1 = get_cached_lc(thisyear, MAX_DAYS, year);
    len2 = get_cached_lc(nextyear, MAX_DAYS, year + 1);

    /*
     * Luncar calendar calculated above starts at Lunar calendar month 11, day
     * 1 of previous Gregorian year. Because Leapmonth close to the end of
     * Gregorian year can only be found by compute Lunar calendar of the next
     * year, merge lunar calendars from this and next year results the lunar
     * calendar for this Gregorian year.
     */
    ystart = g2jd(year, 1, 1.0);
    yend = g2jd(year, 12, 31.0);
    k = 0;
    /*
     * lunar calendar after this lunar calendar month 11, day 1 shall come from
     * lc of next year
     */
    for (i = 0; i < len1; i++) {
        if (thisyear[i]->jd == nextyear[0]->jd)
            break;

        if (thisyear[i]->jd >= ystart)
            output[k++] = thisyear[i];
    }

    for (i = 0; k < MAX_DAYS && i < len2 && nextyear[i]->jd <= yend; k++, i++)
        output[k] = nextyear[i];

    print_lunarcal(output, k);
}


int get_cache_index(int year)
{
    int i;

    for (i = 0; i < CACHESIZE; i++)
        if (cached_lcs[i]->year == year)
            return i;

    return -1;
}


int get_cached_lc(struct lunarcal *lcs[], int len, int year)
{
    int i, k, lc_days;

    for (i = 0; i < len; i++)
        lcs[i] = NULL;

    if ((k = get_cache_index(year)) != -1) {
        for (i = 0; i < cached_lcs[k]->len; i++)
            lcs[i] = cached_lcs[k]->lcs[i];

        return cached_lcs[k]->len;
    }

    /* not in cache, generate a new lunar calendar */
    lc_days = gen_lunar_calendar(lcs, len, year);

    add_cache(lcs, lc_days);

    return lc_days;
}


void add_cache(struct lunarcal *lcs[], int len)
{
    int i;
    struct lunarcal_cache *p;

    if (cachep >= CACHESIZE) {
        cachep = 0;
        rewinded = 1;
    }

    p = cached_lcs[cachep];
    if (rewinded)
        for (i = 0; i < p->len; i++)
            free(p->lcs[i]);

    for (i = 0; i < len; i++)
        p->lcs[i] = lcs[i];

    /* the first day in lcs is lc month 11, day 1 of previous lc year */
    p->year = lcs[0]->lyear + 1;
    p->len = len;
    cachep++;
}


/* find all solarterms and newmoons related to this years lc */
void update_solarterms_newmoons(int year)
{
    int i;
    double jd_nm, est_nm;
    int start_solarterm_lon = -120;  /* Сѩ of last year */

    /* search solar terms start from Сѩ of last year */
    for (i = 0; i < MAX_SOLARTERMS; i++) {
        solarterms[i].longitude = start_solarterm_lon + i * 15;
        solarterms[i].jd = normjd(
                            solarterm(year, (double) solarterms[i].longitude),
                            TZ_CN);
    }

    /* search 15 newmoons start 30 days before last Winter Solstice */
    est_nm = solarterms[2].jd - 30;
    for (i = 0; i < MAX_NEWMOONS; i++) {
        jd_nm = newmoon(est_nm);
        newmoons[i] = normjd(jd_nm, TZ_CN);
        est_nm = jd_nm + SYNODIC_MONTH;
    }
}


/* mark year, month and day number, plus solarterms and holiday */
int gen_lunar_calendar(struct lunarcal *lcs[], int len, int year)
{
    int i, k, m, n;
    int leapmonth, lyear, month;
    int is_lm;
    double lc_november1st, jd, end;
    struct lunarcal *lc;
    GregorianDate g;

    update_solarterms_newmoons(year);
    end = solarterms[26].jd;  /* ends with Winter Solstic */
    n = 0;
    month = 0;
    leapmonth = find_leap();

    /* start from month 11 of previous lunar calendar year */
    lc_november1st = newmoons[nm_before_ws_index];
    g = jd2g(lc_november1st);
    lyear = g.year;
    for (m = nm_before_ws_index; m < MAX_NEWMOONS - 1; m++) {
        month = m - nm_before_ws_index;

        is_lm = 0;
        if (leapmonth && month == leapmonth)
            is_lm = 1;

        /* adjust leapmonth */
        if (leapmonth && month >= leapmonth)
            month -= 1;

        /*
         * month count start from Winter Month,
         * month 0 is lunar calendar month 11,
         * month 1 is lc month 12,
         * month 2 is lc month  1 ...
         * convert them to month 1 to 12
         */
        if (month > 1)
            month -= 1;
        else
            month += 11;

        if (month == 1)
            lyear += 1;  /* ���³�һ starts a new lc year */

        for (i = 0, jd = newmoons[m]; jd < newmoons[m + 1] && jd < end; i++) {
            lc = lcalloc(jd);
            lc->lyear = lyear;
            lc->month = month;
            lc->day = i + 1;
            lc->is_lm = is_lm;
            lcs[n++] = lc;
            jd += 1.0;
        }

        if (jd > end)
            break;
    }

    /* mark solarterms */
    for (i = 0; i < MAX_SOLARTERMS - 1; i++) {
        if (solarterms[i].jd >= lc_november1st) {
            k = (int) (solarterms[i].jd - lc_november1st);
            if (lcs[k])
                lcs[k]->solarterm = i;
        }
    }

    /* mark Traditional Chinese holiday */
    mark_holiday(lcs, n);

    return n;
}


/*
 * mark traditional chinese holiday
 *
 * ���˽�(���³���)     ��Ϧ(���µ����һ��)     ����(һ��һ��)
 * Ԫ����(һ��ʮ����)   ��ʳ��(������ǰһ��)     �����(���³���)
 * ��Ϧ��(���³���)     ��Ԫ��(����ʮ����)       �����(����ʮ����)
 * ������(���¾���)     ��Ԫ��(ʮ��ʮ����)
 */
void mark_holiday(struct lunarcal *lcs[], int len)
{
    int i;
    struct lunarcal *lc;

    for (i = 0; i < len; i++) {
        lc = lcs[i];
        if (lc->solarterm == 9)  /* ���� */
            lcs[i - 1]->holiday = 4;     /* ��ʳ */

        if (lc->is_lm)
            continue;

        if (lc->month == 12 && lc->day == 8) {
            lc->holiday = 0;             /* ���� index into CN_HOLIDAY */
            i += 15;            /* fastforward */
        } else if (lc->month == 9 && lc->day == 9) {
            lc->holiday = 9;             /* ���� */
            i += 27;
        } else if (lc->month == 10 && lc->day == 15) {
            lc->holiday = 10;            /* ��Ԫ */
            break;
        }

    }
}


/*
 * find last newmoon before Winter Solstic and determin the leapmonth
 *
 * Return: 0 if not a leap year
 *         values other than 0 indicate leapmonth, count from lc month
 *         11(Winter Month)
 *             1: leap month 11, ��ʮһ��, one month after Winter Month
 *             2: leap month 12, ��ʮ����, two month after Winter Month
 *             3: leap month 1, ������, three month after Winter Month
 *             ...
 */
int find_leap(void)
{
    int nmcount, is_leap, leapmonth, i, n;
    double ws1 = solarterms[2].jd;   /* Winter Solstic of last year */
    double ws2 = solarterms[26].jd;  /* Winter Solstic of this year */

    /*
     * find the last new moon before first Winter Solstic
     * the lunar calendar month that Winter Solstic belongs is always month 11,
     */
    for (i = 1; i < MAX_NEWMOONS; i++)
        if (newmoons[i] > ws1) {
            nm_before_ws_index = i - 1;
            break;
        }

    /* count newmoons between two Winter Solstice */
    nmcount = 0;
    for (i = 0; i < MAX_NEWMOONS; i++)
        if (newmoons[i] > ws1 && newmoons[i] <= ws2)
            nmcount += 1;

    /* leap year has more than 12 newmoons between two Winter Solstice */
    leapmonth = 0;
    if (nmcount <= 12)
        return leapmonth;

    /*
     * the leap month is the first lunar calendar month which does NOT contain
     * solar terms that is multiple of 30 degrees
     */
    int cur_st = 0;
    for (i = nm_before_ws_index; i < MAX_NEWMOONS - 1; i++) {
        is_leap = 1;
        for (n = cur_st; n < MAX_SOLARTERMS; n++) {
            if (solarterms[n].jd >= newmoons[i + 1])
                break;

            if (solarterms[n].jd >= newmoons[i] &&
                solarterms[n].longitude % 30 == 0)
                    is_leap = 0;
        }
        cur_st = (n - 1) < 0 ? 0 : n - 1;

        if (is_leap) {
            leapmonth = i - nm_before_ws_index;
            break;
        }
    }

    return leapmonth;
}


struct lunarcal *lcalloc(double jd)
{
    struct lunarcal *p;

    p = (struct lunarcal *) malloc(sizeof(struct lunarcal));
    if (p) {
        p->jd = jd;
        p->solarterm = -1;
        p->lyear = -1;
        p->month = -1;
        p->day = -1;
        p->holiday = -1;
        p->is_lm = 0;
    }

    return p;
}

void print_lunarcal(struct lunarcal *lcs[], int len)
{
    int i;
    char isodate[BUFSIZE], dtstart[BUFSIZE], dtend[BUFSIZE];
    char summary[BUFSIZE], utcstamp[BUFSIZE];
    struct lunarcal *lc;
    struct tm *utc_time;
    time_t t = time(NULL);

    utc_time = gmtime(&t);
    memset(utcstamp, 0, BUFSIZE);
    sprintf(utcstamp, "%04d%02d%02dT%02d%02d%02dZ",
            1900 + utc_time->tm_year, 1 + utc_time->tm_mon, utc_time->tm_mday,
            utc_time->tm_hour, utc_time->tm_min, utc_time->tm_sec);

    for (i = 0; i < len; i++) {
        lc = lcs[i];
        jdftime(isodate, lc->jd, "%y-%m-%d", 0, 0);
        jdftime(dtstart, lc->jd, "%y%m%d", 0, 0);
        jdftime(dtend, lc->jd, "%y%m%d", 24, 0);

        memset(summary, 0, BUFSIZE);

        if (lc->solarterm != -1) {
            strcat(summary, " ");
            strcat(summary, CN_SOLARTERM[lc->solarterm]);
        }

        if (lc->holiday != -1) {
            strcat(summary, " ");
            strcat(summary, CN_HOLIDAY[lc->holiday]);
        }

        printf("BEGIN:VEVENT\n"
               "DTSTAMP:%s\n"
               "UID:%s-lc@infinet.github.io\n"
               "DTSTART;VALUE=DATE:%s\n"
               "DTEND;VALUE=DATE:%s\n"
               "STATUS:CONFIRMED\n"
               "SUMMARY:%s\n"
               "END:VEVENT\n", utcstamp, isodate, dtstart, dtend, summary);
     }
}
