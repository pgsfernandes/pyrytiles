import os
from compilers import *
from decompile import decompile_tileset

#input_dir = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/emerald")
#input_dir = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/emerald")
#input_dir_secondary = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/secondarycomptest")
#out_dir = os.path.expandvars("$HOME/Documents/pkmndecomps/pokeemerald-expansion/data/tilesets/primary/test_primary")
#out_dir_secondary = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/secondarycomptest/output")
#out_dir = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/decompHE/outtest")

'''
input_dir = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/decompiletest3/output2")
out_dir = os.path.expandvars("$HOME/Documents/pkmndecomps/pokeemerald-expansion/data/tilesets/primary/test_primary")
compile_primary(input_dir,out_dir)
'''

#decompile_tileset(primary_path="lightplat2", out_dir="lightplat2/output")
#decompile_tileset(primary_path="lightplat2", secondary_path="lightplatsec", out_dir="lightplatsec/output")
#decompile_tileset(primary_path="decompiletest3", secondary_path="decompiletestsec2", out_dir="decompiletestsec2/output2")
#decompile_tileset(primary_path="Test/EmeraldGeneral", out_dir="Test/EmeraldGeneral/Decompiled")

#input_dir = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/lightplat2/output")
#out_dir = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/lightplat2/compiled")
#compile_primary(input_dir,out_dir,optimal=True)
#compile_primary(path="Test/EmeraldGeneral/Decompiled",out_dir="Test/EmeraldGeneral/Recompiled",optimal=True)

'''
input_dir_secondary = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/sec_comp_test1")
input_dir_primary = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/decompiletest3")
output_dir = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/sec_comp_test1/output")

compile_secondary(input_dir_secondary, output_dir, input_dir_primary, optimal=False)
'''

#decompile_tileset(primary_path="Test/EmeraldGeneral", secondary_path="Test/Pacifidlog", out_dir="Test/Pacifidlog/DecompiledEmeraldOriginal")
#compile_primary(path="Test/EmeraldGeneral/Decompiled",out_dir="Test/EmeraldGeneral/Recompiled",optimal=False)
#compile_secondary(path="Test/Slateport/DecompiledEmeraldOriginal",out_dir="Test/Slateport/Recompiled-New",path_primary="Test/EmeraldGeneral/Recompiled",optimal=False)
#compile_secondary(path="Test/Mauville/DecompiledEmeraldOriginal",out_dir="Test/Mauville/Recompiled",path_primary="Test/EmeraldGeneral",optimal=False)
compile_secondary(path="Test/Pacifidlog/DecompiledEmeraldOriginal",out_dir="Test/Pacifidlog/Recompiled",path_primary="Test/EmeraldGeneral/Recompiled",optimal=True)