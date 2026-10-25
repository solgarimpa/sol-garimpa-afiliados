// SOL GARIMPA — backend/routers.js
// ATENÇÃO: se existir outro Router em routers.js, PRESERVE as funções anteriores.
// Ao criar o router no Editor, use o prefixo: oferta
// A página criada normalmente se chama: oferta-page
import { ok, notFound } from 'wix-router';
import { fetch } from 'wix-fetch';

// ALTERE SOMENTE ESTA URL após configurar GitHub Pages.
// Exemplo de FORMATO, não URL ativa: https://USUARIO.github.io/REPOSITORIO/ofertas.json
const CATALOGO_JSON_URL = 'https://SEU_USUARIO.github.io/SEU_REPOSITORIO/ofertas.json';
const MODELO_PAGINA = 'oferta-page';
const IDADE_MAXIMA_HORAS = 72;

function urlRastreada(raw) {
  try {
    const u = new URL(String(raw || ''));
    const hosts = ['awin1.com', 'www.awin1.com', 'awin.com', 'www.awin.com'];
    return u.protocol === 'https:' && hosts.includes(u.hostname.toLowerCase()) ? u.href : '';
  } catch (_) { return ''; }
}

async function obterCatalogo() {
  if (CATALOGO_JSON_URL.includes('SEU_USUARIO') || CATALOGO_JSON_URL.includes('SEU_REPOSITORIO')) {
    console.error('SOL GARIMPA: configure CATALOGO_JSON_URL em routers.js');
    return null;
  }
  const resposta = await fetch(CATALOGO_JSON_URL, {method: 'get'});
  if (!resposta.ok) throw new Error('Catálogo HTTP ' + resposta.status);
  const dados = await resposta.json();
  if (!dados || !Array.isArray(dados.cards)) return null;
  const atualizado = Date.parse(dados.atualizado_em);
  if (!Number.isFinite(atualizado) || Date.now() - atualizado > IDADE_MAXIMA_HORAS*3600000 || atualizado > Date.now()+3600000) {
    console.warn('SOL GARIMPA: catálogo ausente, antigo ou data inválida');
    return null;
  }
  return dados;
}

export async function oferta_Router(request) {
  // Evita roteamento inesperado e pedidos inválidos.
  const partes = request.path || [];
  const slug = partes[0];
  if (partes.length !== 1 || !slug || !/^[a-z0-9-]{5,110}$/.test(slug)) return notFound();
  try {
    const catalogo = await obterCatalogo();
    if (!catalogo) return notFound();
    const p = catalogo.cards.find(x => x.slug === slug && x.tipo !== 'sem_oferta');
    if (!p) return notFound();
    const linkSeguro = urlRastreada(p.link);
    if (!linkSeguro || !p.titulo || !p.loja) return notFound();
    const produto = {
      titulo: String(p.titulo).slice(0,180),
      loja: String(p.loja).slice(0,100),
      imagem: /^https:\/\//.test(String(p.imagem || '')) ? p.imagem : '',
      preco: typeof p.preco === 'number' && p.preco > 0 ? p.preco : null,
      preco_anterior: typeof p.preco_anterior === 'number' && p.preco_anterior > p.preco ? p.preco_anterior : null,
      cupom: p.cupom ? String(p.cupom).slice(0,80) : '',
      descricao: p.descricao ? String(p.descricao).slice(0,350) : '',
      termos: p.termos ? String(p.termos).slice(0,500) : '',
      validade: p.validade || '',
      tipo: p.tipo,
      link: linkSeguro,
      url_sol_garimpa: 'https://www.ofertaspravc.com.br/oferta/' + slug,
      atualizado_em: catalogo.atualizado_em
    };
    const titulo = produto.titulo + ' | ' + produto.loja + ' | SOL GARIMPA';
    const descricao = (produto.descricao || 'Oferta de ' + produto.loja + ' na SOL GARIMPA. Confira preço, condições e disponibilidade diretamente na loja.').slice(0,155);
    const metas = [
      {property: 'og:title', content: titulo},
      {property: 'og:description', content: descricao},
      {property: 'og:url', content: produto.url_sol_garimpa},
      {property: 'og:type', content: 'website'}
    ];
    if (produto.imagem) metas.push({property: 'og:image', content: produto.imagem});
    // Conteúdo de feed costuma ser duplicado/temporário: não indexar automaticamente.
    // A prévia do WhatsApp continua usando os metadados Open Graph acima.
    const head = {title: titulo, description: descricao, noIndex: true, metaTags: metas};
    const cache = {cache: {tags: ['ofertas-sol-garimpa'], ttl: 1800}};
    return ok(MODELO_PAGINA, produto, head, cache);
  } catch (erro) {
    console.error('SOL GARIMPA: Router indisponível', String(erro));
    return notFound();
  }
}

// Inicialmente sem URLs de produtos no sitemap, pois ofertas voláteis ficam noindex.
// Após criar conteúdo editorial original e durável, podemos incluir uma seleção.
export function oferta_SiteMap() {
  return [];
}
