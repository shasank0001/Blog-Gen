"""Validate production settings without displaying credentials or making provider calls."""
import os
import re
import sys


def main():
    checking = 'SECRET_KEY and typed settings'
    try:
        from app.core.config import settings
        from app.services.metering import prices
        checking = 'POSTGRES_PASSWORD (32+ URL-safe characters)'
        password = os.getenv('POSTGRES_PASSWORD', '')
        if not re.fullmatch(r'[A-Za-z0-9_-]{32,}', password):
            raise ValueError('POSTGRES_PASSWORD must contain at least 32 URL-safe letters, digits, underscores or hyphens')
        checking = 'LLM_PRICING_JSON'
        rates = prices()
        for name in ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GOOGLE_API_KEY', 'PINECONE_API_KEY', 'FIRECRAWL_API_KEY']:
            checking = name
            value = getattr(settings, name)
            if value and any(marker in value.lower() for marker in ['your-', 'change_me', 'replace-with']):
                raise ValueError(f'{name} is still a placeholder; set a real key or leave it empty')
        if settings.ALLOW_REGISTRATION:
            print('WARNING: Public registration is enabled; new accounts can use the server provider keys.')
        if not settings.USE_LOCAL_LLM and not rates:
            print('WARNING: No cloud model rates are configured. Cloud generation will be blocked until LLM_PRICING_JSON is set.')
        if not settings.USE_LOCAL_LLM and not any([settings.OPENAI_API_KEY, settings.ANTHROPIC_API_KEY, settings.GOOGLE_API_KEY]):
            print('WARNING: Configure a model provider or Ollama before generating articles.')
        if not settings.PINECONE_API_KEY:
            print('INFO: Document indexing requires PINECONE_API_KEY (and an embedding provider).')
        if not settings.FIRECRAWL_API_KEY:
            print('INFO: Web research and style URL scraping require FIRECRAWL_API_KEY.')
    except Exception:
        # Settings validation errors can contain secrets. Never print the exception.
        print(f'Preflight failed. Check {checking} in the deployment env file. Credentials have been omitted.', file=sys.stderr)
        return 1
    print('Deployment settings are valid. External service connectivity has not been tested.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
