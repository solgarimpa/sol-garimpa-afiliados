# SOL GARIMPA — Instalação da nova estrutura no Wix

Página única do componente, alimentada pelo feed GitHub e pelo Worker SHEIN, com filtros de loja.

## Endereços por página

| Página Wix | URL para Embed a site |
|---|---|
| Cupons - página inicial | https://solgarimpa.github.io/sol-garimpa-afiliados/central/?tipo=cupons&loja=todas&visao=inicio |
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
