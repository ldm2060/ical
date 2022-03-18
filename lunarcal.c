#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "lunarcalbase.h"


int main(int argc, char *argv[])
{
    int start, end;
    time_t now = time(0);
	tm *ltm = localtime(&now);
	end = 1900 + ltm->tm_year + 1;
	start = end - 2;

    printf("BEGIN:VCALENDAR\n"
           "PRODID:-//Chen Wei//Chinese Lunar Calendar//EN\n"
           "VERSION:2.0\n"
           "CALSCALE:GREGORIAN\n"
           "METHOD:PUBLISH\n"
           "X-WR-CALNAME:24节气\n"
           "X-WR-TIMEZONE:Asia/Shanghai\n"
           "X-WR-CALDESC:中国农历%d-%d, 包括节气.\n", start, end);
    while (start <= end) {
        cn_lunarcal(start);
        start++;
    }
    printf("END:VCALENDAR\n");

    return 0;
}
