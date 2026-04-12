const fs = require('fs');
const vm = require('vm');
const path = require('path');

const root = path.resolve(__dirname, '..', 'dist');
const local = {};
const localStorage = {
  getItem: (k) => Object.prototype.hasOwnProperty.call(local, k) ? local[k] : null,
  setItem: (k, v) => { local[k] = String(v); },
  removeItem: (k) => { delete local[k]; },
};
const session = {};
const sessionStorage = {
  getItem: (k) => Object.prototype.hasOwnProperty.call(session, k) ? session[k] : null,
  setItem: (k, v) => { session[k] = String(v); },
  removeItem: (k) => { delete session[k]; },
};
const document = {
  body: { dataset: { page:'product', product:'veridion' } },
  getElementById(){ return null; },
  querySelectorAll(){ return []; },
  addEventListener(){},
  querySelector(){ return null; },
  head: { appendChild(){} },
};
const sandbox = {
  console,
  window: {},
  document,
  localStorage,
  sessionStorage,
  location: { pathname:'/products/veridion/index.html', search:'', href:'http://example.test/products/veridion/index.html', origin:'http://example.test' },
  URLSearchParams,
  fetch: async () => ({ ok:false, text: async () => '', json: async () => ({}) }),
  setTimeout,
  clearTimeout,
  Date,
  Math,
  JSON,
  String,
  Number,
  Array,
  Object,
  RegExp,
  encodeURIComponent,
  FormData: class { constructor(){} },
};
Object.assign(sandbox.window, sandbox);
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(root,'assets','site-data.js'),'utf8'), sandbox);
vm.runInContext(fs.readFileSync(path.join(root,'assets','site.js'),'utf8'), sandbox);
const app = sandbox.window.NV0App || sandbox.NV0App;
if (!app) throw new Error('NV0App not exposed');

app.ensureSeedData();
const pubs = app.read('nv0-engine-publications');
if (pubs.length < 8) throw new Error('seed publications missing');
const demo = app.createDemo({ product:'veridion', company:'Acme', name:'Kim', email:'kim@example.com', team:'3인', need:'랜딩 샘플' });
if (!/^DEMO-VER-/.test(demo.code)) throw new Error('demo create failed');
const order = app.createOrder({ product:'veridion', plan:'Growth', billing:'one-time', paymentMethod:'invoice', company:'Acme', name:'Kim', email:'kim@example.com', note:'바로 시작' });
if (!order.code.includes('VER')) throw new Error('order code build failed');
if (!order.publicationIds || order.publicationIds.length < 1) throw new Error('order publications missing');
const lookup = app.createLookup({ email:'kim@example.com', code:order.code });
if (lookup.code !== order.code) throw new Error('lookup create failed');
app.setAdminToken('runtime-token');
if (app.getAdminToken() !== 'runtime-token') throw new Error('admin token storage failed');
const productBoard = app.productBoardHref('veridion', order.publicationIds[0]);
const portal = app.portalHref(order);
if (!/products\/veridion\/board/.test(productBoard)) throw new Error('product board href failed');
if (!/portal\/index\.html/.test(portal) || !portal.includes(order.code)) throw new Error('portal href failed');
console.log(JSON.stringify({ seedCount: pubs.length, demoCode: demo.code, orderCode: order.code, publicationCount: order.publicationIds.length }));
