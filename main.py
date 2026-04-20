import os
from compilers import compile_primary, compile_secondary
from decompile import decompile_tileset

# To load a directory it is sometimes more convenient to do: os.path.expandvars("$HOME/Documents/...")
#decompile_tileset(primary_path="Test/EmeraldGeneral", secondary_path="Test/Pacifidlog", out_dir="Test/Pacifidlog/DecompiledEmeraldOriginal")

#compile_primary(path="Test/Other",out_dir="Test/Other/RecompiledTriple",optimal=False, triple_layer=True)
#compile_secondary(path="Test/OtherSec",out_dir="Test/OtherSec/RecompiledTriple",path_primary="Test/Other/RecompiledTriple", optimal=False, triple_layer=True)

#compile_primary(path="Test/EmeraldGeneral/Decompiled",out_dir="Test/EmeraldGeneral/Recompiled",optimal=False, triple_layer=False)
#compile_secondary(path="Test/Slateport/DecompiledEmeraldOriginal",out_dir="Test/Slateport/Recompiled",path_primary="Test/EmeraldGeneral/Recompiled",optimal=False)

compile_primary(path="Test/EmeraldGeneral/Decompiled",out_dir="Test/EmeraldGeneral/RecompiledTriple",optimal=False, triple_layer=True)
compile_secondary(path="Test/Slateport/DecompiledEmeraldOriginal",out_dir="Test/Slateport/RecompiledTriple",path_primary="Test/EmeraldGeneral/RecompiledTriple",optimal=False,triple_layer=True)

#decompile_tileset(primary_path="Test/EmeraldGeneral/RecompiledTriple", out_dir="Test/EmeraldGeneral/DecompiledTriple", triple_layer=True)
#decompile_tileset(primary_path="Test/EmeraldGeneral/RecompiledTriple", secondary_path="Test/Slateport/RecompiledTriple", out_dir="Test/Slateport/DecompiledTriple", triple_layer=True)