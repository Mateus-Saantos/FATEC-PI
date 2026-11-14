# Sistema do Instituto Batista Lázaro Ferreira Filho (módulos em Python)

Projeto Integrador ADS I - FATEC Paulínia - 2026.
Aplicação de terminal que usa o banco de dados MySQL/MariaDB da pasta `banco/`.

## Módulos (um arquivo cada)

| Arquivo | O que faz | Requisitos |
|---|---|---|
| `autenticacao.py` | Login por e-mail ou telefone, termo LGPD no primeiro acesso, recuperação de senha, bloqueio por tentativas | RF06, RF07, RF08, RN009, RN012 |
| `cadastro_beneficiario.py` | Cadastro do beneficiário, matrícula nas turmas, responsável legal para menores | RF02, RF05, RN004, LGPD art. 14 |
| `cadastro_voluntario.py` | Cadastro do voluntário com Termo de Voluntariado; cria o acesso como Professor | RF01, RN001, RN014 |
| `cadastro_secretario.py` | Cadastro de secretário (só o Administrador) | RF04 |
| `cadastro_modalidade.py` | Modalidades, turmas (dias, sala, horário), vagas e limite de faltas | RF03, RN004, RN005, RN006 |
| `consulta_cadastros.py` | Busca de beneficiários e voluntários; correção de contato (só o Administrador) | RF14, RF15, RN013 |
| `chamada.py` | Chamada com alerta de faltas, consulta de chamadas e histórico do aluno | RF09, RF10, RF11, RN007, RN008 |
| `relatorios.py` | Consulta com filtros, modelos, exportação PDF/XLSX/CSV e impressão | RF12, RN010 |
| `auditoria.py` | Registro e consulta do log de acessos e alterações | RF13, RN011 |

Apoio: `config.py` (variáveis de ambiente), `db.py` (conexão e transações), `erros.py`,
`seguranca.py` (hash bcrypt, sessão, permissões), `validacao.py` (CPF, datas, senha...),
`interface.py` (telas do terminal) e `main.py` (login e menus por perfil).

Cada função de negócio recebe a sessão do usuário, valida os dados, grava no banco dentro
de uma transação e devolve um `Resultado(ok, mensagem, dados)`. As telas de terminal ficam
no fim de cada arquivo, separadas da regra de negócio.

## Como executar

1. Instalar o MySQL 8 ou MariaDB 10.5+ e o Python 3.10+.
2. Criar o banco (na pasta `banco/`):
   ```
   mysql -u root -p < 01_schema_instituto_batista.sql
   mysql -u root -p < 02_dados_exemplo.sql
   ```
3. Criar um usuário de banco só para o sistema, sem permissão de apagar histórico:
   ```sql
   CREATE USER 'app_sistema'@'localhost' IDENTIFIED BY 'troque-esta-senha';
   GRANT SELECT, INSERT, UPDATE ON instituto_batista.* TO 'app_sistema'@'localhost';
   ```
4. Instalar as bibliotecas: `pip install -r requirements.txt`
5. Informar a conexão e rodar:
   ```
   export DB_USER=app_sistema DB_PASSWORD='troque-esta-senha'     # Windows: set DB_USER=...
   python main.py
   ```

Usuários de exemplo (senha `Demo@2026`): `admin@demo.org` (Administrador),
`secretaria@demo.org` (Secretário), `maria.silva@demo.org` (Professora de Balé),
`carlos.santos@demo.org` (Professor de Judô), `lucia.costa@demo.org` (primeiro acesso: mostra o termo LGPD).

## Testes

```
export MYSQL_CLI="mysql -u root -p'senha-do-root'"    # o teste recria o banco a cada caso
export DB_USER=root DB_PASSWORD='senha-do-root'
python -m unittest tests.test_sistema -v
```
São 43 testes: validações, login e recuperação de senha, cadastros, chamada com liberação de
vaga, relatórios, exportações e permissões por perfil. O teste apaga e recria o banco
`instituto_batista`: nunca rode contra dados reais.

## Limitações conhecidas (explicar na apresentação)

- É uma aplicação de **terminal**; a interface web é o protótipo do Figma. Os módulos
  (regras e acesso ao banco) são a base para uma API ou interface web.
- **Não há envio real de e-mail.** A recuperação de senha mostra o link no terminal
  (simulação). Em produção: SMTP e não devolver o link.
- A sessão e o bloqueio de tentativas ficam em memória (somem ao fechar o programa).
- O dígito verificador do CPF é validado aqui (Python); o banco confere só o formato.
- Impressão simulada no terminal; em uma aplicação web seria a janela de impressão do navegador.
- Beneficiário não tem login (os perfis definidos são Administrador, Secretário e Professor).

