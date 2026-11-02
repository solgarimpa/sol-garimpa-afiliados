const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(
  path.join(__dirname, '../wix_router/routers.js'), 'utf8'
).replace(/^import\s+.*?;\s*$/gm, '').replace(/export\s+(?=(async\s+)?function)/g, '');

const slugAtual = 'rakuten-aaaaaaaaaaaaaaaaaaaa';
const slugAntigo = 'rakuten-bbbbbbbbbbbbbbbbbbbb';
const slugAwin = 'awin-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
const catalogo = {
  gerado_em: new Date().toISOString(),
  cards: [
    {
      slug: slugAtual, rede: 'Rakuten', tipo: 'produto',
      titulo: 'Produto ativo', loja: 'Loja exemplo', preco: 59,
      imagem: 'https://example.com/item.jpg',
      link: 'https://click.linksynergy.com/link?id=1234',
      historico: false
    },
    {
      slug: slugAntigo, rede: 'Rakuten', tipo: 'produto',
      titulo: 'Produto removido', loja: 'Loja exemplo', preco: null,
      imagem: 'https://example.com/old.jpg',
      link: 'https://click.linksynergy.com/link?id=1235',
      historico: true
    },
    {
      slug: 'lomadee-cccccccccccccccccccc', rede: 'Lomadee', tipo: 'promocao',
      titulo: 'Outro produto', loja: 'Loja amiga', preco: null,
      imagem: 'https://example.com/other.jpg',
      link: 'https://lmdee.link/foo',
      historico: false
    }
  ]
};

function carregar(erroDeRede = false) {
  const context = {
    URL,
    Date,
    Number,
    String,
    Array,
    Set,
    console,
    fetch: async () => {
      if (erroDeRede) throw new Error('Falha externa');
      return { ok: true, json: async () => catalogo };
    },
    wixData: {get: async () => null},
    ok: (page, data, head) => ({status: 200, page, data, head}),
    notFound: () => ({status: 404}),
  };
  vm.createContext(context);
  vm.runInContext(source + '\nthis.testRouter = oferta_Router;', context);
  return context.testRouter;
}

test('produto ativo continua com compra e ofertas relacionadas', async () => {
  const r = await carregar()({path: [slugAtual]});
  assert.equal(r.status, 200);
  assert.equal(r.data.preco, 59);
  assert.match(r.data.link, /linksynergy.com/);
  assert.ok(r.data.sugestoes.length >= 1);
});

test('produto excluido do feed exibe pagina alternativa, nao 404', async () => {
  const r = await carregar()({path: ['rakuten-dddddddddddddddddddd']});
  assert.equal(r.status, 200);
  assert.equal(r.data.link, '');
  assert.ok(r.data.sugestoes.length >= 1);
  assert.equal(r.head.noIndex, true);
});

test('produto historico nao mostra preco antigo', async () => {
  const r = await carregar()({path: [slugAntigo]});
  assert.equal(r.status, 200);
  assert.equal(r.data.preco, null);
  assert.equal(r.data.link, '');
});

test('falha de rede retorna pagina util sem link ou preco', async () => {
  const r = await carregar(true)({path: [slugAtual]});
  assert.equal(r.status, 200);
  assert.equal(r.data.link, '');
  assert.equal(r.data.preco, null);
});

test('slug incorreto continua 404', async () => {
  const r = await carregar()({path: ['palavra-invalida']});
  assert.equal(r.status, 404);
});

test('Awin que nao existe nao quebra outras ofertas', async () => {
  const r = await carregar()({path: [slugAwin]});
  assert.equal(r.status, 200);
  assert.ok(r.data.sugestoes.length >= 1);
});
