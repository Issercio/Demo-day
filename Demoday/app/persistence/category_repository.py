from app.models import Category
from app import db
from typing import List, Optional

class CategoryRepository:
    @staticmethod
    def get_all() -> List[Category]:
        """Récupérer toutes les catégories avec validation ID"""
        try:
            print("=== REPOSITORY GET ALL ===")
            categories = Category.query.all()
            valid_categories = []
            
            for cat in categories:
                if cat.id is not None:
                    print(f"Catégorie valide REPO: {cat.id} - {cat.name}")
                    valid_categories.append(cat)
                else:
                    print(f"ERREUR REPO: Catégorie sans ID: {cat.name}")
            
            return valid_categories
        except Exception as e:
            print(f"Erreur REPO get_all: {str(e)}")
            return []
    
    @staticmethod
    def get_by_id(category_id: int) -> Optional[Category]:
        """Récupérer une catégorie par ID avec validation"""
        try:
            print(f"=== REPOSITORY GET BY ID {category_id} ===")
            category = Category.query.get(category_id)
            
            if category and category.id is None:
                print(f"ERREUR REPO: Catégorie corrompue pour ID {category_id}")
                return None
            
            return category
        except Exception as e:
            print(f"Erreur REPO get_by_id: {str(e)}")
            return None
    
    @staticmethod
    def create(name: str) -> Optional[Category]:
        """Créer une nouvelle catégorie avec validation"""
        try:
            print(f"=== REPOSITORY CREATE: {name} ===")
            
            # Vérifier unicité
            existing = Category.query.filter_by(name=name).first()
            if existing:
                print(f"REPO: Catégorie existante: {name}")
                return None
            
            category = Category(name=name)
            db.session.add(category)
            db.session.flush()  # Obtenir l'ID
            
            if category.id is None:
                print(f"ERREUR REPO: Pas d'ID généré pour {name}")
                db.session.rollback()
                return None
            
            db.session.commit()
            print(f"REPO: Catégorie créée avec ID {category.id}")
            return category
            
        except Exception as e:
            print(f"Erreur REPO create: {str(e)}")
            db.session.rollback()
            return None
    
    @staticmethod
    def update(category_id: int, name: str) -> Optional[Category]:
        """Modifier une catégorie"""
        try:
            print(f"=== REPOSITORY UPDATE {category_id}: {name} ===")
            category = CategoryRepository.get_by_id(category_id)
            
            if not category:
                return None
            
            # Vérifier unicité
            existing = Category.query.filter(
                Category.name == name, 
                Category.id != category_id
            ).first()
            if existing:
                print(f"REPO: Nom déjà utilisé: {name}")
                return None
            
            category.name = name
            db.session.commit()
            print(f"REPO: Catégorie {category_id} modifiée")
            return category
            
        except Exception as e:
            print(f"Erreur REPO update: {str(e)}")
            db.session.rollback()
            return None
    
    @staticmethod
    def delete(category_id: int) -> bool:
        """Supprimer une catégorie et ses produits"""
        try:
            print(f"=== REPOSITORY DELETE {category_id} ===")
            category = CategoryRepository.get_by_id(category_id)
            
            if not category:
                return False
            
            # Supprimer produits associés
            from app.models import Product
            products_deleted = Product.query.filter_by(category_id=category_id).delete()
            print(f"REPO: {products_deleted} produits supprimés")
            
            # Supprimer catégorie
            db.session.delete(category)
            db.session.commit()
            print(f"REPO: Catégorie {category_id} supprimée")
            return True
            
        except Exception as e:
            print(f"Erreur REPO delete: {str(e)}")
            db.session.rollback()
            return False
