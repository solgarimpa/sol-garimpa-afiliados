# Sol Garimpa — Netshoes: integração com Wix
Página de origem: https://github.com/solgarimpa/sol-garimpa-afiliados/blob/main/docs/netshoes/index.html

## URL da vitrine
https://solgarimpa.github.io/sol-garimpa-afiliados/netshoes/

## URL para incorporar no Wix
https://solgarimpa.github.io/sol-garimpa-afiliados/netshoes/?embed=1

## Como usar no editor tradicional Wix
1. Adicione uma página em branco com o nome **Netshoes | Ofertas e Cupons** e slug **netshoes**.
2. Dentro da página, use Adicionar elementos > Incorporar código > Incorporar site.
3. Cole a URL para incorporar acima. Alternativamente, use Incorporar HTML e cole o conteúdo do arquivo wix-embed.html.
4. Estique o elemento pela largura útil, ajuste a altura para exibir todo o conteúdo (sugestão inicial: 1740px; no celular pode ser necessário aumentar), confira a visualização em celular e publique.
5. Adicione um link Netshoes nos menus, se desejado.

O GitHub Pages precisa estar publicado a partir da pasta docs. O repositório está com GitHub Pages habilitado; a resposta HTTP pública desta página ainda não foi validada.
O arquivo index.html busca docs/rakuten/ofertas.json via raw.githubusercontent.com, filtrando exclusivamente o MID 43984 (Netshoes WL) e usando apenas os URLs de afiliado Rakuten do SID ANi/csO07bU. O conteúdo recarrega a cada 15 minutos; a fonte tem cron próprio, portanto não equivale a atualização em tempo real. O cupom 10% SOLGARIMPAOFERTAS é divulgado separadamente, com validação no carrinho.
