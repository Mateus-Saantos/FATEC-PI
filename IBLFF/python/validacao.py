"""Validações e formatações reutilizadas por todos os módulos."""
import re
from datetime import date, datetime

from erros import ErroNegocio


def somente_digitos(texto):
    return re.sub(r"\D", "", texto or "")


def validar_cpf(cpf):
    """Valida o CPF pelos dois dígitos verificadores (RF05)."""
    c = somente_digitos(cpf)
    if len(c) != 11 or c == c[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(c[i]) * (n + 1 - i) for i in range(n))
        if (soma * 10 % 11) % 10 != int(c[n]):
            return False
    return True


def formatar_cpf(cpf):
    c = somente_digitos(cpf)
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}" if len(c) == 11 else (cpf or "")


def mascarar_cpf(cpf):
    """Esconde parte do CPF em relatórios (LGPD: minimização)."""
    c = somente_digitos(cpf)
    return f"***.{c[3:6]}.{c[6:9]}-**" if len(c) == 11 else ""


def validar_telefone(telefone):
    """Telefone brasileiro com DDD: 10 ou 11 dígitos."""
    return len(somente_digitos(telefone)) in (10, 11)


def formatar_telefone(telefone):
    t = somente_digitos(telefone)
    if len(t) == 11:
        return f"({t[:2]}) {t[2:7]}-{t[7:]}"
    if len(t) == 10:
        return f"({t[:2]}) {t[2:6]}-{t[6:]}"
    return telefone or ""


def validar_email(email):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email or ""))


def validar_nome(nome):
    nome = " ".join((nome or "").split())
    if len(nome) < 3 or not re.search(r"[A-Za-zÀ-ÿ]", nome):
        raise ErroNegocio("Informe o nome completo.")
    return nome


def converter_data(valor, rotulo="Data", permitir_futuro=False):
    """Aceita DD/MM/AAAA, DD-MM-AAAA ou um objeto date. Devolve date."""
    if isinstance(valor, datetime):
        valor = valor.date()
    if isinstance(valor, date):
        resultado = valor
    else:
        texto = (valor or "").strip()
        resultado = None
        for formato in ("%d/%m/%Y", "%d-%m-%Y"):
            try:
                resultado = datetime.strptime(texto, formato).date()
                break
            except ValueError:
                continue
        if resultado is None:
            raise ErroNegocio(f"{rotulo} inválida. Use o formato DD/MM/AAAA.")
    if not permitir_futuro and resultado > date.today():
        raise ErroNegocio(f"{rotulo} não pode ser futura.")
    return resultado


def calcular_idade(nascimento, hoje=None):
    hoje = hoje or date.today()
    return hoje.year - nascimento.year - (
        (hoje.month, hoje.day) < (nascimento.month, nascimento.day))


def validar_nascimento(valor):
    nasc = converter_data(valor, "Data de nascimento")
    if calcular_idade(nasc) > 120:
        raise ErroNegocio("Data de nascimento inválida.")
    return nasc


def validar_hora(texto, rotulo="Horário"):
    try:
        return datetime.strptime((texto or "").strip(), "%H:%M").strftime("%H:%M:00")
    except ValueError:
        raise ErroNegocio(f"{rotulo} inválido. Use HH:MM.")


def validar_senha(senha):
    """Mínimo de 8 caracteres, com letra e número (RNF07)."""
    if len(senha or "") < 8 or not re.search(r"[A-Za-z]", senha) \
            or not re.search(r"\d", senha):
        raise ErroNegocio("A senha deve ter ao menos 8 caracteres, com letras e números.")
