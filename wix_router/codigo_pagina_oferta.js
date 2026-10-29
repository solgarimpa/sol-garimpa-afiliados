// SOL GARIMPA — Código da Router Page "oferta-page" no Wix Editor.
// Elementos necessários: tituloProduto, nomeLoja, fotoProduto,
// precoAtual, precoAnterior, textoCupom, descricaoProduto,
// btnComprar, btnWhatsapp, btnVoltar, observacao.
import wixWindowFrontend from 'wix-window-frontend';

function moeda(valor) {
  return Number(valor).toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL'
  });
}

$w.onReady(function () {
  const p = wixWindowFrontend.getRouterData();
  if (!p || !p.titulo || !p.link) {
    $w('#tituloProduto').text = 'Oferta indisponível';
    $w('#btnComprar').hide();
    $w('#btnWhatsapp').hide();
    return;
  }

  $w('#tituloProduto').text = p.titulo;
  $w('#nomeLoja').text = p.loja + (p.rede ? ' • ' + p.rede : '');

  if (p.imagem && p.imagem.startsWith('https://')) {
    $w('#fotoProduto').src = p.imagem;
    $w('#fotoProduto').alt = p.titulo;
  } else {
    $w('#fotoProduto').collapse();
  }

  if (typeof p.preco === 'number' && p.preco > 0) {
    $w('#precoAtual').text = moeda(p.preco);
  } else {
    $w('#precoAtual').text = 'Confira o preço na loja';
  }

  if (typeof p.preco_anterior === 'number' &&
      typeof p.preco === 'number' &&
      p.preco_anterior > p.preco) {
    $w('#precoAnterior').text = 'Antes: ' + moeda(p.preco_anterior);
  } else {
    $w('#precoAnterior').collapse();
  }

  if (p.cupom) {
    $w('#textoCupom').text = 'Cupom: ' + p.cupom;
  } else {
    $w('#textoCupom').collapse();
  }

  if (p.descricao) {
    $w('#descricaoProduto').text = p.descricao;
  } else {
    $w('#descricaoProduto').collapse();
  }

  $w('#btnComprar').label = 'IR PARA A LOJA';
  $w('#btnComprar').link = p.link; // Preserva o link rastreado da rede.

  const partes = [
    '🛍️ *OFERTA SOL GARIMPA*',
    '🏬 ' + p.loja,
    '✨ ' + p.titulo
  ];
  if (typeof p.preco === 'number' && p.preco > 0) {
    partes.push('💰 ' + moeda(p.preco));
  }
  if (p.cupom) partes.push('🎟️ Cupom: ' + p.cupom);
  partes.push('👉 Confira: ' + p.url_sol_garimpa);
  partes.push('⚠️ Preço, condições e estoque devem ser confirmados na loja.');

  $w('#btnWhatsapp').label = 'COMPARTILHAR NO WHATSAPP';
  $w('#btnWhatsapp').link =
    'https://wa.me/?text=' + encodeURIComponent(partes.join('\n'));

  $w('#btnVoltar').label = 'VER MAIS OFERTAS';
  $w('#btnVoltar').link = 'https://www.ofertaspravc.com.br/';
  $w('#observacao').text =
    'Publicidade • Podemos receber comissão pelas compras elegíveis. ' +
    'Preços e disponibilidade são definidos pelas lojas parceiras.';
});
