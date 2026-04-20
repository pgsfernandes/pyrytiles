import os
from compilers import compile_primary, compile_secondary
from decompile import decompile_tileset

'''
input_dir_secondary = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/sec_comp_test1")
input_dir_primary = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/decompiletest3")
output_dir = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/sec_comp_test1/output")

compile_secondary(input_dir_secondary, output_dir, input_dir_primary, optimal=False)
'''

#decompile_tileset(primary_path="Test/EmeraldGeneral", secondary_path="Test/Pacifidlog", out_dir="Test/Pacifidlog/DecompiledEmeraldOriginal")
compile_primary(path="Test/EmeraldGeneral/Decompiled",out_dir="Test/EmeraldGeneral/Recompiled",optimal=False)
compile_secondary(path="Test/Slateport/DecompiledEmeraldOriginal",out_dir="Test/Slateport/Recompiled",path_primary="Test/EmeraldGeneral/Recompiled",optimal=False)
#compile_secondary(path="Test/Mauville/DecompiledEmeraldOriginal",out_dir="Test/Mauville/Recompiled",path_primary="Test/EmeraldGeneral",optimal=False)
#compile_secondary(path="Test/Pacifidlog/DecompiledEmeraldOriginal",out_dir="Test/Pacifidlog/Recompiled",path_primary="Test/EmeraldGeneral/Recompiled",optimal=True)