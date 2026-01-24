#!/bin/bash

# Script per gestire il progetto Shelly Energy Report Generator
# Compatibile con macOS (Homebrew), Linux e Windows (Git Bash)

if [ $# -eq 0 ]; then
    echo "Usage: $0 {setup|run|clean|update}"
    echo ""
    echo "Commands:"
    echo "  setup    - Crea virtual environment e installa dipendenze"
    echo "  run      - Esegue il programma principale"
    echo "  clean    - Rimuove virtual environment e cache"
    echo "  update   - Aggiorna tutte le dipendenze"
    exit 1
fi

COMMAND=$1

# Rileva il sistema operativo
OS_NAME=$(uname -s)
echo "Sistema operativo: $OS_NAME"

# Trova il comando python corretto
find_python() {
    # Prova diverse varianti
    for cmd in python3.12 python3.11 python3.10 python3.9 python3 python; do
        if command -v $cmd &> /dev/null; then
            echo $cmd
            return 0
        fi
    done
    echo "python3"  # fallback
    return 1
}

PYTHON_CMD=$(find_python)

if ! command -v $PYTHON_CMD &> /dev/null; then
    echo "❌ Python non trovato!"
    echo "Installa Python 3.9 o superiore:"
    if [ "$OS_NAME" = "Darwin" ]; then
        echo "  brew install python@3.11"
    elif [ "$OS_NAME" = "Linux" ]; then
        echo "  sudo apt install python3 python3-venv python3-pip"
    fi
    exit 1
fi

echo "✅ Python trovato: $($PYTHON_CMD --version)"

# Trova il comando pip corretto
find_pip() {
    # Prova diverse varianti
    for cmd in pip3.12 pip3.11 pip3.10 pip3.9 pip3 pip; do
        if command -v $cmd &> /dev/null; then
            echo $cmd
            return 0
        fi
    done
    echo "pip"  # fallback
    return 1
}

PIP_CMD=$(find_pip)

case $COMMAND in
    setup)
        echo "🚀 Configurazione del progetto..."
        
        # Crea cartelle necessarie
        echo "📁 Creazione struttura cartelle..."
        mkdir -p data reports logs
        
        # Crea virtual environment
        echo "🐍 Creazione virtual environment..."
        $PYTHON_CMD -m venv venv
        
        if [ $? -ne 0 ]; then
            echo "❌ Errore nella creazione del virtual environment"
            echo "Prova ad installare python3-venv:"
            if [ "$OS_NAME" = "Darwin" ]; then
                echo "  brew install python@3.11"
            elif [ "$OS_NAME" = "Linux" ]; then
                echo "  sudo apt install python3-venv"
            fi
            exit 1
        fi
        
        # Attiva virtual environment
        echo "🔌 Attivazione virtual environment..."
        
        if [ "$OS_NAME" = "MINGW64_NT" ] || [ "$OS_NAME" = "CYGWIN_NT" ]; then
            # Windows Git Bash/Cygwin
            source venv/Scripts/activate
        else
            # macOS/Linux
            source venv/bin/activate
        fi
        
        # Aggiorna pip
        echo "Aggiornamento pip..."
        python -m pip install --upgrade pip
        
        # Installa dipendenze
        echo "Installazione dipendenze..."
        
        # Prima controlla se requirements.txt esiste
        if [ ! -f "requirements.txt" ]; then
            echo "[WARN] File requirements.txt non trovato"
            echo "Creazione requirements.txt di base..."
            cat > requirements.txt << EOF
# Requirements base per Shelly Energy Report Generator
pandas>=2.1.4
numpy>=1.26.0
matplotlib>=3.8.2
seaborn>=0.13.0
reportlab>=4.0.4
python-dateutil>=2.8.2
pytz>=2023.3.post1
pillow>=10.1.0
EOF
        fi
        
        pip install -r requirements.txt
        
        # Verifica installazione
        echo "Verifica installazione..."
        python -c "import pandas, numpy, matplotlib, reportlab; print('[OK] Tutte le dipendenze installate correttamente')"
        
        # Crea file di esempio se la cartella data è vuota
        if [ -z "$(ls -A data 2>/dev/null)" ]; then
            echo "📝 Creazione file CSV di esempio..."
            cat > data/emdata_example.csv << EOF
timestamp,total_act_energy,max_act_power,min_act_power,avg_voltage,avg_current
1701388800,1000,1500,100,230.5,6.5
1701388860,1050,1600,110,231.0,6.8
1701388920,1100,1550,105,230.8,6.6
EOF
            echo "📄 Creato data/emdata_example.csv"
        fi
        
        echo ""
        echo "🎉 Configurazione completata!"
        echo ""
        echo "Prossimi passi:"
        echo "1. Inserisci i tuoi file CSV nella cartella 'data/'"
        echo "2. Esegui: $0 run"
        echo "3. I report saranno generati in 'reports/'"
        ;;
    
    run)
        echo "▶️  Avvio del programma..."
        
        if [ ! -d "venv" ]; then
            echo "❌ Virtual environment non trovato"
            echo "Esegui prima: $0 setup"
            exit 1
        fi
        
        # Attiva virtual environment
        echo "🔌 Attivazione virtual environment..."
        
        if [ "$OS_NAME" = "MINGW64_NT" ] || [ "$OS_NAME" = "CYGWIN_NT" ]; then
            source venv/Scripts/activate
        else
            source venv/bin/activate
        fi
        
        # Controlla se esiste main.py
        if [ -f "src/main.py" ]; then
            MAIN_SCRIPT="src/main.py"
        elif [ -f "main.py" ]; then
            MAIN_SCRIPT="main.py"
        elif [ -f "shelly_energy_report.py" ]; then
            MAIN_SCRIPT="shelly_energy_report.py"
        else
            echo "❌ Nessun file principale trovato!"
            echo "Cerca tra:"
            echo "  - src/main.py"
            echo "  - main.py"
            echo "  - shelly_energy_report.py"
            echo "Oppure specifica il percorso: python tuo_file.py"
            exit 1
        fi
        
        echo "📄 Esecuzione: $MAIN_SCRIPT"
        python "$MAIN_SCRIPT"
        
        # Se c'è un errore, suggerisce soluzioni
        if [ $? -ne 0 ]; then
            echo ""
            echo "⚠️  Errore durante l'esecuzione"
            echo "Prova:"
            echo "1. Verifica che i file CSV siano nella cartella 'data/'"
            echo "2. Aggiorna le dipendenze: $0 update"
            echo "3. Ripristina l'ambiente: $0 clean && $0 setup"
        fi
        ;;
    
    clean)
        echo "🧹 Pulizia ambiente..."
        
        # Chiede conferma
        read -p "Rimuovere virtual environment e cache? (s/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Ss]$ ]]; then
            echo "Rimozione venv..."
            rm -rf venv
            
            echo "Rimozione cache Python..."
            find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
            find . -type f -name "*.pyc" -delete 2>/dev/null || true
            find . -type f -name "*.pyo" -delete 2>/dev/null || true
            find . -type f -name "*.pyd" -delete 2>/dev/null || true
            find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
            find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
            
            echo "Rimozione file temporanei..."
            rm -rf .coverage htmlcov .cache build dist *.egg-info 2>/dev/null || true
            
            echo "✅ Pulizia completata"
        else
            echo "❌ Pulizia annullata"
        fi
        ;;
    
    update)
        echo "🔄 Aggiornamento dipendenze..."
        
        if [ ! -d "venv" ]; then
            echo "❌ Virtual environment non trovato"
            echo "Esegui prima: $0 setup"
            exit 1
        fi
        
        if [ "$OS_NAME" = "MINGW64_NT" ] || [ "$OS_NAME" = "CYGWIN_NT" ]; then
            source venv/Scripts/activate
        else
            source venv/bin/activate
        fi
        
        echo "Aggiornamento pip..."
        python -m pip install --upgrade pip
        
        echo "Aggiornamento pacchetti..."
        
        if [ -f "requirements.txt" ]; then
            echo "Aggiornamento da requirements.txt..."
            pip install --upgrade -r requirements.txt
        else
            echo "Aggiornamento pacchetti installati..."
            pip list --outdated --format=freeze | grep -v '^\-e' | cut -d = -f 1 | xargs -n1 pip install -U
        fi
        
        echo "Generazione nuovo requirements.txt..."
        pip freeze > requirements.txt
        
        echo "[OK] Aggiornamento completato"
        ;;
    
    *)
        echo "[ERROR] Comando non valido: $COMMAND"
        echo "Usage: $0 {setup|run|clean|update}"
        exit 1
        ;;
esac