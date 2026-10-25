// SOL GARIMPA — código da página Router: oferta-page
// IDs dos elementos a criar no Wix Editor, veja PASSO_A_PASSO.md
import wixWindowFrontend from 'wix-window-frontend';

const reais = valor => Number(valor).toLocaleString('pt-BR', {style:'currency',currency:'BRL'});
const textoSeguro = texto => String(texto || '').trim();

$w.onReady(function () {
  const p = wixWindowFrontend.getRouterData();
  if (!p || !p.link || !p.titulo) {
    $w('#tituloProduto').text = 'Oferta indisponível';
    $w('#btnComprar').hide();
    $w('#btnWhatsapp').hide();
    return;
  }
  $w('#tituloProduto').text = p.titulo;
  $w('#nomeLoja').text = 'Loja parceira: ' + p.loja;

  if (p.imagem && p.imagem.startsWith('https://')) {
    $w('#fotoProduto').src = p.imagem;
    $w('#fotoProduto').alt = p.titulo;
  } else {
    $w('#fotoProduto').collapse();
  }
  if (p.preco !== null && Number.isFinite(p.preco)) {
    $w('#precoAtual').text = reais(p.preco);
  } else {
    $w('#precoAtual').text = 'Confira o preço na loja';
  }
  if (p.preco_anterior && p.preco_anterior > p.preco) {
    $w('#precoAnterior').text = 'Antes: ' + reais(p.preco_anterior);
  } else {
    $w('#precoAnterior').collapse();
  }
  if (p.cupom) {
    $w('#textoCupom').text = 'Cupom: ' + p.cupom;
  } else {
    $w('#textoCupom').collapse();
  }
  if (p.descricao) {
    $w('#descricaoProduto').text = textoSeguro(p.descricao);
  } else {
    $w('#descricaoProduto').collapse();
  }
  $w('#btnComprar').label = 'IR PARA A LOJA';
  $w('#btnComprar').link = p.link; // Link Awin original: mantém comissão/rastreamento

  const partes = ['🛍️ *OFERTA SOL GARIMPA*', '🏬 ' + p.loja, '✨ ' + p.titulo];
  if (p.preco !== null && Number.isFinite(p.preco)) partes.push('💰 ' + reais(p.preco));
  if (p.cupom) partes.push('🎟️ Cupom: ' + p.cupom);
  partes.push('👉 Confira: ' + p.url_sol_garimpa);
  partes.push('⚠️ Preço e disponibilidade devem ser conferidos na loja.');
  $w('#btnWhatsapp').label = 'COMPARTILHAR NO WHATSAPP';
  $w('#btnWhatsapp').link = 'https://wa.me/?text=' + encodeURIComponent(partes.join('\n'));
  $w('#btnVoltar').link = 'https://www.ofertaspravc.com.br/';
  $w('#observacao').text = 'Publicidade • Podemos receber comissão. Os valores e estoques são definidos pela loja parceira e podem mudar.';
});
