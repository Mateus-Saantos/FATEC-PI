SET NAMES utf8mb4;   -- garante UTF-8 independentemente do terminal
-- =====================================================================
-- TESTES DAS REGRAS DE NEGÓCIO DO BANCO (evidência para a banca)
-- Rodar depois de 01 e 02:  mysql --force -t < 03_testes_banco.sql
-- (--force continua após os erros que são ESPERADOS)
-- =====================================================================
USE instituto_batista;

SELECT '--- T1 (RN003/RF05): CPF duplicado deve ser REJEITADO ---' AS teste;
INSERT INTO pessoa (nome, cpf, email) VALUES ('Duplicado', '54323194897', 'dup@demo.org');
-- ESPERADO: ERROR 1062 Duplicate entry (uq_pessoa_cpf)

SELECT '--- T2 (RF05): CPF fora do formato deve ser REJEITADO ---' AS teste;
INSERT INTO pessoa (nome, cpf, email) VALUES ('CPF ruim', '123', 'ruim@demo.org');
-- ESPERADO: ERROR 4025 CONSTRAINT ck_pessoa_cpf failed
-- (o dígito verificador do CPF é validado na aplicação)

SELECT '--- T3 (LGPD art. 14): menor sem responsável é REJEITADO ---' AS teste;
INSERT INTO pessoa (id, nome, data_nasc, email) VALUES (51, 'Menor Teste', '2014-03-03', 'menor@demo.org');
INSERT INTO beneficiario (pessoa_id) VALUES (51);
-- ESPERADO: ERROR 1644 'Menor de idade exige responsavel legal e consentimento'
INSERT INTO pessoa (id, nome, email) VALUES (52, 'Sem Nascimento', 'semnasc@demo.org');
INSERT INTO beneficiario (pessoa_id) VALUES (52);
-- ESPERADO: ERROR 1644 'Data de nascimento obrigatoria para beneficiario'
INSERT INTO beneficiario (pessoa_id, responsavel_nome, responsavel_telefone, consentimento_responsavel_em)
VALUES (51, 'Responsável Teste', '19991119999', NOW());
-- ESPERADO: aceito (menor COM responsável e consentimento)

SELECT '--- T4 (RN014): voluntário sem termo não vira responsável ---' AS teste;
INSERT INTO pessoa (id, nome, cpf, email) VALUES (50, 'Voluntário sem termo', '56321223360', 'sem.termo@demo.org');
INSERT INTO voluntario (id, pessoa_id, materia_funcao, termo_assinado) VALUES (50, 50, 'Violão', FALSE);
INSERT INTO modalidade (nome, voluntario_id, periodicidade, vagas_maximas)
VALUES ('Violão', 50, '1x por semana', 10);
-- ESPERADO: ERROR 1644 'Voluntario sem termo de voluntariado assinado'

SELECT '--- T5 (RF09/RF10/RN005): 3ª falta seguida de Clara libera a vaga ---' AS teste;
SELECT beneficiario, faltas_consecutivas, situacao FROM vw_frequencia WHERE turma = 'Balé Turma A';
-- ANTES: Clara = 2 faltas consecutivas, situação FALTAS RECORRENTES
INSERT INTO chamada (turma_id, data_aula, registrada_por) VALUES (1, '2026-11-05', 3);
SET @ch = LAST_INSERT_ID();
INSERT INTO presenca (chamada_id, matricula_id, status) VALUES
 (@ch,1,'AUSENTE'), (@ch,2,'PRESENTE'), (@ch,3,'AUSENTE'),
 (@ch,4,'PRESENTE'), (@ch,5,'PRESENTE'), (@ch,6,'PRESENTE');
SELECT beneficiario, faltas_consecutivas, situacao FROM vw_frequencia WHERE turma = 'Balé Turma A';
-- ESPERADO: Clara = 3, VAGA LIBERADA; Ana = 2, FALTAS RECORRENTES; demais ATIVO

SELECT '--- T6 (tela de chamada): lista só com alunos ativos e alerta ---' AS teste;
SELECT aluno, CONCAT(faltas_consecutivas, '/', limite_faltas) AS faltas, alerta
  FROM vw_lista_chamada WHERE turma_id = 1 ORDER BY aluno;
-- ESPERADO: 5 alunos (Clara saiu); Ana com 2/3 e alerta ATENCAO

SELECT '--- T7 (RN004): modalidade lotada bloqueia matrícula; vaga liberada reabre ---' AS teste;
INSERT INTO modalidade (id, nome, voluntario_id, periodicidade, vagas_maximas, limite_faltas)
VALUES (90, 'Oficina Teste', 1, '1x por semana', 2, 3);
INSERT INTO turma (id, modalidade_id, voluntario_id, nome, sala) VALUES (90, 90, 1, 'Oficina Teste A', 'Sala D');
INSERT INTO matricula (beneficiario_id, turma_id) VALUES (7, 90), (8, 90);   -- Carlos e Mariana
SELECT modalidade, vagas_ocupadas, vagas_maximas, lotada FROM vw_vagas_modalidade WHERE modalidade = 'Oficina Teste';
INSERT INTO matricula (beneficiario_id, turma_id) VALUES (2, 90);            -- Beatriz Ramos
-- ESPERADO: ERROR 1644 'Modalidade sem vagas disponiveis' (2/2, lotada = 1)
SET @mc = (SELECT id FROM matricula WHERE beneficiario_id = 7 AND turma_id = 90);
SET @mm = (SELECT id FROM matricula WHERE beneficiario_id = 8 AND turma_id = 90);
INSERT INTO chamada (turma_id, data_aula, registrada_por) VALUES (90, '2026-11-09', 3);
INSERT INTO presenca (chamada_id, matricula_id, status) VALUES (LAST_INSERT_ID(), @mc, 'AUSENTE'), (LAST_INSERT_ID(), @mm, 'PRESENTE');
INSERT INTO chamada (turma_id, data_aula, registrada_por) VALUES (90, '2026-11-16', 3);
INSERT INTO presenca (chamada_id, matricula_id, status) VALUES (LAST_INSERT_ID(), @mc, 'AUSENTE'), (LAST_INSERT_ID(), @mm, 'PRESENTE');
INSERT INTO chamada (turma_id, data_aula, registrada_por) VALUES (90, '2026-11-23', 3);
INSERT INTO presenca (chamada_id, matricula_id, status) VALUES (LAST_INSERT_ID(), @mc, 'AUSENTE'), (LAST_INSERT_ID(), @mm, 'PRESENTE');
SELECT modalidade, vagas_ocupadas, vagas_maximas, lotada FROM vw_vagas_modalidade WHERE modalidade = 'Oficina Teste';
-- ESPERADO: Carlos perdeu a vaga; ocupadas = 1/2, lotada = 0
INSERT INTO matricula (beneficiario_id, turma_id) VALUES (2, 90);
-- ESPERADO: aceita (vaga reaberta)

SELECT '--- T8 (RN008/RNF05): histórico de presença não pode ser apagado ---' AS teste;
DELETE FROM presenca WHERE id = 1;
-- ESPERADO: ERROR 1644 'Historico de presenca nao pode ser excluido'
DELETE FROM chamada WHERE id = 1;
-- ESPERADO: ERROR 1644 'Chamada nao pode ser excluida'

SELECT '--- T9: chamada duplicada (mesma turma e data) é rejeitada ---' AS teste;
INSERT INTO chamada (turma_id, data_aula, registrada_por) VALUES (1, '2026-10-27', 3);
-- ESPERADO: ERROR 1062 Duplicate entry (uq_chamada_turma_data)

SELECT '--- T10 (RF13): auditoria registrou as liberações de vaga ---' AS teste;
SELECT tipo_evento, entidade, entidade_id, detalhe FROM log_auditoria;
-- ESPERADO: 2 linhas VAGA_LIBERADA (Clara e Carlos), '3 faltas consecutivas'

SELECT '--- T11 (cards de modalidades): vagas e lotação ---' AS teste;
SELECT modalidade, vagas_ocupadas, vagas_maximas, vagas_disponiveis, lotada FROM vw_vagas_modalidade ORDER BY modalidade;

SELECT '--- T12 (cards): turmas com vários dias, sala e horário ---' AS teste;
SELECT t.nome AS turma, t.sala, CONCAT(TIME_FORMAT(t.horario_inicio,'%H:%i'),'-',TIME_FORMAT(t.horario_fim,'%H:%i')) AS horario,
       GROUP_CONCAT(td.dia_semana ORDER BY FIELD(td.dia_semana,'SEG','TER','QUA','QUI','SEX','SAB')) AS dias
  FROM turma t JOIN turma_dia td ON td.turma_id = t.id
 WHERE t.id < 90 GROUP BY t.id, t.nome, t.sala, t.horario_inicio, t.horario_fim ORDER BY t.id;

SELECT '--- T13 (RF11/RF12): histórico e frequência por beneficiário ---' AS teste;
SELECT beneficiario, modalidade, total_aulas, presencas, faltas, percentual_frequencia, situacao
  FROM vw_frequencia WHERE turma = 'Balé Turma A' ORDER BY beneficiario;
