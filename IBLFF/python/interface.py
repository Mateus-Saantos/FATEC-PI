"""Funções de tela do terminal usadas por todos os módulos."""
import getpass


def linha(caractere="-", tamanho=78):
    print(caractere * tamanho)


def cabecalho(titulo):
    print()
    linha("=")
    print(titulo.upper())
    linha("=")


def ler(rotulo, obrigatorio=True, padrao=None):
    """Lê um texto do teclado. Repete enquanto estiver vazio (se obrigatório)."""
    while True:
        sufixo = f" [{padrao}]" if padrao else ""
        valor = input(f"{rotulo}{sufixo}: ").strip()
        if not valor and padrao:
            return padrao
        if valor or not obrigatorio:
            return valor
        print("Campo obrigatório.")


def ler_senha(rotulo="Senha"):
    return getpass.getpass(f"{rotulo}: ")


def confirmar(pergunta):
    return input(f"{pergunta} (s/n): ").strip().lower() in ("s", "sim")


def mostrar(resultado):
    """Mostra a mensagem de um Resultado de forma objetiva."""
    print(("[OK] " if resultado.ok else "[ERRO] ") + resultado.mensagem)
    return resultado.ok


def tabela(linhas, colunas):
    """colunas = [(chave, título, largura), ...]"""
    if not linhas:
        print("Nenhum registro encontrado.")
        return
    cab = " | ".join(f"{t:<{l}}" for _, t, l in colunas)
    print(cab)
    print("-" * len(cab))
    for item in linhas:
        print(" | ".join(f"{str(item.get(c, '') if item.get(c) is not None else ''):<{l}.{l}}"
                         for c, _, l in colunas))


def ler_inteiros(rotulo):
    """Lê números separados por vírgula (ex.: '1, 3') e devolve uma lista."""
    texto = ler(rotulo)
    try:
        return [int(x) for x in texto.replace(";", ",").split(",") if x.strip()]
    except ValueError:
        print("Digite apenas números separados por vírgula.")
        return []
