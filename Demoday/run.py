from app import create_app
import os

app = create_app()

if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes')
    ssl_context = None
    if os.environ.get('FLASK_HTTPS', '').lower() in ('1', 'true', 'yes'):
        here = os.path.dirname(os.path.abspath(__file__))
        cert = os.environ.get('SSL_CERT_FILE', os.path.join(here, 'certs', 'localhost.pem'))
        key = os.environ.get('SSL_KEY_FILE', os.path.join(here, 'certs', 'localhost-key.pem'))
        if os.path.isfile(cert) and os.path.isfile(key):
            ssl_context = (cert, key)  # certificat local auto-signé (./setup.sh)
        else:
            ssl_context = 'adhoc'
    # 0.0.0.0 = démo en salle. HTTPS si FLASK_HTTPS=1 (sinon HTTP).
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '5000')), debug=debug, ssl_context=ssl_context)
