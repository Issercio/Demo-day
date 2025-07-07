import click
from flask.cli import with_appcontext
from app import db
from app.models import User

@click.command('create-admin')
@click.argument('username')
@click.argument('email')
@click.argument('password')
@with_appcontext
def create_admin_command(username, email, password):
    """Create an admin user."""
    try:
        user = User(
            username=username,
            email=email,
            is_admin=True,
            password=password  # Pass password directly to constructor
        )
        db.session.add(user)
        db.session.commit()
        click.echo(f'Successfully created admin user: {username}')
    except Exception as e:
        db.session.rollback()
        click.echo(f'Error creating admin user: {str(e)}')
        raise