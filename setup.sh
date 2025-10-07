#!/bin/bash
# Quick setup script
# Just run: ./setup.sh

echo "🤖 Monad Trading Bot Setup"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.11+"
    exit 1
fi

# Check Node
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 18+"
    exit 1
fi

echo "✅ Python and Node.js found"
echo ""

# Create venv
echo "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python deps
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Install Node deps  
echo "Installing Node.js dependencies..."
npm install

# Setup .env
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file from template..."
    cp .env.example .env
    
    # Generate encryption key
    echo ""
    echo "Generating encryption key..."
    KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    
    # Replace in .env
    sed -i "s/GENERATE_YOUR_OWN_KEY_HERE_USING_COMMAND_ABOVE/$KEY/" .env
    
    echo "✅ Encryption key generated and added to .env"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your Telegram bot token!"
    echo "   Get one from @BotFather on Telegram"
else
    echo "⚠️  .env file already exists, skipping"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your TELEGRAM_BOT_TOKEN"
echo "2. Run: source venv/bin/activate"  
echo "3. Run: python src/main.py"
echo ""
echo "Your bot should start and you'll see 'Bot started successfully'"
