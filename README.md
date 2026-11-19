# Minha Financeira — Private Obsidian Cloud 24/7 + PWA

Sistema financeiro pessoal 100% em nuvem 24/7 e instalável pelo navegador (PWA — celular e PC), projetado com estética **Private Obsidian & Ouro/Esmeralda**.

## Recursos Principais
- **Multi-Perfil Isolado:** `Entrar` / `Criar Novo Perfil`, edição de perfil, troca de senha e backup isolado `.zip` por usuário.
- **Caixa Rápido (`+` em todas as telas):** registro em 2 toques (`+R$ 100 Uber`, `-R$ 20 Mercado`), filtros por período (`Hoje`, `7 dias`, `Mês`), busca e fechamento **Entrou · Saiu · Sobrou**.
- **Contas a Vencer:** fixas mensais e parceladas (`Nx`), ajuste automático para meses curtos (`dia 30/31` → `28/29` em fevereiro), baixa em 1 toque integrada ao Caixa e estorno limpo.
- **Meus Cartões de Crédito:** paleta livre de cores (cor do indicador = cor real do cartão), limite dinâmico, fechamento/vencimento, compras à vista e `Nx` e baixa de fatura integrada ao Caixa.
- **Módulos de Dívida estilo Cartão Virtual (ex.: `Thiago`, `Seu Luiz`):** múltiplos módulos com cor própria, fechamento, vencimento, compras à vista/parceladas, exclusão individual sem apagar o módulo, baixa mensal e alertas no Radar.
- **Painel Executivo & Radar Unificado:** KPIs do mês, prioridades (**Atrasado · Vence Hoje · Próximos 7 dias · Próximos 15 dias**) e gráficos limpos.
- **Persistência 24/7 Criptografada (`AES-256-GCM`):** cofre privado em `minha-financeira-vault` + Anti-Sono 24/7 via GitHub Actions (repositório público = **0 minutos** da cota privada).

## Deploy Gratuito (R$ 0,00) na 2ª Conta Render
1. Na sua **2ª conta gratuita do Render**, clique em **New + → Blueprint** (ou **Web Service → Docker**) e selecione o repositório público `thiagolucaslus-debug/minha-financeira`.
2. Preencha as variáveis de ambiente (`CLOUD_VAULT_GITHUB_TOKEN`, `CLOUD_VAULT_AES_KEY`, `CLOUD_VAULT_HYDRATE_SECRET`, `CLOUD_VAULT_REPO=thiagolucaslus-debug/minha-financeira-vault`).
3. Após o deploy gerar a URL (`https://minha-financeira-xxxx.onrender.com`), adicione a variável `RENDER_APP_URL` em **Settings → Secrets and variables → Actions → Variables** deste repositório para ativar o ping 24/7 automático a cada 10 minutos.
