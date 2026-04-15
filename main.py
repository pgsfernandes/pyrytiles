import os
from compilers import *

input_dir = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/emerald")
out_dir = os.path.expandvars("$HOME/Documents/pkmndecomps/pokeemerald-expansion/data/tilesets/primary/test_primary")
#out_dir = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/decompHE/outtest")
compile_primary(input_dir,out_dir)