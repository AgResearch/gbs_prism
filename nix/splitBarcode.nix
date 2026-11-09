# MGI splitBarcode, packaged from the eRI EasyBuild installation.
#
# splitBarcode is proprietary MGI software with no public download, and the vendor
# tarball the EasyBuild recipe names
# (splitBarcode_V2.0.0_release_4_basecallLite_MGI.tar.gz) has no source_urls and is
# not retained on eRI - only the installed tree survives. So unlike bcl-convert.nix,
# which fetchurls a vendor RPM, this repackages the installed tree. See flake.nix for
# the input that supplies it.
#
# What is being packaged: a prebuilt x86-64 ELF `bin/splitBarcode` plus a vendored
# `lib/`. `bin/splitBarcode` carries RPATH `$ORIGIN/../lib`, which autoPatchelfHook
# rewrites; `addAutoPatchelfSearchPath $out/lib` below is what lets it keep resolving
# the vendored libraries after that rewrite.
#
{ lib
, stdenv
, autoPatchelfHook
, src
, zlib
}:

stdenv.mkDerivation {
  pname = "splitBarcode";
  version = "2.0.0-4";

  inherit src;

  nativeBuildInputs = [ autoPatchelfHook ];

  # glibc comes from stdenv. libstdc++, libgcc_s and libz are vendored in the tree
  # and kept, since the binary was built against those; zlib is listed so
  # autoPatchelf has a fallback if a future build stops vendoring it.
  buildInputs = [
    stdenv.cc.cc.lib
    zlib
  ];

  dontConfigure = true;
  dontBuild = true;

  installPhase = ''
    runHook preInstall

    mkdir -p $out/bin $out/lib
    cp -r bin/splitBarcode $out/bin/
    cp -r lib/. $out/lib/

    # Vendor barcode lists, kept for reference. NB these are MGI's own UDP lists and
    # must NOT be fed to splitBarcode as a -B file: they list every index and
    # concatenate i5+i7, the opposite order to what a T1+ SE GBS lane needs. The
    # pipeline generates its own per-lane -B file.
    for f in BarcodeV2.1.txt BarcodeV3.0.txt; do
      if [ -f "$f" ]; then
        install -Dm444 "$f" "$out/share/splitBarcode/$f"
      fi
    done

    runHook postInstall
  '';

  preFixup = ''
    addAutoPatchelfSearchPath $out/lib
  '';

  # The tree ships its own libstdc++/libgcc_s; leave them alone rather than having
  # autoPatchelf prefer the nixpkgs ones, which is not the combination MGI tested.
  autoPatchelfIgnoreMissingDeps = false;

  meta = with lib; {
    description = "MGI splitBarcode - demultiplexer for DNBSEQ sequencing data";
    homepage = "https://en.mgi-tech.com/";
    license = licenses.unfree;
    platforms = [ "x86_64-linux" ];
    mainProgram = "splitBarcode";
  };
}
