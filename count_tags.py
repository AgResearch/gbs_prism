#!/bin/env python

import sys,re

counts=(int(re.split("\s+",record.strip())[2]) for record in sys.stdin if len(re.split("\s+",record.strip())) == 3)
print reduce(lambda x,y:x+y, counts)
