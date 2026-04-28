---
name: verificar-bot
description: Verifica se o bot do Fitness 2026 está funcionando corretamente — checar saúde do servidor, banco de dados e conexão com WhatsApp
---

Você está verificando a saúde do Bot Fitness 2026. Siga os passos abaixo em ordem e reporte o resultado de cada um claramente.

## Informações do projeto

- **Bot Railway:** https://fitness-group-agent-production.up.railway.app
- **Health endpoint:** https://fitness-group-agent-production.up.railway.app/health
- **Evolution API:** https://evolution-api-production-3cfd.up.railway.app
- **Branch do código:** master
- **Repositório:** https://github.com/OberdanGaia/fitness-group-agent

## Passos de verificação

### 1. Checar se o servidor está respondendo
Faça uma requisição HTTP GET para o health endpoint e reporte:
- Se respondeu com status 200: ✅ Servidor OK
- Se deu timeout ou erro de conexão: ❌ Servidor fora do ar — orientar a checar o Railway

### 2. Checar se o código no Railway está atualizado
Compare o último commit no git local com o que está no Railway:
- Rode `git log --oneline -3` para ver os últimos commits
- Informe o hash e mensagem do commit mais recente
- Lembre ao usuário que o Railway faz redeploy automático a cada push — se o commit bater, o código está atualizado

### 3. Orientar verificação dos logs no Railway
Instrua o usuário a:
1. Acessar railway.app
2. Entrar no projeto → serviço do bot → aba **Logs**
3. Procurar por linhas com `ERROR` ou `CRITICAL`
4. Verificar se a última linha de log tem um timestamp recente

### 4. Checar arquivos críticos do projeto
Verifique se os seguintes arquivos existem e não estão vazios:
- `app/services/report_service.py`
- `app/handlers/workout_handler.py`
- `app/api/webhooks.py`

### 5. Resumo final
Ao final, apresente um resumo com:
- ✅ ou ❌ para cada item verificado
- Se houver problema, indique qual serviço está com problema e o que fazer
- Se tudo estiver OK, confirme que o bot está saudável
