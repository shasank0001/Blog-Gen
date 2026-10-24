"""Create an account without opening public registration: python -m app.manage EMAIL."""
import argparse
import asyncio
import getpass
import sys

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.core.models import User
from app.core.security import get_password_hash


async def create_user(email, password):
    async with AsyncSessionLocal() as db, db.begin():
        if (await db.execute(select(User.id).where(User.email == email))).scalar_one_or_none():
            raise ValueError('An account with this email already exists')
        db.add(User(email=email, hashed_password=get_password_hash(password)))


async def run(email, password):
    try:
        await create_user(email, password)
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('email')
    args = parser.parse_args()
    try:
        email = str(TypeAdapter(EmailStr).validate_python(args.email))
        password = getpass.getpass('New password (12+ characters, at most 72 UTF-8 bytes): ')
        if len(password) < 12 or len(password.encode()) > 72:
            raise ValueError('Password must have at least 12 characters and at most 72 UTF-8 bytes')
        if password != getpass.getpass('Repeat password: '):
            raise ValueError('Passwords do not match')
        asyncio.run(run(email, password))
    except (ValueError, ValidationError) as exc:
        print(f'Account was not created: {exc}', file=sys.stderr)
        return 1
    print('Account created. You can sign in now.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
