# SOL GARIMPA — IMPLANTAÇÃO NO WIX EDITOR (SEM CMS)

Última preparação: 25/10/2026. **Nenhum código foi publicado no site pelo assistente.**

## Arquitetura

Awin (22 anunciantes) → GitHub Actions (6/6h) → GitHub Pages `ofertas.json` público **sem tokens** →
Wix Velo Router com prefixo `oferta` e uma única `oferta-page` → Botão de compra abre **link afiliado Awin**.

**Um único layout de página** é reutilizado com URLs diferentes. Cada URL representa uma oferta, sem páginas estáticas individuais e **sem CMS**.

## PASSO 1 — Ativar o catálogo automático já preparado

Para 500+ possíveis itens, a Awin não entrega tudo pelo endpoint de cupons. Use o coletor de feeds do pacote (`scripts/sync_awin.py`); ele consulta anúncios aprovados e dados válidos de produto. **Não garante 500 itens**, depende do inventário que suas lojas fornecem e de aprovação.

1. GitHub (desktop): crie um repositório, por exemplo `sol-garimpa-afiliados` (público, por exigir Pages pública neste arranjo).
2. Envie o **conteúdo da pasta deste pacote**, inclusive `.github/workflows` (mantenha a hierarquia dos arquivos).
3. GitHub → `Settings` → `Secrets and variables` → `Actions` → `New repository secret`:
   - `AWIN_PUBLISHER_TOKEN` = token Publisher API da Awin;
   - `AWIN_DATAFEED_KEY` = chave privada do feed da Awin.
   Nunca envie credenciais por WhatsApp, chat, Git commit ou HTML.
4. Awin: ferramenta **Create-a-Feed** fornece a chave/URL de feed; API Credentials fornece token de Publisher.
5. GitHub → `Settings` → `Pages` → `Build and deployment` → Source = `GitHub Actions`.
6. GitHub → `Actions` → `Atualizar ofertas Awin SOL GARIMPA` → `Run workflow`.
7. Aguarde execução concluída. Copie a URL **real** informada em GitHub Pages. O catálogo estará em:
   `https://SEU_USUARIO.github.io/SEU_REPOSITORIO/ofertas.json` (EXEMPLO, não endereço ativo).
8. Abra `ofertas.json` no navegador e confirme `atualizado_em`, `cards`, `slug`, `url_sol_garimpa` e que produtos têm `link` Awin rastreado.

## PASSO 2 — No Wix Editor, criar o Router

Confirmação oficial: https://dev.wix.com/docs/develop-websites/articles/coding-with-velo/routers/create-a-router

1. Abra o editor do site SOL GARIMPA no computador.
2. Velo → `Page Code` → `Main Pages` → botão `+` → `Add a Router`.
3. Preencha o prefixo **`oferta`** e clique em **`Add & Edit Code`**.
4. O editor cria `Backend & Public/routers.js`, uma página geralmente nomeada `oferta-page` em `Router Pages`.
5. Em `Backend & Public` → `routers.js`: substitua **apenas** as funções `oferta_Router` e `oferta_SiteMap` (e adicione imports). Não apague funções de outros Routers que já possam existir. Use `wix_router/routers.js`.
6. Em `wix_router/routers.js`, troque `CATALOGO_JSON_URL` pelo link público real do passo 1. Se a página Router tiver outro nome, altere a constante `MODELO_PAGINA`.

## PASSO 3 — Montar a única página-modelo no Wix Editor

Em `Router Pages` → `oferta-page`, adicione os elementos nativos abaixo. O texto pode ser provisório: o Velo preencherá tudo conforme a URL acessada.

| Tipo de elemento Wix | ID EXATO no painel Propriedades | Texto inicial |
| --- | --- | --- |
| Texto / Título | `tituloProduto` | Oferta SOL GARIMPA |
| Texto | `nomeLoja` | Loja parceira |
| Imagem | `fotoProduto` | Imagem ilustrativa temporária; será substituída se houver imagem no feed |
| Texto | `precoAtual` | Confira na loja |
| Texto | `precoAnterior` | Antes: — |
| Texto | `textoCupom` | Cupom disponível |
| Texto | `descricaoProduto` | Oferta selecionada pela SOL GARIMPA |
| Botão | `btnComprar` | IR PARA A LOJA |
| Botão | `btnWhatsapp` | COMPARTILHAR NO WHATSAPP |
| Botão | `btnVoltar` | VER MAIS OFERTAS |
| Texto | `observacao` | Publicidade • preços sujeitos a alteração |

IDs são sensíveis a maiúsculas e minúsculas. No editor, clique no elemento → `Properties & Events` → ID.

Selecione `oferta-page` → Código da página e cole **todo** `wix_router/codigo_pagina_oferta.js`.

## PASSO 4 — Publicar e testar

1. Clique `Salvar` e `Publicar` no Wix Editor.
2. Pegue uma oferta real do `docs/ofertas.json`, copie o campo `url_sol_garimpa`, abra em janela privada.
3. Confira foto, título, valor, cupom (quando houver) e a prévia ao compartilhar no WhatsApp.
4. Clique em `IR PARA A LOJA`: o destino precisa ser um **link autorizado da Awin com seu Publisher ID**, não um link de terceiros.
5. No WhatsApp, o botão compartilha a URL `ofertaspravc.com.br/oferta/...`, não o link Awin.
6. Confira se o link do anúncio continua correto após a próxima atualização do GitHub Actions.

### Publicar também o carrossel na página inicial

O pacote inclui `docs/index.html`, vitrine completa para hospedar no GitHub Pages.
No Wix Editor → `Adicionar Elementos` → `Incorporar Código` → `Incorporar Site` → URL da página GitHub Pages (a mesma pasta de `ofertas.json`, sem nome de arquivo).
Ajuste a altura e largura. Os botões `Ver oferta` abrirão a página correspondente do próprio domínio SOL GARIMPA.

### SEO responsável

O router configura `og:title`, `og:image`, `og:description` para WhatsApp.
**Inicialmente `noIndex: true` e `oferta_SiteMap()` vazio:** feeds afiliados com conteúdo duplicado e promoções temporárias não devem ser automaticamente indexados em massa. Após acrescentar textos originais, avaliaremos indexar páginas duráveis e sitemap seletivo.

### Faltas e limitações

- Awin só mostra ofertas reais quando token + chave de feed estiverem corretos e parceria aprovada. As cinco lojas sem feed recebem ofertas/cuponagens quando a API oferece.
- A automação Awin pode retornar menos de 500 ofertas, mesmo com limite 40 produtos/loja; depende das fontes.
- Rakuten e Lomadee exigem adaptadores de fonte, autorização e links rastreados específicos. **Este pacote inicial ativa Awin**, sem inventar integrações Rakuten/Lomadee.
- Não existe disparo automático para grupos de WhatsApp neste pacote. O botão compartilha um post; o arquivo `docs/fila_whatsapp.json` prepara a integração posterior de envio com autorização.
- O GitHub Pages é público. Nunca armazene credenciais nem dados privados em `docs/`.
- O Wix ainda impõe limites de requisições, desempenho e uso de backend. **Não há promessa de 10 mil requisições ou URLs ilimitadas**.
- Se `ofertas.json` não existir, estiver desatualizado por 72h ou não possuir o produto, o router retorna 404. É uma proteção contra promoções removidas. O intervalo normal de sincronização é de 6 horas; a página em si tem cache de 30 minutos.
- Nenhum preço ou desconto é estimado pelo router. A plataforma define preço e disponibilidade no checkout.

## Fontes Wix oficiais

- https://dev.wix.com/docs/develop-websites/articles/coding-with-velo/routers/about-routers
- https://dev.wix.com/docs/develop-websites/articles/coding-with-velo/routers/create-a-router
- https://dev.wix.com/docs/develop-websites/articles/best-practices/caching/implement-router-caching
- https://dev.wix.com/docs/velo/apis/wix-fetch/fetch
- https://dev.wix.com/docs/velo/apis/wix-window-frontend/get-router-data
