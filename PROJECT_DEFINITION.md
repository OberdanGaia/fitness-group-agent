# Agente WhatsApp — Grupo Fitness 2026

## Visão Geral

Agente conectado a um grupo no WhatsApp responsável por gerir uma aposta fitness entre amigos. Os participantes enviam fotos diárias comprovando treinos realizados. O objetivo de cada participante é completar 200 treinos entre 01/01/2026 e 20/12/2026. Quem não completar paga uma multa proporcional, e o valor arrecadado financia um churrasco dos vencedores.

**Fórmula da multa:** `(1 – X/200) × R$500`

---

## Regras do Grupo

### 1. Treino Válido
- Qualquer atividade física com intenção de melhorar condicionamento (academia, corrida, dança, natação, futebol, bike, etc.)
- **Não vale:** atividades sem intenção de treino (andar no mercado/shopping, turismo, deslocamentos)
- Duração mínima: **30 minutos** ou **4 km** (corridas)

### 2. Envio no Grupo
- Enviar com identificação **N/200** (ex: "47/200")
- Prazo: até **3 horas após o treino**
- Sem retroativos — o treino deve ser registrado **no mesmo dia**

**Formatos aceitos de comprovação:**
- **Com relógio:** 1 foto com data/hora + filtro do Instagram ou dados do exercício
- **Sem relógio:** foto no início e no fim com filtro do Instagram mostrando data e hora
- **Corridas na rua:** comprovar km e minutos percorridos

### 3. Limites por Dia
- Máximo **2 treinos por dia**, de **modalidades diferentes**
- O 2º treino deve ser em **turno diferente** do 1º
- Mínimo de **1 hora de intervalo** entre treinos

**Turnos:**
| Turno      | Horário   |
|------------|-----------|
| Madrugada  | 00h – 06h |
| Manhã      | 06h – 12h |
| Tarde      | 12h – 18h |
| Noite      | 18h – 24h |

> O turno é definido pelo **horário de início** do treino.

### 4. Entrantes após 01/01/2026
- Contam treinos a partir da data de entrada no grupo
- Treinos retroativos não valem

### 5. Afastamento Médico
- Reduz proporcionalmente a meta de 200 treinos

### 6. Desistência
- Pagamento proporcional aos treinos feitos até a desistência

### 7. Novas Regras
- Só podem ser adicionadas após 01/01/2026
- Regras existentes não serão alteradas

### 8. Fiscalização
- Todos os participantes devem ajudar a monitorar o cumprimento das regras

---

## Participantes

- **Total atual:** 21 participantes (grupo aberto a novos membros ao longo do ano)
- O grupo no WhatsApp já existe

### Administradores
| Nome           | Papel                        |
|----------------|------------------------------|
| Oberdan Hideki | Admin principal / decisor final |
| Heloisa Hilario | Administradora               |
| Gabie          | Administradora               |

---

## Comportamento do Agente

### Registro de Treinos

- O agente fica **silencioso** — não responde no grupo ao receber treinos
- Detecta a sinalização **"N/200"** nas mensagens dos participantes
- Correlaciona foto + texto "N/200" mesmo quando enviados em **mensagens separadas** (foto primeiro, texto depois), atribuindo corretamente ao participante que enviou

### Validação

- O agente **não questiona** o conteúdo das fotos — confia na auto-fiscalização do grupo
- Se o grupo identificar e concluir que um treino é inválido:
  1. O agente **sempre pergunta ao admin Oberdan** antes de excluir qualquer treino já contabilizado
  2. Aguarda a **confirmação de Oberdan** para executar a ação
  3. Após a ação, informa no grupo: **ação tomada + contagem atual** do participante afetado
- Se houver questionamento claro sobre um treino, o agente **aciona automaticamente os administradores** antes de qualquer intervenção

### Interação com o Agente

- Apenas os **3 administradores** podem interagir com o agente
- Participantes comuns não têm acesso a comandos

### Relatórios Automáticos

**Quando:**
- Automaticamente todo **dia 1º de cada mês às 07:00**
- Sob demanda quando Oberdan enviar **`#relatorio`** no grupo

**Conteúdo:**
- Ranking completo de participantes (treinos feitos / meta individual)
- Análise comparativa com o relatório anterior:
  - Quem está **"On Fire"** (maior evolução desde o último relatório)
  - Quem está **estagnado** (sem treinos no período)
  - Quem **subiu ou desceu** no ranking
- **Tom:** leve, engraçado e motivacional — objetivo é animar o grupo, não gerar competição

> O formato e tom do relatório serão ajustados conforme os testes e feedback dos participantes.

---

## Dashboard Web

- Painel externo em **página web** para acompanhamento do grupo
- Acessível pelos administradores para visualização em tempo real do progresso de cada participante
- O dashboard nativo do Supabase já oferece visibilidade dos dados sem necessidade de construção adicional; um dashboard customizado será desenvolvido apenas se necessário

---

## Arquitetura Técnica

| Componente        | Tecnologia         | Motivo                                                                 |
|-------------------|--------------------|------------------------------------------------------------------------|
| WhatsApp          | Evolution API      | Única opção viável para grupos pessoais — conexão via QR code          |
| Backend           | Python + FastAPI   | Linguagem legível, robusto ecossistema de IA e agendamento             |
| Banco de dados    | Supabase           | PostgreSQL gerenciado + dashboard nativo + storage de fotos + free tier generoso |
| Armazenamento     | Supabase Storage   | Fotos de treino armazenadas junto ao banco, sem serviço separado       |
| Relatórios (IA)   | Claude API         | Geração de texto com tom leve e engraçado, ajustável por prompts       |
| Agendamento       | APScheduler        | Disparo automático do relatório dia 1º às 07:00, integrado ao Python   |
| Dashboard         | Supabase Dashboard | Interface nativa; Streamlit como complemento se precisar de mais       |
| Hospedagem        | Railway            | Deploy simples sem gestão de servidor, plano gratuito suficiente       |

### Fluxo da Arquitetura

```
Grupo WhatsApp
      │
      ▼
Evolution API (ponte WhatsApp — conexão via QR code)
      │
      ▼
Agente Python (FastAPI)
  ├── Detecta "N/200" + foto e correlaciona mensagens
  ├── Salva treino no Supabase (banco + fotos no Storage)
  ├── APScheduler → relatório automático dia 1º às 07:00
  ├── Aciona Claude API para gerar relatórios
  └── Envia mensagens ao grupo via Evolution API
      │
      ▼
Supabase
  ├── Banco de dados PostgreSQL (treinos, participantes, histórico)
  └── Storage (fotos de treino)
      │
      ▼
Dashboard (Supabase nativo + complemento web se necessário)
```

---

## Resumo Técnico

| Item                        | Definição                                           |
|-----------------------------|-----------------------------------------------------|
| Período                     | 01/01/2026 – 20/12/2026                             |
| Meta por participante        | 200 treinos                                         |
| Multa máxima                | R$500 (proporcional)                                |
| Participantes atuais        | 21                                                  |
| Grupo WhatsApp              | Já existe                                           |
| Respostas automáticas       | Somente relatórios e notificações de ação           |
| Interação com agente        | Apenas administradores                              |
| Relatório automático        | Dia 1º de cada mês às 07:00 + comando #relatorio    |
| Dashboard                   | Supabase Dashboard nativo + web customizado se necessário |
| Banco de dados              | Supabase (PostgreSQL)                               |
| Armazenamento de fotos      | Supabase Storage                                    |
| Hospedagem do agente        | Railway                                             |
| Decisor final               | Oberdan Hideki                                      |
