{
  description = "Java 8 Parser in Python";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python312;
        pythonPackages = python.pkgs;
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            python
            pythonPackages.lark
            pythonPackages.pytest
            pythonPackages.pytest-xdist
            pkgs.jdk8
          ];

          shellHook = ''
            export JAVA_HOME=${pkgs.jdk8}
            echo "Java 8 Parser Development Environment"
            echo "Python: $(python --version)"
            echo "Java: $(java -version 2>&1 | head -1)"
          '';
        };
      }
    );
}
