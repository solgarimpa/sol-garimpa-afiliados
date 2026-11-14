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
- Agendamento de origem: cron `17,47 * * * *` em `.github/workflows/atualizar_cupons_awin.yml` para intervalo programado de 30 minutos. A execução real do GitHub Actions pode atrasar.
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
O HTML das subpaginas separa dois destinos: uma selecao Sol Garimpa
(vitrines Shopee, Mercado Livre, Magalu, AliExpress/Site Wix, SHEIN e lista Amazon)
e o link direto para o marketplace. O link direto **nao deve ser divulgado como
rastreado**; as vitrines e listas nao asseguram que um cupom especifico sirva
para todos os produtos nem comissionamento de cada compra.

## Auditoria de integridade dos cupons — 13/11/2026

- A Rakuten devolvia cupons e promocoes pela API, mas o script nao exportava
  `couponcode`; corrigido no `scripts/sync_rakuten.py`.
- A consolidacao `scripts/build_cupons_central.py` agora aceita promocoes
  Rakuten sem codigo, mas so exibe voucher copiavel quando existe codigo oficial.
- O coletor dos marketplaces descarta placeholders como `OFERTANOLINK`
  inclusive quando vierem do Worker (nao apenas do HTML de agregadores).
- Testes unitarios de dados de cupons em `tests/test_cupons_integridade.py`.
- Link Locator da Rakuten continua respondendo HTTP 404 para anunciantes
  sem feed de produto: agora o registro explicita status HTTP em vez de
  somente `RuntimeError`. Sem credencial/acesso a endpoint funcional nao
  ha como garantir novas criacoes por essa fonte.
- Magalu e AliExpress podem continuar com poucos vouchers com codigo:
  a escassez nas fontes consultadas nao deve ser mascarada com codigos inventados.
- As campanhas de produtos nao sao verificadas em carrinho. Se um cupom
  perder validade entre coletas, a confirmacao final continua sendo da loja.

## Revisao de atualizacao — 12/11/2026

- Coleta dos seis marketplaces: cron `5,35 * * * *`, intervalo programado de 30 minutos.
- Central de cupons Awin/Rakuten/Lomadee: cron `17,47 * * * *`, intervalo programado de 30 minutos.
- HTML dos marketplaces e das centrais: busca novo JSON a cada 5 minutos enquanto a pagina estiver aberta.
- HTML dos marketplaces oculta listas com mais de 90 minutos desde a coleta, registros com validade expirada e codigos marcados como resgatados/esgotados/vencidos.
- Worker historico Pelando sem prazo valido: so importar publicacoes das ultimas 24 horas, nao sete dias.
- Feeds Awin/Rakuten/Lomadee com mais de 3 horas nao sao usados pelo consolidado.
- Falhas HTTP 403 de Pelando/Cuponomia continuam possiveis; nao contornar bloqueios. Meliuz e os Workers continuam como fontes alternativas quando responderem.
- O GitHub Pages precisa concluir uma publicacao; o editor Wix deve estar incorporando o URL remoto e nao uma copia estaticamente colada do HTML.

## Nova página iFood (14/11/2026)

- Criar uma subpágina Wix de cupons iFood, sugerida URL: `/cupons-ifood`.
- No Wix Editor > Adicionar elementos > Incorporar código > Incorporar site, usar a URL:
  `https://solgarimpa.github.io/sol-garimpa-afiliados/central/cupons-marketplace.html?loja=ifood`
- A lista vem de `docs/central/ifood-cupons.json`, alimentada pelo mesmo workflow programado de 30 minutos.
- Fontes públicas: Méliuz, Seletronic e complementos Pelando/Cuponomia, somente se acessíveis; falhas HTTP 403 não são contornadas.
- A página recarrega o JSON a cada 5 minutos enquanto aberta, oculta lista desatualizada acima de 90 minutos e exibe o CTA para o WhatsApp Sol Garimpa.
- O botão iFood é link direto, NÃO há rastreamento de afiliado nem comissão afirmada.
- O catálogo apresenta cupons divulgados publicamente, NÃO códigos validados no checkout.
- O Wix Editor ainda precisa receber a nova página e incorporar a URL; publicar código no GitHub NÃO publica automaticamente uma nova página Wix.
