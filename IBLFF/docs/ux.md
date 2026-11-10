# Contexto de UX/UI - Instituto Batista Lázaro Ferreira Filho
Documento de diretrizes de design e estrutura para a geração automatizada de interfaces (Figma Make & Copilot) com base no Documento de Análise de Requisitos.

## 1. Visão Geral do Sistema e Diretrizes Globais
- **Público-Alvo:** Usuários com baixo conhecimento técnico. A interface deve ser extremamente intuitiva, acessível e direta.
- **Plataforma:** Aplicação Web Multiplataforma (responsiva para computadores, tablets e smartphones).
- **Estilo Visual:** Limpo, focado em usabilidade e com alta legibilidade.
- **Navegação:** Menus claros focados nos módulos principais: Cadastro, Controle de Presença e Relatórios.
- **Feedback Visual:** Mensagens de erro e sucesso devem ser objetivas e fáceis de compreender.
- **Privacidade (LGPD):** Termos de consentimento explícitos devem ter destaque no fluxo de primeiro acesso.

## 2. Estrutura de Páginas e Insights de Design

### A. Módulo de Login e Recuperação de Senha
* **Requisitos Base:** Entrada com e-mail ou telefone e senha. Recuperação de senha via e-mail ou telefone. Termo de consentimento (LGPD) no primeiro acesso.
* **Insights de Design:**
  - **Layout:** Centralizado e minimalista. Ideal para acesso rápido via mobile.
  - **Inputs:** Campos grandes e claros para E-mail/Telefone e Senha, com opção de "mostrar senha".
  - **Primeiro Acesso:** Um modal ou tela dedicada para o aceite dos termos da LGPD antes de prosseguir para o sistema.
  - **Ação Secundária:** Link visível de "Esqueci minha senha", levando a um fluxo simples de validação (via e-mail ou SMS).

### B. Módulo de Cadastros (Voluntários e Beneficiários)
* **Requisitos Base:** 
  - Voluntário: Nome, nascimento, CPF, telefone, e-mail, senha, matéria/função, termo de voluntariado assinado.
  - Beneficiário: Nome, nascimento, CPF, telefone, e-mail, senha, endereço, matérias/cursos. Validação de CPF (evitar duplicidade).
* **Insights de Design:**
  - **Formulários Estruturados:** Devido à quantidade de dados, usar formulários em etapas (Step-by-step) ou divididos em blocos visuais (Ex: Dados Pessoais, Contato, Modalidades).
  - **Máscaras de Input:** Aplicar máscaras automáticas em CPF, Telefone e Data de Nascimento para evitar erros de digitação.
  - **Feedback em Tempo Real:** Indicador visual (ícone de check verde ou alerta vermelho) no campo de CPF para mostrar se ele é válido e único no sistema.
  - **Upload/Aceite de Documentos:** Para voluntários, uma área clara de anexo ou checkbox de assinatura digital do Termo de Voluntariado.

### C. Módulo de Chamada (Controle de Presença)
* **Requisitos Base:** Voluntário autorizado anota presença/ausência. Histórico de presença. Liberação de vaga por faltas consecutivas.
* **Insights de Design:**
  - **Otimização Mobile:** Como a chamada ocorrerá durante as aulas (noturno, ambiente escolar), a tela deve ser excelente em celulares.
  - **Lista de Beneficiários (Alunos):** Uso de listas com botões de ação rápida tipo "Toggle" (Alternância) para Presente (Verde) / Ausente (Vermelho) ao lado de cada nome.
  - **Alertas Visuais:** Destacar alunos que estão próximos do limite de faltas consecutivas (Ex: um ícone de alerta laranja informando risco de perda da vaga).
  - **Filtros Iniciais:** Dropdown rápido para selecionar a Turma/Modalidade antes de iniciar a chamada.

### D. Módulo de Relatórios e Auditoria
* **Requisitos Base:** Filtros (Turma, Modalidade), exportação em PDF, XLSX, CSV. Apenas administradores.
* **Insights de Design:**
  - **Painel de Filtros:** Uma barra lateral ou área superior contendo seletores (Select/Dropdowns) para Turma, Modalidade e Período de datas.
  - **Pré-visualização (Data Table):** Uma tabela exibindo os resultados refinados antes da exportação, com paginação para manter o tempo de resposta abaixo de 2 segundos.
  - **Botões de Exportação:** Botões com ícones correspondentes aos formatos de arquivo (PDF, Excel, CSV) posicionados no canto superior ou inferior da tabela de dados.

### E. Módulo de Gestão de Modalidades
* **Requisitos Base:** Cadastro de modalidade (Descrição, Voluntário, periodicidade, quantidade de vagas). Limite de vagas.
* **Insights de Design:**
  - **Visualização em Cards:** Mostrar as modalidades ativas (Balé, Jazz, Judô, etc.) em formato de cartões (Cards).
  - **Indicador de Vagas:** Uma barra de progresso visual dentro de cada card mostrando a ocupação (Ex: "15/20 vagas preenchidas"). Se estiver lotado, o card pode assumir um tom mais neutro ou exibir um selo de "Turma Lotada".

## 3. Componentes de UI Sugeridos para o Figma Make
- **Inputs e Formulários:** Bordas de 1px, estado de erro em vermelho (ex: #DA1E28) acompanhado de texto auxiliar explicativo abaixo do campo (ex: "CPF inválido").
- **Toggles de Presença:** Botões grandes para facilitar o toque na tela do celular.
- **Tabelas de Dados:** Com zebra-striping (linhas com cores alternadas sutis) para facilitar a leitura de relatórios extensos em telas maiores.
- **Tipografia Escalonável:** Tamanhos de fonte maiores para títulos e rótulos de campos para auxiliar a leitura sob condições de luz variáveis (salas de aula à noite).
