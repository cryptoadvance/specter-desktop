with import <nixpkgs> { };
with pkgs.python38Packages;

stdenv.mkDerivation {
  name = "specter-desktop";
  buildInputs = [
    python38Full
    python38Packages.virtualenv
    python38Packages.pip
    python38Packages.pip-tools
    libusb1
  ];
  shellHook = ''
    cd ..
    pip-compile --generate-hashes requirements.in > requirements.txt
    pip3 install virtualenv
    virtualenv --python=python3 .env
    source .env/bin/activate
    pip3 install -r requirements.txt --require-hashes
    pip3 install -e .
    python3 setup.py install
  '';
}
