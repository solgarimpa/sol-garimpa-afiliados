// SOL GARIMPA — modelo para Backend & Public / routers.js
// Prefixo do Router: oferta | Página modelo: oferta-page
// Preservar funções de outros Routers existentes no Wix.
// Fontes: catálogo GitHub (Rakuten/Lomadee) + CMS Wix "Ofertas" (Awin).
import { ok, notFound } from 'wix-router';
import { fetch } from 'wix-fetch';
import wixData from 'wix-data';

const CATALOGO_URL = 'https://raw.githubusercontent.com/solgarimpa/sol-garimpa-afiliados/main/docs/paginas_ofertas.json';
const CATALOGO_AWIN_ANTIGO = 'https://solgarimpa.github.io/sol-garimpa-afiliados/ofertas.json';
const PAGINA_MODELO = 'oferta-page';
const SITE_URL = 'https://www.ofertaspravc.com.br';
const VALIDADE_CATALOGO_HORAS = 72;

function texto(valor, tamanho = 200) {
  return String(valor || '').replace(/\s+/g, ' ').trim().slice(0, tamanho);
}

function httpsSeguro(valor) {
  try {
    const u = new URL(String(valor || ''));
    const h = u.hostname.toLowerCase();
    if (u.protocol !== 'https:' || !h || u.username || u.password) return '';
    if (['localhost', '127.0.0.1', '0.0.0.0', '::1'].includes(h) || h.endsWith('.local')) return '';
    return u.href;
  } catch (_) {
    return '';
  }
}

// Mantém apenas os domínios de rastreamento que as integrações utilizam.
function linkAfiliado(valor, rede) {
  const url = httpsSeguro(valor);
  if (!url) return '';
  const host = new URL(url).hostname.toLowerCase();
  const dominios = {
    Awin: ['awin1.com', 'www.awin1.com', 'awin.com', 'www.awin.com'],
    Rakuten: ['click.linksynergy.com'],
    Lomadee: ['lmdee.link']
  };
  return (dominios[rede] || []).includes(host) ? url : '';
}

function valorBRL(valor) {
  return typeof valor === 'number' && Number.isFinite(valor) && valor > 0 ? valor : null;
}

function expirou(valor) {
  if (!valor) return false;
  const timestamp = Date.parse(valor);
  return !Number.isFinite(timestamp) || timestamp <= Date.now();
}

function produtoNormalizado(dados, slug) {
  if (!dados || dados.slug !== slug || !dados.titulo || !dados.loja) return null;
  if (expirou(dados.validade)) return null;
  const link = linkAfiliado(dados.link, dados.rede);
  if (!link) return null;
  const moeda = texto(dados.moeda || 'BRL', 3).toUpperCase();
  const preco = moeda === 'BRL' ? valorBRL(dados.preco) : null;
  const anterior = moeda === 'BRL' ? valorBRL(dados.preco_anterior) : null;
  return {
    titulo: texto(dados.titulo, 180),
    loja: texto(dados.loja, 100),
    rede: texto(dados.rede, 30),
    tipo: texto(dados.tipo, 20),
    imagem: httpsSeguro(dados.imagem),
    preco,
    preco_anterior: anterior && preco && anterior > preco ? anterior : null,
    cupom: texto(dados.cupom, 80),
    descricao: texto(dados.descricao, 350),
    validade: dados.validade || '',
    link,
    url_sol_garimpa: SITE_URL + '/oferta/' + slug
  };
}

async function obterCatalogo() {
  const resposta = await fetch(CATALOGO_URL, { method: 'get' });
  if (!resposta.ok) throw new Error('Catálogo GitHub HTTP ' + resposta.status);
  const catalogo = await resposta.json();
  if (!catalogo || !Array.isArray(catalogo.cards)) throw new Error('Catálogo inválido');
  const gerado = Date.parse(catalogo.gerado_em);
  const idade = Date.now() - gerado;
  if (!Number.isFinite(gerado) || idade < -3600000 ||
      idade > VALIDADE_CATALOGO_HORAS * 3600000) {
    throw new Error('Catálogo desatualizado');
  }
  return catalogo;
}

async function buscarAwinNoWix(slug) {
  const id = slug.slice(5);
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(id)) return null;
  const item = await wixData.get('Ofertas', id, { suppressAuth: true });
  if (!item || item.active !== true ||
      String(item.source || '').toLowerCase() !== 'awin') return null;
  if (expirou(item.expiresAt)) return null;
  const link = linkAfiliado(item.affiliateUrl, 'Awin');
  if (!link) return null;
  return produtoNormalizado({
    slug,
    rede: 'Awin',
    tipo: 'produto',
    titulo: item.title,
    loja: item.marketplace || 'Loja parceira',
    imagem: item.imageUrl || item.image,
    preco: item.currentPrice,
    preco_anterior: item.oldPrice,
    descricao: item.description,
    validade: item.expiresAt || null,
    link
  }, slug);
}

// Compatibilidade: mantém URLs antigas da Awin enquanto houver produtos no feed anterior.
async function buscarAwinLegado(slug) {
  const resposta = await fetch(CATALOGO_AWIN_ANTIGO, { method: 'get' });
  if (!resposta.ok) return null;
  const catalogo = await resposta.json();
  if (!catalogo || !Array.isArray(catalogo.cards)) return null;
  const atualizado = Date.parse(catalogo.atualizado_em);
  if (!Number.isFinite(atualizado) ||
      Date.now() - atualizado > VALIDADE_CATALOGO_HORAS * 3600000 ||
      atualizado > Date.now() + 3600000) return null;
  const registro = catalogo.cards.find(
    p => p.slug === slug && p.tipo !== 'sem_oferta'
  );
  return produtoNormalizado(
    registro ? { ...registro, rede: 'Awin' } : null,
    slug
  );
}

function criarResposta(produto, sugestoes = []) {
  const titulo = (produto.titulo + ' | ' + produto.loja + ' | SOL GARIMPA').slice(0, 160);
  const resumo = (produto.descricao || ('Confira esta oferta da ' + produto.loja +
    ' na SOL GARIMPA. Preço e disponibilidade sujeitos à confirmação na loja.')).slice(0, 155);
  const tags = [
    { property: 'og:title', content: titulo },
    { property: 'og:description', content: resumo },
    { property: 'og:url', content: produto.url_sol_garimpa },
    { property: 'og:type', content: 'website' }
  ];
  if (produto.imagem) tags.push({ property: 'og:image', content: produto.imagem });
  const head = {
    title: titulo,
    description: resumo,
    noIndex: true, // Feed volátil: não indexar páginas sem conteúdo original.
    metaTags: tags,
    links: [{ rel: 'canonical', href: produto.url_sol_garimpa }]
  };
  return ok(
    PAGINA_MODELO,
    { ...produto, sugestoes },
    head,
    { cache: { tags: ['sol-garimpa-oferta'], ttl: 600 } }
  );
}

export async function oferta_Router(request) {
  const partes = request.path || [];
  const slug = partes[0];
  if (partes.length !== 1 || !/^(awin|rakuten|lomadee)-[a-z0-9-]{8,65}$/.test(slug || '')) {
    return notFound();
  }
  try {
    if (slug.startsWith('awin-')) {
      let produto = await buscarAwinNoWix(slug);
      if (!produto) produto = await buscarAwinLegado(slug);
      return produto ? criarResposta(produto) : notFound();
    }
    const catalogo = await obterCatalogo();
    const registro = catalogo.cards.find(p => p.slug === slug);
    const produto = produtoNormalizado(registro, slug);
    if (!produto) return notFound();

    const sugestoes = catalogo.cards
      .filter(p => p.slug !== slug && p.loja === produto.loja && !expirou(p.validade))
      .slice(0, 4)
      .map(p => ({
        titulo: texto(p.titulo, 120),
        imagem: httpsSeguro(p.imagem),
        preco: valorBRL(p.preco),
        url: SITE_URL + '/oferta/' + p.slug
      }));
    return criarResposta(produto, sugestoes);
  } catch (erro) {
    console.error('SOL GARIMPA: erro ao abrir oferta', String(erro));
    return notFound();
  }
}

export function oferta_SiteMap() {
  // Indexação seletiva somente após revisão editorial das páginas.
  return [];
}
