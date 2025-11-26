{
  description = "pyjopa - Python Java Parser and Compiler";

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

        pyjopa = pythonPackages.buildPythonApplication {
          pname = "pyjopa";
          version = "0.1.0";
          src = ./.;
          format = "pyproject";

          nativeBuildInputs = [
            pythonPackages.setuptools
          ];

          propagatedBuildInputs = [
            pythonPackages.lark
          ];

          doCheck = false;
        };
      in
      {
        packages = {
          default = pyjopa;
          pyjopa = pyjopa;
        };

        apps.default = {
          type = "app";
          program = "${pyjopa}/bin/pyjopa";
        };

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
            export PYTHONPATH="$PWD:$PYTHONPATH"
            echo "pyjopa Development Environment"
            echo "Python: $(python --version)"
            echo "Java: $(java -version 2>&1 | head -1)"
          '';
        };
      }
    );
}
