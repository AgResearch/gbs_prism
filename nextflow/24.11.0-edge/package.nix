{ fetchFromGitHub
, gradle_8
, nextflow
, ...
}:
nextflow.overrideAttrs (finalAttrs: previousAttrs: rec {
  version = "24.11.0-edge";
  src = fetchFromGitHub {
    owner = "nextflow-io";
    repo = "nextflow";
    rev = "6e231be115c31f4e29e6deab45f668ae7e75917d";
    hash = "sha256-Ob1lt4WfEAZO+3E0vqjWTdLY7IZDiCA0wr3tDjikgyE=";
  };
  mitmCache = gradle_8.fetchDeps {
    inherit (previousAttrs) pname;
    data = ./deps.json;
  };
})
