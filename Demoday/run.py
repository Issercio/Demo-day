from app import create_app
import os

app = create_app()

if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes')
    # 0.0.0.0 = démo en salle. Le debugger Flask reste off sauf FLASK_DEBUG=1.
    app.run(host='0.0.0.0', port=5000, debug=debug)
