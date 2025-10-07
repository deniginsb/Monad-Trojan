# Source Code

Main bot files. Everything's here except the database file and logs (those are in .gitignore).

## Files

- `main.py` - Telegram bot handlers, all the button callbacks and message handling
- `blockchain.py` - Web3 stuff, talks to Monad RPC and DEX router
- `security.py` - Encryption for private keys (Fernet + optional passphrase)
- `portfolio.py` - Portfolio visualization with those ASCII charts
- `database.py` - SQLite ORM using SQLAlchemy
- `config.py` - Configuration, loads from .env file

## Code style

Not following any particular style guide tbh, just tried to keep it clean and commented where it matters.

Main pattern is:
- User clicks button → `main.py` callback → calls blockchain/database functions → sends result back to Telegram

Security stuff is in its own module so it's easier to audit.

## Adding features

If you want to add stuff:

1. New command = add handler in `main.py`  
2. Need blockchain interaction = add method in `blockchain.py`
3. Storing data = add to `database.py` models
4. New settings = update `UserSettings` model

Pretty straightforward. Feel free to fork and customize.
