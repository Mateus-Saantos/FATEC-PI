SET NAMES utf8mb4;   -- garante UTF-8 independentemente do terminal
-- =====================================================================
-- PROJETO INTEGRADOR ADS I - FATEC Paulínia - 2026
-- Sistema de Cadastro de Voluntários e Beneficiários
-- Instituto Batista Lázaro Ferreira Filho
-- Script DDL (MySQL 8 / MariaDB 10.5+)  |  Charset utf8mb4
-- Ordem de execução: 01_schema -> 02_dados_exemplo -> 03_testes
-- =====================================================================

DROP DATABASE IF EXISTS instituto_batista;
CREATE DATABASE instituto_batista
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
USE instituto_batista;

-- ---------------------------------------------------------------------
-- 1. PESSOAS E ACESSO
-- ---------------------------------------------------------------------

-- Dados pessoais comuns a voluntários, beneficiários e secretários.
-- CPF, e-mail e telefone são únicos (RF05, RN003; login por e-mail
-- ou telefone, RF06). CPF/telefone/endereço são opcionais porque o
-- secretário é cadastrado só com nome, e-mail e senha (RF04).
CREATE TABLE pessoa (
    id           INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    nome         VARCHAR(120)  NOT NULL,
    data_nasc    DATE          NULL,
    cpf          CHAR(11)      NULL,                -- somente dígitos
    telefone     VARCHAR(15)   NULL,                -- somente dígitos, com DDD
    email        VARCHAR(120)  NULL,
    endereco     VARCHAR(255)  NULL,
    criado_em    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_pessoa_cpf (cpf),
    UNIQUE KEY uq_pessoa_email (email),
    UNIQUE KEY uq_pessoa_telefone (telefone),
    CONSTRAINT ck_pessoa_cpf CHECK (cpf IS NULL OR cpf REGEXP '^[0-9]{11}$'),
    CONSTRAINT ck_pessoa_contato CHECK (email IS NOT NULL OR telefone IS NOT NULL)
) ENGINE=InnoDB;

-- Perfis de acesso (RF14): Administrador, Secretário, Professor.
CREATE TABLE perfil (
    id    TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    nome  VARCHAR(30)      NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_perfil_nome (nome)
) ENGINE=InnoDB;

-- Credenciais de acesso. Só a senha em HASH é armazenada (RNF07),
-- nunca a senha em texto. Use bcrypt (custo >= 10) na aplicação.
CREATE TABLE usuario (
    id             INT UNSIGNED     NOT NULL AUTO_INCREMENT,
    pessoa_id      INT UNSIGNED     NOT NULL,
    perfil_id      TINYINT UNSIGNED NOT NULL,
    senha_hash     VARCHAR(255)     NOT NULL,
    primeiro_acesso BOOLEAN         NOT NULL DEFAULT TRUE,  -- RF08
    ativo          BOOLEAN          NOT NULL DEFAULT TRUE,
    criado_em      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_usuario_pessoa (pessoa_id),
    CONSTRAINT fk_usuario_pessoa FOREIGN KEY (pessoa_id) REFERENCES pessoa (id),
    CONSTRAINT fk_usuario_perfil FOREIGN KEY (perfil_id) REFERENCES perfil (id)
) ENGINE=InnoDB;

-- Prova do consentimento LGPD (RF08, RN012): quando, qual versão
-- do termo e de qual IP o usuário aceitou.
CREATE TABLE aceite_lgpd (
    id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
    usuario_id    INT UNSIGNED NOT NULL,
    versao_termo  VARCHAR(20)  NOT NULL,
    aceito_em     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip            VARCHAR(45)  NULL,
    PRIMARY KEY (id),
    KEY ix_aceite_usuario (usuario_id),
    CONSTRAINT fk_aceite_usuario FOREIGN KEY (usuario_id) REFERENCES usuario (id)
) ENGINE=InnoDB;

-- Recuperação de senha (RF07, RN009). Guarda apenas o HASH do token;
-- o token vale 1 hora e só pode ser usado uma vez.
CREATE TABLE token_redefinicao_senha (
    id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    usuario_id  INT UNSIGNED NOT NULL,
    token_hash  CHAR(64)     NOT NULL,
    expira_em   DATETIME     NOT NULL,
    usado_em    DATETIME     NULL,
    criado_em   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_token_hash (token_hash),
    KEY ix_token_usuario (usuario_id),
    CONSTRAINT fk_token_usuario FOREIGN KEY (usuario_id) REFERENCES usuario (id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 2. VOLUNTÁRIOS E BENEFICIÁRIOS
-- ---------------------------------------------------------------------

-- RF01, RN001, RN014: o termo de voluntariado deve estar assinado
-- antes do cadastro ser liberado.
CREATE TABLE voluntario (
    id               INT UNSIGNED NOT NULL AUTO_INCREMENT,
    pessoa_id        INT UNSIGNED NOT NULL,
    materia_funcao   VARCHAR(80)  NOT NULL,
    termo_assinado   BOOLEAN      NOT NULL DEFAULT FALSE,
    data_assinatura  DATE         NULL,
    ativo            BOOLEAN      NOT NULL DEFAULT TRUE,
    PRIMARY KEY (id),
    UNIQUE KEY uq_voluntario_pessoa (pessoa_id),
    CONSTRAINT fk_voluntario_pessoa FOREIGN KEY (pessoa_id) REFERENCES pessoa (id),
    CONSTRAINT ck_voluntario_termo CHECK (termo_assinado = FALSE OR data_assinatura IS NOT NULL)
) ENGINE=InnoDB;

-- RF02, RN002. Para menores de 18 anos o responsável legal e o
-- consentimento dele são obrigatórios (LGPD, art. 14) - ver triggers.
CREATE TABLE beneficiario (
    id             INT UNSIGNED NOT NULL AUTO_INCREMENT,
    pessoa_id      INT UNSIGNED NOT NULL,
    responsavel_nome             VARCHAR(120) NULL,
    responsavel_cpf              CHAR(11)     NULL,
    responsavel_telefone         VARCHAR(15)  NULL,
    consentimento_responsavel_em DATETIME     NULL,
    ativo          BOOLEAN      NOT NULL DEFAULT TRUE,
    criado_em      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_beneficiario_pessoa (pessoa_id),
    CONSTRAINT fk_beneficiario_pessoa FOREIGN KEY (pessoa_id) REFERENCES pessoa (id),
    CONSTRAINT ck_benef_resp_cpf CHECK (responsavel_cpf IS NULL OR responsavel_cpf REGEXP '^[0-9]{11}$')
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 3. MODALIDADES, TURMAS E MATRÍCULAS
-- ---------------------------------------------------------------------

-- RF03, RN004, RN005, RN006.
-- limite_faltas: valor "X" configurável por modalidade (RN005).
CREATE TABLE modalidade (
    id              INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    nome            VARCHAR(80)   NOT NULL,
    descricao       VARCHAR(255)  NULL,               -- texto do card
    voluntario_id   INT UNSIGNED  NOT NULL,           -- responsável
    periodicidade   VARCHAR(60)   NOT NULL,           -- ex.: '2x por semana'
    vagas_maximas   SMALLINT UNSIGNED NOT NULL,
    limite_faltas   TINYINT UNSIGNED  NOT NULL DEFAULT 3,
    ativo           BOOLEAN       NOT NULL DEFAULT TRUE,
    PRIMARY KEY (id),
    UNIQUE KEY uq_modalidade_nome (nome),
    KEY ix_modalidade_voluntario (voluntario_id),
    CONSTRAINT fk_modalidade_voluntario FOREIGN KEY (voluntario_id) REFERENCES voluntario (id),
    CONSTRAINT ck_modalidade_vagas  CHECK (vagas_maximas > 0),
    CONSTRAINT ck_modalidade_faltas CHECK (limite_faltas > 0)
) ENGINE=InnoDB;

-- Turma = grupo de uma modalidade conduzido por um professor (voluntário).
CREATE TABLE turma (
    id             INT UNSIGNED NOT NULL AUTO_INCREMENT,
    modalidade_id  INT UNSIGNED NOT NULL,
    voluntario_id  INT UNSIGNED NOT NULL,             -- professor da turma
    nome           VARCHAR(80)  NOT NULL,
    sala           VARCHAR(30)  NULL,
    horario_inicio TIME         NOT NULL DEFAULT '19:00:00',
    horario_fim    TIME         NOT NULL DEFAULT '21:00:00',
    ativa          BOOLEAN      NOT NULL DEFAULT TRUE,
    PRIMARY KEY (id),
    UNIQUE KEY uq_turma_nome (modalidade_id, nome),
    KEY ix_turma_voluntario (voluntario_id),
    CONSTRAINT fk_turma_modalidade FOREIGN KEY (modalidade_id) REFERENCES modalidade (id),
    CONSTRAINT fk_turma_voluntario FOREIGN KEY (voluntario_id) REFERENCES voluntario (id),
    CONSTRAINT ck_turma_horario CHECK (horario_fim > horario_inicio)
) ENGINE=InnoDB;

-- Dias da semana de cada turma (uma turma pode ter vários dias).
CREATE TABLE turma_dia (
    turma_id    INT UNSIGNED NOT NULL,
    dia_semana  ENUM('SEG','TER','QUA','QUI','SEX','SAB') NOT NULL,
    PRIMARY KEY (turma_id, dia_semana),
    CONSTRAINT fk_turma_dia FOREIGN KEY (turma_id) REFERENCES turma (id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

-- Vínculo do beneficiário com a turma. A vaga fica ocupada enquanto
-- status = 'ATIVA'. Ao atingir o limite de faltas, vira 'VAGA_LIBERADA'
-- (RF10) - o registro NÃO é apagado, preservando o histórico (RN008).
CREATE TABLE matricula (
    id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
    beneficiario_id INT UNSIGNED NOT NULL,
    turma_id        INT UNSIGNED NOT NULL,
    status          ENUM('ATIVA','VAGA_LIBERADA','CANCELADA') NOT NULL DEFAULT 'ATIVA',
    data_matricula  DATE         NOT NULL DEFAULT (CURRENT_DATE),
    data_encerramento DATE       NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_matricula (beneficiario_id, turma_id),
    KEY ix_matricula_turma (turma_id, status),
    CONSTRAINT fk_matricula_beneficiario FOREIGN KEY (beneficiario_id) REFERENCES beneficiario (id),
    CONSTRAINT fk_matricula_turma FOREIGN KEY (turma_id) REFERENCES turma (id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 4. CHAMADA E PRESENÇA
-- ---------------------------------------------------------------------

-- Uma chamada = uma aula de uma turma em uma data (RF09).
CREATE TABLE chamada (
    id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
    turma_id      INT UNSIGNED NOT NULL,
    data_aula     DATE         NOT NULL,
    registrada_por INT UNSIGNED NOT NULL,             -- usuario (professor)
    registrada_em DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_chamada_turma_data (turma_id, data_aula),
    KEY ix_chamada_data (data_aula),
    CONSTRAINT fk_chamada_turma   FOREIGN KEY (turma_id) REFERENCES turma (id),
    CONSTRAINT fk_chamada_usuario FOREIGN KEY (registrada_por) REFERENCES usuario (id)
) ENGINE=InnoDB;

-- Presença de cada aluno em cada chamada (RF09, RF11).
CREATE TABLE presenca (
    id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
    chamada_id    INT UNSIGNED NOT NULL,
    matricula_id  INT UNSIGNED NOT NULL,
    status        ENUM('PRESENTE','AUSENTE') NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_presenca (chamada_id, matricula_id),
    KEY ix_presenca_matricula (matricula_id),
    CONSTRAINT fk_presenca_chamada   FOREIGN KEY (chamada_id)   REFERENCES chamada (id),
    CONSTRAINT fk_presenca_matricula FOREIGN KEY (matricula_id) REFERENCES matricula (id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 5. RELATÓRIOS E AUDITORIA
-- ---------------------------------------------------------------------

-- Modelos de relatório criados pelo administrador (Caso de uso 4.1).
CREATE TABLE modelo_relatorio (
    id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    nome        VARCHAR(80)  NOT NULL,
    criado_por  INT UNSIGNED NOT NULL,
    criado_em   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_modelo_nome (nome),
    CONSTRAINT fk_modelo_usuario FOREIGN KEY (criado_por) REFERENCES usuario (id)
) ENGINE=InnoDB;

CREATE TABLE modelo_relatorio_campo (
    modelo_id  INT UNSIGNED NOT NULL,
    campo      VARCHAR(60)  NOT NULL,                 -- ex.: 'beneficiario', 'faltas'
    ordem      TINYINT UNSIGNED NOT NULL DEFAULT 1,
    PRIMARY KEY (modelo_id, campo),
    CONSTRAINT fk_modelo_campo FOREIGN KEY (modelo_id) REFERENCES modelo_relatorio (id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

-- Auditoria (RF13, RN011, RNF06): login, alterações e chamadas.
CREATE TABLE log_auditoria (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    usuario_id  INT UNSIGNED    NULL,                 -- NULL em login falho
    tipo_evento VARCHAR(40)     NOT NULL,             -- ex.: 'LOGIN_OK', 'CHAMADA_REGISTRADA'
    entidade    VARCHAR(40)     NULL,
    entidade_id INT UNSIGNED    NULL,
    detalhe     VARCHAR(255)    NULL,
    ip          VARCHAR(45)     NULL,
    criado_em   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_log_data (criado_em),
    KEY ix_log_usuario (usuario_id),
    KEY ix_log_evento (tipo_evento)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 6. REGRAS DE NEGÓCIO NO BANCO (funções, triggers, views)
-- ---------------------------------------------------------------------
DELIMITER $$

-- Faltas consecutivas de uma matrícula (RF10/RN005).
-- Conta as faltas posteriores à última aula em que o aluno compareceu.
CREATE FUNCTION fn_faltas_consecutivas(p_matricula_id INT UNSIGNED)
RETURNS INT
READS SQL DATA
BEGIN
    DECLARE v_ultima DATE;
    DECLARE v_total  INT;

    SELECT MAX(c.data_aula) INTO v_ultima
      FROM presenca p
      JOIN chamada  c ON c.id = p.chamada_id
     WHERE p.matricula_id = p_matricula_id
       AND p.status <> 'AUSENTE';

    SELECT COUNT(*) INTO v_total
      FROM presenca p
      JOIN chamada  c ON c.id = p.chamada_id
     WHERE p.matricula_id = p_matricula_id
       AND p.status = 'AUSENTE'
       AND c.data_aula > COALESCE(v_ultima, '1000-01-01');

    RETURN v_total;
END$$

-- RN004: bloqueia matrícula quando a modalidade está sem vagas.
CREATE TRIGGER trg_matricula_bi
BEFORE INSERT ON matricula
FOR EACH ROW
BEGIN
    DECLARE v_max      INT;
    DECLARE v_ocupadas INT;

    IF NEW.status = 'ATIVA' THEN
        SELECT m.vagas_maximas INTO v_max
          FROM turma t JOIN modalidade m ON m.id = t.modalidade_id
         WHERE t.id = NEW.turma_id;

        SELECT COUNT(*) INTO v_ocupadas
          FROM matricula mt
          JOIN turma t ON t.id = mt.turma_id
         WHERE mt.status = 'ATIVA'
           AND t.modalidade_id = (SELECT modalidade_id FROM turma WHERE id = NEW.turma_id);

        IF v_ocupadas >= v_max THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Modalidade sem vagas disponiveis';
        END IF;
    END IF;
END$$

-- RF10/RN005: após registrar uma falta, libera a vaga se atingiu o limite.
CREATE TRIGGER trg_presenca_ai
AFTER INSERT ON presenca
FOR EACH ROW
BEGIN
    DECLARE v_limite INT;
    DECLARE v_faltas INT;

    IF NEW.status = 'AUSENTE' THEN
        SELECT m.limite_faltas INTO v_limite
          FROM matricula mt
          JOIN turma t      ON t.id = mt.turma_id
          JOIN modalidade m ON m.id = t.modalidade_id
         WHERE mt.id = NEW.matricula_id;

        SET v_faltas = fn_faltas_consecutivas(NEW.matricula_id);

        IF v_faltas >= v_limite THEN
            UPDATE matricula
               SET status = 'VAGA_LIBERADA', data_encerramento = CURRENT_DATE
             WHERE id = NEW.matricula_id AND status = 'ATIVA';

            INSERT INTO log_auditoria (tipo_evento, entidade, entidade_id, detalhe)
            VALUES ('VAGA_LIBERADA', 'matricula', NEW.matricula_id,
                    CONCAT(v_faltas, ' faltas consecutivas'));
        END IF;
    END IF;
END$$

-- RN008/RNF05: histórico de presença nunca é excluído.
CREATE TRIGGER trg_presenca_bd BEFORE DELETE ON presenca
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Historico de presenca nao pode ser excluido';
END$$

CREATE TRIGGER trg_chamada_bd BEFORE DELETE ON chamada
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Chamada nao pode ser excluida';
END$$

-- RN001/RN014: voluntário só pode ser liberado com o termo assinado.
-- (voluntário sem termo é permitido no cadastro, mas não pode ser
-- responsável por modalidade nem professor de turma.)
CREATE TRIGGER trg_modalidade_bi BEFORE INSERT ON modalidade
FOR EACH ROW
BEGIN
    IF (SELECT termo_assinado FROM voluntario WHERE id = NEW.voluntario_id) = FALSE THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Voluntario sem termo de voluntariado assinado';
    END IF;
END$$

CREATE TRIGGER trg_turma_bi BEFORE INSERT ON turma
FOR EACH ROW
BEGIN
    IF (SELECT termo_assinado FROM voluntario WHERE id = NEW.voluntario_id) = FALSE THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Voluntario sem termo de voluntariado assinado';
    END IF;
END$$

-- LGPD art. 14: beneficiário menor de 18 anos exige responsável legal
-- (nome e telefone) e a data do consentimento dele.
CREATE TRIGGER trg_beneficiario_bi BEFORE INSERT ON beneficiario
FOR EACH ROW
BEGIN
    DECLARE v_nasc DATE;
    SELECT data_nasc INTO v_nasc FROM pessoa WHERE id = NEW.pessoa_id;
    IF v_nasc IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Data de nascimento obrigatoria para beneficiario';
    END IF;
    IF TIMESTAMPDIFF(YEAR, v_nasc, CURDATE()) < 18
       AND (NEW.responsavel_nome IS NULL OR NEW.responsavel_telefone IS NULL
            OR NEW.consentimento_responsavel_em IS NULL) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Menor de idade exige responsavel legal e consentimento';
    END IF;
END$$

CREATE TRIGGER trg_beneficiario_bu BEFORE UPDATE ON beneficiario
FOR EACH ROW
BEGIN
    DECLARE v_nasc DATE;
    SELECT data_nasc INTO v_nasc FROM pessoa WHERE id = NEW.pessoa_id;
    IF v_nasc IS NOT NULL
       AND TIMESTAMPDIFF(YEAR, v_nasc, CURDATE()) < 18
       AND (NEW.responsavel_nome IS NULL OR NEW.responsavel_telefone IS NULL
            OR NEW.consentimento_responsavel_em IS NULL) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Menor de idade exige responsavel legal e consentimento';
    END IF;
END$$

DELIMITER ;

-- Ocupação de vagas por modalidade (alimenta os cards da tela de
-- Gestão de Modalidades: "15/20 vagas preenchidas" e "Turma Lotada").
CREATE VIEW vw_vagas_modalidade AS
SELECT m.id AS modalidade_id,
       m.nome AS modalidade,
       m.vagas_maximas,
       COUNT(mt.id)                         AS vagas_ocupadas,
       m.vagas_maximas - COUNT(mt.id)       AS vagas_disponiveis,
       (COUNT(mt.id) >= m.vagas_maximas)    AS lotada
  FROM modalidade m
  LEFT JOIN turma t      ON t.modalidade_id = m.id
  LEFT JOIN matricula mt ON mt.turma_id = t.id AND mt.status = 'ATIVA'
 WHERE m.ativo = TRUE
 GROUP BY m.id, m.nome, m.vagas_maximas;

-- Histórico e frequência por matrícula (RF11) e base dos relatórios
-- (RF12). A coluna "situacao" gera os selos da tela de relatórios:
-- ATIVO / FALTAS RECORRENTES (a 1 falta do limite) / VAGA LIBERADA.
CREATE VIEW vw_frequencia AS
SELECT mt.id                AS matricula_id,
       p.nome               AS beneficiario,
       p.cpf,
       md.nome              AS modalidade,
       t.nome               AS turma,
       mt.status            AS status_matricula,
       COUNT(pr.id)         AS total_aulas,
       COALESCE(SUM(pr.status = 'PRESENTE'), 0) AS presencas,
       COALESCE(SUM(pr.status = 'AUSENTE'), 0)  AS faltas,
       ROUND(100 * SUM(pr.status = 'PRESENTE') / NULLIF(COUNT(pr.id), 0), 1)
                            AS percentual_frequencia,
       fn_faltas_consecutivas(mt.id) AS faltas_consecutivas,
       CASE
         WHEN mt.status = 'VAGA_LIBERADA' THEN 'VAGA LIBERADA'
         WHEN mt.status = 'CANCELADA'     THEN 'CANCELADA'
         WHEN fn_faltas_consecutivas(mt.id) >= md.limite_faltas - 1
                                          THEN 'FALTAS RECORRENTES'
         ELSE 'ATIVO'
       END AS situacao
  FROM matricula mt
  JOIN beneficiario b ON b.id = mt.beneficiario_id
  JOIN pessoa p       ON p.id = b.pessoa_id
  JOIN turma t        ON t.id = mt.turma_id
  JOIN modalidade md  ON md.id = t.modalidade_id
  LEFT JOIN presenca pr ON pr.matricula_id = mt.id
 GROUP BY mt.id, p.nome, p.cpf, md.nome, md.limite_faltas, t.nome, mt.status;

-- Lista da tela de Chamada: só alunos com matrícula ATIVA, com o
-- contador "faltas/limite" (ex.: 2/3) e o alerta visual (OK, ATENCAO).
-- Quem já perdeu a vaga não aparece mais na lista.
CREATE VIEW vw_lista_chamada AS
SELECT mt.turma_id,
       mt.id                          AS matricula_id,
       p.nome                         AS aluno,
       fn_faltas_consecutivas(mt.id)  AS faltas_consecutivas,
       md.limite_faltas,
       CASE
         WHEN fn_faltas_consecutivas(mt.id) >= md.limite_faltas     THEN 'LIMITE'
         WHEN fn_faltas_consecutivas(mt.id) >= md.limite_faltas - 1 THEN 'ATENCAO'
         ELSE 'OK'
       END AS alerta
  FROM matricula mt
  JOIN beneficiario b ON b.id = mt.beneficiario_id AND b.ativo = TRUE
  JOIN pessoa p       ON p.id = b.pessoa_id
  JOIN turma t        ON t.id = mt.turma_id AND t.ativa = TRUE
  JOIN modalidade md  ON md.id = t.modalidade_id
 WHERE mt.status = 'ATIVA';

-- ---------------------------------------------------------------------
-- 7. DADOS DE DOMÍNIO (obrigatórios para o sistema funcionar)
-- ---------------------------------------------------------------------
INSERT INTO perfil (nome) VALUES ('Administrador'), ('Secretário'), ('Professor');
