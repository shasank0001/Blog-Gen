"""Standard-library-only initializer, runnable inside the small Python container."""
import argparse
import os
from pathlib import Path
import secrets


def initialize(template, destination):
    text = Path(template).read_text()
    text = text.replace('GENERATE_DATABASE_PASSWORD', secrets.token_hex(32))
    text = text.replace('GENERATE_SIGNING_SECRET', secrets.token_urlsafe(48))
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as output:
        output.write(text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='.env.production')
    args = parser.parse_args()
    try:
        initialize('.env.production.example', args.output)
    except FileExistsError:
        raise SystemExit('The env file already exists. It was not changed.')
    print('Created the deployment env file with unique secrets. Configure your domain and provider settings, then run ./deploy.sh up.')
