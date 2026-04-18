import os
from compilers import *

input_dir = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/emerald")
input_dir_secondary = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/secondarycomptest")
out_dir = os.path.expandvars("$HOME/Documents/pkmndecomps/pokeemerald-expansion/data/tilesets/primary/test_primary")
out_dir_secondary = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/secondarycomptest/output")
#out_dir = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/decompHE/outtest")
#compile_primary(input_dir,out_dir)

compile_secondary(input_dir_secondary, out_dir_secondary, input_dir,optimal=True)