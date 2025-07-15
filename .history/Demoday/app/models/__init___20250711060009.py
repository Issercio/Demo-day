from .category import Category
from .user import User
from app.extensions import db

# Import du modèle Product depuis le fichier principal models.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from app.models import Product