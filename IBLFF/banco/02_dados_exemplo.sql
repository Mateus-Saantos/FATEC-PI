SET NAMES utf8mb4;   -- garante UTF-8 independentemente do terminal
-- =====================================================================
-- DADOS FICTÍCIOS PARA DEMONSTRAÇÃO - nunca usar em produção
-- Espelham as telas do protótipo (modalidades, professores, turmas).
-- Nomes, CPFs e telefones são inventados. LGPD: não carregar dados
-- reais de beneficiários (muitos são menores) em ambiente de teste.
-- Senha de todos os usuários de exemplo: Demo@2026 (hash bcrypt, custo 10)
-- =====================================================================
USE instituto_batista;

SET @hash = '$2b$10$YQHtyOBQXWVfBgyNupvyfOIz8Ow2g8Ct3LnLNzpENwNy3JX6W992W';

-- Pessoas: 1 admin, 2 secretária, 3-8 professores, 9-16 beneficiários ----
INSERT INTO pessoa (id, nome, data_nasc, cpf, telefone, email, endereco) VALUES
 (1,  'Administrador Demo', '1985-03-10', '52601815906', '19990000001', 'admin@demo.org',      NULL),
 (2,  'Secretaria Demo',    '1990-07-22', NULL,          '19990000002', 'secretaria@demo.org', NULL),
 (3,  'Maria Silva',        '1984-04-12', '08301661305', '19990000003', 'maria.silva@demo.org',   NULL),
 (4,  'Carlos Santos',      '1979-09-30', '18609139034', '19990000004', 'carlos.santos@demo.org', NULL),
 (5,  'Ana Lima',           '1991-01-18', '99603082430', '19990000005', 'ana.lima@demo.org',      NULL),
 (6,  'Beatriz Nunes',      '1988-06-25', '62819482112', '19990000006', 'beatriz.nunes@demo.org', NULL),
 (7,  'Roberto Dias',       '1982-12-02', '99351819019', '19990000007', 'roberto.dias@demo.org',  NULL),
 (8,  'Lucia Costa',        '1986-08-14', '93786579741', '19990000008', 'lucia.costa@demo.org',   NULL),
 (9,  'Ana Souza',          '2012-05-14', '54323194897', '19990000009', 'resp.ana@demo.org',      'Rua das Flores, 100 - Paulínia/SP'),
 (10, 'Beatriz Ramos',      '2011-08-19', '75749118606', '19990000010', 'resp.beatriz@demo.org',  'Rua Sete, 45 - Paulínia/SP'),
 (11, 'Clara Mendes',       '2013-02-03', '25276018987', '19990000011', 'resp.clara@demo.org',    'Av. Brasil, 250 - Paulínia/SP'),
 (12, 'Daniela Freitas',    '2010-11-27', '55597971115', '19990000012', 'resp.daniela@demo.org',  'Rua Nove, 12 - Paulínia/SP'),
 (13, 'Eduarda Costa',      '2012-09-09', '47104974601', '19990000013', 'resp.eduarda@demo.org',  'Rua Dez, 33 - Paulínia/SP'),
 (14, 'Fernanda Lima',      '2004-06-15', '50752917080', '19990000014', 'fernanda@demo.org',      'Rua Onze, 8 - Paulínia/SP'),
 (15, 'Carlos Pereira',     '2010-09-02', '34236671255', '19990000015', 'resp.carlos@demo.org',   'Rua Doze, 71 - Paulínia/SP'),
 (16, 'Mariana Santos',     '2013-12-20', '76842684650', '19990000016', 'resp.mariana@demo.org',  'Rua Treze, 5 - Paulínia/SP');

-- Usuários (1=Administrador, 2=Secretário, 3=Professor) -------------------
INSERT INTO usuario (id, pessoa_id, perfil_id, senha_hash, primeiro_acesso) VALUES
 (1, 1, 1, @hash, FALSE),
 (2, 2, 2, @hash, FALSE),
 (3, 3, 3, @hash, FALSE),
 (4, 4, 3, @hash, FALSE),
 (5, 5, 3, @hash, FALSE),
 (6, 6, 3, @hash, FALSE),
 (7, 7, 3, @hash, FALSE),
 (8, 8, 3, @hash, TRUE);

INSERT INTO aceite_lgpd (usuario_id, versao_termo, ip)
SELECT id, 'v1.0', '127.0.0.1' FROM usuario WHERE primeiro_acesso = FALSE;

-- Voluntários (professores) com termo assinado --------------------------
INSERT INTO voluntario (id, pessoa_id, materia_funcao, termo_assinado, data_assinatura) VALUES
 (1, 3, 'Balé',    TRUE, '2026-02-01'),
 (2, 4, 'Judô',    TRUE, '2026-02-01'),
 (3, 5, 'Violino', TRUE, '2026-02-01'),
 (4, 6, 'Jazz',    TRUE, '2026-02-01'),
 (5, 7, 'Karatê',  TRUE, '2026-02-01'),
 (6, 8, 'Teclado', TRUE, '2026-02-01');

-- Modalidades (iguais às do protótipo) ----------------------------------
INSERT INTO modalidade (id, nome, descricao, voluntario_id, periodicidade, vagas_maximas, limite_faltas) VALUES
 (1, 'Balé',    'Dança clássica para crianças e jovens, desenvolvendo expressão corporal.', 1, '2x por semana', 20, 3),
 (2, 'Judô',    'Arte marcial japonesa que desenvolve disciplina, foco e respeito.',        2, '2x por semana', 15, 3),
 (3, 'Violino', 'Instrumento de cordas para iniciantes e intermediários.',                  3, '1x por semana', 10, 3),
 (4, 'Jazz',    'Dança moderna e contemporânea, unindo técnica e liberdade criativa.',      4, '2x por semana', 20, 3),
 (5, 'Karatê',  'Arte marcial que cultiva autodefesa, concentração e valores humanos.',     5, '2x por semana', 15, 3),
 (6, 'Teclado', 'Iniciação musical ao teclado e teoria musical básica.',                    6, '1x por semana', 12, 3);

INSERT INTO turma (id, modalidade_id, voluntario_id, nome, sala, horario_inicio, horario_fim) VALUES
 (1, 1, 1, 'Balé Turma A',    'Sala B', '18:30', '20:00'),
 (2, 2, 2, 'Judô Turma A',    'Sala A', '18:00', '19:30'),
 (3, 3, 3, 'Violino Turma A', 'Sala C', '19:00', '21:00'),
 (4, 4, 4, 'Jazz Turma A',    'Sala B', '19:30', '21:00'),
 (5, 5, 5, 'Karatê Turma A',  'Sala A', '18:00', '19:30'),
 (6, 6, 6, 'Teclado Turma A', 'Sala C', '20:00', '21:30');

INSERT INTO turma_dia (turma_id, dia_semana) VALUES
 (1,'TER'),(1,'QUI'),
 (2,'SEG'),(2,'QUA'),
 (3,'SEX'),
 (4,'SEG'),(4,'SEX'),
 (5,'QUA'),(5,'SEX'),
 (6,'TER');

-- Beneficiários: menores com responsável legal e consentimento ----------
INSERT INTO beneficiario (id, pessoa_id, responsavel_nome, responsavel_cpf, responsavel_telefone, consentimento_responsavel_em) VALUES
 (1, 9,  'Márcia Souza',    NULL, '19991110001', '2026-02-10 19:00:00'),
 (2, 10, 'Paulo Ramos',     NULL, '19991110002', '2026-02-10 19:10:00'),
 (3, 11, 'Sandra Mendes',   NULL, '19991110003', '2026-02-11 18:45:00'),
 (4, 12, 'Jorge Freitas',   NULL, '19991110004', '2026-02-11 19:00:00'),
 (5, 13, 'Renata Costa',    NULL, '19991110005', '2026-02-12 19:20:00'),
 (6, 14, NULL, NULL, NULL, NULL),                         -- adulta: dispensa responsável
 (7, 15, 'Luciana Pereira', NULL, '19991110007', '2026-02-12 19:30:00'),
 (8, 16, 'Fábio Santos',    NULL, '19991110008', '2026-02-13 18:50:00');

INSERT INTO matricula (id, beneficiario_id, turma_id) VALUES
 (1, 1, 1), (2, 2, 1), (3, 3, 1), (4, 4, 1), (5, 5, 1), (6, 6, 1),  -- Balé
 (7, 7, 2),                                                          -- Carlos  -> Judô
 (8, 8, 3);                                                          -- Mariana -> Violino

-- Histórico de chamadas do Balé (terças e quintas) ----------------------
-- Ana: 1 falta | Clara: 2 faltas seguidas (FALTAS RECORRENTES) | Daniela: falta isolada
INSERT INTO chamada (id, turma_id, data_aula, registrada_por) VALUES
 (1, 1, '2026-10-27', 3), (2, 1, '2026-10-29', 3), (3, 1, '2026-11-03', 3);

INSERT INTO presenca (chamada_id, matricula_id, status) VALUES
 (1,1,'PRESENTE'),(1,2,'PRESENTE'),(1,3,'PRESENTE'),(1,4,'PRESENTE'),(1,5,'PRESENTE'),(1,6,'PRESENTE'),
 (2,1,'PRESENTE'),(2,2,'PRESENTE'),(2,3,'AUSENTE'), (2,4,'AUSENTE'), (2,5,'PRESENTE'),(2,6,'PRESENTE'),
 (3,1,'AUSENTE'), (3,2,'PRESENTE'),(3,3,'AUSENTE'), (3,4,'PRESENTE'),(3,5,'PRESENTE'),(3,6,'PRESENTE');

-- Modelo de relatório ----------------------------------------------------
INSERT INTO modelo_relatorio (id, nome, criado_por) VALUES (1, 'Frequência por turma', 1);
INSERT INTO modelo_relatorio_campo (modelo_id, campo, ordem) VALUES
 (1, 'beneficiario', 1), (1, 'modalidade', 2), (1, 'presencas', 3), (1, 'faltas', 4), (1, 'situacao', 5);
