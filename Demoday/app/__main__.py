from . import test_database_connection

if __name__ == "__main__":
    test_database_connection()
    print("Démarrage des tests de la base de données...")
    if test_database_connection():
        print("Tests de la base de données réussis.")
    else:
        print("Échec des tests de la base de données.")
    print("Tests de la base de données terminés.")
