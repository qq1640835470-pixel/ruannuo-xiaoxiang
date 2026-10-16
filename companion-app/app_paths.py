"""Project-owned storage is stable across packaged and independent launches."""
import pathlib
HOME=pathlib.Path(__file__).resolve().parent.parent/'companion-data'
DATA=HOME/'companion-v01'
MODELS=HOME/'models'
