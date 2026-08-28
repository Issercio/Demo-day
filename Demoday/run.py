from app import create_app

app = create_app()

if __name__ == '__main__':
    # Forcer l'utilisation de localhost au lieu de 127.0.0.1
    app.run(host='0.0.0.0', port=5000, debug=True)