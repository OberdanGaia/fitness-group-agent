---
name: deploy
description: Salva as mudanças no GitHub e dispara o redeploy automático no Railway para o Bot Fitness 2026
---

Você está fazendo o deploy do Bot Fitness 2026. Siga os passos abaixo em ordem.

## Informações do projeto

- **Branch:** master
- **Repositório:** https://github.com/OberdanGaia/fitness-group-agent
- **Deploy:** automático no Railway a cada push para master
- **Arquivos sensíveis que NUNCA devem ser commitados:** `.env`, qualquer arquivo com senha ou chave de API

## Passos do deploy

### 1. Ver o que mudou
Rode `git status` e `git diff --stat` para mostrar ao usuário exatamente quais arquivos foram alterados.

Apresente de forma clara:
- Quais arquivos foram modificados
- Se há arquivos novos ainda não rastreados

### 2. Confirmar com o usuário
Pergunte ao usuário:
- Se os arquivos listados são os que ele quer enviar
- Uma descrição curta do que foi feito (ex: "ajustei o tom do relatório") — use isso para montar a mensagem de commit

Se o usuário não souber descrever, sugira uma mensagem baseando-se nos arquivos alterados.

### 3. Verificar segurança
Antes de commitar, confirme que nenhum arquivo sensível está na lista:
- `.env` → nunca commitar
- Qualquer arquivo com "secret", "key", "password" no nome → perguntar ao usuário antes

### 4. Fazer o commit
- Adicione apenas os arquivos relevantes (evite `git add .` se houver arquivos sensíveis)
- Crie o commit com mensagem clara em português ou inglês
- Sempre inclua no final do commit: `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`

### 5. Push para o GitHub
Rode `git push origin master` e confirme que foi bem-sucedido.

### 6. Confirmar o deploy
Informe ao usuário:
- ✅ Código enviado para o GitHub com sucesso
- O Railway vai detectar a mudança e redeployar automaticamente em ~1 minuto
- Para acompanhar: railway.app → projeto → aba **Deployments**
- Para testar depois do deploy: enviar `#relatorio` no privado para o bot
