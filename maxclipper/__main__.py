"""Allow ``python -m maxclipper`` in addition to the ``maxclipper`` script."""

from maxclipper.cli import main

if __name__ == "__main__":
    main()