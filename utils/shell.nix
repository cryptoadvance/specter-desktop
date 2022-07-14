with import <nixpkgs> { };
with pkgs.python38Packages;

stdenv.mkDerivation {
  name = "specter-desktop";
  buildInputs = [
    python38Full
    python38Packages.virtualenv
    python38Packages.pip
    libusb1
  ];
  shellHook = ''
    cd ..
    pip3 install virtualenv
    virtualenv --python=python3 .env
    source .env/bin/activate
    pip3 install -r requirements.txt --require-hashes
    pip3 install -e .
    python3 setup.py install
  '';
}
