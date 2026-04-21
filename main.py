import os
import pyrytiles

# To load a directory it is sometimes more convenient to do: os.path.expandvars("$HOME/Documents/...")

#Compiling Emerald's primary tileset and Slateport's tileset
pyrytiles.compile_primary(path="Test/EmeraldGeneral/Decompiled",out_dir="Test/EmeraldGeneral/Recompiled",optimal=False, triple_layer=False)
pyrytiles.compile_secondary(path="Test/Slateport/DecompiledEmeraldOriginal",out_dir="Test/Slateport/Recompiled",path_primary="Test/EmeraldGeneral/Recompiled",optimal=False, triple_layer=False)

#Decompile Emerald's primary tileset and Slateport's tileset that were compiled with triple-layer
#pyrytiles.decompile_tileset(primary_path="Test/EmeraldGeneral/RecompiledTriple", out_dir="Test/EmeraldGeneral/DecompiledTriple", triple_layer=True)
#pyrytiles.decompile_tileset(primary_path="Test/EmeraldGeneral/RecompiledTriple", secondary_path="Test/Slateport/RecompiledTriple", out_dir="Test/Slateport/DecompiledTriple", triple_layer=True)