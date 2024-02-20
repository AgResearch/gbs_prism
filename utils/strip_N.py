import re,sys

for record in sys.stdin:
   if re.match("^\s*>",record) is None:                     # ignore fasta header lines
      print("".join(re.split("[Nn]",record)),end="")        # split on N,n then join together
   else:
      print(record,end="")

