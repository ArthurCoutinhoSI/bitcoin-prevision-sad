<!--
Sync Impact Report
==================
Version change: 1.0.0 → 1.1.0
Bump rationale: novo princípio e ampliação material das verificações de revisão;
mudança compatível com as regras existentes.

Modified principles:
- Nenhum princípio existente foi renomeado ou redefinido.

Added principles:
- VI. Documentação Completa e Atualizada

Added sections:
- Nenhuma.

Removed sections:
- Nenhuma.

Follow-up TODOs:
- Nenhum. Não há placeholders pendentes.
-->

# Constituição do bitcoin-prevision-sad

## Core Principles

### I. Simplicidade e Manutenibilidade (NÃO NEGOCIÁVEL)

Toda solução DEVE ser a mais simples que atenda ao requisito atual, sem antecipar
necessidades futuras.

- Cada módulo DEVE ter um único propósito claro e uma interface pública documentada.
- Recursos nativos da linguagem e da plataforma DEVEM ser preferidos a novas dependências.
- Abstrações especulativas, código morto e otimização prematura NÃO DEVEM ser introduzidos.
- Refatorações que reduzam complexidade são permitidas dentro do escopo aprovado, desde que
  cobertas por testes.
- Nomes, estrutura e fluxo DEVEM permitir que uma pessoa compreenda o código sem consultar
  o autor.

**Racional**: um sistema de apoio à decisão precisa ser auditável e evolutivo; complexidade
acidental encarece manutenção e aumenta o risco de erros silenciosos.

### II. Separação de Responsabilidades

A arquitetura DEVE separar aquisição/armazenamento de dados, regras de domínio e
apresentação ou API.

- Regras de domínio NÃO DEVEM depender de interface, persistência, frameworks ou provedores
  externos; as dependências apontam para dentro.
- Acesso a dados e integrações externas DEVEM ficar atrás de interfaces explícitas.
- Uma mudança que atravesse camadas DEVE ser refletida no plano antes da implementação.
- Contratos entre camadas DEVEM ser pequenos, tipados quando a linguagem permitir e
  documentados.

**Racional**: fronteiras claras tornam as regras de decisão testáveis de forma isolada e
permitem substituir fontes de dados ou interfaces sem reescrever o domínio.

### III. Controle de Escopo (NÃO NEGOCIÁVEL)

A implementação DEVE limitar-se ao que a especificação e o plano aprovados exigem.

- Funcionalidades, telas, endpoints, refatorações, configurações ou documentações não
  solicitadas NÃO DEVEM ser adicionadas.
- Todo trabalho identificado como necessário fora do escopo DEVE ser registrado como
  proposta e aprovado antes de ser executado.
- Cada alteração DEVE ser rastreável a um requisito ou tarefa aprovados.
- Em caso de dúvida sobre o escopo, a IA DEVE perguntar antes de implementar.

**Racional**: escopo não controlado dilui a entrega, aumenta o risco técnico e dificulta a
revisão; a IA não substitui a decisão humana sobre prioridades.

### IV. Dependências e Infraestrutura Justificadas

Nenhuma biblioteca, framework, serviço, banco de dados, pipeline de CI/CD, contêiner ou
recurso de nuvem DEVE ser adicionado sem justificativa explícita e aprovada.

- A justificativa DEVE apresentar o problema, as alternativas avaliadas (incluindo a
  solução nativa) e o custo de manutenção, segurança e licenciamento.
- A justificativa DEVE ser registrada no plano ou em um registro de decisão antes da
  inclusão.
- Dependências DEVEM ter versão fixada e licença compatível com o projeto.
- Infraestrutura nova DEVE ser considerada apenas quando um requisito concreto a exigir.

**Racional**: cada dependência e recurso adiciona superfície de ataque, custo operacional e
risco de abandono; a justificativa explícita mantém essas decisões reversíveis e auditáveis.

### V. Qualidade Verificável

Mudanças de comportamento DEVEM ser acompanhadas de testes automatizados no nível mais
adequado e com o menor custo de manutenção.

- Cálculos de domínio, indicadores e sinais DEVEM ter testes determinísticos com dados
  fixos; tempo, fuso horário e aleatoriedade DEVEM ser controlados.
- Testes NÃO DEVEM depender de rede, serviços externos ou estado compartilhado.
- Análise estática, lint e build DEVEM passar antes do merge.
- Contratos públicos e erros DEVEM ser explícitos e documentados.
- A suíte de testes DEVE ser executável por um único comando documentado.

**Racional**: resultados de um sistema de apoio à decisão só são confiáveis quando
reproduzíveis; testes determinísticos permitem detectar regressões em regras financeiras.

### VI. Documentação Completa e Atualizada

A documentação DEVE ser tratada como parte da entrega e mantida no mesmo repositório e na
mesma alteração que modifica comportamento, contrato, dados ou operação.

- O projeto DEVE manter: propósito e escopo; instalação e execução; visão geral da
  arquitetura e fronteiras; regras de domínio, indicadores, fórmulas e premissas; esquema,
  origem e limitações dos dados; contratos públicos; operação e diagnóstico de falhas; e
  decisões arquiteturais relevantes com contexto, alternativas e consequências.
- A documentação DEVE ter um ponto de entrada único que referencie todos os documentos.
- Exemplos e comandos DEVEM ser reproduzíveis e verificados; instruções obsoletas NÃO DEVEM
  ser mantidas.
- Segredos, dados pessoais e credenciais NÃO DEVEM aparecer na documentação.
- Mudanças de comportamento DEVEM atualizar a documentação afetada na mesma entrega; essa
  atualização integra o escopo aprovado e não viola o Princípio III.
- Toda revisão DEVE rejeitar alterações que deixem a documentação ausente, incorreta ou
  desatualizada.

**Racional**: documentação completa torna o sistema auditável, reproduzível e transferível;
em um SAD financeiro, premissas e limitações não documentadas podem induzir decisões
equivocadas.

## Restrições Adicionais

- O sistema DEVE permanecer uma única aplicação executável até que um requisito concreto
  justifique sua divisão.
- O arquivo `dc.csv` e demais dados históricos DEVEM ser tratados como entrada somente
  leitura; artefatos derivados DEVEM ser reproduzíveis.
- Segredos NÃO DEVEM ser versionados; configuração sensível DEVE vir de variáveis de
  ambiente.
- O sistema DEVE apenas apoiar decisões; execução de ordens ou transações financeiras está
  fora do escopo.
- Funcionalidades fora do escopo aprovado DEVEM ser registradas como proposta, não
  implementadas.

## Fluxo de Desenvolvimento

- O trabalho DEVE seguir o fluxo Spec Kit: especificação, plano, tarefas e implementação.
- O plano DEVE incluir uma verificação de conformidade com esta constituição antes da
  implementação.
- Toda revisão DEVE verificar: aderência ao escopo, separação de responsabilidades,
  necessidade de novas dependências, cobertura de testes e atualização da documentação
  exigida pelo Princípio VI.
- Exceções e complexidade adicional DEVEM ser registradas com justificativa e aprovação
  explícita; sem isso, a mudança NÃO DEVE ser aceita.
- Nenhuma alteração DEVE ser integrada com verificações obrigatórias falhando.
- Em conflito entre esta constituição e outra prática, esta constituição prevalece.

## Governance

Esta constituição prevalece sobre demais práticas e convenções do projeto.

- **Emendas**: propostas de alteração DEVEM descrever motivação, impacto e plano de
  migração; DEVEM ser aprovadas pelo mantenedor responsável antes da aplicação.
- **Versionamento**: o número de versão segue SemVer. MAJOR para remoção ou redefinição
  incompatível de princípios ou regras; MINOR para novo princípio, seção ou orientação
  materialmente ampliada; PATCH para esclarecimentos e correções sem mudança semântica.
- **Conformidade**: todo plano, tarefa e revisão DEVE verificar esta constituição.
  Não conformidade bloqueia o merge. Exceções DEVEM ser documentadas, justificadas e ter
  prazo ou condição de expiração.
- **Registro**: a data de ratificação e a data da última emenda DEVEM ser mantidas no
  rodapé deste documento em formato ISO `YYYY-MM-DD`.

**Version**: 1.1.0 | **Ratified**: 2026-11-07 | **Last Amended**: 2026-11-07
