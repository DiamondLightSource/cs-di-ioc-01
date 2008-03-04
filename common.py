'''Common resources.'''

from Numeric import *
from MLab import *

from dls.ca2 import catools
import server


# List of all BPMs in the storage ring.
BPMS = ['SR%02dC-DI-EBPM-%02d' % (c+1, n+1)
    for c in range(24) for n in range(7)]
BPM_count = len(BPMS)



# Extract the useful definitions from catools and export them here.
for name in dir(catools):
    if name[:4] == 'dbr_':
        globals()[name] = getattr(catools, name)

del catools
