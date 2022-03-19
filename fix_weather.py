
def mo_month(str1, index, month):
    str1 = str1[:index] + str(int(month / 10)) + str(month % 10) + str1[index+2:]
    return str1
def mo_year(str1, index, year):
    str1 = str1[:index] + str(int(year / 1000)) + str(int(year / 100) % 10) + str(int(year % 100 / 10)) + str(year % 10) + str1[index+4:]
    return str1
path = {'gy.ics','cd.ics'}

for filep in path:
    with open(filep , 'r', encoding='utf-8') as fin:
        list = fin.readlines()
        fin.close()
        year = month = 0
        day = 0
        isaddm = False
        isaddy = False
        for i in range(0, len(list)):
            if list[i][0:2] == 'DT':
                if list[i][5] == 'R':
                    month = int(list[i][23:2+23])
                    if day < int(list[i][25:27]):
                        day = int(list[i][25:27])
                    else: isaddm = True
                    if isaddm :
                        new_mon = (int(list[i][23:2+23]) + 1) % 12
                        if(month > new_mon) : isaddy = True
                        month = new_mon
                        list[i] = mo_month(list[i], 23, month) 
                    if isaddy:
                        year = int(list[i][19:4+19]) + 1
                        list[i] = mo_year(list[i], 19, year)
                elif list[i][2] == 'E':
                    if isaddm:
                        list[i] = mo_month(list[i], 21, month)
                    if isaddy:
                        list[i]= mo_year(list[i], 17, year)
                elif list[i][5] == 'M':
                    if isaddm:
                        list[i] = mo_month(list[i], 12, month)
                    if isaddy:
                        list[i]= mo_year(list[i], 8, year)
        with open(filep, 'w', encoding='utf-8') as fout:
            fout.writelines(list)
            fout.close()
