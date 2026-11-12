"""Configurações do sistema (lidas de variáveis de ambiente).

Nada de senha fixa no código: defina as variáveis antes de executar, por exemplo:
    export DB_USER=app_sistema
    export DB_PASSWORD='sua-senha'
"""
import os

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "instituto_batista"),
    "charset": "utf8mb4",
    "unix_socket": os.getenv("DB_SOCKET") or None,   # opcional (Linux/macOS)
}

IP_LOCAL = os.getenv("APP_IP", "127.0.0.1")           # IP gravado no log (terminal)
URL_BASE = os.getenv("APP_URL", "http://localhost:5000")
VERSAO_TERMO_LGPD = "v1.0"
VALIDADE_TOKEN_MINUTOS = 60                           # RN009: token vale 1 hora
MAX_TENTATIVAS_LOGIN = 5                              # bloqueio temporário de login
BLOQUEIO_MINUTOS = 5
PASTA_EXPORTACAO = os.getenv("APP_EXPORT_DIR", "exportacoes")
