#!/usr/bin/env python
import csv
from itertools import izip
import sys
import os


first = sys.argv[1]
merged = "{}_merged.csv".format("".join(first[:-4]))

for i, fn in enumerate(sys.argv[1:]):
    a = list(csv.reader(open(fn, "rb")))
    base = os.path.dirname(fn)
    a[0].append("file")
    a[1].append(base)
    output = "{}_pivot.csv".format("".join(fn[:-4]))
    if i == 0:
        csv.writer(open(merged, "wb")).writerow(a[0])
    csv.writer(open(merged, "ab")).writerow(a[1])

a = izip(*csv.reader(open(merged, "rb")))
output = "{}_merged_pivot.csv".format("".join(first[:-4]))
csv.writer(open(output, "wb")).writerows(a)
print(output)
print(merged)
