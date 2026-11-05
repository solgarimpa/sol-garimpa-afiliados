# SOL GARIMPA — Instalação da nova estrutura no Wix

Página única do componente, alimentada pelo feed GitHub e pelo Worker SHEIN, com filtros de loja.

## Endereços por página

| Página Wix | URL para Embed a site |
|---|---|
| Cupons Awin — página anterior, preservada | https://solgarimpa.github.io/sol-garimpa-afiliados/cupons/ |
| **Nova central geral de cupons — HTML separado** | **https://solgarimpa.github.io/sol-garimpa-afiliados/cupons-geral/** |
| Cupons - Todas as lojas | https://solgarimpa.github.io/sol-garimpa-afiliados/central/?tipo=cupons&loja=todas |
| Achadinhos - página inicial | https://solgarimpa.github.io/sol-garimpa-afiliados/central/?tipo=achadinhos&loja=todas&visao=inicio |
| Achadinhos - Todas as ofertas | https://solgarimpa.github.io/sol-garimpa-afiliados/central/?tipo=achadinhos&loja=todas |
| cupons - mercado-livre | https://solgarimpa.github.io/sol-garimpa-afiliados/central/?tipo=cupons&loja=mercado-livre |
| cupons - shopee | https://solgarimpa.github.io/sol-garimpa-afiliados/central/?tipo=cupons&loja=shopee |
| cupons - magalu | https://solgarimpa.github.io/sol-garimpa-afiliados/central/?tipo=cupons&loja=magalu |
| cupons - amazon | https://solgarimpa.github.io/sol-garimpa-afiliados/central/?tipo=cupons&loja=amazon |
| cupons - shein | https://solgarimpa.github.io/sol-garimpa-afiliados/central/?tipo=cupons&loja=shein |
| cupons - aliexpress | https://solgarimpa.github.io/sol-garimpa-afiliados/central/?tipo=cupons&loja=aliexpress |
| achadinhos - mercado-livre | https://solgarimpa.github.io/sol-garimpa-afiliados/central/?tipo=achadinhos&loja=mercado-livre |
| achadinhos - shopee | https://solgarimpa.github.io/sol-garimpa-afiliados/central/?tipo=achadinhos&loja=shopee |
| achadinhos - magalu | https://solgarimpa.github.io/sol-garimpa-afiliados/central/?tipo=achadinhos&loja=magalu |
| achadinhos - amazon | https://solgarimpa.github.io/sol-garimpa-afiliados/central/?tipo=achadinhos&loja=amazon |
| achadinhos - shein | https://solgarimpa.github.io/sol-garimpa-afiliados/central/?tipo=achadinhos&loja=shein |
| achadinhos - aliexpress | https://solgarimpa.github.io/sol-garimpa-afiliados/central/?tipo=achadinhos&loja=aliexpress |

## Instalação em cada página Wix Editor

1. Abra a página/subpágina no Editor.
2. Adicionar elementos (+) → Incorporar código → Incorporar um site (Embed a site).
3. Cole a URL correspondente desta tabela; clique Aplicar.
4. Ajuste a largura para 100% e a altura para cerca de 1350 px, conforme a quantidade de cards e a versão mobile.
5. Mantenha um H1 e texto introdutório nativos do Wix para SEO; conteúdo dentro de iframe nem sempre é indexável como texto da página.
6. Visualize no desktop/mobile e publique apenas após testar.

## Critérios de publicação

- Awin/Rakuten/Lomadee: feed existente `docs/paginas_ofertas.json`, somente registros ativos/não históricos. Cupons só quando presentes.
- SHEIN: Worker `sol-garimpa-shein-cupons`, códigos públicos e validade não confirmada em checkout.
- Produtos/fotos: apenas quando o feed contém imagem original válida.
- Marketplaces sem oferta no feed novo: há botão para página/vitrine antiga. Os endereços existentes não são modificados.
- A lista `lojas-referencia.json` serve apenas para pesquisar nomes. Não implica parceria ou cashback.
- Cashback: não anunciar cashback próprio nem porcentagens de terceiros sem comprovação e rastreamento próprio.

## Manutenção

O HTML fica em `docs/central/index.html`. Alterá-lo atualiza os 16 contextos por query string, sem colar novos códigos em cada página.

## Página principal de cupons — modelo de navegação atualizado em 02/11/2026

- Arquivo público da **nova central**: `docs/cupons-geral/index.html`. O HTML anterior de cupons Awin continua em `docs/cupons/index.html`, e a galeria geral Awin permanece em `docs/index.html`.
- Catálogo único: `docs/cupons/catalogo.json`, atualizado por `scripts/build_cupons_central.py` com dados existentes da Awin, Rakuten e Lomadee, sem raspagem da Promobit.
- A nova central é um **segundo elemento HTML**, a ser adicionado em uma página separada no Wix via **Incorporar um site** com a URL `https://solgarimpa.github.io/sol-garimpa-afiliados/cupons-geral/`. Não substitua os HTML Awin existentes.
- Agendamento de origem: quatro regras cron em `.github/workflows/atualizar_cupons_awin.yml` para intervalos de 45 minutos, conforme execução efetiva da plataforma.
- Se o catálogo unificado ainda não estiver publicado, o HTML usa o feed já disponível `docs/cupons/ofertas.json` como reserva.
- Para SEO na página Wix mantenha H1 nativo e texto visível, pois indexação do conteúdo do iframe não é garantida.
- Não confundir estrutura de navegação semelhante com redistribuir material protegido da Promobit: fontes de dados são as redes de afiliados próprias.


## Subpaginas de cupons dos seis marketplaces — versao unificada (05/11/2026)

HTML unico que preserva estilo laranja, cupons do Meliuz, Pelando recente via
Worker e Codigos SHEIN nao verificados em secao identificada.
Os cupons anunciados por fontes de terceiros nao garantem validade nem cashback.

Instalar como "Incorporar um site" em cada pagina Wix (ou como iframe HTML):

- Mercado Livre: https://solgarimpa.github.io/sol-garimpa-afiliados/central/cupons-marketplace.html?loja=mercado-livre
- Shopee: https://solgarimpa.github.io/sol-garimpa-afiliados/central/cupons-marketplace.html?loja=shopee
- Magalu: https://solgarimpa.github.io/sol-garimpa-afiliados/central/cupons-marketplace.html?loja=magalu
- AliExpress: https://solgarimpa.github.io/sol-garimpa-afiliados/central/cupons-marketplace.html?loja=aliexpress
- SHEIN: https://solgarimpa.github.io/sol-garimpa-afiliados/central/cupons-marketplace.html?loja=shein
- Amazon: https://solgarimpa.github.io/sol-garimpa-afiliados/central/cupons-marketplace.html?loja=amazon

Coleta a cada 30 minutos em scripts/sync_cupons_marketplaces.py pelo workflow
atualizar_cupons_shopee.yml; html recarrega catalogo a cada 5 minutos enquanto aberto.
A coleta de Pelando e Cuponomia pode retornar HTTP 403 e NAO deve ser contornada;
nesse caso o JSON registra a falha sem afirmar acesso.
Fontes diretas da Awin/Rakuten/Lomadee continuam independentes em docs/cupons/catalogo.json.
Nao confundir atualizado (observado) com testado: os cupons nao foram testados no checkout.
Somente o link SHEIN do Worker existente tem rastreamento historicamente configurado;
para outras lojas, os links atuais nao devem ser apresentados como links de afiliado.
