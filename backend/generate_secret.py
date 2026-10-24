"""Replace the example secret during first-time setup; preserve custom secrets."""
from pathlib import Path
import secrets

if __name__ == "__main__":
    path = Path(__file__).parent / ".env"
    content = path.read_text()
    content = content.replace('SECRET_KEY="replace-with-strong-secret"',
                              f'SECRET_KEY="{secrets.token_urlsafe(48)}"')
    path.write_text(content)
    path.chmod(0o600)
